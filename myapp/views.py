# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Case, Exists, IntegerField, OuterRef, When
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

# Django REST Framework
from rest_framework import generics, permissions, status, viewsets
from rest_framework.authentication import (
    BasicAuthentication,
    SessionAuthentication,
    TokenAuthentication,
)
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from rest_framework.views import APIView

# django-filter
from django_filters.rest_framework import DjangoFilterBackend

# Local app imports
from .dashboard_service import (
    PENDING_SORT_OPTIONS,
    get_high_risk_queue,
    get_recent_execution_history,
    sort_pending_queue,
)
from .evaluation_service import calculate_ticket_category_stats, calculate_triage_metrics
from .forms import SupportTicketForm
from .models import SupportTicket, TicketTriageDecision
from .permissions import IsAuthenticatedWriteAdminDelete
from .serializers import SupportTicketSerializer
from .triage_service import (
    build_high_risk_support_package,
    run_triage_execution_workflow,
    submit_human_review,
)

def _search_tickets(tickets, query):
    if not query:
        return tickets
    if query.isascii() and query.isdecimal():
        if len(query) > 19:
            return tickets.none()
        return tickets.filter(pk=int(query))
    return tickets.filter(order__order_number__icontains=query)


@login_required
def ticket_list(request):
    status = request.GET.get('status')
    category = request.GET.get('category')
    query = request.GET.get("q", "").strip()

    tickets = _search_tickets(
        SupportTicket.objects.select_related("order", "customer").annotate(
            has_decision=Exists(
                TicketTriageDecision.objects.filter(ticket_id=OuterRef("pk"))
            )
        ),
        query,
    )

    if status:
        tickets = tickets.filter(status=status)
    if category:
        tickets = tickets.filter(category=category)

    tickets = tickets.order_by(
        Case(
            When(has_decision=False, status__in=("open", "in_progress"), then=0),
            When(has_decision=False, then=1),
            default=2,
            output_field=IntegerField(),
        ),
        "pk",
    )

    return render(request, 'ticket_list.html', {
        'tickets': tickets,
        'selected_status': status,
        'selected_category': category,
        'search_query': query,
    })

@login_required
def ticket_create(request):

    if request.method == 'POST':
        form = SupportTicketForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect('ticket_list')

    else:
        form = SupportTicketForm()

    return render(request, 'ticket_form.html', {'form': form, 'title': '新增客服案件', 'button_text': '新增客服案件'})

@login_required
def ticket_edit(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)

    if request.method == 'POST':
        form = SupportTicketForm(request.POST, instance=ticket)

        if form.is_valid():
            form.save()
            return redirect('ticket_list')

    else:
        form = SupportTicketForm(instance=ticket)

    return render(request, 'ticket_form.html', {'form': form, 'title': '修改客服案件', 'button_text': '修改儲存'})

@login_required
def ticket_delete(request, ticket_id):

    if not request.user.is_staff:
        raise PermissionDenied
    
    ticket = get_object_or_404(SupportTicket, id=ticket_id)

    if request.method == 'POST':
        try:
            ticket.delete()
        except ProtectedError:
            return render(
                request,
                'ticket_confirm_delete.html',
                {
                    'ticket': ticket,
                    'error_message': '此案件已有評估紀錄，無法刪除。',
                },
            )

        return redirect('ticket_list')

    return render(request, 'ticket_confirm_delete.html', {'ticket': ticket})

@login_required
@require_POST
def run_ticket_triage(request, ticket_id):
    ticket = get_object_or_404(
      SupportTicket,
      id=ticket_id,
    )

    if ticket.triage_decisions.exists():
        messages.warning(
            request,
            "This ticket has already been triaged."
        )
        return redirect("ticket_list")

    decision, route, _, _ = run_triage_execution_workflow(
        ticket,
        "manual",
        )

    if decision is not None and route == "human_review":
        return redirect(
            "high_risk_review",
            ticket_id=ticket.id,
        )

    return redirect("ticket_list")

