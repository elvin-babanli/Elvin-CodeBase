"""Management command: send weekly analytics report email."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime

from analytics.models import (
    VisitorProfile,
    VisitorSession,
    PageView,
    AuthEvent,
    ReportLog,
)
from django.db.models import Count
from django.conf import settings


class Command(BaseCommand):
    help = "Send weekly analytics report to admin email"

    def handle(self, *args, **options):
        to_email = getattr(settings, "ADMIN_REPORT_EMAIL", "elvinbabanli0@gmail.com")
        now = timezone.now()
        week_end = now.date()
        week_start = week_end - timedelta(days=7)
        start = timezone.make_aware(datetime.combine(week_start, datetime.min.time()))
        end = timezone.make_aware(datetime.combine(week_end, datetime.min.time()))

        visitors = VisitorProfile.objects.filter(last_seen__gte=start, last_seen__lt=end).count()
        sessions = VisitorSession.objects.filter(entry_at__gte=start, entry_at__lt=end).count()
        views = PageView.objects.filter(viewed_at__gte=start, viewed_at__lt=end).count()
        new_regs = AuthEvent.objects.filter(
            event_type="register_success", created_at__gte=start, created_at__lt=end
        ).count()
        failed_logins = AuthEvent.objects.filter(
            event_type="login_failed", created_at__gte=start, created_at__lt=end
        ).count()

        top_pages = list(
            PageView.objects.filter(viewed_at__gte=start, viewed_at__lt=end)
            .values("path")
            .annotate(c=Count("id"))
            .order_by("-c")[:5]
        )
        top_countries = list(
            VisitorSession.objects.filter(entry_at__gte=start, entry_at__lt=end)
            .exclude(country="")
            .values("country")
            .annotate(c=Count("id"))
            .order_by("-c")[:5]
        )

        pages_str = "\n".join(f"  - {p['path']}: {p['c']}" for p in top_pages) or "  (none)"
        countries_str = "\n".join(f"  - {c['country']}: {c['c']}" for c in top_countries) or "  (none)"

        body = f"""
Weekly Analytics Report — {week_start} to {week_end}

Visitors: {visitors}
Sessions: {sessions}
Page views: {views}
New registrations: {new_regs}
Failed login attempts: {failed_logins}

Top pages:
{pages_str}

Top countries:
{countries_str}

—
B Labs Analytics
"""
        try:
            from django.core.mail import send_mail

            send_mail(
                subject=f"Weekly Report — {week_start} to {week_end}",
                message=body.strip(),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                fail_silently=False,
            )
            ReportLog.objects.create(
                report_type="weekly",
                sent_to=to_email,
                date_range=f"{week_start} to {week_end}",
                success=True,
            )
            self.stdout.write(self.style.SUCCESS(f"Weekly report sent to {to_email}"))
        except Exception as e:
            ReportLog.objects.create(
                report_type="weekly", sent_to=to_email, date_range=f"{week_start} to {week_end}", success=False
            )
            self.stdout.write(self.style.ERROR(f"Failed: {e}"))
