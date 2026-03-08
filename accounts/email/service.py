"""
Unified email service for B Labs.
Single source for: register welcome, OTP/verification, forgot password, future updates.
Production-ready: env-based config, error handling, logging.
"""
import logging
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .constants import BRAND_NAME, get_from_email

logger = logging.getLogger(__name__)


def _is_email_configured():
    """Check if real SMTP is configured (not console backend)."""
    backend = getattr(settings, "EMAIL_BACKEND", "") or ""
    if "console" in backend:
        return False
    if "smtp" not in backend.lower():
        return False
    host = getattr(settings, "EMAIL_HOST", "") or ""
    user = getattr(settings, "EMAIL_HOST_USER", "") or ""
    pwd = getattr(settings, "EMAIL_HOST_PASSWORD", "") or ""
    return bool(host and user and pwd)


def _send_templated(
    to_emails,
    subject,
    html_template_name,
    context=None,
    text_template_name=None,
):
    """
    Send HTML email from template. Returns True on success, False on failure.
    On failure: logs error, does not raise (user-friendly behavior).
    """
    if context is None:
        context = {}
    context.setdefault("brand_name", BRAND_NAME)
    context.setdefault("from_email_display", get_from_email())

    to_list = [to_emails] if isinstance(to_emails, str) else list(to_emails)
    from_addr = get_from_email()

    try:
        html_content = render_to_string(html_template_name, context)
    except Exception as e:
        logger.exception("Email template render failed (template=%s): %s", html_template_name, e)
        return False

    if text_template_name:
        try:
            text_content = render_to_string(text_template_name, context)
        except Exception as e:
            logger.warning("Text template failed, using stripped HTML: %s", e)
            text_content = strip_tags(html_content)
    else:
        text_content = strip_tags(html_content)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_addr,
        to=to_list,
    )
    msg.attach_alternative(html_content, "text/html")

    try:
        msg.send(fail_silently=False)
        logger.info("Email sent to %s: %s", to_list, subject)
        return True
    except Exception as e:
        err_str = str(e).lower()
        if "authentication" in err_str or "535" in str(e):
            logger.error(
                "Email SMTP auth failed. Check EMAIL_HOST_USER and EMAIL_HOST_PASSWORD. %s", e
            )
        elif "connection" in err_str or "timed out" in err_str:
            logger.error("Email SMTP connection failed. Check EMAIL_HOST, EMAIL_PORT. %s", e)
        else:
            logger.exception("Email send failed: %s", e)
        return False


def send_register_welcome(to_email: str, first_name: str = "") -> bool:
    """Send welcome email after successful registration."""
    if not _is_email_configured():
        logger.warning(
            "Email not configured (console backend or missing env). "
            "Set EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DEFAULT_FROM_EMAIL."
        )
    display_name = (first_name or "").strip() or "there"
    return _send_templated(
        to_emails=to_email,
        subject=f"Welcome to {BRAND_NAME}",
        html_template_name="accounts/emails/welcome.html",
        context={"first_name": display_name},
        text_template_name="accounts/emails/welcome.txt",
    )


def send_otp_code(to_email: str, code: str, purpose: str = "verification") -> bool:
    """
    Send 6-digit OTP/verification code.
    purpose: 'password_reset', 'verification', 'login_confirmation', etc.
    """
    if not _is_email_configured():
        logger.warning("Email not configured. OTP email would not be sent.")

    purpose_labels = {
        "password_reset": "password reset",
        "verification": "account verification",
        "login_confirmation": "login confirmation",
    }
    purpose_label = purpose_labels.get(purpose, "verification")

    return _send_templated(
        to_emails=to_email,
        subject=f"Your {BRAND_NAME} Verification Code",
        html_template_name="accounts/emails/otp_code.html",
        context={"code": code, "purpose": purpose_label},
        text_template_name="accounts/emails/otp_code.txt",
    )


def send_password_reset_code(to_email: str, code: str) -> bool:
    """Send password reset verification code (6-digit OTP)."""
    return send_otp_code(to_email, code, purpose="password_reset")


def send_update_announcement(to_email: str, subject: str, html_body: str) -> bool:
    """Future: send update/announcement emails. Uses same branded sender."""
    return _send_templated(
        to_emails=to_email,
        subject=subject,
        html_template_name="accounts/emails/update.html",
        context={"content": html_body},
    )
