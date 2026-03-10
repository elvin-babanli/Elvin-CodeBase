"""
Email constants. Single source of truth for brand and sender.
Envelope sender (MAIL FROM) must match EMAIL_HOST_USER to avoid 550 relay denied.
"""
from django.conf import settings

# Brand
BRAND_NAME = "B Labs"
DOMAIN = "elvin-babanli.com"
# Default sender address (used when no EMAIL_HOST_USER / DEFAULT_FROM_EMAIL)
SENDER_EMAIL = "updates@elvin-babanli.com"


def get_from_email():
    """
    From address for MAIL FROM. Must match EMAIL_HOST_USER when using SMTP auth
    to avoid 550 relay denied. Falls back to DEFAULT_FROM_EMAIL or updates@elvin-babanli.com.
    """
    default_sender = f"{BRAND_NAME} <{SENDER_EMAIL}>"
    from_setting = getattr(settings, "DEFAULT_FROM_EMAIL", "") or ""
    auth_user = getattr(settings, "EMAIL_HOST_USER", "") or ""
    if auth_user:
        return f"{BRAND_NAME} <{auth_user}>"
    return from_setting if from_setting else default_sender
