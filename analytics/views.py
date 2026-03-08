"""
Admin dashboard views. Each section = separate page.
Protected by AdminDashboardMiddleware.
"""
import csv
import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.contrib.auth.models import User
from datetime import timedelta

from .models import (
    VisitorProfile,
    VisitorSession,
    PageView,
    ClickEvent,
    AuthEvent,
    DailyTraffic,
    WeeklyTraffic,
    AdminNote,
    AIAnalysisResult,
    ReportLog,
)

ONLINE_MINUTES = 5


def _nav_pages():
    return [
        {"url": "analytics:dashboard", "label": "Overview"},
        {"url": "analytics:live", "label": "Live"},
        {"url": "analytics:users", "label": "Users"},
        {"url": "analytics:guests", "label": "Guests"},
        {"url": "analytics:traffic", "label": "Traffic"},
        {"url": "analytics:events", "label": "Events"},
        {"url": "analytics:devices", "label": "Devices"},
        {"url": "analytics:countries", "label": "Countries"},
        {"url": "analytics:ai_analysis", "label": "AI Analysis"},
        {"url": "analytics:reports", "label": "Reports"},
        {"url": "analytics:user_management", "label": "User Management"},
    ]


def _base_ctx(active=""):
    now = timezone.now()
    cutoff = now - timedelta(minutes=ONLINE_MINUTES)
    online_count = VisitorSession.objects.filter(entry_at__gte=cutoff).values("visitor").distinct().count()
    return {
        "nav_pages": _nav_pages(),
        "active": active,
        "online_count": online_count,
        "total_visitors": VisitorProfile.objects.count(),
        "registered_count": VisitorProfile.objects.filter(user__isnull=False).count(),
        "guest_count": VisitorProfile.objects.filter(user__isnull=True).count(),
        "total_page_views": PageView.objects.count(),
    }


def dashboard_overview(request):
    ctx = _base_ctx("Overview")
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    ctx["today_visitors"] = VisitorProfile.objects.filter(last_seen__gte=today_start).count()
    ctx["today_views"] = PageView.objects.filter(viewed_at__gte=today_start).count()
    ctx["week_visitors"] = VisitorProfile.objects.filter(last_seen__gte=week_start).count()
    top_pages = list(PageView.objects.values("path").annotate(c=Count("id")).order_by("-c")[:10])
    top_countries = list(VisitorSession.objects.exclude(country="").values("country").annotate(c=Count("id")).order_by("-c")[:8])
    ctx["top_pages"] = top_pages
    ctx["top_countries"] = top_countries
    ctx["top_pages_views"] = sum(p["c"] for p in top_pages)
    ctx["top_countries_sessions"] = sum(c["c"] for c in top_countries)
    return render(request, "analytics/pages/overview.html", ctx)


def dashboard_live(request):
    ctx = _base_ctx("Live")
    cutoff = timezone.now() - timedelta(minutes=ONLINE_MINUTES)
    ctx["sessions"] = VisitorSession.objects.filter(entry_at__gte=cutoff).select_related("visitor").order_by("-entry_at")[:100]
    return render(request, "analytics/pages/live.html", ctx)


def dashboard_users(request):
    ctx = _base_ctx("Users")
    ctx["users"] = User.objects.all().order_by("-date_joined")[:200]
    return render(request, "analytics/pages/users.html", ctx)


def dashboard_guests(request):
    ctx = _base_ctx("Guests")
    ctx["guests"] = VisitorProfile.objects.filter(user__isnull=True).order_by("-last_seen")[:200]
    return render(request, "analytics/pages/guests.html", ctx)


def dashboard_traffic(request):
    ctx = _base_ctx("Traffic")
    now = timezone.now()
    week_start = now - timedelta(days=7)
    ctx["daily_data"] = list(
        PageView.objects.filter(viewed_at__gte=week_start)
        .annotate(day=TruncDate("viewed_at"))
        .values("day")
        .annotate(c=Count("id"))
        .order_by("day")
    )
    ctx["top_pages"] = list(PageView.objects.values("path").annotate(c=Count("id")).order_by("-c")[:15])
    ctx["top_countries"] = list(VisitorSession.objects.exclude(country="").values("country").annotate(c=Count("id")).order_by("-c")[:10])
    ctx["top_devices"] = list(VisitorSession.objects.exclude(device_type="").values("device_type").annotate(c=Count("id")).order_by("-c")[:10])
    ctx["top_browsers"] = list(VisitorSession.objects.exclude(browser="").values("browser").annotate(c=Count("id")).order_by("-c")[:10])
    return render(request, "analytics/pages/traffic.html", ctx)


