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

    def clean(self):
        cleaned_data = super().clean()

        if self.instance.pk and self.instance.triage_decisions.exists():
            category = cleaned_data.get("category")

            if category is not None and category != self.instance.category:
                self.add_error(
                    "category",
                    "案件已完成評估，不能修改問題分類。"
                )

            requested_action = cleaned_data.get("requested_action")

            if (
                requested_action is not None
                and requested_action != self.instance.requested_action
            ):
                self.add_error(
                    "requested_action",
                    "案件已完成評估，不能修改處理需求。"
                )

            order = cleaned_data.get("order")

            if order is not None and order != self.instance.order:
                self.add_error(
                    "order",
                    "案件已完成評估，不能修改關聯訂單。"
                )

        customer = cleaned_data.get("customer")
        order = cleaned_data.get("order")

        if order is not None and customer != order.customer:
            self.add_error(
                "customer",
                "案件客戶必須與訂單客戶一致。"
            )

        return cleaned_data