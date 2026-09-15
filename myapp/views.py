from django.shortcuts import render, redirect, get_object_or_404
from .models import SupportTicket
from .forms import SupportTicketForm
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import SupportTicketSerializer
from rest_framework import status
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework import viewsets
from rest_framework import permissions
from .permissions import IsAuthenticatedWriteAdminDelete
from rest_framework.authentication import TokenAuthentication, SessionAuthentication, BasicAuthentication
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

def ticket_list(request):
    status = request.GET.get('status')
    category = request.GET.get('category')

    tickets = SupportTicket.objects.all()

    if status:
        tickets = tickets.filter(status=status)
    if category:
        tickets = tickets.filter(category=category)

    return render(request, 'ticket_list.html', {'tickets': tickets, 'selected_status': status, 'selected_category' : category})


def ticket_create(request):

    if request.method == 'POST':
        form = SupportTicketForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect('ticket_list')

    else:
        form = SupportTicketForm()

    return render(request, 'ticket_form.html', {'form': form, 'title': '新增客服案件', 'button_text': '新增客服案件'})


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

def ticket_delete(request, ticket_id):

    ticket = get_object_or_404(SupportTicket, id=ticket_id)

    if request.method == 'POST':
        ticket.delete()
        return redirect('ticket_list')

    return render(request, 'ticket_confirm_delete.html', {'ticket': ticket})

@api_view(['GET','POST'])
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
        ticket.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class SupportTicketListAPIView(APIView):
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
        ticket.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class SupportTicketListGenericAPIView(generics.ListCreateAPIView):
    queryset = SupportTicket.objects.all()
    serializer_class = SupportTicketSerializer

class SupportTicketDetailGenericAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SupportTicket.objects.all()
    serializer_class = SupportTicketSerializer
    lookup_url_kwarg = 'ticket_id'

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