def dashboard_events(request):
    ctx = _base_ctx("Events")
    ctx["auth_events"] = AuthEvent.objects.all().order_by("-created_at")[:100]
    ctx["click_events"] = ClickEvent.objects.select_related("session").order_by("-created_at")[:100]
    return render(request, "analytics/pages/events.html", ctx)


def dashboard_devices(request):
    ctx = _base_ctx("Devices")
    ctx["devices"] = list(VisitorSession.objects.exclude(device_type="").values("device_type").annotate(c=Count("id")).order_by("-c"))
    ctx["browsers"] = list(VisitorSession.objects.exclude(browser="").values("browser").annotate(c=Count("id")).order_by("-c"))
    ctx["os_list"] = list(VisitorSession.objects.exclude(os="").values("os").annotate(c=Count("id")).order_by("-c"))
    return render(request, "analytics/pages/devices.html", ctx)


def dashboard_countries(request):
    ctx = _base_ctx("Countries")
    ctx["countries"] = list(VisitorSession.objects.exclude(country="").values("country").annotate(c=Count("id")).order_by("-c"))
    return render(request, "analytics/pages/countries.html", ctx)


def dashboard_ai_analysis(request):
    ctx = _base_ctx("AI Analysis")
    ctx["users"] = User.objects.all()[:100]
    ctx["guests"] = VisitorProfile.objects.filter(user__isnull=True).order_by("-last_seen")[:100]
    return render(request, "analytics/pages/ai_analysis.html", ctx)


def dashboard_reports(request):
    ctx = _base_ctx("Reports")
    ctx["report_logs"] = ReportLog.objects.all().order_by("-sent_at")[:50]
    return render(request, "analytics/pages/reports.html", ctx)


def dashboard_user_management(request):
    ctx = _base_ctx("User Management")
    ctx["users"] = User.objects.all().order_by("-date_joined")
    return render(request, "analytics/pages/user_management.html", ctx)


# APIs
@require_GET
def api_live(request):
    cutoff = timezone.now() - timedelta(minutes=ONLINE_MINUTES)
    sessions = VisitorSession.objects.filter(entry_at__gte=cutoff).select_related("visitor").order_by("-entry_at")[:50]
    data = [{"id": s.id, "visitor": s.visitor.anonymous_id[:12], "path": s.landing_page or "/", "country": s.country or "—", "device": s.device_type or "—", "browser": s.browser or "—"} for s in sessions]
    return JsonResponse({"ok": True, "visitors": data})


@require_GET
def api_traffic(request):
    from django.db.models.functions import TruncDate
    days = int(request.GET.get("days", 7))
    start = timezone.now() - timedelta(days=days)
    rows = list(PageView.objects.filter(viewed_at__gte=start).annotate(day=TruncDate("viewed_at")).values("day").annotate(c=Count("id")).order_by("day"))
    return JsonResponse({"ok": True, "data": [{"date": str(r["day"]), "count": r["c"]} for r in rows]})


@require_POST
def api_click(request):
    from .services.tracker import track_click
    track_click(request, request.POST.get("event_type", "unknown"), request.POST.get("element_id", ""), request.POST.get("element_class", ""), request.POST.get("target_url", ""), request.POST.get("page_path", request.path))
    return JsonResponse({"ok": True})


@require_GET
def api_footprint(request):
    """Get full footprint for user or visitor. Used for expand view."""
    from .services.footprint_service import get_full_footprint

    vid = request.GET.get("visitor_id")
    uid = request.GET.get("user_id")
    v = None
    if vid:
        v = VisitorProfile.objects.filter(anonymous_id=vid).first()
    elif uid:
        v = VisitorProfile.objects.filter(user_id=uid).first()
    if not v:
        return JsonResponse({"ok": False, "error": "Not found"}, status=404)
    footprint = get_full_footprint(v)
    return JsonResponse({"ok": True, "footprint": footprint})


@require_GET
def api_past_analyses(request):
    """Get past AI analyses for user or visitor."""
    vid = request.GET.get("visitor_id")
    uid = request.GET.get("user_id")
    v = None
    if vid:
        v = VisitorProfile.objects.filter(anonymous_id=vid).first()
    elif uid:
        v = VisitorProfile.objects.filter(user_id=uid).first()
    if not v:
        return JsonResponse({"ok": False, "error": "Not found"}, status=404)
    results = AIAnalysisResult.objects.filter(visitor=v).order_by("-created_at")[:10]
    data = [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "risk_score": r.risk_score,
            "summary": r.summary,
            "raw_response": r.raw_response,
        }
        for r in results
    ]
    return JsonResponse({"ok": True, "analyses": data})


