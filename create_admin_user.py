#!/usr/bin/env python
"""Create admin user and optionally auto-login URL."""
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.contrib.auth import get_user_model, login
User = get_user_model()

email = "elvinbabanli0@gmail.com"
password = "Elvin2002Natig2015@"

if User.objects.filter(email__iexact=email).exists():
    u = User.objects.get(email__iexact=email)
    u.set_password(password)
    u.save()
    print("Password updated for", email)
else:
    u = User.objects.create_user(
        username=email.split("@")[0],
        email=email,
        password=password,
        first_name="Elvin",
        last_name="Babanli",
    )
    print("User created:", email)
print("Done. Login: elvinbabanli0@gmail.com / Elvin2002Natig2015@")
