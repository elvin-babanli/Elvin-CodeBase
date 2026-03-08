"""Create UserProfile when User is created. Send welcome email on register."""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import UserProfile
from .email import send_register_welcome

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
        if instance.email:
            try:
                send_register_welcome(
                    to_email=instance.email,
                    first_name=(instance.first_name or "").strip() or None,
                )
            except Exception as e:
                logger.warning("Welcome email send failed for %s: %s", instance.email, e)
