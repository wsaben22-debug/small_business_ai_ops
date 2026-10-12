from django import forms
from .models import SupportTicket

class SupportTicketForm(forms.ModelForm):
    
    class Meta:
        model = SupportTicket
        fields = [
            'order', 
            'customer', 
            'category', 
            'requested_action',
            'status', 
            'message',
        ]

        labels = {
            "order": "訂單",
            "customer": "客戶",
            "category": "問題分類",
            "requested_action": "請求動作",
            "status": "處理狀態",
            "message": "問題內容",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["order"].empty_label = "請選擇訂單"
        self.fields["customer"].empty_label = "請選擇客戶"