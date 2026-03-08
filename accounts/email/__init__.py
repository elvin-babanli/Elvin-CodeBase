"""
Unified email service for B Labs.
All system emails: updates@elvin-babanli.com with B Labs branding.
"""
from .service import (
    send_register_welcome,
    send_otp_code,
    send_password_reset_code,
    send_update_announcement,
)

__all__ = [
    "send_register_welcome",
    "send_otp_code",
    "send_password_reset_code",
    "send_update_announcement",
]
