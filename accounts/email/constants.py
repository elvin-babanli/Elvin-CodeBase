"""
Email constants. Single source of truth for brand and sender.
All system emails use B Labs branding and updates@elvin-babanli.com.
"""
from django.conf import settings

# Brand
BRAND_NAME = "B Labs"
DOMAIN = "elvin-babanli.com"

# From address - must match EMAIL_HOST_USER for SMTP auth
# Format: "B Labs <updates@elvin-babanli.com>"
def get_from_email():
    """Get branded from_email from settings. Never use fallback personal Gmail."""
    return getattr(
        settings,
        "DEFAULT_FROM_EMAIL",
        f"{BRAND_NAME} <updates@{DOMAIN}>",
    )
