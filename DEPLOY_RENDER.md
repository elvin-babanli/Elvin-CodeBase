# Render Deploy — Portfolio Site

## Build Command

```
pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput
```

## Start Command

```
gunicorn core.wsgi:application --bind 0.0.0.0:$PORT
```

## Environment Variables

| Key | Value |
|-----|-------|
| `SECRET_KEY` | Random 50+ characters |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `elvin-babanli.com,www.elvin-babanli.com,.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://elvin-babanli.com,https://www.elvin-babanli.com` |

### PostgreSQL

- Create PostgreSQL instance
- Connect to web service → `DATABASE_URL` is set automatically

### Email (B Labs)

| Key | Value | Required |
|-----|-------|----------|
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` | No (auto when SMTP set) |
| `EMAIL_HOST` | `smtp.gmail.com` | Yes |
| `EMAIL_PORT` | `587` | No |
| `EMAIL_USE_TLS` | `True` | No |
| `EMAIL_HOST_USER` | `updates@elvin-babanli.com` | Yes |
| `EMAIL_HOST_PASSWORD` | Google Workspace app password | Yes |
| `DEFAULT_FROM_EMAIL` | `B Labs <updates@elvin-babanli.com>` | No |
| `SERVER_EMAIL` | `updates@elvin-babanli.com` | No |

See `EMAIL_SETUP.md` for details.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Blank page / site not loading | Use only gunicorn in Start Command; run migrate in Build |
| auth_user table missing | Add `python manage.py migrate --noinput` to Build Command |
| Verification code not received | Set `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`; see `EMAIL_SETUP.md` |
| 500 on email send | Check logs; ensure app password is valid and 2FA is enabled |
