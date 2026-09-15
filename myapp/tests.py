from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from .models import Customer, Order, SupportTicket


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