"""
Authentication URL configuration.
"""
from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="auth_login"),
    path("register/", views.register_view, name="auth_register"),
    path("logout/", views.logout_view, name="auth_logout"),
    path("profile/", views.profile_view, name="auth_profile"),
    path("forgot-password/", views.forgot_password_view, name="auth_forgot_password"),
    path("verify-code/", views.verify_code_view, name="auth_verify_code"),
    path("reset-password/", views.reset_password_view, name="auth_reset_password"),
    path("dev-auto-login/", views.dev_auto_login_view, name="auth_dev_auto_login"),
]
