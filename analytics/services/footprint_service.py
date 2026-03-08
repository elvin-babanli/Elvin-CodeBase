"""
Footprint service. Aggregates all in-app data for a visitor/user.
Used for expand view and AI analysis.
"""
from django.db.models import Avg, Max, Count
from django.utils import timezone
from datetime import timedelta

from ..models import (
    VisitorProfile,
    VisitorSession,
    PageView,
    ClickEvent,
    AuthEvent,
    AdminNote,
)


ONLINE_MINUTES = 5


def get_full_footprint(visitor) -> dict:
    """Aggregate all footprint data for a visitor. Returns structured dict."""
    if not visitor:
        return {}

    sessions = list(visitor.sessions.all().order_by("-entry_at")[:50])
    page_views = list(
        PageView.objects.filter(session__visitor=visitor).order_by("-viewed_at")[:100]
    )
    click_events = list(
        ClickEvent.objects.filter(session__visitor=visitor).order_by("-created_at")[:100]
    )
    auth_events = list(visitor.auth_events.all().order_by("-created_at")[:50])
    admin_notes = [
        {
            "note": n.note,
            "created_by_email": n.created_by_email,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in AdminNote.objects.filter(visitor=visitor)[:20]
    ]

    user = visitor.user
    sec_profile = None
    if user:
        try:
            sec_profile = user.security_profile
        except Exception:
            pass

    # Identity
    identity = {
        "user_id": user.id if user else None,
        "visitor_id": visitor.id,
        "anonymous_id": visitor.anonymous_id[:16],
        "email": user.email if user else None,
        "first_name": user.first_name if user else None,
        "last_name": user.last_name if user else None,
        "registration_date": user.date_joined.isoformat() if user and user.date_joined else None,
        "last_login": user.last_login.isoformat() if user and user.last_login else None,
        "account_type": "registered" if visitor.user_id else "guest",
    }

    # Sessions summary
    avg_dur = (
        VisitorSession.objects.filter(visitor=visitor)
        .exclude(duration_seconds__isnull=True)
        .aggregate(a=Avg("duration_seconds"))["a"]
    )
    max_dur = (
        VisitorSession.objects.filter(visitor=visitor)
        .aggregate(m=Max("duration_seconds"))["m"]
    )
    cutoff = timezone.now() - timedelta(minutes=ONLINE_MINUTES)
    latest_sess = sessions[0] if sessions else None
    is_online = latest_sess and latest_sess.entry_at >= cutoff if latest_sess else False

    session_summary = {
        "total_session_count": visitor.total_sessions,
        "first_seen": visitor.first_seen.isoformat() if visitor.first_seen else None,
        "last_seen": visitor.last_seen.isoformat() if visitor.last_seen else None,
        "current_online_status": "online" if is_online else "offline",
        "average_session_duration_seconds": round(avg_dur, 1) if avg_dur else None,
        "longest_session_seconds": max_dur,
        "latest_session_duration_seconds": latest_sess.duration_seconds if latest_sess else None,
        "entry_page": latest_sess.landing_page if latest_sess else None,
        "exit_page": None,  # would need last page of last session
        "pages_per_session": round(visitor.total_page_views / visitor.total_sessions, 1)
        if visitor.total_sessions
        else 0,
    }
    if sessions and sessions[0].page_views.exists():
        pvs = list(sessions[0].page_views.all().order_by("-viewed_at")[:1])
        if pvs:
            session_summary["exit_page"] = pvs[0].path

    # Device & Browser (from latest sessions)
    devices = {}
    for s in sessions[:10]:
        if s.device_type:
            devices[s.device_type] = devices.get(s.device_type, 0) + 1
        if s.browser:
            devices[f"browser:{s.browser}"] = devices.get(f"browser:{s.browser}", 0) + 1
        if s.os:
            devices[f"os:{s.os}"] = devices.get(f"os:{s.os}", 0) + 1
    device_browser = {
        "device_type": latest_sess.device_type if latest_sess else None,
        "operating_system": latest_sess.os if latest_sess else None,
        "browser": latest_sess.browser if latest_sess else None,
        "user_agent": (latest_sess.user_agent[:200] if latest_sess and latest_sess.user_agent else None),
    }

    # Geo
    countries = {}
    for s in sessions:
        if s.country:
            countries[s.country] = countries.get(s.country, 0) + 1
    geo = {
        "ip_address": latest_sess.ip_address if latest_sess else None,
        "country": latest_sess.country if latest_sess else None,
        "city": latest_sess.city if latest_sess else None,
        "referrer": latest_sess.referrer[:200] if latest_sess and latest_sess.referrer else None,
        "countries_used": list(countries.keys()) if countries else [],
    }

    # Page activity
    all_paths = list(set(pv.path for pv in page_views))
    path_counts = {}
    for pv in page_views:
        path_counts[pv.path] = path_counts.get(pv.path, 0) + 1
    most_visited = max(path_counts.items(), key=lambda x: x[1]) if path_counts else (None, 0)
    page_activity = {
        "total_page_views": visitor.total_page_views,
        "all_visited_pages": all_paths[:30],
        "most_visited_page": most_visited[0],
        "most_visited_count": most_visited[1],
        "latest_visited_pages": [pv.path for pv in page_views[:10]],
    }

    # Click events
    event_types = {}
    for ce in click_events:
        event_types[ce.event_type] = event_types.get(ce.event_type, 0) + 1
    event_activity = {
        "click_events": [{"type": ce.event_type, "page": ce.page_path, "at": ce.created_at.isoformat()} for ce in click_events[:20]],
        "event_type_counts": event_types,
    }

    # Auth / Security
    login_success = sum(1 for e in auth_events if e.event_type == "login_success")
    login_failed = sum(1 for e in auth_events if e.event_type == "login_failed")
    auth_activity = {
        "login_attempts": login_success + login_failed,
        "failed_logins": login_failed,
        "successful_logins": login_success,
        "password_reset_requests": sum(1 for e in auth_events if e.event_type == "password_reset_request"),
        "suspicious_retry_count": visitor.suspicious_count,
        "admin_notes": admin_notes,
        "current_risk_score": float(visitor.risk_score) if visitor.risk_score else 0,
        "security_profile_failed_logins": sec_profile.failed_login_count if sec_profile else None,
    }

    # Analytics summary
    returning = visitor.total_sessions > 1
    active_days = len(set(s.entry_at.date().isoformat() for s in sessions)) if sessions else 0
    analytics_summary = {
        "returning_visitor": returning,
        "engagement_level": _engagement_level(visitor),
        "usage_frequency": visitor.total_sessions,
        "active_days": active_days,
        "recent_activity_summary": f"{visitor.total_page_views} page views, {visitor.total_sessions} sessions",
    }

    return {
        "identity": identity,
        "session_summary": session_summary,
        "device_browser": device_browser,
        "geo": geo,
        "page_activity": page_activity,
        "event_activity": event_activity,
        "auth_security": auth_activity,
        "analytics_summary": analytics_summary,
    }


def _engagement_level(visitor) -> str:
    pv = visitor.total_page_views
    sess = visitor.total_sessions
    if pv >= 50 or sess >= 10:
        return "high"
    if pv >= 10 or sess >= 3:
        return "medium"
    return "low"
