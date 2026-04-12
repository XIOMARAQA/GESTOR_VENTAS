from django.urls import path

from apps.core import views_auth

urlpatterns = [
    path("registro/", views_auth.RegistroEmpresaView.as_view(), name="auth-registro"),
    path("login/", views_auth.LoginView.as_view(), name="auth-login"),
    path("session/", views_auth.SessionView.as_view(), name="auth-session"),
    path("logout/", views_auth.LogoutView.as_view(), name="auth-logout"),
]
