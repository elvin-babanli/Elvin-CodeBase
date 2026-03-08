# Email Setup — B Labs

All system emails (welcome, OTP, forgot password, updates) are sent from:

- **Sender:** B Labs &lt;updates@elvin-babanli.com&gt;
- **Domain:** elvin-babanli.com
- **Workspace:** Google Workspace

## 1. Google Workspace App Password

1. Sign in to [Google Admin](https://admin.google.com) (or the workspace account)
2. Security → 2-Step Verification (must be enabled)
3. App passwords → Generate
4. App: Mail, Device: Other → name it "Django B Labs"
5. Copy the 16-character password

## 2. Environment Variables

Set these in Render Dashboard or `.env`:

| Key | Value | Required |
|-----|-------|----------|
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` | No (auto when SMTP configured) |
| `EMAIL_HOST` | `smtp.gmail.com` | Yes (for SMTP) |
| `EMAIL_PORT` | `587` | No (default) |
| `EMAIL_USE_TLS` | `True` | No (default) |
| `EMAIL_HOST_USER` | `updates@elvin-babanli.com` | Yes |
| `EMAIL_HOST_PASSWORD` | App password (16 chars) | Yes |
| `DEFAULT_FROM_EMAIL` | `B Labs <updates@elvin-babanli.com>` | No (has default) |
| `SERVER_EMAIL` | `updates@elvin-babanli.com` | No (has default) |

Legacy: `GMAIL_APP_PASSWORD` can be used as fallback for `EMAIL_HOST_PASSWORD` if set.

## 3. Example `.env` (Production)

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=updates@elvin-babanli.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
DEFAULT_FROM_EMAIL=B Labs <updates@elvin-babanli.com>
SERVER_EMAIL=updates@elvin-babanli.com
```

## 4. Local Development

If env vars are not set, emails are printed to the console (no real delivery). Check terminal output for verification codes and welcome messages.

## 5. Security

- Never commit passwords or app passwords
- Use only environment variables
- `EMAIL_HOST_USER` and the address in `DEFAULT_FROM_EMAIL` must match for SMTP auth
