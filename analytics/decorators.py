"""Admin dashboard access control."""
from functools import wraps
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings


def _is_dashboard_admin(user):
    if not user or not user.is_authenticated:
        return False
    emails = getattr(settings, "ADMIN_DASHBOARD_EMAILS", [])
    if isinstance(emails, str):
        emails = [e.strip() for e in emails.split(",") if e.strip()]
    return user.email and user.email.lower() in [e.lower() for e in emails]


def admin_dashboard_required(view_func):
    """Decorator: only allow users in ADMIN_DASHBOARD_EMAILS."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(settings.LOGIN_URL + f"?next={request.path}")
        if not _is_dashboard_admin(request.user):
            return redirect("home")
        return view_func(request, *args, **kwargs)
    return login_required(_wrapped)
