"""Management command: send daily analytics report email."""
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
from django.conf import settings


class Command(BaseCommand):
    help = "Send daily analytics report to admin email"

    def handle(self, *args, **options):
        to_email = getattr(settings, "ADMIN_REPORT_EMAIL", "elvinbabanli0@gmail.com")
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        start = timezone.make_aware(datetime.combine(yesterday, datetime.min.time()))
        end = timezone.make_aware(datetime.combine(today, datetime.min.time()))

        visitors = VisitorProfile.objects.filter(last_seen__gte=start, last_seen__lt=end).count()
        sessions = VisitorSession.objects.filter(entry_at__gte=start, entry_at__lt=end).count()
        views = PageView.objects.filter(viewed_at__gte=start, viewed_at__lt=end).count()
        new_regs = AuthEvent.objects.filter(event_type="register_success", created_at__gte=start, created_at__lt=end).count()
        failed_logins = AuthEvent.objects.filter(event_type="login_failed", created_at__gte=start, created_at__lt=end).count()

        body = f"""
Daily Analytics Report — {yesterday}

Visitors: {visitors}
Sessions: {sessions}
Page views: {views}
New registrations: {new_regs}
Failed login attempts: {failed_logins}

—
B Labs Analytics
"""
        try:
            from django.core.mail import send_mail
            send_mail(
                subject=f"Daily Report — {yesterday}",
                message=body.strip(),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                fail_silently=False,
            )
            ReportLog.objects.create(
                report_type="daily",
                sent_to=to_email,
                date_range=str(yesterday),
                success=True,
            )
            self.stdout.write(self.style.SUCCESS(f"Report sent to {to_email}"))
        except Exception as e:
            ReportLog.objects.create(report_type="daily", sent_to=to_email, date_range=str(yesterday), success=False)
            self.stdout.write(self.style.ERROR(f"Failed: {e}"))
