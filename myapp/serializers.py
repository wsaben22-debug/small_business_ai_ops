from rest_framework import serializers
from .models import SupportTicket

class SupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = '__all__'

    def validate(self, attrs):
        if self.instance and self.instance.triage_decisions.exists():
            if (
                'category' in attrs
                and attrs['category'] != self.instance.category
            ):
                raise serializers.ValidationError({
                    'category': '案件已完成評估，不能修改問題分類。'
                })

            if (
                'requested_action' in attrs
                and attrs['requested_action'] != self.instance.requested_action
            ):
                raise serializers.ValidationError({
                    'requested_action': '案件已完成評估，不能修改請求動作。'
                })

            if (
                'order' in attrs
                and attrs['order'] != self.instance.order
            ):
                raise serializers.ValidationError({
                    'order': '案件已完成評估，不能修改訂單。'
                })

        customer = attrs.get(
            'customer',
            self.instance.customer if self.instance else None
        )

        order = attrs.get(
            'order',
            self.instance.order if self.instance else None
        )

        if order and customer != order.customer:
            raise serializers.ValidationError({
                'customer': '案件客戶必須與訂單客戶一致。'
            })

        return attrs