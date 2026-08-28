from django.shortcuts import render, redirect, get_object_or_404
from .models import SupportTicket
from .forms import SupportTicketForm
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import SupportTicketSerializer
from rest_framework import status

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