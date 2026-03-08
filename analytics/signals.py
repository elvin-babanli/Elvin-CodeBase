"""Track auth events via Django signals."""
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver

from .services.tracker import track_auth_event


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    if request:
        track_auth_event(request, "login_success", user=user, success=True)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if request and user:
        track_auth_event(request, "logout", user=user, success=True)
