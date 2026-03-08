"""Admin dashboard access middleware. Protects /admin-dashboard/*"""
from django.shortcuts import redirect
from django.conf import settings


ADMIN_EMAIL = "elvinbabanli0@gmail.com"


def _is_admin(user):
    if not user or not user.is_authenticated:
        return False
    return user.email and user.email.lower() == ADMIN_EMAIL.lower()


class AdminDashboardMiddleware:
    """Block /admin-dashboard/ for non-admin users."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        # Allow tracking API for all visitors (used by main site)
        if path == "/admin-dashboard/api/click/" and request.method == "POST":
            return self.get_response(request)
        if path.startswith("/admin-dashboard/"):
            if not _is_admin(request.user):
                return redirect(settings.LOGIN_URL + f"?next={path}")
        return self.get_response(request)
