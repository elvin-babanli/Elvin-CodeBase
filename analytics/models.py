"""
Analytics models. Production-ready. All data in DB.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class VisitorProfile(models.Model):
    """Visitor profile. Registered users link via user FK."""
    anonymous_id = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analytics_visitors",
    )
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    total_sessions = models.PositiveIntegerField(default=0)
    total_page_views = models.PositiveIntegerField(default=0)
    request_count = models.PositiveIntegerField(default=0)
    risk_score = models.FloatField(default=0.0, blank=True)
    suspicious_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "analytics_visitor_profiles"
        ordering = ["-last_seen"]

    @property
    def is_registered(self):
        return self.user_id is not None


class VisitorSession(models.Model):
    """Single browsing session."""
    visitor = models.ForeignKey(
        VisitorProfile,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    session_key = models.CharField(max_length=64, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    browser = models.CharField(max_length=64, blank=True)
    os = models.CharField(max_length=64, blank=True)
    device_type = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=64, blank=True)
    city = models.CharField(max_length=128, blank=True)
    referrer = models.URLField(max_length=512, blank=True)
    landing_page = models.CharField(max_length=512, blank=True)
    entry_at = models.DateTimeField(auto_now_add=True)
    exit_at = models.DateTimeField(null=True, blank=True)
    page_views_count = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "analytics_visitor_sessions"
        ordering = ["-entry_at"]


class PageView(models.Model):
    """Page view record."""
    session = models.ForeignKey(
        VisitorSession,
        on_delete=models.CASCADE,
        related_name="page_views",
    )
    path = models.CharField(max_length=512, db_index=True)
    title = models.CharField(max_length=256, blank=True)
    referrer = models.CharField(max_length=512, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analytics_page_views"
        ordering = ["-viewed_at"]


class ClickEvent(models.Model):
    """Click/interaction event."""
    session = models.ForeignKey(
        VisitorSession,
        on_delete=models.CASCADE,
        related_name="click_events",
    )
    event_type = models.CharField(max_length=64)
    element_id = models.CharField(max_length=128, blank=True)
    element_class = models.CharField(max_length=256, blank=True)
    target_url = models.CharField(max_length=512, blank=True)
    page_path = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analytics_click_events"
        ordering = ["-created_at"]


class AuthEvent(models.Model):
    """Login, register, logout events."""
    EVENT_TYPES = [
        ("login_success", "Login Success"),
        ("login_failed", "Login Failed"),
        ("register_success", "Register Success"),
        ("register_failed", "Register Failed"),
        ("logout", "Logout"),
        ("password_reset_request", "Password Reset Request"),
        ("password_reset_success", "Password Reset Success"),
    ]
    visitor = models.ForeignKey(
        VisitorProfile,
        on_delete=models.CASCADE,
        related_name="auth_events",
        null=True,
        blank=True,
    )
    session = models.ForeignKey(
        VisitorSession,
        on_delete=models.CASCADE,
        related_name="auth_events",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analytics_auth_events",
    )
    event_type = models.CharField(max_length=32, choices=EVENT_TYPES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    email_attempted = models.EmailField(blank=True)
    success = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analytics_auth_events"
        ordering = ["-created_at"]


class DailyTraffic(models.Model):
    """Daily aggregate stats."""
    date = models.DateField(unique=True, db_index=True)
    total_visitors = models.PositiveIntegerField(default=0)
    total_sessions = models.PositiveIntegerField(default=0)
    total_page_views = models.PositiveIntegerField(default=0)
    registered_visitors = models.PositiveIntegerField(default=0)
    guest_visitors = models.PositiveIntegerField(default=0)
    new_registrations = models.PositiveIntegerField(default=0)
    failed_logins = models.PositiveIntegerField(default=0)
    top_pages = models.JSONField(default=dict, blank=True)
    top_countries = models.JSONField(default=dict, blank=True)
    top_browsers = models.JSONField(default=dict, blank=True)
    top_devices = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "analytics_daily_traffic"
        ordering = ["-date"]
        verbose_name = "Daily Traffic"


class WeeklyTraffic(models.Model):
    """Weekly aggregate stats."""
    week_start = models.DateField(unique=True, db_index=True)
    total_visitors = models.PositiveIntegerField(default=0)
    total_sessions = models.PositiveIntegerField(default=0)
    total_page_views = models.PositiveIntegerField(default=0)
    new_registrations = models.PositiveIntegerField(default=0)
    failed_logins = models.PositiveIntegerField(default=0)
    top_pages = models.JSONField(default=dict, blank=True)
    top_countries = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "analytics_weekly_traffic"
        ordering = ["-week_start"]


class UserSecurityProfile(models.Model):
    """Security profile for users."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_profile",
    )
    risk_score = models.FloatField(default=0.0)
    failed_login_count = models.PositiveIntegerField(default=0)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "analytics_user_security_profile"


class AdminNote(models.Model):
    """Admin notes on visitor or user."""
    visitor = models.ForeignKey(
        VisitorProfile,
        on_delete=models.CASCADE,
        related_name="note_records",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="analytics_admin_notes",
        null=True,
        blank=True,
    )
    note = models.TextField()
    created_by_email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analytics_admin_notes"
        ordering = ["-created_at"]


class ReportLog(models.Model):
    report_type = models.CharField(max_length=16, choices=[("daily", "Daily"), ("weekly", "Weekly")])
    sent_to = models.EmailField()
    sent_at = models.DateTimeField(auto_now_add=True)
    date_range = models.CharField(max_length=64, blank=True)
    success = models.BooleanField(default=True)

    class Meta:
        db_table = "analytics_report_logs"
        ordering = ["-sent_at"]


class AIAnalysisResult(models.Model):
    """AI analysis result. Stores structured analysis + footprint snapshot."""
    visitor = models.ForeignKey(
        VisitorProfile,
        on_delete=models.CASCADE,
        related_name="ai_results",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="analytics_ai_results",
        null=True,
        blank=True,
    )
    summary = models.TextField(blank=True)
    risk_assessment = models.TextField(blank=True)
    behavior_notes = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    risk_score = models.FloatField(null=True, blank=True, help_text="0-100 from AI")
    raw_response = models.JSONField(default=dict, blank=True)
    footprint_snapshot = models.JSONField(default=dict, blank=True, help_text="Data sent to AI")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analytics_ai_analysis_results"
        ordering = ["-created_at"]
