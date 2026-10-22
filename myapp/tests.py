from django.apps import apps
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
    TriageExecutionRecord,
    TriageRiskGateRecord,
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
    execute_low_risk_action,
    run_triage_execution_workflow,
    build_high_risk_support_package,
    build_high_risk_recommendation,
    submit_human_review,
)
from .evaluation_service import calculate_triage_metrics
from django.urls import reverse
from .dashboard_service import get_high_risk_queue
import json
from pydantic import ValidationError as PydanticValidationError
from unittest.mock import patch

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

    def test_anonymous_cannot_read_ticket_list(self):
        response = self.client.get('/api/viewset/tickets/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_evaluated_ticket_cannot_patch_order(self):
        other_order = Order.objects.create(
            customer=self.customer,
            shipping_address='另一個測試地址',
            status='pending',
            order_number='TEST-002',
        )

        decision, err = run_triage(
            self.ticket,
            "manual",
        )

        self.assertIsNotNone(decision)
        self.assertIsNone(err)

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f'/api/viewset/tickets/{self.ticket.id}/',
            {
                'order': other_order.id,
            },
            format='json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.order,
            self.order
        )

    def test_ticket_customer_must_match_order_customer(self):
        other_customer = Customer.objects.create(
            name='另一位測試客戶',
            phone='0987654321',
            email='other@example.com',
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f'/api/viewset/tickets/{self.ticket.id}/',
            {
                'customer': other_customer.id,
            },
            format='json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.customer,
            self.customer
        )

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

    def test_other_api_styles_use_same_permission_rules(self):
        list_urls = [
            "/api/tickets/",
            "/api/apiview/tickets/",
            "/api/generic/tickets/",
        ]

        detail_urls = [
            f"/api/tickets/{self.ticket.id}/",
            f"/api/apiview/tickets/{self.ticket.id}/",
            f"/api/generic/tickets/{self.ticket.id}/",
        ]

        for url in list_urls:
            with self.subTest(url=url, method="GET"):
                response = self.client.get(url)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_401_UNAUTHORIZED,
                )

            with self.subTest(url=url, method="POST"):
                response = self.client.post(
                    url,
                    {},
                    format="json",
                )
                self.assertEqual(
                    response.status_code,
                    status.HTTP_401_UNAUTHORIZED,
                )

        for url in detail_urls:
            with self.subTest(url=url, method="GET"):
                response = self.client.get(url)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_401_UNAUTHORIZED,
                )

            with self.subTest(url=url, method="DELETE"):
                response = self.client.delete(url)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_401_UNAUTHORIZED,
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

    def test_authenticated_user_can_read_ticket_list(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get('/api/viewset/tickets/')

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
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

    def test_staff_cannot_delete_evaluated_ticket_via_api(self):
        decision, err = run_triage(self.ticket, "manual")

        self.assertIsNotNone(decision)
        self.assertIsNone(err)

        self.client.force_authenticate(user=self.staff_user)

        response = self.client.delete(
            f"/api/tickets/{self.ticket.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT
        )

        self.assertTrue(
            SupportTicket.objects.filter(
                id=self.ticket.id
            ).exists()
        )

    def test_staff_cannot_delete_evaluated_ticket_via_apiview(self):
        decision, err = run_triage(self.ticket, "manual")

        self.assertIsNotNone(decision)
        self.assertIsNone(err)

        self.client.force_authenticate(user=self.staff_user)

        response = self.client.delete(
            f"/api/apiview/tickets/{self.ticket.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT
        )

        self.assertTrue(
            SupportTicket.objects.filter(
                id=self.ticket.id
            ).exists()
        )

    def test_staff_cannot_delete_evaluated_ticket_via_generic(self):
        decision, err = run_triage(self.ticket, "manual")

        self.assertIsNotNone(decision)
        self.assertIsNone(err)

        self.client.force_authenticate(user=self.staff_user)

        response = self.client.delete(
            f"/api/generic/tickets/{self.ticket.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT
        )

        self.assertTrue(
            SupportTicket.objects.filter(
                id=self.ticket.id
            ).exists()
        )

    def test_staff_cannot_delete_evaluated_ticket_via_viewset(self):
        decision, err = run_triage(self.ticket, "manual")

        self.assertIsNotNone(decision)
        self.assertIsNone(err)

        self.client.force_authenticate(user=self.staff_user)

        response = self.client.delete(
            f"/api/viewset/tickets/{self.ticket.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT
        )

        self.assertTrue(
            SupportTicket.objects.filter(
                id=self.ticket.id
            ).exists()
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

    def test_evaluated_ticket_cannot_patch_category(self):
        decision, err = run_triage(
            self.ticket,
            "manual",
        )

        self.assertIsNotNone(decision)
        self.assertIsNone(err)

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f'/api/viewset/tickets/{self.ticket.id}/',
            {
                'category': 'refund',
            },
            format='json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.category,
            'other'
        )

    def test_evaluated_ticket_cannot_patch_requested_action(self):
        decision, err = run_triage(
            self.ticket,
            "manual",
        )

        self.assertIsNotNone(decision)
        self.assertIsNone(err)

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f'/api/viewset/tickets/{self.ticket.id}/',
            {
                'requested_action': 'refund',
            },
            format='json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.requested_action,
            'other'
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

    def test_evaluated_ticket_can_put_unchanged_protected_fields(self):
        decision, err = run_triage(self.ticket, "manual")

        self.assertIsNotNone(decision)
        self.assertIsNone(err)

        self.client.force_authenticate(user=self.user)

        url = f"/api/viewset/tickets/{self.ticket.id}/"

        data = {
            "customer": self.customer.id,
            "order": self.order.id,
            "category": self.ticket.category,
            "requested_action": self.ticket.requested_action,
            "message": "PUT 已評估案件更新測試",
            "status": "in_progress",
        }

        response = self.client.put(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.ticket.refresh_from_db()

        self.assertEqual(self.ticket.message, "PUT 已評估案件更新測試")
        self.assertEqual(self.ticket.status, "in_progress")

        self.assertEqual(self.ticket.order_id, self.order.id)
        self.assertEqual(self.ticket.category, data["category"])
        self.assertEqual(
            self.ticket.requested_action,
            data["requested_action"]
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

class WebPermissionTests(TestCase):

    def setUp(self):
        self.normal_user = User.objects.create_user(
            username="web_normal_user",
            password="Test1234!",
        )

        self.staff_user = User.objects.create_user(
            username="web_staff_user",
            password="Test1234!",
            is_staff=True,
        )

        self.customer = Customer.objects.create(
            name="Web 權限測試客戶",
            phone="0912345678",
            email="web_permission@example.com",
        )

        self.order = Order.objects.create(
            customer=self.customer,
            shipping_address="Web 權限測試地址",
            status="pending",
            order_number="WEB-PERM-001",
        )

        self.ticket = SupportTicket.objects.create(
            customer=self.customer,
            order=self.order,
            category="other",
            message="Web permission test ticket",
            status="open",
        )

    def test_anonymous_user_is_redirected_from_protected_web_views(self):
        protected_urls = [
            reverse("ticket_list"),
            reverse("ticket_create"),
            reverse("ticket_edit", args=[self.ticket.id]),
            reverse("ticket_delete", args=[self.ticket.id]),
            reverse("triage_dashboard"),
            reverse("high_risk_review", args=[self.ticket.id]),
        ]

        for url in protected_urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    302,
                )

                self.assertIn(
                    "/login/",
                    response.url,
                )

        decision_count_before = TicketTriageDecision.objects.count()

        response = self.client.post(
            reverse(
                "run_ticket_triage",
                args=[self.ticket.id],
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertIn(
            "/login/",
            response.url,
        )

        self.assertEqual(
            TicketTriageDecision.objects.count(),
            decision_count_before,
        )

    def test_normal_user_cannot_delete_ticket(self):
        self.client.force_login(self.normal_user)

        delete_url = reverse(
            "ticket_delete",
            args=[self.ticket.id],
        )

        response = self.client.get(delete_url)

        self.assertEqual(
            response.status_code,
            403,
        )

        list_response = self.client.get(
            reverse("ticket_list")
        )

        self.assertNotContains(
            list_response,
            delete_url,
        )

    def test_staff_user_can_access_delete_ticket(self):
        self.client.force_login(self.staff_user)

        delete_url = reverse(
            "ticket_delete",
            args=[self.ticket.id],
        )

        response = self.client.get(delete_url)

        self.assertEqual(
            response.status_code,
            200,
        )

        list_response = self.client.get(
            reverse("ticket_list")
        )

        self.assertContains(
            list_response,
            delete_url,
        )

    def test_evaluated_ticket_cannot_edit_category_via_web(self):
        decision, err = run_triage(self.ticket, "manual")

        self.assertIsNotNone(decision)
        self.assertIsNone(err)

        self.client.force_login(self.normal_user)

        response = self.client.post(
            reverse("ticket_edit", args=[self.ticket.id]),
            {
                "order": self.order.id,
                "customer": self.customer.id,
                "category": "refund",
                "requested_action": self.ticket.requested_action,
                "status": self.ticket.status,
                "message": self.ticket.message,
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("category", response.context["form"].errors)

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.category, "other")

    def test_evaluated_ticket_cannot_edit_requested_action_via_web(self):
        decision, err = run_triage(self.ticket, "manual")

        self.assertIsNotNone(decision)
        self.assertIsNone(err)

        self.client.force_login(self.normal_user)

        response = self.client.post(
            reverse("ticket_edit", args=[self.ticket.id]),
            {
                "order": self.order.id,
                "customer": self.customer.id,
                "category": self.ticket.category,
                "requested_action": "refund",
                "status": self.ticket.status,
                "message": self.ticket.message,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("requested_action", response.context["form"].errors)

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.requested_action, "other")

    def test_evaluated_ticket_cannot_edit_order_via_web(self):
        other_order = Order.objects.create(
            customer=self.customer,
            shipping_address="Web 測試地址 B",
            status="paid",
            order_number="WEB-ORDER-ALT-001",
        )

        decision, err = run_triage(self.ticket, "manual")

        self.assertIsNotNone(decision)
        self.assertIsNone(err)

        self.client.force_login(self.normal_user)

        response = self.client.post(
            reverse("ticket_edit", args=[self.ticket.id]),
            {
                "order": other_order.id,
                "customer": self.customer.id,
                "category": self.ticket.category,
                "requested_action": self.ticket.requested_action,
                "status": self.ticket.status,
                "message": self.ticket.message,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("order", response.context["form"].errors)

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.order, self.order)

    def test_ticket_customer_must_match_order_customer_via_web(self):
        other_customer = Customer.objects.create(
            name="Web 測試客戶 B",
            phone="0999999999",
            email="web-consistency-b@example.com",
        )

        self.client.force_login(self.normal_user)

        response = self.client.post(
            reverse("ticket_edit", args=[self.ticket.id]),
            {
                "order": self.order.id,
                "customer": other_customer.id,
                "category": self.ticket.category,
                "requested_action": self.ticket.requested_action,
                "status": self.ticket.status,
                "message": self.ticket.message,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("customer", response.context["form"].errors)

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.customer, self.customer)

    def test_evaluated_ticket_can_edit_message_and_status_via_web(self):
        decision, err = run_triage(self.ticket, "manual")

        self.assertIsNotNone(decision)
        self.assertIsNone(err)

        self.client.force_login(self.normal_user)

        response = self.client.post(
            reverse("ticket_edit", args=[self.ticket.id]),
            {
                "order": self.order.id,
                "customer": self.customer.id,
                "category": self.ticket.category,
                "requested_action": self.ticket.requested_action,
                "status": "in_progress",
                "message": "Updated message after triage",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.ticket.refresh_from_db()

        self.assertEqual(self.ticket.status, "in_progress")
        self.assertEqual(
            self.ticket.message,
            "Updated message after triage"
        )

    def test_staff_cannot_delete_evaluated_ticket_via_web(self):
        decision, err = run_triage(self.ticket, "manual")

        self.assertIsNotNone(decision)
        self.assertIsNone(err)

        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("ticket_delete", args=[self.ticket.id])
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "此案件已有評估紀錄，無法刪除。"
        )

        self.assertTrue(
            SupportTicket.objects.filter(
                id=self.ticket.id
            ).exists()
        )

    def test_staff_can_delete_unevaluated_ticket_via_web(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("ticket_delete", args=[self.ticket.id])
        )

        self.assertEqual(response.status_code, 302)

        self.assertFalse(
            SupportTicket.objects.filter(
                id=self.ticket.id
            ).exists()
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

    def test_run_ticket_triage_blocks_duplicate_decision(self):
        user = User.objects.create_user(
            username="triage_web_user",
            password="Test1234!",
        )

        self.client.force_login(user)
        
        url = reverse(
            "run_ticket_triage",
            args=[self.ticket.id],
        )

        first_response = self.client.post(url)

        self.assertEqual(
            first_response.status_code,
            302,
        )

        self.ticket.refresh_from_db()

        decision_count_before = self.ticket.triage_decisions.count()

        execution_count_before = TriageExecutionRecord.objects.filter(
            decision__ticket=self.ticket,
        ).count()

        ticket_status_before = self.ticket.status

        second_response = self.client.post(
            url,
            follow=True,
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.triage_decisions.count(),
            decision_count_before,
        )

        self.assertEqual(
            TriageExecutionRecord.objects.filter(
                decision__ticket=self.ticket,
            ).count(),
            execution_count_before,
        )

        self.assertEqual(
            self.ticket.status,
            ticket_status_before,
        )

        self.assertContains(
            second_response,
            "This ticket has already been triaged.",
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

    def test_high_risk_queue_uses_persisted_risk_gate_result(self):
        decision, error = run_triage(
            self.ticket,
            "manual",
        )

        self.assertIsNone(error)

        self.assertTrue(
            decision.requires_human
        )

        TriageRiskGateRecord.objects.create(
            decision=decision,
            route="auto_handle",
            reason="persisted gate result test",
            gate_version="risk_gate_v1",
        )

        high_risk_queue = get_high_risk_queue()

        queued_ticket_ids = [
            item["ticket_id"]
            for item in high_risk_queue
        ]

        self.assertNotIn(
            self.ticket.id,
            queued_ticket_ids,
        )

    def test_triage_workflow_route_decision(self):
        decision, route, reason = run_triage_workflow(
            self.ticket,
            "manual"
        )

        self.assertIsNotNone(decision)
        self.assertEqual(route, "human_review")
        self.assertTrue(reason)

        gate_record = decision.risk_gate_record

        self.assertEqual(
            gate_record.route,
            route,
        )

        self.assertEqual(
            gate_record.reason,
            reason,
        )

        self.assertEqual(
            gate_record.gate_version,
            "risk_gate_v1",
        )

    def test_low_risk_info_ticket_moves_to_in_progress(self):
        self.ticket.requested_action = "info"
        self.ticket.save(update_fields=["requested_action"])

        decision, error = run_triage(self.ticket, "manual")

        self.assertIsNone(error)

        action_code, reason = execute_low_risk_action(decision)

        self.ticket.refresh_from_db()

        self.assertEqual(action_code, "info_triage_prepared")
        self.assertTrue(reason)
        self.assertEqual(self.ticket.status, "in_progress")

        execution_record = TriageExecutionRecord.objects.get(
            decision=decision
        )

        self.assertEqual(
            execution_record.action_code,
            "info_triage_prepared",
        )

        self.assertEqual(
            execution_record.execution_status,
            "success",
        )

        self.assertEqual(
            execution_record.ticket_status_before,
            "open",
        )

        self.assertEqual(
            execution_record.ticket_status_after,
            "in_progress",
        )

        self.assertEqual(
            execution_record.reason,
            reason,
        )

    def test_low_risk_action_blocks_human_review_route(self):
        decision, error = run_triage(self.ticket, "manual")

        self.assertIsNone(error)

        action_code, reason = execute_low_risk_action(decision)

        self.ticket.refresh_from_db()

        self.assertIsNone(action_code)
        self.assertTrue(reason)
        self.assertEqual(self.ticket.status, "open")

    def test_low_risk_action_blocks_unsupported_action(self):
        decision = SimpleNamespace(
            requires_human=False,
            human_reason="no human review required",
            priority_level="medium",
            requested_action_snapshot="exchange",
            ticket=self.ticket,
        )

        action_code, reason = execute_low_risk_action(decision)

        self.ticket.refresh_from_db()

        self.assertIsNone(action_code)
        self.assertTrue(reason)
        self.assertEqual(self.ticket.status, "open")

    def test_low_risk_action_blocks_non_open_ticket(self):
        self.ticket.requested_action = "info"
        self.ticket.save(update_fields=["requested_action"])

        decision, error = run_triage(self.ticket, "manual")

        self.assertIsNone(error)

        self.ticket.status = "in_progress"
        self.ticket.save(update_fields=["status"])

        action_code, reason = execute_low_risk_action(decision)

        self.ticket.refresh_from_db()

        self.assertIsNone(action_code)
        self.assertTrue(reason)
        self.assertEqual(self.ticket.status, "in_progress")

        execution_record = TriageExecutionRecord.objects.get(
        decision=decision
        )

        self.assertEqual(
            execution_record.execution_status,
            "skipped",
        )

        self.assertEqual(
            execution_record.ticket_status_before,
            "in_progress",
        )

        self.assertEqual(
            execution_record.ticket_status_after,
            "in_progress",
        )

        self.assertEqual(
            execution_record.reason,
            reason,
        )

    def test_executon_workflow_auto_handles_low_risk_info(self):
        self.ticket.requested_action = "info"
        self.ticket.save(update_fields=["requested_action"])

        decision, route, action_code, reason = (
            run_triage_execution_workflow(
                self.ticket,
                "manual",
            )
        )

        self.ticket.refresh_from_db()

        self.assertIsNotNone(decision)
        self.assertEqual(route, "auto_handle")
        self.assertEqual(action_code, "info_triage_prepared")
        self.assertTrue(reason)
        self.assertEqual(self.ticket.status, "in_progress")

    def test_high_risk_support_package_is_created_for_human_review(self):
        decision, error = run_triage(self.ticket, "manual")

        self.assertIsNone(error)

        package, package_error = build_high_risk_support_package(decision)

        self.assertIsNone(package_error)
        self.assertIsNotNone(package)

        self.assertEqual(package["ticket_id"], self.ticket.id)
        self.assertEqual(package["route"], "human_review")
        self.assertEqual(package["category"], decision.category_snapshot)
        self.assertEqual(
            package["requested_action"],
            decision.requested_action_snapshot,
        )

        self.assertEqual(
            package["priority"]["level"],
            decision.priority_level,
        )

        self.assertEqual(
            package["priority"]["score"],
            decision.priority_score,
        )

        self.assertIn(
            "review_requested_action",
            package["decision_support"]["options"],
        )

        self.assertEqual(
            package["decision_support"]["recommended_action"],
            "review_requested_action",
        )

        self.assertEqual(
            package["decision_support"]["recommendation_reason"],
            decision.human_reason,
        )

    def test_high_risk_support_package_blocks_auto_handle(self):
        self.ticket.requested_action = "info"
        self.ticket.save(update_fields=["requested_action"])

        decision, error = run_triage(self.ticket, "manual")

        self.assertIsNone(error)

        package, package_error = build_high_risk_support_package(decision)

        self.assertIsNone(package)
        self.assertEqual(
                package_error,
                "decision is not routed to human review",
        )

    def test_high_risk_support_package_includes_customer_and_order(self):
        decision, error = run_triage(self.ticket, "manual")

        self.assertIsNone(error)

        package, package_error = build_high_risk_support_package(decision)

        self.assertIsNone(package_error)
        self.assertIsNotNone(package)

        self.assertEqual(
            package["customer"]["id"],
            self.customer.id,
        )
        self.assertEqual(
            package["customer"]["name"],
            self.customer.name,
        )
        self.assertEqual(
            package["customer"]["email"],
            self.customer.email,
        )
        self.assertEqual(
            package["customer"]["phone"],
            self.customer.phone,
        )

        self.assertEqual(
            package["order"]["id"],
            self.order.id,
        )
        self.assertEqual(
            package["order"]["order_number"],
            self.order.order_number,
        )
        self.assertEqual(
            package["order"]["status"],
            self.order.status,
        )
        self.assertEqual(
            package["order"]["shipping_address"],
            self.order.shipping_address,
        )

    def test_high_risk_support_package_falls_back_to_order_customer(self):
        self.ticket.customer = None
        self.ticket.save(update_fields=["customer"])

        decision, error = run_triage(self.ticket, "manual")

        self.assertIsNone(error)

        package, package_error = build_high_risk_support_package(decision)

        self.assertIsNone(package_error)
        self.assertIsNotNone(package)

        self.assertEqual(
            package["customer"]["id"],
            self.order.customer.id,
        )
        self.assertEqual(
            package["customer"]["name"],
            self.order.customer.name,
        )
        self.assertEqual(
            package["customer"]["email"],
            self.order.customer.email,
        )

    def test_high_risk_support_package_includes_ticket_history(self):
        previous_ticket_1 = SupportTicket.objects.create(
            customer=self.customer,
            order=self.order,
            category="damaged",
            requested_action="exchange",
            message="previous damaged ticket",
            status="closed",
        )

        previous_ticket_2 = SupportTicket.objects.create(
            customer=self.customer,
            order=self.order,
            category="delivery",
            requested_action="info",
            message="previous delivery ticket",
            status="closed",
        )

        decision, error = run_triage(self.ticket, "manual")

        self.assertIsNone(error)

        package, package_error = build_high_risk_support_package(decision)

        self.assertIsNone(package_error)
        self.assertIsNotNone(package)

        history = package["ticket_history"]

        self.assertEqual(
            history["prior_ticket_count"],
            2,
        )

        self.assertEqual(
            history["same_category_ticket_count"],
            1,
        )

        recent_ticket_ids = [
            ticket["ticket_id"]
            for ticket in history["recent_tickets"]
        ]

        self.assertIn(
            previous_ticket_1.id,
            recent_ticket_ids,
        )
        self.assertIn(
            previous_ticket_2.id,
            recent_ticket_ids,
        )

        self.assertNotIn(
            self.ticket.id,
            recent_ticket_ids,
        )

    def test_high_risk_support_package_limits_recent_tickets_to_five(self):
        for i in range(6):
            SupportTicket.objects.create(
                customer=self.customer,
                order=self.order,
                category="delivery",
                requested_action="info",
                message=f"history ticket {i}",
                status="closed",
            )

        decision, error = run_triage(self.ticket, "manual")

        self.assertIsNone(error)

        package, package_error = build_high_risk_support_package(decision)

        self.assertIsNone(package_error)
        self.assertIsNotNone(package)

        history = package["ticket_history"]

        self.assertEqual(
            history["prior_ticket_count"],
            6,
        )

        self.assertEqual(
            len(history["recent_tickets"]),
            5,
        )

    def test_high_priority_recommends_escalation(self):
        decision = SimpleNamespace(
            requires_human=False,
            human_reason="no human review required",
            priority_level="high",
        )

        recommendation, error = build_high_risk_recommendation(decision)

        self.assertIsNone(error)
        self.assertIsNotNone(recommendation)

        self.assertEqual(
            recommendation["recommended_action"],
            "escalate_high_priority_case",
        )

        self.assertTrue(
            recommendation["recommendation_reason"]
        )

    def test_calculate_triage_metrics(self):
        # 1. Human Review：requires_human=True
        first_decision, error = run_triage(
            self.ticket,
            "manual",
        )

        self.assertIsNone(error)

        # 2. Auto Handle：info + medium priority
        auto_ticket = SupportTicket.objects.create(
            customer=self.customer,
            order=self.order,
            category="delivery",
            requested_action="info",
            message="auto handle evaluation ticket",
            status="open",
        )

        run_triage_execution_workflow(
            auto_ticket,
            "manual",
        )

        # 3. Human Review：requires_human=False，但 priority=high
        high_order = Order.objects.create(
            order_number="V2-EVAL-001",
            shipping_address="Evaluation Test Address",
            status="paid",
            customer=self.customer,
        )

        OrderItem.objects.create(
            order=high_order,
            product=self.product,
            quantity=1,
            unit_price="9000.00",
        )

        high_ticket = SupportTicket.objects.create(
            customer=self.customer,
            order=high_order,
            category="damaged",
            requested_action="info",
            message="high priority evaluation ticket",
            status="open",
        )

        high_decision, error = run_triage(
            high_ticket,
            "manual",
        )

        self.assertIsNone(error)
        self.assertEqual(high_decision.priority_level, "high")
        self.assertFalse(high_decision.requires_human)

        metrics = calculate_triage_metrics()

        self.assertEqual(metrics["total_decisions"], 3)
        self.assertEqual(metrics["human_review_count"], 2)
        self.assertEqual(metrics["auto_handled_count"], 1)

        self.assertEqual(metrics["human_review_rate"], 66.67)
        self.assertEqual(metrics["auto_handled_rate"], 33.33)

    def test_triage_metrics_uses_persisted_risk_gate_result(self):
        decision, error = run_triage(
            self.ticket,
            "manual",
        )

        self.assertIsNone(error)
        self.assertIsNotNone(decision)
        self.assertTrue(decision.requires_human)

        TriageRiskGateRecord.objects.create(
            decision=decision,
            route="auto_handle",
            reason="persisted route precedence test",
            gate_version="risk_gate_v1",
        )

        metrics = calculate_triage_metrics()

        self.assertEqual(metrics["total_decisions"], 1)
        self.assertEqual(metrics["human_review_count"], 0)

    def test_submit_human_review_rejects_blank_reason(self):
        decision, err = run_triage(self.ticket, "manual")

        self.assertIsNotNone(decision)
        self.assertIsNone(err)

        review_record, review_error = submit_human_review(
            decision,
            "review_requested_action",
            "   ",
        )

        self.assertIsNone(review_record)
        self.assertEqual(
            review_error,
            "human review reason is required",
        )

    def test_submit_human_review_creates_record_and_blocks_duplicate(self):
        decision, error = run_triage(
            self.ticket,
            "manual",
        )

        self.assertIsNone(error)

        review_record, review_error = submit_human_review(
            decision,
            "review_requested_action",
            "reviewer agrees with the system recommendation",
        )

        self.assertIsNone(review_error)
        self.assertIsNotNone(review_record)

        self.assertEqual(
            review_record.selected_action,
            "review_requested_action",
        )

        self.assertEqual(
            review_record.recommended_action_snapshot,
            "review_requested_action",
        )

        self.assertTrue(
            review_record.accepted_recommendation
        )

        self.assertEqual(
            review_record.decision,
            decision,
        )

        duplicate_record, duplicate_error = submit_human_review(
            decision,
            "request_more_information",
            "second review should not be allowed",
        )

        self.assertIsNone(duplicate_record)

        self.assertEqual(
            duplicate_error,
            "human review already exists for this decision",
        )

    def test_submit_human_review_blocks_closed_ticket(self):
        decision, error = run_triage(
            self.ticket,
            "manual",
        )

        self.assertIsNone(error)

        self.ticket.status = "closed"
        self.ticket.save(update_fields=["status"])

        review_record, review_error = submit_human_review(
            decision,
            "review_requested_action",
            "closed ticket should not be reviewed",
        )

        self.assertIsNone(review_record)

        self.assertEqual(
            review_error,
            "ticket status=closed is not eligible for human review",
        )

class TicketAIAssistRecordTests(TestCase):

    def test_ai_assist_record_saves_pending_snapshot(self):

        record_model = apps.get_model(
            "myapp",
            "TicketAIAssistRecord",
        )

        user = User.objects.create_user(
            username="ai_reviewer",
            password="Test1234!",
        )

        customer = Customer.objects.create(
            name="AI 測試客戶",
            phone="0912345678",
            email="ai-record@example.com",
        )

        order = Order.objects.create(
            customer=customer,
            shipping_address="測試地址",
            status="paid",
            order_number="AI-TEST-001",
        )

        ticket = SupportTicket.objects.create(
            customer=customer,
            order=order,
            category="refund",
            requested_action="refund",
            message="商品有問題，希望退款。",
            status="open",
        )

        decision, error = run_triage(
            ticket,
            "manual",
        )

        self.assertIsNone(error)
        self.assertIsNotNone(decision)

        snapshot = {
            "message": ticket.message,
            "category": decision.category_snapshot,
            "requested_action": decision.requested_action_snapshot,
        }

        record = record_model.objects.create(
            decision=decision,
            requested_by=user,
            input_snapshot=snapshot,
            model_name="gemini-2.5-flash",
            prompt_version="v1",
        )

        record.refresh_from_db()

        self.assertEqual(record.status, "pending")
        self.assertEqual(record.input_snapshot, snapshot)
        self.assertIsNone(record.output_data)

        self.assertEqual(record.decision, decision)
        self.assertEqual(record.requested_by, user)

        self.assertTrue(
            decision.ai_assist_records.filter(
                pk=record.pk
            ).exists()
        )

        record.status = "success"

        with self.assertRaises(ValidationError):
            record.full_clean()

class AIInputSnapshotTests(TestCase):

    def test_high_risk_snapshot_is_json_safe_and_excludes_pii(self):

        from .ai_service import build_ai_input_snapshot

        customer = Customer.objects.create(
            name="AI 測試客戶",
            phone="0912345678",
            email="ai-snapshot@example.com",
        )

        order = Order.objects.create(
            customer=customer,
            shipping_address="AI 測試配送地址",
            status="paid",
            order_number="AI-SNAPSHOT-001",
        )

        product = Product.objects.create(
            name="測試商品",
            stock=10,
            price="3500.00",
            product_code="AI-SNAPSHOT-P01",
        )

        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=1,
            unit_price="3500.00",
        )

        ticket = SupportTicket.objects.create(
            customer=customer,
            order=order,
            category="refund",
            requested_action="refund",
            message=(
                "商品有瑕疵，希望申請退款。"
                "請聯絡 0912345678 或 ai-snapshot@example.com。"
            ),
            status="open",
        )

        decision, route, _ = run_triage_workflow(
            ticket,
            "manual",
        )

        self.assertIsNotNone(decision)
        self.assertEqual(route, "human_review")

        snapshot, error = build_ai_input_snapshot(decision)

        self.assertIsNone(error)

        self.assertIn(
            "商品有瑕疵，希望申請退款。",
            snapshot["ticket_message"],
        )

        self.assertNotIn(
            customer.phone,
            snapshot["ticket_message"],
        )

        self.assertNotIn(
            customer.email,
            snapshot["ticket_message"],
        )

        self.assertEqual(snapshot["category"], "refund")
        self.assertEqual(snapshot["requested_action"], "refund")
        self.assertEqual(snapshot["order_total"], "3500.00")
        self.assertEqual(snapshot["risk_gate_route"], "human_review")

        self.assertTrue({
            "severity_level",
            "impact_level",
            "urgency_level",
            "priority_level",
            "prior_ticket_count",
        }.issubset(snapshot))

        payload = json.dumps(
            snapshot,
            ensure_ascii=False,
        )

        for sensitive_value in (
            customer.name,
            customer.phone,
            customer.email,
            order.shipping_address,
        ):
            self.assertNotIn(sensitive_value, payload)

    def test_auto_handle_decision_cannot_build_ai_snapshot(self):

        from .ai_service import build_ai_input_snapshot

        customer = Customer.objects.create(
            name="低風險測試客戶",
            phone="0912345678",
            email="ai-low-risk@example.com",
        )

        order = Order.objects.create(
            customer=customer,
            shipping_address="測試地址",
            status="paid",
            order_number="AI-LOW-001",
        )

        ticket = SupportTicket.objects.create(
            customer=customer,
            order=order,
            category="other",
            requested_action="info",
            message="請問訂單目前的處理進度？",
            status="open",
        )

        decision, route, _ = run_triage_workflow(
            ticket,
            "manual",
        )

        self.assertIsNotNone(decision)
        self.assertEqual(route, "auto_handle")

        snapshot, snapshot_error = build_ai_input_snapshot(
            decision
        )

        self.assertIsNone(snapshot)

        self.assertEqual(
            snapshot_error,
            "decision is not routed to human review",
        )

class AIAssistOutputTests(TestCase):

    def test_ai_output_requires_correct_structure(self):

        from .ai_service import AIAssistOutput

        valid_output = {
            "summary": "客戶反映商品損壞。",
            "risk_notes": [
                "需要人工確認退款條件"
            ],
            "reply_draft": "您好，我們已收到您的問題。",
        }

        result = AIAssistOutput.model_validate(
            valid_output
        )

        self.assertEqual(
            result.model_dump(),
            valid_output,
        )

        invalid_output = {
            "summary": "客戶要求退款",
            "risk_notes": "需要人工確認",
            "reply_draft": "您好，我們已收到您的問題。",
        }

        with self.assertRaises(PydanticValidationError):
            AIAssistOutput.model_validate(
                invalid_output
            )

class GeminiServiceTests(TestCase):

    def test_generate_ai_assist_returns_valid_output(self):

        from .ai_service import generate_ai_assist

        snapshot = {
            "ticket_message": "商品損壞，希望退款。",
            "risk_gate_route": "human_review",
        }

        expected_output = {
            "summary": "客戶反映商品損壞。",
            "risk_notes": ["退款需要人工審核"],
            "reply_draft": "您好，我們已收到您的問題。",
        }

        with patch.dict(
            "os.environ",
            {"GEMINI_API_KEY": "fake-test-key"},
        ):
            with patch("google.genai.Client") as mock_client:

                mock_response = (
                    mock_client.return_value
                    .models.generate_content.return_value
                )

                mock_response.text = json.dumps(
                    expected_output,
                    ensure_ascii=False,
                )

                result, error = generate_ai_assist(snapshot)

                self.assertIsNone(error)
                self.assertEqual(result, expected_output)

                mock_client.return_value.models.generate_content.assert_called_once()
                mock_client.return_value.close.assert_called_once()

                http_options = mock_client.call_args.kwargs.get(
                    "http_options"
                )

                self.assertIsNotNone(http_options)

                self.assertEqual(
                    http_options.timeout,
                    60000,
                )

                self.assertEqual(
                    http_options.retry_options.attempts,
                    1,
                )

    def test_generate_ai_assist_handles_api_failure(self):

        from .ai_service import generate_ai_assist

        snapshot = {
            "ticket_message": "商品損壞，希望退款。",
            "risk_gate_route": "human_review",
        }

        with patch.dict(
            "os.environ",
            {"GEMINI_API_KEY": "fake-test-key"},
        ):
            with patch("myapp.ai_service.genai.Client") as mock_client:

                mock_client.return_value.models.generate_content.side_effect = (
                    RuntimeError("simulated API failure")
                )

                result, error = generate_ai_assist(snapshot)

                self.assertIsNone(result)
                self.assertEqual(
                    error,
                    "GEMINI_REQUEST_FAILED",
                )

                mock_client.return_value.close.assert_called_once()

    def test_generate_ai_assist_rejects_invalid_output(self):

        from .ai_service import generate_ai_assist

        snapshot = {
            "ticket_message": "商品損壞，希望退款。",
            "risk_gate_route": "human_review",
        }

        with patch.dict(
            "os.environ",
            {"GEMINI_API_KEY": "fake-test-key"},
        ):
            with patch("myapp.ai_service.genai.Client") as mock_client:

                mock_response = (
                    mock_client.return_value
                    .models.generate_content.return_value
                )

                mock_response.text = json.dumps({
                    "summary": "客戶要求退款",
                    "risk_notes": "需要人工審核",
                    "reply_draft": "您好，我們已收到您的問題。",
                })

                result, error = generate_ai_assist(snapshot)

                self.assertIsNone(result)

                self.assertEqual(
                    error,
                    "GEMINI_REQUEST_FAILED",
                )

                mock_client.return_value.close.assert_called_once()

    def test_generate_ai_assist_handles_client_init_failure(self):

            from .ai_service import generate_ai_assist

            snapshot = {
                "ticket_message": "商品損壞，希望退款。",
                "risk_gate_route": "human_review",
            }

            with patch.dict(
                "os.environ",
                {"GEMINI_API_KEY": "fake-test-key"},
            ):
                with patch(
                    "myapp.ai_service.genai.Client",
                    side_effect=RuntimeError(
                        "simulated client initialization failure"
                    ),
                ):

                    result, error = generate_ai_assist(snapshot)

            self.assertIsNone(result)

            self.assertEqual(
                error,
                "GEMINI_REQUEST_FAILED",
            )

class AIAssistWorkflowTests(TestCase):

    def test_successful_ai_assist_saves_record(self):

        from .ai_service import run_ai_assist

        user = User.objects.create_user(
            username="ai_workflow_user",
            password="Test1234!",
        )

        customer = Customer.objects.create(
            name="AI Workflow 測試客戶",
            phone="0912345678",
            email="ai-workflow@example.com",
        )

        order = Order.objects.create(
            customer=customer,
            shipping_address="測試地址",
            status="paid",
            order_number="AI-WORKFLOW-001",
        )

        ticket = SupportTicket.objects.create(
            customer=customer,
            order=order,
            category="refund",
            requested_action="refund",
            message="商品損壞，希望退款。",
            status="open",
        )

        decision, route, _ = run_triage_workflow(
            ticket,
            "manual",
        )

        self.assertEqual(route, "human_review")

        expected_output = {
            "summary": "客戶反映商品損壞。",
            "risk_notes": ["退款需要人工審核"],
            "reply_draft": "您好，我們已收到您的問題。",
        }

        with patch(
            "myapp.ai_service.generate_ai_assist",
            return_value=(expected_output, None),
        ) as mock_generate:

            record, error = run_ai_assist(
                decision,
                user,
            )

        self.assertIsNone(error)
        self.assertIsNotNone(record)

        record.refresh_from_db()

        self.assertEqual(record.status, "success")
        self.assertEqual(record.output_data, expected_output)
        self.assertEqual(record.decision, decision)
        self.assertEqual(record.requested_by, user)

        self.assertEqual(
            record.input_snapshot["risk_gate_route"],
            "human_review",
        )

        mock_generate.assert_called_once()

        review_record, review_error = submit_human_review(
            decision,
            "review_requested_action",
            "測試 AI 分析後完成人工審核",
        )

        self.assertIsNone(review_error)
        self.assertIsNotNone(review_record)

        self.client.force_login(user)

        response = self.client.get(
            reverse("high_risk_review", args=[ticket.id])
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "此案件已完成人工審核",
        )

        self.assertNotContains(
            response,
            "執行 AI 輔助分析",
        )

        self.assertContains(
            response,
            expected_output["summary"],
        )

        self.assertContains(
            response,
            expected_output["risk_notes"][0],
        )

        self.assertContains(
            response,
            expected_output["reply_draft"],
        )

        ticket.status = "closed"
        ticket.save(update_fields=["status"])

        response = self.client.get(
            reverse("high_risk_review", args=[ticket.id])
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            expected_output["summary"],
        )

        self.assertNotContains(
            response,
            "執行 AI 輔助分析",
        )

    def test_failed_ai_assist_saves_failed_record(self):

        from .ai_service import run_ai_assist

        user = User.objects.create_user(
            username="ai_failure_user",
            password="Test1234!",
        )

        customer = Customer.objects.create(
            name="AI 失敗測試客戶",
            phone="0912345678",
            email="ai-failure@example.com",
        )

        order = Order.objects.create(
            customer=customer,
            shipping_address="測試地址",
            status="paid",
            order_number="AI-FAIL-001",
        )

        ticket = SupportTicket.objects.create(
            customer=customer,
            order=order,
            category="refund",
            requested_action="refund",
            message="商品損壞，希望退款。",
            status="open",
        )

        decision, route, _ = run_triage_workflow(
            ticket,
            "manual",
        )

        self.assertIsNotNone(decision)
        self.assertEqual(route, "human_review")

        with patch(
            "myapp.ai_service.generate_ai_assist",
            return_value=(None, "GEMINI_REQUEST_FAILED"),
        ) as mock_generate:

            record, error = run_ai_assist(
                decision,
                user,
            )

        self.assertIsNotNone(record)

        self.assertEqual(
            error,
            "GEMINI_REQUEST_FAILED",
        )

        record.refresh_from_db()

        self.assertEqual(record.status, "failed")
        self.assertIsNone(record.output_data)

        self.assertEqual(
            record.error_code,
            "GEMINI_REQUEST_FAILED",
        )

        self.assertIsNotNone(record.completed_at)

        self.assertEqual(record.decision, decision)
        self.assertEqual(record.requested_by, user)

        self.assertEqual(
            decision.ai_assist_records.count(),
            1,
        )

        mock_generate.assert_called_once()

    def test_closed_ticket_cannot_run_ai_assist(self):

        from .ai_service import run_ai_assist

        user = User.objects.create_user(
            username="ai_closed_user",
            password="Test1234!",
        )

        customer = Customer.objects.create(
            name="已關閉案件測試客戶",
            phone="0912345678",
            email="ai-closed@example.com",
        )

        order = Order.objects.create(
            customer=customer,
            shipping_address="測試地址",
            status="paid",
            order_number="AI-CLOSED-001",
        )

        ticket = SupportTicket.objects.create(
            customer=customer,
            order=order,
            category="refund",
            requested_action="refund",
            message="商品損壞，希望退款。",
            status="open",
        )

        decision, route, _ = run_triage_workflow(
            ticket,
            "manual",
        )

        self.assertIsNotNone(decision)
        self.assertEqual(route, "human_review")

        ticket.status = "closed"
        ticket.save(update_fields=["status"])

        with patch(
            "myapp.ai_service.generate_ai_assist"
        ) as mock_generate:

            record, error = run_ai_assist(
                decision,
                user,
            )

        self.assertIsNone(record)
        self.assertEqual(
            error,
            "AI_ASSIST_TICKET_NOT_ELIGIBLE",
        )

        self.assertEqual(
            decision.ai_assist_records.count(),
            0,
        )

        mock_generate.assert_not_called()

    def test_reviewed_ticket_cannot_run_ai_assist(self):

        from .ai_service import run_ai_assist

        user = User.objects.create_user(
            username="ai_reviewed_user",
            password="Test1234!",
        )

        customer = Customer.objects.create(
            name="已審核測試客戶",
            phone="0912345678",
            email="ai-reviewed@example.com",
        )

        order = Order.objects.create(
            customer=customer,
            shipping_address="測試地址",
            status="paid",
            order_number="AI-REVIEWED-001",
        )

        ticket = SupportTicket.objects.create(
            customer=customer,
            order=order,
            category="refund",
            requested_action="refund",
            message="商品損壞，希望退款。",
            status="open",
        )

        decision, route, _ = run_triage_workflow(
            ticket,
            "manual",
        )

        self.assertIsNotNone(decision)
        self.assertEqual(route, "human_review")

        review_record, review_error = submit_human_review(
            decision,
            "review_requested_action",
            "已完成案件人工審核",
        )

        self.assertIsNone(review_error)
        self.assertIsNotNone(review_record)

        with patch(
            "myapp.ai_service.generate_ai_assist",
            return_value=(
                {
                    "summary": "測試摘要",
                    "risk_notes": ["測試注意事項"],
                    "reply_draft": "測試回覆",
                },
                None,
            ),
        ) as mock_generate:

            record, error = run_ai_assist(
                decision,
                user,
            )

        self.assertIsNone(record)

        self.assertEqual(
            error,
            "AI_ASSIST_ALREADY_REVIEWED",
        )

        self.assertEqual(
            decision.ai_assist_records.count(),
            0,
        )

        mock_generate.assert_not_called()

    def test_same_successful_snapshot_reuses_ai_record(self):

        from .ai_service import run_ai_assist

        user = User.objects.create_user(
            username="ai_reuse_user",
            password="Test1234!",
        )

        customer = Customer.objects.create(
            name="重複分析測試客戶",
            phone="0912345678",
            email="ai-reuse@example.com",
        )

        order = Order.objects.create(
            customer=customer,
            shipping_address="測試地址",
            status="paid",
            order_number="AI-REUSE-001",
        )

        ticket = SupportTicket.objects.create(
            customer=customer,
            order=order,
            category="refund",
            requested_action="refund",
            message="商品損壞，希望退款。",
            status="open",
        )

        decision, route, _ = run_triage_workflow(
            ticket,
            "manual",
        )

        self.assertIsNotNone(decision)
        self.assertEqual(route, "human_review")

        expected_output = {
            "summary": "客戶反映商品損壞。",
            "risk_notes": ["退款需要人工審核"],
            "reply_draft": "您好，我們已收到您的問題。",
        }

        with patch(
            "myapp.ai_service.generate_ai_assist",
            return_value=(expected_output, None),
        ) as mock_generate:

            first_record, first_error = run_ai_assist(
                decision,
                user,
            )

            second_record, second_error = run_ai_assist(
                decision,
                user,
            )

        self.assertIsNone(first_error)
        self.assertIsNone(second_error)

        self.assertIsNotNone(first_record)
        self.assertIsNotNone(second_record)

        self.assertEqual(
            first_record.pk,
            second_record.pk,
        )

        self.assertEqual(
            decision.ai_assist_records.count(),
            1,
        )

        mock_generate.assert_called_once()

    def test_pending_ai_assist_blocks_duplicate_request(self):

        from .ai_service import (
            run_ai_assist,
            build_ai_input_snapshot,
        )

        user = User.objects.create_user(
            username="ai_pending_user",
            password="Test1234!",
        )

        customer = Customer.objects.create(
            name="Pending 測試客戶",
            phone="0912345678",
            email="ai-pending@example.com",
        )

        order = Order.objects.create(
            customer=customer,
            shipping_address="測試地址",
            status="paid",
            order_number="AI-PENDING-001",
        )

        ticket = SupportTicket.objects.create(
            customer=customer,
            order=order,
            category="refund",
            requested_action="refund",
            message="商品損壞，希望退款。",
            status="open",
        )

        decision, route, _ = run_triage_workflow(
            ticket,
            "manual",
        )

        self.assertIsNotNone(decision)
        self.assertEqual(route, "human_review")

        snapshot, snapshot_error = build_ai_input_snapshot(
            decision
        )

        self.assertIsNone(snapshot_error)

        pending_record = decision.ai_assist_records.create(
            requested_by=user,
            input_snapshot=snapshot,
            model_name="gemini-3.8-flash",
            prompt_version="v1",
        )

        self.assertEqual(pending_record.status, "pending")

        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                decision.ai_assist_records.create(
                    requested_by=user,
                    input_snapshot=snapshot,
                    model_name="gemini-3.8-flash",
                    prompt_version="v1",
                )

        expected_output = {
            "summary": "測試摘要",
            "risk_notes": ["需要人工審核"],
            "reply_draft": "您好，我們已收到您的問題。",
        }

        with patch(
            "myapp.ai_service.generate_ai_assist",
            return_value=(expected_output, None),
        ) as mock_generate:

            record, error = run_ai_assist(
                decision,
                user,
            )

        self.assertIsNone(record)

        self.assertEqual(
            error,
            "AI_ASSIST_ALREADY_RUNNING",
        )

        self.assertEqual(
            decision.ai_assist_records.count(),
            1,
        )

        mock_generate.assert_not_called()

        with patch(
            "django.db.models.query.QuerySet.exists",
            return_value=False,
        ):
            with patch(
                "myapp.ai_service.generate_ai_assist"
            ) as mock_race:

                race_record, race_error = run_ai_assist(
                    decision,
                    user,
                )

        self.assertIsNone(race_record)

        self.assertEqual(
            race_error,
            "AI_ASSIST_ALREADY_RUNNING",
        )

        self.assertEqual(
            decision.ai_assist_records.count(),
            1,
        )

        mock_race.assert_not_called()

        original_message = decision.ticket.message

        decision.ticket.message = "商品仍有問題，補充退款說明。"
        decision.ticket.save(update_fields=["message"])

        with patch(
            "myapp.ai_service.generate_ai_assist"
        ) as mock_generate:

            changed_record, changed_error = run_ai_assist(
                decision,
                user,
            )

        self.assertIsNone(changed_record)
        self.assertEqual(
            changed_error,
            "AI_ASSIST_ALREADY_RUNNING",
        )

        mock_generate.assert_not_called()

        decision.ticket.message = original_message
        decision.ticket.save(update_fields=["message"])

        from datetime import timedelta
        from django.utils import timezone

        stale_time = timezone.now() - timedelta(minutes=10)

        decision.ai_assist_records.filter(
            pk=pending_record.pk,
        ).update(created_at=stale_time)

        with patch(
            "myapp.ai_service.generate_ai_assist",
            return_value=(expected_output, None),
        ) as mock_retry:

            new_record, retry_error = run_ai_assist(
                decision,
                user,
            )

        self.assertIsNone(retry_error)
        self.assertIsNotNone(new_record)

        self.assertEqual(new_record.status, "success")

        pending_record.refresh_from_db()

        self.assertEqual(pending_record.status, "failed")

        self.assertEqual(
            pending_record.error_code,
            "AI_ASSIST_STALE_PENDING",
        )

        self.assertIsNotNone(pending_record.completed_at)

        self.assertEqual(
            decision.ai_assist_records.count(),
            2,
        )

        mock_retry.assert_called_once()

class AIAssistWebEndpointTests(TestCase):

    def test_anonymous_post_redirects_to_login(self):

        url = reverse(
            "run_ticket_ai_assist",
            args=[1],
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)

        self.assertIn(
            "/login/",
            response["Location"],
        )

    def test_authenticated_requests_require_post_and_csrf(self):

        from django.test import Client

        user = User.objects.create_user(
            username="ai_web_security_user",
            password="Test1234!",
        )

        client = Client(enforce_csrf_checks=True)
        client.force_login(user)

        url = reverse(
            "run_ticket_ai_assist",
            args=[1],
        )

        get_response = client.get(url)

        self.assertEqual(
            get_response.status_code,
            405,
        )

        post_response = client.post(url)

        self.assertEqual(
            post_response.status_code,
            403,
        )

    def test_authenticated_post_runs_ai_assist(self):

        user = User.objects.create_user(
            username="ai_web_user",
            password="Test1234!",
        )

        customer = Customer.objects.create(
            name="Web AI 測試客戶",
            phone="0912345678",
            email="web-ai@example.com",
        )

        order = Order.objects.create(
            customer=customer,
            shipping_address="測試地址",
            status="paid",
            order_number="WEB-AI-001",
        )

        ticket = SupportTicket.objects.create(
            customer=customer,
            order=order,
            category="refund",
            requested_action="refund",
            message="商品損壞，希望退款。",
            status="open",
        )

        decision, route, _ = run_triage_workflow(
            ticket,
            "manual",
        )

        self.assertIsNotNone(decision)
        self.assertEqual(route, "human_review")

        self.client.force_login(user)

        url = reverse(
            "run_ticket_ai_assist",
            args=[ticket.id],
        )

        with patch(
            "myapp.ai_service.run_ai_assist",
            return_value=(object(), None),
        ) as mock_run:

            response = self.client.post(url)

        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            response.url,
            reverse(
                "high_risk_review",
                args=[ticket.id],
            ),
        )

        mock_run.assert_called_once_with(
            decision,
            user,
        )


class PrepareLiveDemoCommandTests(TestCase):

    def setUp(self):
        from django.core.management import call_command

        # 測試資料只建立在 Django Test Database
        call_command(
            "seed_demo",
            "--with-tickets",
            verbosity=0,
        )

    def test_dry_run_does_not_modify_created_at(self):
        from django.core.management import call_command
        from django.test import override_settings

        from myapp.models import SupportTicket

        ticket = SupportTicket.objects.get(
            message__startswith="[DEMO-T001]"
        )

        original_created_at = ticket.created_at

        with override_settings(ALLOW_DEMO_DATA_RESET=False):
            call_command(
                "prepare_live_demo",
                verbosity=0,
            )

        ticket.refresh_from_db()

        self.assertEqual(
            ticket.created_at,
            original_created_at,
        )

        self.assertEqual(
            ticket.status,
            "open",
        )

        self.assertFalse(
            ticket.triage_decisions.exists()
        )

    def test_execute_updates_only_live_demo_tickets(self):
        from datetime import timedelta

        from django.core.management import call_command
        from django.test import override_settings
        from django.utils import timezone

        from myapp.models import SupportTicket
        from myapp.management.commands.seed_demo import (
            DEMO_LIVE_TICKET_IDS,
            DEMO_TICKETS,
        )
        from myapp.management.commands.seed_demo_triage import (
            predict_demo_route,
        )

        # 先記錄一筆非 Live Ticket 的建立時間
        other_ticket = SupportTicket.objects.get(
            message__startswith="[DEMO-T003]"
        )
        original_other_time = other_ticket.created_at

        # 只在隔離測試資料庫中開啟安全設定
        with override_settings(
            ALLOW_DEMO_DATA_RESET=True,
            DEBUG=True,
        ):
            call_command(
                "prepare_live_demo",
                "--execute",
                verbosity=0,
            )

        expected_routes = {
            "DEMO-T001": "auto_handle",
            "DEMO-T002": "human_review",
            "DEMO-T004": "auto_handle",
            "DEMO-T025": "human_review",
            "DEMO-T034": "human_review",
            "DEMO-T040": "human_review",
        }

        specs = {
            data["demo_id"]: data
            for data in DEMO_TICKETS
            if data["demo_id"] in DEMO_LIVE_TICKET_IDS
        }

        for demo_id in DEMO_LIVE_TICKET_IDS:
            ticket = SupportTicket.objects.get(
                message__startswith=f"[{demo_id}]"
            )

            actual_hours = (
                timezone.now() - ticket.created_at
            ).total_seconds() / 3600

            target_hours = specs[demo_id]["waiting_hours"]

            self.assertAlmostEqual(
                actual_hours,
                target_hours,
                delta=0.05,
            )

            self.assertEqual(
                predict_demo_route(ticket),
                expected_routes[demo_id],
            )

            self.assertEqual(ticket.status, "open")
            self.assertFalse(ticket.triage_decisions.exists())

        # 確認非 Live Ticket 沒有被更新
        other_ticket.refresh_from_db()

        self.assertEqual(
            other_ticket.created_at,
            original_other_time,
        )

    def test_execute_is_blocked_when_reset_disabled(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from django.test import override_settings

        from myapp.models import SupportTicket

        ticket = SupportTicket.objects.get(
            message__startswith="[DEMO-T001]"
        )

        original_created_at = ticket.created_at

        with override_settings(ALLOW_DEMO_DATA_RESET=False):
            with self.assertRaises(CommandError):
                call_command(
                    "prepare_live_demo",
                    "--execute",
                    verbosity=0,
                )

        ticket.refresh_from_db()

        self.assertEqual(
            ticket.created_at,
            original_created_at,
        )
