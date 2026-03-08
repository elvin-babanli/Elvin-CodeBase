"""Analytics utilities: user agent parsing, geo lookup."""
import re
import uuid
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def parse_user_agent(ua_string: str) -> dict:
    """Parse user agent into browser, os, device_type."""
    ua = (ua_string or "").lower()
    browser = "Unknown"
    os_name = "Unknown"
    device_type = "desktop"

    # Device
    if "mobile" in ua and "tablet" not in ua:
        device_type = "mobile"
    elif "tablet" in ua or "ipad" in ua:
        device_type = "tablet"

    # OS
    if "windows" in ua:
        os_name = "Windows"
    elif "mac os" in ua or "macintosh" in ua:
        os_name = "macOS"
    elif "linux" in ua:
        os_name = "Linux"
    elif "android" in ua:
        os_name = "Android"
    elif "iphone" in ua or "ipad" in ua:
        os_name = "iOS"

    # Browser
    if "edg/" in ua or "edge/" in ua:
        browser = "Edge"
    elif "opr/" in ua or "opera" in ua:
        browser = "Opera"
    elif "chrome" in ua and "chromium" not in ua:
        browser = "Chrome"
    elif "firefox" in ua or "fxios" in ua:
        browser = "Firefox"
    elif "safari" in ua and "chrome" not in ua:
        browser = "Safari"

    return {"browser": browser, "os": os_name, "device_type": device_type}


def get_client_ip(request) -> str:
    """Get client IP from request."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def generate_visitor_id() -> str:
    return uuid.uuid4().hex


def extract_domain(referrer: str) -> str:
    try:
        parsed = urlparse(referrer)
        return parsed.netloc or ""
    except Exception:
        return ""


def get_geo_from_ip(ip: str) -> tuple:
    """Return (country, city) from IP. Uses ip-api.com. Returns ("", "") on fail."""
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        return "", ""
    try:
        import requests
        r = requests.get(f"http://ip-api.com/json/{ip}?fields=country,city", timeout=1)
        if r.status_code == 200:
            d = r.json()
            return (d.get("country") or "", (d.get("city") or ""))
    except Exception:
        pass
    return "", ""