@require_POST
def api_analyze(request):
    from .services.footprint_service import get_full_footprint
    from .services.ai_service import analyze_footprint

    vid = request.POST.get("visitor_id")
    uid = request.POST.get("user_id")
    v = None
    if vid:
        v = VisitorProfile.objects.filter(anonymous_id=vid).first()
    elif uid:
        v = VisitorProfile.objects.filter(user_id=uid).first()
    if not v:
        return JsonResponse({"ok": False, "error": "Not found"}, status=404)

    footprint = get_full_footprint(v)
    result = analyze_footprint(footprint)
    if "error" in result:
        return JsonResponse({"ok": False, "error": result["error"]}, status=400)

    summary = result.get("behavior_summary", result.get("summary", ""))
    risk_score = result.get("risk_score_0_to_100")
    if risk_score is not None:
        try:
            risk_score = float(risk_score)
        except (TypeError, ValueError):
            risk_score = None

    AIAnalysisResult.objects.create(
        visitor=v,
        user=v.user,
        summary=summary,
        risk_assessment=result.get("risk_reasoning", result.get("risk_assessment", "")),
        behavior_notes=result.get("suspicious_activity_assessment", result.get("behavior_notes", "")),
        recommendations=result.get("recommended_admin_action", result.get("recommendations", "")),
        risk_score=risk_score,
        raw_response=result,
        footprint_snapshot=footprint,
    )
    return JsonResponse({"ok": True, "result": result})


ADMIN_EMAIL = "elvinbabanli0@gmail.com"


@require_POST
def api_user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.email and user.email.lower() == ADMIN_EMAIL.lower():
        return JsonResponse({"ok": False, "message": "Cannot delete admin user"}, status=400)
    email = user.email
    user.delete()
    return JsonResponse({"ok": True, "message": f"User {email} deleted"})


@require_POST
def api_auth_event_delete(request, pk):
    e = get_object_or_404(AuthEvent, pk=pk)
    e.delete()
    return JsonResponse({"ok": True, "message": "Auth event deleted"})


@require_POST
def api_click_event_delete(request, pk):
    e = get_object_or_404(ClickEvent, pk=pk)
    e.delete()
    return JsonResponse({"ok": True, "message": "Click event deleted"})


def _export_filters(request):
    """Build queryset filters from request params."""
    from django.db.models import Q
    qs = VisitorSession.objects.all()
    if request.GET.get("country"):
        qs = qs.filter(country__icontains=request.GET["country"])
    if request.GET.get("device"):
        qs = qs.filter(device_type__icontains=request.GET["device"])
    if request.GET.get("browser"):
        qs = qs.filter(browser__icontains=request.GET["browser"])
    days = request.GET.get("days", "")
    if days.isdigit():
        start = timezone.now() - timedelta(days=int(days))
        qs = qs.filter(entry_at__gte=start)
    return qs


@require_GET
def api_export_csv(request):
    """Export sessions to CSV. Admin only."""
    qs = _export_filters(request)[:5000]
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="analytics-sessions.csv"'
    w = csv.writer(response)
    w.writerow(["id", "visitor_id", "country", "city", "device", "browser", "os", "landing_page", "entry_at"])
    for s in qs.select_related("visitor"):
        w.writerow([
            s.id, s.visitor.anonymous_id[:16], s.country or "", s.city or "",
            s.device_type or "", s.browser or "", s.os or "", s.landing_page or "", str(s.entry_at),
        ])
    return response


@require_GET
def api_export_json(request):
    """Export sessions to JSON. Admin only."""
    qs = _export_filters(request)[:5000]
    data = []
    for s in qs.select_related("visitor"):
        data.append({
            "id": s.id,
            "visitor_id": s.visitor.anonymous_id[:16],
            "country": s.country or "",
            "city": s.city or "",
            "device": s.device_type or "",
            "browser": s.browser or "",
            "os": s.os or "",
            "landing_page": s.landing_page or "",
            "entry_at": s.entry_at.isoformat() if s.entry_at else "",
        })
    return HttpResponse(json.dumps(data, indent=2), content_type="application/json")
