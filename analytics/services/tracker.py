"""
Analytics tracker service. Records visits, page views, clicks, auth events.
Lightweight to avoid performance impact.
"""
import logging
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from ..models import (
    VisitorProfile,
    VisitorSession,
    PageView,
    ClickEvent,
    AuthEvent,
)
from ..utils import parse_user_agent, get_client_ip, generate_visitor_id, get_geo_from_ip

logger = logging.getLogger(__name__)

# Paths to skip tracking (admin, static, api)
SKIP_PATHS = ("/admin/", "/static/", "/media/", "/analytics/", "/admin-dashboard/", "/favicon.ico", "/robots.txt")

# Minutes of inactivity to consider "online"
ONLINE_MINUTES = 5


def _should_track(path: str) -> bool:
    return not any(path.startswith(p) for p in SKIP_PATHS)


def get_or_create_visitor(request):
    """Get or create visitor profile. Returns (visitor, created)."""
    sid = request.session.session_key
    if not sid:
        return None, False

    visitor_id = request.session.get("analytics_visitor_id")
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        # Prefer visitor linked to user
        v = VisitorProfile.objects.filter(user=user).first()
        if v:
            v.last_seen = timezone.now()
            v.save(update_fields=["last_seen"])
            return v, False
        if visitor_id:
            v = VisitorProfile.objects.filter(anonymous_id=visitor_id).first()
            if v:
                v.user = user
                v.last_seen = timezone.now()
                v.save(update_fields=["user", "last_seen"])
                return v, False

    if visitor_id:
        v = VisitorProfile.objects.filter(anonymous_id=visitor_id).first()
        if v:
            v.last_seen = timezone.now()
            v.save(update_fields=["last_seen"])
            return v, False

    new_id = generate_visitor_id()
    request.session["analytics_visitor_id"] = new_id
    v = VisitorProfile.objects.create(
        anonymous_id=new_id,
        user=user if (user and user.is_authenticated) else None,
    )
    return v, True


def get_or_create_session(request, visitor):
    """Get or create session for this request."""
    if not visitor:
        return None
    sk = request.session.session_key
    if not sk:
        return None

    sess = VisitorSession.objects.filter(session_key=sk).first()
    if sess:
        return sess

    ip = get_client_ip(request)
    ua = request.META.get("HTTP_USER_AGENT", "")
    parsed = parse_user_agent(ua)
    referrer = request.META.get("HTTP_REFERER", "")[:512]
    path = request.path or "/"
    country, city = get_geo_from_ip(ip) if ip else ("", "")

    sess = VisitorSession.objects.create(
        visitor=visitor,
        session_key=sk,
        ip_address=ip if ip and ip not in ("127.0.0.1", "::1") else None,
        user_agent=ua[:500],
        browser=parsed["browser"],
        os=parsed["os"],
        device_type=parsed["device_type"],
        country=country,
        city=city,
        referrer=referrer,
        landing_page=path,
    )
    visitor.total_sessions += 1
    visitor.save(update_fields=["total_sessions"])
    return sess


def track_page_view(request, path=None, title=""):
    """Record a page view."""
    if not _should_track(path or request.path):
        return
    try:
        visitor, _ = get_or_create_visitor(request)
        if not visitor:
            return
        sess = get_or_create_session(request, visitor)
        if not sess:
            return
        PageView.objects.create(
            session=sess,
            path=path or request.path,
            title=title[:256],
            referrer=request.META.get("HTTP_REFERER", "")[:512],
        )
        sess.page_views_count += 1
        sess.save(update_fields=["page_views_count"])
        visitor.total_page_views += 1
        visitor.request_count += 1
        visitor.save(update_fields=["total_page_views", "request_count"])
    except Exception as e:
        logger.warning("Analytics track_page_view failed: %s", e)


def track_click(request, event_type, element_id="", element_class="", target_url="", page_path=""):
    """Record a click event."""
    try:
        visitor, _ = get_or_create_visitor(request)
        if not visitor:
            return
        sess = get_or_create_session(request, visitor)
        if not sess:
            return
        ClickEvent.objects.create(
            session=sess,
            event_type=event_type,
            element_id=element_id[:128],
            element_class=element_class[:256],
            target_url=target_url[:512],
            page_path=page_path[:512],
        )
    except Exception as e:
        logger.warning("Analytics track_click failed: %s", e)


def track_auth_event(request, event_type, user=None, email_attempted="", success=False):
    """Record auth event (login, register, etc)."""
    try:
        visitor, _ = get_or_create_visitor(request)
        sess = VisitorSession.objects.filter(session_key=request.session.session_key).first()
        ip = get_client_ip(request)
        AuthEvent.objects.create(
            visitor=visitor,
            session=sess,
            user=user,
            event_type=event_type,
            ip_address=ip if ip and ip != "127.0.0.1" else None,
            email_attempted=email_attempted[:254],
            success=success,
        )
        if event_type == "login_failed" and visitor:
            visitor.suspicious_count += 1
            visitor.save(update_fields=["suspicious_count"])
    except Exception as e:
        logger.warning("Analytics track_auth_event failed: %s", e)


def update_session_exit(session_key):
    """Update session exit time and duration."""
    try:
        sess = VisitorSession.objects.filter(session_key=session_key).first()
        if sess:
            sess.exit_at = timezone.now()
            if sess.entry_at:
                delta = sess.exit_at - sess.entry_at
                sess.duration_seconds = int(delta.total_seconds())
            sess.save(update_fields=["exit_at", "duration_seconds"])
    except Exception as e:
        logger.warning("Analytics update_session_exit failed: %s", e)


class AnalyticsMiddleware(MiddlewareMixin):
    """Middleware to track page views and ensure visitor/session exist."""

    def process_request(self, request):
        request._analytics_tracked = False

    def process_response(self, request, response):
        if not hasattr(request, "_analytics_tracked") or request._analytics_tracked:
            return response
        if _should_track(request.path):
            try:
                track_page_view(request)
                request._analytics_tracked = True
            except Exception:
                pass
        return response
