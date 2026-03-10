"""
Flight notification service: SMS and Email.
Abstract layer for future Twilio/similar integration.
No fake success: returns controlled response based on actual send attempt.
"""
import logging
import re
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

# SMS: Set TWILIO_* or similar when real provider is configured
SMS_PROVIDER_CONFIGURED = bool(
    getattr(settings, "TWILIO_ACCOUNT_SID", None)
    and getattr(settings, "TWILIO_AUTH_TOKEN", None)
    and getattr(settings, "TWILIO_PHONE_NUMBER", None)
)


def _format_phone(phone: str) -> str:
    """Normalize to digits only, preserve leading + if present."""
    s = (phone or "").strip()
    if not s:
        return ""
    has_plus = s.startswith("+")
    digits = re.sub(r"\D", "", s)
    if has_plus and digits:
        return "+" + digits
    return digits


def _validate_phone(phone: str) -> tuple[bool, str]:
    """
    Validate phone for SMS. Returns (valid, error_message).
    Expects E.164 or national format with country code.
    """
    normalized = _format_phone(phone)
    if not normalized:
        return False, "Phone number is required"
    if len(normalized) < 10:
        return False, "Invalid phone number"
    if len(normalized) > 16:
        return False, "Invalid phone number"
    return True, ""


def _normalize_flight_for_display(flight: dict[str, Any]) -> dict[str, Any]:
    """Ensure flight has display fields for SMS/email. Handles minimal stored payload."""
    f = flight or {}
    route = f.get("route_display") or ""
    if not route and (f.get("origin") or f.get("destination")):
        route = f"{f.get('origin', '')} → {f.get('destination', '')}"
    price = f.get("price_display")
    if not price and f.get("price") is not None:
        cur = f.get("currency", "USD")
        price = f"{f['price']:.2f} {cur}" if isinstance(f.get("price"), (int, float)) else f"{f.get('price')} {cur}"
    dep_date = f.get("departure_date") or f.get("depart_date", "")
    dep_time = f.get("departure_time") or f.get("depart_time", "")
    airline = f.get("primary_airline") or f.get("airline", "")
    stops = f.get("stop_label", "")
    if stops == "" and f.get("stops") is not None:
        s = f["stops"]
        stops = "Direct" if s == 0 else ("1 stop" if s == 1 else f"{s} stops")
    dur = f.get("total_duration", "")
    if not dur and f.get("duration_minutes") is not None:
        m = f["duration_minutes"]
        if isinstance(m, (int, float)):
            h, mi = int(m) // 60, int(m) % 60
            dur = f"{h}h {mi}m" if mi else f"{h}h"
    return {
        "route_display": route,
        "price_display": price or "",
        "departure_date": dep_date,
        "departure_time": dep_time,
        "arrival_date": f.get("arrival_date", ""),
        "arrival_time": f.get("arrival_time", ""),
        "primary_airline": airline,
        "stop_label": stops,
        "total_duration": dur,
        "departure_iata": f.get("departure_iata") or f.get("origin", ""),
        "arrival_iata": f.get("arrival_iata") or f.get("destination", ""),
    }


def _format_flight_sms(flight: dict[str, Any]) -> str:
    """Short, readable SMS format."""
    n = _normalize_flight_for_display(flight)
    parts = [
        f"Flight: {n['route_display']}",
        f"Date: {n['departure_date']} {n['departure_time']}",
        f"Airline: {n['primary_airline']}",
        f"Stops: {n['stop_label']}",
        f"Duration: {n['total_duration']}",
        f"Price: {n['price_display']}",
    ]
    return " | ".join(p for p in parts if p.split(":", 1)[-1].strip())


def send_flight_sms(phone: str, flight: dict[str, Any]) -> dict[str, Any]:
    """
    Send flight summary via SMS.
    Returns {success: bool, error?: str, provider_used?: str}.
    No fake success: if provider not configured, returns success=False with clear error.
    """
    valid, err = _validate_phone(phone)
    if not valid:
        return {"success": False, "error": err}

    body = _format_flight_sms(flight)

    if SMS_PROVIDER_CONFIGURED:
        try:
            # Placeholder for Twilio: when configured, call here
            # from twilio.rest import Client
            # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            # message = client.messages.create(body=body, from_=settings.TWILIO_PHONE_NUMBER, to=normalized)
            # return {"success": True, "provider_used": "twilio"}
            logger.warning("SMS provider configured but send_flight_sms not implemented for Twilio")
            return {"success": False, "error": "SMS service is temporarily unavailable"}
        except Exception as e:
            logger.exception("SMS send failed: %s", e)
            return {"success": False, "error": "Unable to send details right now"}
    else:
        # No provider: controlled response, no fake delivery
        logger.info("SMS not sent (no provider): phone=%s, body_len=%d", _format_phone(phone)[:6] + "***", len(body))
        return {"success": False, "error": "SMS service is not configured"}


def send_flight_email(to_email: str, flight: dict[str, Any]) -> dict[str, Any]:
    """
    Send flight summary via email.
    Uses accounts.email infrastructure.
    Returns {success: bool, error?: str}.
    """
    email = (to_email or "").strip().lower()
    if not email:
        return {"success": False, "error": "Email is required"}
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        return {"success": False, "error": "Invalid email address"}

    try:
        from accounts.email.service import _is_email_configured, _send_templated
        from accounts.email.constants import BRAND_NAME

        if not _is_email_configured():
            logger.warning("Email not configured. Flight summary would not be sent.")
            return {"success": False, "error": "Email service is not configured"}

        flight_ctx = {**flight, **_normalize_flight_for_display(flight)}
        subject = f"Flight details: {flight_ctx.get('route_display', 'Your trip')}"
        ok = _send_templated(
            to_emails=email,
            subject=subject,
            html_template_name="main/emails/flight_summary.html",
            context={"flight": flight_ctx},
            text_template_name="main/emails/flight_summary.txt",
        )
        if ok:
            return {"success": True}
        return {"success": False, "error": "Unable to send email right now"}
    except Exception as e:
        logger.exception("Flight email send failed: %s", e)
        return {"success": False, "error": "Unable to send details right now"}