@api_view(['GET','POST'])
@authentication_classes([
    TokenAuthentication,
    SessionAuthentication,
    BasicAuthentication,
])
@permission_classes([IsAuthenticatedWriteAdminDelete])
def support_ticket_api(request):
    if request.method == 'GET':
        tickets = SupportTicket.objects.all()
        serializer = SupportTicketSerializer(tickets, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = SupportTicketSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET','PUT','PATCH','DELETE'])
@authentication_classes([
    TokenAuthentication,
    SessionAuthentication,
    BasicAuthentication,
])
@permission_classes([IsAuthenticatedWriteAdminDelete])
def support_ticket_detail_api(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)

    if request.method == 'GET':
        serializer = SupportTicketSerializer(ticket)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = SupportTicketSerializer(ticket, data=request.data) 

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'PATCH':
        serializer = SupportTicketSerializer(ticket, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) 

    elif request.method == 'DELETE':
        try:
            ticket.delete()
        except ProtectedError:
            return Response(
                {'detail': '此案件已有評估紀錄，無法刪除。'},
                status=status.HTTP_409_CONFLICT
            )

        return Response(status=status.HTTP_204_NO_CONTENT)

class SupportTicketListAPIView(APIView):
    authentication_classes = [
        TokenAuthentication,
        SessionAuthentication,
        BasicAuthentication,
    ]

    permission_classes = [
        IsAuthenticatedWriteAdminDelete,
    ]

    def get(self, request):
        tickets = SupportTicket.objects.all()
        serializer = SupportTicketSerializer(tickets, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = SupportTicketSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SupportTicketDetailAPIView(APIView):
    authentication_classes = [
        TokenAuthentication,
        SessionAuthentication,
        BasicAuthentication,
    ]

    permission_classes = [
        IsAuthenticatedWriteAdminDelete,
    ]
    
    def get(self, request, ticket_id):
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
        serializer = SupportTicketSerializer(ticket)
        return Response(serializer.data)
    
    def put(self, request, ticket_id):
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
        serializer = SupportTicketSerializer(ticket, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, ticket_id):
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
        serializer = SupportTicketSerializer(ticket, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, ticket_id):
        ticket = get_object_or_404(SupportTicket, id=ticket_id)

        try:
            ticket.delete()
        except ProtectedError:
            return Response(
                {"detail": "此案件已有評估紀錄，無法刪除。"},
                status=status.HTTP_409_CONFLICT
            )

        return Response(status=status.HTTP_204_NO_CONTENT)

class SupportTicketListGenericAPIView(generics.ListCreateAPIView):
    queryset = SupportTicket.objects.all().order_by("id")
    serializer_class = SupportTicketSerializer

    authentication_classes = [
        TokenAuthentication,
        SessionAuthentication,
        BasicAuthentication,
    ]

    permission_classes = [
        IsAuthenticatedWriteAdminDelete,
    ]

class SupportTicketDetailGenericAPIView(generics.RetrieveUpdateDestroyAPIView):
    
    queryset = SupportTicket.objects.all()
    serializer_class = SupportTicketSerializer
    lookup_url_kwarg = 'ticket_id'

    authentication_classes = [
        TokenAuthentication,
        SessionAuthentication,
        BasicAuthentication,
    ]

    permission_classes = [
        IsAuthenticatedWriteAdminDelete,
    ]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)

        except ProtectedError:
            return Response(
                {"detail": "此案件已有評估紀錄，無法刪除。"},
                status=status.HTTP_409_CONFLICT
            )

class SupportTicketViewSet(viewsets.ModelViewSet):
    queryset = SupportTicket.objects.all()
    serializer_class = SupportTicketSerializer

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'category']
    ordering_fields = ['created_at', 'id']
    ordering = ['id']

    authentication_classes = [
        TokenAuthentication,
        SessionAuthentication,
        BasicAuthentication,
    ]

    permission_classes = [IsAuthenticatedWriteAdminDelete]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)

        except ProtectedError:
            return Response(
                {"detail": "此案件已有評估紀錄，無法刪除。"},
                status=status.HTTP_409_CONFLICT
            )

