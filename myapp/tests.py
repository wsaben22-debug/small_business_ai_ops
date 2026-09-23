from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from types import SimpleNamespace
from .models import (
    Customer, 
    Order, 
    OrderItem, 
    Product, 
    SupportTicket, 
    TicketTriageDecision,
)
from django.test import TestCase
from .triage_service import (
    assess_severity,
    assess_impact,
    assess_urgency,
    assess_priority,
    assess_human_requirement,
    check_eligibility,
    calculate_order_total,
    calculate_waiting_hours,
    run_triage,
    evaluate_risk_gate,
    run_triage_workflow,
    excute_low_risk_action
)

class SupportTicketPermissionTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='normal_user',
            password='Test1234!'
        )

        self.customer = Customer.objects.create(
            name='測試客戶',
            phone='0912345678',
            email='test@example.com'
        )

        self.order = Order.objects.create(
            customer=self.customer,
            shipping_address='測試地址',
            status='pending',
            order_number='TEST-001'
        )

        self.ticket = SupportTicket.objects.create(
            customer=self.customer,
            order=self.order,
            category='other',
            message='DELETE 權限測試案件',
            status='open'
        )

        self.staff_user = User.objects.create_user(
            username='staff_user',
            password='Test123!',
            is_staff=True
        )

    def test_anonymous_can_read_ticket_list(self):
        response = self.client.get('/api/viewset/tickets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anonymous_cannot_create_ticket(self):

        response = self.client.post(
            '/api/viewset/tickets/',
            {},
            format='json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_authenticated_user_can_create_ticket(self):

        self.client.force_authenticate(user=self.user)

        data = {
            'category' : 'other',
            'message' : '自動測試建立案件',
            'status' : 'open',
            'customer' : self.customer.id,
            'order' : self.order.id,
        }

        response = self.client.post(
            '/api/viewset/tickets/',
            data,
            format='json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.assertTrue(
            SupportTicket.objects.filter(
                message='自動測試建立案件'
            ).exists()
        )

    def test_normal_user_cannot_delete_ticket(self):

        self.client.force_authenticate(user=self.user)

        response = self.client.delete(
            f'/api/viewset/tickets/{self.ticket.id}/'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

        self.assertTrue(
            SupportTicket.objects.filter(id=self.ticket.id).exists()
        )

    def test_staff_user_can_delete_ticket(self):
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.delete(
            f'/api/viewset/tickets/{self.ticket.id}/'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT
        )

        self.assertFalse(
            SupportTicket.objects.filter(id=self.ticket.id).exists()
        )

    def test_authenticated_user_can_patch_ticket(self):

        self.client.force_authenticate(user=self.user)

        data = {
            'status' : 'in_progress'
        }

        response = self.client.patch(
            f'/api/viewset/tickets/{self.ticket.id}/',
            data,
            format='json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.status,
            'in_progress'
        )

    def test_authenticated_user_can_put_ticket(self):

        self.client.force_authenticate(user=self.user)

        url = f'/api/viewset/tickets/{self.ticket.id}/'

        data = {
            'customer' : self.customer.id,
            'order' : self.order.id,
            'category' : self.ticket.category,
            'message' : 'PUT 自動測試更新案件',
            'status' : 'in_progress',
        }

        response = self.client.put(
            url, data, format='json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.message,
            'PUT 自動測試更新案件'
        )

        self.assertEqual(
            self.ticket.status,
            'in_progress'
        )

    def test_anonymous_user_cannot_put_ticket(self):

        url = f'/api/viewset/tickets/{self.ticket.id}/'

        data = {
            'customer': self.customer.id,
            'order': self.order.id,
            'category': self.ticket.category,
            'message': '匿名使用者嘗試PUT',
            'status': 'in_progress',
        }

        response = self.client.put(
            url, data, format='json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_anonymous_user_cannot_delete_ticket(self):

        url = f'/api/viewset/tickets/{self.ticket.id}/'

        response = self.client.delete(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_anonymous_user_cannot_patch_ticket(self):

        url = f'/api/viewset/tickets/{self.ticket.id}/'

        data = {
            'status': 'in_progress'
        }

        response = self.client.patch(
            url, data, format='json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

class TicketTriageWorkflowTests(TestCase):

    def setUp(self):

        self.customer = Customer.objects.create(
            name="V2 測試客戶",

            phone="0911111111",

            email="v2test@example.com"
        )

        self.order = Order.objects.create(
            customer=self.customer,

            shipping_address="V2 測試地址",

            status="paid",

            order_number="V2-TEST-001",
        )

        self.product = Product.objects.create(
            name="V2 測試商品",

            price="1000.00",

            product_code="V2-P001",

            stock=10,
        )

        self.order_item = OrderItem.objects.create(
            order=self.order,

            product=self.product,

            quantity=2,

            unit_price="1500.00",
        )

        self.ticket = SupportTicket.objects.create(
            customer=self.customer,

            order=self.order,

            category="damaged",

            requested_action="other",

            message="V2 workflow test ticket",

            status="open",
        )

    def test_calculate_order_total(self):

        order_total = calculate_order_total(self.order)

        self.assertEqual(order_total, 3000)

    def test_core_assessment_rules(self):

        severity_level, severity_score, severity_reason = assess_severity("damaged")

        impact_level, impact_score, impact_reason = assess_impact(3000)

        priority_score, priority_level = assess_priority(
            severity_score,
            impact_score,
            3,
        )
        self.assertEqual(severity_level, "high")
        self.assertEqual(severity_score, 3)

        self.assertEqual(impact_level, "medium")
        self.assertEqual(impact_score, 2)

        self.assertEqual(priority_score, 8)
        self.assertEqual(priority_level, "high")

    def test_run_triage_creates_decision(self):

        decision, error = run_triage(
            self.ticket,
            "manual",
        )

        self.assertIsNotNone(decision)
        self.assertIsNone(error)

        self.assertEqual(
            TicketTriageDecision.objects.count(),
            1,
        )

        self.assertEqual(
            decision.ticket,
            self.ticket,
        )

        self.assertEqual(
            decision.category_snapshot,
            "damaged",
        )

        self.assertEqual(
            decision.order_total_snapshot,
            3000,
        )

        self.assertEqual(
            decision.priority_score,
            6,
        )

        self.assertEqual(
            decision.priority_level,
            "medium"
        )

        self.assertTrue(
            decision.requires_human
        )

    def test_closed_ticket_does_not_create_decision(self):

        self.ticket.status = "closed"
        self.ticket.save()

        decision, error = run_triage(
            self.ticket,
            "manual",
        )

        self.assertIsNone(decision)

        self.assertEqual(
            error,
            "status=closed is not eligible for triage",
        )

        self.assertEqual(
            TicketTriageDecision.objects.count(),
            0,
        )

    def test_retriage_creates_decision_history(self):
        first_decision, first_error = run_triage(
            self.ticket,
            "manual",
        )

        second_decision, second_error = run_triage(
            self.ticket,
            "manual",
        )

        self.assertIsNone(first_error)
        self.assertIsNone(second_error)

        self.assertEqual(
            self.ticket.triage_decisions.count(),
            2,
        )

        self.assertNotEqual(
            first_decision.id,
            second_decision.id,
        )

        latest_decision = self.ticket.triage_decisions.order_by(
            "-created_at"
        ).first()

        self.assertEqual(
            latest_decision.id,
            second_decision.id,
        )

    def test_decision_is_immutable(self):

        decision, error = run_triage(
            self.ticket,
            "manual",
        )

        self.assertIsNone(error)

        original_priority_score = decision.priority_score

        decision.priority_score = 3

        with self.assertRaises(ValidationError):
            decision.save()

        saved_decision = TicketTriageDecision.objects.get(
            id=decision.id
        )

        self.assertEqual(
            saved_decision.priority_score,
            original_priority_score,
        )

    def test_impact_boundary_values(self):
        level, score, reason = assess_impact(2999)
        self.assertEqual(level, "low")
        self.assertEqual(score, 1)

        level, score, reason = assess_impact(3000)
        self.assertEqual(level, "medium")
        self.assertEqual(score, 2)

        level, score, reason = assess_impact(7999)
        self.assertEqual(level, "medium")
        self.assertEqual(score, 2)

        level, score, reason = assess_impact(8000)
        self.assertEqual(level, "high")
        self.assertEqual(score, 3)

    def test_urgency_boundary_values(self):
        level, score, reason = assess_urgency(23)
        self.assertEqual(level, "low")
        self.assertEqual(score, 1)

        level, score, reason = assess_urgency(24)
        self.assertEqual(level, "medium")
        self.assertEqual(score, 2)

        level, score, reason = assess_urgency(71)
        self.assertEqual(level, "medium")
        self.assertEqual(score, 2)

        level, score, reason = assess_urgency(72)
        self.assertEqual(level, "high")
        self.assertEqual(score, 3)

    def test_priorit_boundary_values(self):
        score, level = assess_priority(1,1,1)
        self.assertEqual(score, 3)
        self.assertEqual(level, "low")

        score, level = assess_priority(1,1,2)
        self.assertEqual(score, 4)
        self.assertEqual(level, "low")

        score, level = assess_priority(1,1,3)
        self.assertEqual(score, 5)
        self.assertEqual(level, "medium")

        score, level = assess_priority(1,2,3)
        self.assertEqual(score, 6)
        self.assertEqual(level, "medium")

        score, level = assess_priority(2,2,3)
        self.assertEqual(score, 7)
        self.assertEqual(level, "high")

        score, level = assess_priority(3,3,3)
        self.assertEqual(score, 9)
        self.assertEqual(level, "high")

    def test_ticket_with_decision_cannot_be_deleted(self):
        decision, error = run_triage(self.ticket, "manual")

        self.assertIsNotNone(decision)
        self.assertIsNone(error)

        with self.assertRaises(ProtectedError):
            self.ticket.delete()

        self.assertTrue(
            SupportTicket.objects.filter(id=self.ticket.id).exists()
        )

    def test_trigger_type_is_saved(self):
        decision, error = run_triage(self.ticket, "created")

        self.assertIsNone(error)
        self.assertEqual(decision.trigger_type, "created")

        decision, error = run_triage(self.ticket, "updated")

        self.assertIsNone(error)
        self.assertEqual(decision.trigger_type, "updated")

        decision, error = run_triage(self.ticket, "manual")

        self.assertIsNone(error)
        self.assertEqual(decision.trigger_type, "manual")

    def test_invalid_trigger_type_is_rejected(self):
        with self.assertRaises(ValidationError):
            run_triage(self.ticket, "system")

        self.assertEqual(
            TicketTriageDecision.objects.count(),
            0
        )

    def test_rule_version_is_saved(self):
        decision, error = run_triage(self.ticket, "manual")

        self.assertIsNone(error)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.rule_version, "v1")

    def test_risk_gate_requires_human_routes_to_review(self):
        decision, error = run_triage(self.ticket, "manual")

        self.assertIsNone(error)

        route, reason = evaluate_risk_gate(decision)

        self.assertEqual(route, "human_review")
        self.assertEqual(reason, decision.human_reason)

    def test_gate_high_priority_route_to_review(self):
        decision = SimpleNamespace(
            requires_human=False,
            human_reason="no human requirement from requested action",
            priority_level="high",
        )

        route, reason = evaluate_risk_gate(decision)

        self.assertEqual(route, "human_review")
        self.assertTrue(reason)

    def test_risk_gate_low_risk_route_to_auto_handle(self):
        decision = SimpleNamespace(
            requires_human=False,
            human_reason="no human review required",
            priority_level="medium",
        )

        route, reason = evaluate_risk_gate(decision)

        self.assertEqual(route, "auto_handle")
        self.assertTrue(reason)

    def test_triage_workflow_route_decision(self):
        decision, route, reason = run_triage_workflow(
            self.ticket,
            "manual"
        )

        self.assertIsNotNone(decision)
        self.assertEqual(route, "human_review")
        self.assertTrue(reason)

    def test_low_risk_info_ticket_moves_to_in_progress(self):
        self.ticket.requested_action = "info"
        self.ticket.save(update_fields=["requested_action"])

        decision, error = run_triage(self.ticket, "manual")

        self.assertIsNone(error)

        action_code, reason = excute_low_risk_action(decision)

        self.ticket.refresh_from_db()

        self.assertEqual(action_code, "info_triage_prepared")
        self.assertTrue(reason)
        self.assertEqual(self.ticket.status, "in_progress")