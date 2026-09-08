from django.urls import path
from . import views
from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register('api/viewset/tickets', views.SupportTicketViewSet, basename='support_ticket')

urlpatterns = [
    path('tickets/', views.ticket_list, name='ticket_list'),
    path('tickets/create/', views.ticket_create, name='ticket_create'),
    path('tickets/<int:ticket_id>/edit/', views.ticket_edit, name='ticket_edit'),
    path('tickets/<int:ticket_id>/delete/',views.ticket_delete, name='ticket_delete'),
    path('api/tickets/', views.support_ticket_api, name='support_ticket_api'),
    path('api/tickets/<int:ticket_id>/', views.support_ticket_detail_api, name='support_ticket_detail_api'),
    path('api/apiview/tickets/', views.SupportTicketListAPIView.as_view(), name='support_ticket_list_apiview'),
    path('api/apiview/tickets/<int:ticket_id>/', views.SupportTicketDetailAPIView.as_view(), name='support_ticket_detail_apiview'),
    path('api/generic/tickets/', views.SupportTicketListGenericAPIView.as_view(), name='support_ticket_list_generic'),
    path('api/generic/tickets/<int:ticket_id>/', views.SupportTicketDetailGenericAPIView.as_view(), name='support_ticket_detail_generic'),
]

urlpatterns += router.urls