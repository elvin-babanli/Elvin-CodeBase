"""
Modular email service. Template-based, future-ready for branded HTML and images.
Production-ready: Gmail SMTP, error handling, logging.
"""
import logging
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def _get_from_email():
    return getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@localhost")


def _is_smtp_configured():
    """Check if SMTP is properly configured for real email sending."""
    backend = getattr(settings, "EMAIL_BACKEND", "")
    if "console" in backend:
        return False
    if "smtp" not in backend:
        return False
    host = getattr(settings, "EMAIL_HOST", "")
    user = getattr(settings, "EMAIL_HOST_USER", "")
    pwd = getattr(settings, "EMAIL_HOST_PASSWORD", "")
    return bool(host and user and pwd)


def send_templated_email(to_emails, subject, template_name, context=None, html_template_name=None):
    """
    Send email from a template. Returns True on success, False on failure.
    """
    if context is None:
        context = {}

    try:
        html_template = html_template_name or template_name
        html_content = render_to_string(html_template, context)
    except Exception as e:
        logger.exception("Email template render failed (template=%s): %s", template_name, e)
        return False

    text_content = strip_tags(html_content)
    from_email = _get_from_email()
    if isinstance(to_emails, str):
        to_emails = [to_emails]

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=to_emails,
    )
    msg.attach_alternative(html_content, "text/html")

    try:
        msg.send(fail_silently=False)
        logger.info("Email sent to %s: %s", to_emails, subject)
        return True
    except Exception as e:
        err_msg = str(e).lower()
        if "authentication" in err_msg or "535" in str(e):
            logger.error("Email SMTP auth failed (check EMAIL_HOST_USER / GMAIL_APP_PASSWORD): %s", e)
        elif "connection" in err_msg or "timed out" in err_msg:
            logger.error("Email SMTP connection failed (check EMAIL_HOST, EMAIL_PORT, firewall): %s", e)
        else:
            logger.exception("Email send failed: %s", e)
        return False


def send_password_reset_code(to_email: str, code: str) -> bool:
    """
    Send password reset verification code. Subject: Your Verification Code.
    """
    if not _is_smtp_configured():
        logger.warning("SMTP not configured; email would go to console. Set EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD (or GMAIL_APP_PASSWORD).")

    return send_templated_email(
        to_emails=[to_email],
        subject="Your Verification Code",
        template_name="accounts/emails/password_reset_code.html",
        context={"code": code},
    )