@login_required
def triage_dashboard(request):
    query = request.GET.get("q", "").strip()
    metrics = calculate_triage_metrics()
    pending_queue = get_high_risk_queue()
    high_priority_queue = [
        item for item in pending_queue
        if item["priority_level"] == "high" and item["has_persisted_gate"]
    ]
    high_risk_queue = pending_queue
    if query:
        matching_ids = set(
            _search_tickets(SupportTicket.objects.all(), query).values_list("pk", flat=True)
        )
        high_risk_queue = [
            item for item in pending_queue if item["ticket_id"] in matching_ids
        ]
    high_risk_queue, selected_sort, selected_direction = sort_pending_queue(
        high_risk_queue,
        request.GET.get("sort", "priority_level"),
        request.GET.get("direction", "desc"),
    )
    sort_headers = []
    sort_labels = dict(PENDING_SORT_OPTIONS)
    for field in ("ticket_id", "category", "requested_action", "priority_level", "priority_score"):
        active = field == selected_sort
        next_direction = (
            ("desc" if selected_direction == "asc" else "asc") if active
            else ("desc" if field in ("priority_level", "priority_score") else "asc")
        )
        sort_headers.append({
            "field": field,
            "label": sort_labels[field],
            "next_direction": next_direction,
            "next_label": "升冪" if next_direction == "asc" else "降冪",
            "aria_sort": ("ascending" if selected_direction == "asc" else "descending") if active else "none",
            "icon": ("↑" if selected_direction == "asc" else "↓") if active else "↕",
        })
    recent_execution_history = get_recent_execution_history()

    context = {
        "metrics": metrics,
        "high_risk_queue": high_risk_queue,
        "recent_execution_history": recent_execution_history,
        "search_query": query,
        "pending_review_count": len(pending_queue),
        "high_priority_queue": high_priority_queue,
        "category_stats": calculate_ticket_category_stats(),
        "sort_headers": sort_headers,
        "selected_sort": selected_sort,
        "selected_direction": selected_direction,
    }

    return render(
        request,
        "myapp/triage_dashboard.html",
        context,
    )

@login_required
def high_risk_review(request, ticket_id): 
    ticket = get_object_or_404(
        SupportTicket,
        id=ticket_id,
    )

    latest_decision = (
        ticket.triage_decisions
        .order_by("-created_at")
        .first()
    )

    if latest_decision is None:
        context = {
            "ticket": ticket,
            "package": None,
            "error": "此案件尚未完成風險評估，無法執行 AI 分析。",
            "review_error": None,
        }

        return render(
            request,
            "myapp/high_risk_review.html",
            context,
        )

    review_error = None

    if request.method == "POST":
        selected_action = request.POST.get(
            "selected_action"
        )

        reason = request.POST.get(
            "reason",
            "",
        ).strip()

        review_record, review_error = submit_human_review(
            latest_decision,
            selected_action,
            reason,
        )

        if review_error is None:
            return redirect(
                "triage_dashboard"
            )

    package, error = build_high_risk_support_package(
        latest_decision
    )

    latest_ai_record = (
        latest_decision.ai_assist_records
        .order_by("-created_at", "-pk")
        .first()
    )

    review_completed = hasattr(
        latest_decision,
        "human_review_record",
    )

    context = {
        "ticket": ticket,
        "package": package,
        "error": error,
        "review_error": review_error,
        "latest_ai_record": latest_ai_record,
        "review_completed": review_completed,
    }

    return render(
        request,
        "myapp/high_risk_review.html",
        context,
    )

@login_required
@require_POST
def run_ticket_ai_assist(request, ticket_id):

    from .ai_service import run_ai_assist

    ticket = get_object_or_404(
        SupportTicket,
        id=ticket_id,
    )

    latest_decision = (
        ticket.triage_decisions
        .order_by("-created_at")
        .first()
    )

    if latest_decision is None:
        messages.error(
            request,
            "此案件尚未完成風險評估，無法執行 AI 分析。",
        )

        return redirect(
            "high_risk_review",
            ticket_id=ticket.id,
        )

    record, error = run_ai_assist(
        latest_decision,
        request.user,
    )

    if error is not None:
        error_messages = {
            "AI_ASSIST_ALREADY_REVIEWED": (
                "此案件已完成人工審核，無須重新執行 AI 分析。"
            ),
            "AI_ASSIST_TICKET_NOT_ELIGIBLE": (
                "目前案件狀態無法執行 AI 分析，僅可查看歷史 AI 分析。"
            ),
            "AI_ASSIST_ALREADY_RUNNING": (
                "AI 分析正在處理中，請勿重複送出；人工審核仍可繼續。"
            ),
            "decision is not routed to human review": (
                "此案件未分派至人工審核，無法執行 AI 分析。"
            ),
            "GEMINI_REQUEST_FAILED": (
                "AI 分析未完成，可稍後重試；人工審核仍可繼續。"
            ),
            "GEMINI_API_KEY is not configured": (
                "AI 分析服務尚未就緒，請聯絡管理員；人工審核仍可繼續。"
            ),
        }
        messages.error(
            request,
            error_messages.get(
                error,
                "AI 分析未完成，請聯絡管理員確認；人工審核仍可繼續。",
            ),
        )

    else:
        messages.success(
            request,
            "AI 輔助分析已完成。",
        )

    return redirect(
        "high_risk_review",
        ticket_id=ticket.id,
    )