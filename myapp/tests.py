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