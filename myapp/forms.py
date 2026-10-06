from django import forms
from .models import SupportTicket

class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ['order', 'customer', 'category', 'requested_action','status', 'message',]