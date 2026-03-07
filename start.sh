#!/usr/bin/env bash
# Render start: migrate then gunicorn. Ensures auth_user and all tables exist.
set -o errexit
python manage.py migrate --noinput
exec gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-10000}
