from django.contrib import admin
from django.urls import path,include
from rest_framework.authtoken.views import obtain_auth_token
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),

    path(
      'login/',
      auth_views.LoginView.as_view(template_name='login.html'),
      name='login',
    ),

    path(
      'logout/',
      auth_views.LogoutView.as_view(),
      name='logout',
    ),

    path('',include('myapp.urls')),

    path('api-auth/', include('rest_framework.urls')),

    path('api-token-auth/', obtain_auth_token),
]
