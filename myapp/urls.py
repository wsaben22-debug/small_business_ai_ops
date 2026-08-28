from django.urls import path
from . import views

urlpatterns = [
    path('tickets/', views.ticket_list, name='ticket_list'),
    path('tickets/create/', views.ticket_create, name='ticket_create'),
    path('tickets/<int:ticket_id>/edit/', views.ticket_edit, name='ticket_edit'),
    path('tickets/<int:ticket_id>/delete/',views.ticket_delete, name='ticket_delete'),
    path('api/tickets/', views.support_ticket_api, name='support_ticket_api'),
]