from django.conf import settings


def chat_settings(request):
    return {"CHAT_API_URL": getattr(settings, "CHAT_API_URL", "")}


def admin_dashboard(request):
    """Show Admin Dashboard link only to users in ADMIN_DASHBOARD_EMAILS."""
    show = False
    if request.user.is_authenticated and request.user.email:
        emails = getattr(settings, "ADMIN_DASHBOARD_EMAILS", [])
        if isinstance(emails, str):
            emails = [e.strip().lower() for e in emails.split(",") if e.strip()]
        else:
            emails = [e.lower() for e in emails]
        show = request.user.email.lower() in emails
    return {"show_admin_dashboard": show}
