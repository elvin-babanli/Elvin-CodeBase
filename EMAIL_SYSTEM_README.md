# B Labs Email System

Single, production-ready email infrastructure for B Labs. All system emails use:

- **From:** B Labs \<updates@elvin-babanli.com\>
- **Brand:** B Labs
- **Domain:** elvin-babanli.com

## Architecture

```
accounts/email/
├── constants.py   # Brand, domain, get_from_email()
├── service.py     # send_register_welcome, send_otp_code, send_password_reset_code, send_update_announcement
└── __init__.py    # Public API

accounts/templates/accounts/emails/
├── welcome.html / welcome.txt   # Post-registration
├── otp_code.html / otp_code.txt # 6-digit verification (password reset, etc.)
└── update.html                  # Future announcements
```

## Email Flows

| Flow | Trigger | Function |
|------|---------|----------|
| Register welcome | User signs up | `send_register_welcome()` (via signal) |
| Password reset OTP | Forgot password | `send_password_reset_code()` |
| Resend OTP | Verify code page | `send_password_reset_code()` |
| Future updates | Manual/cron | `send_update_announcement()` |

## Environment Variables

See `.env.example` and `EMAIL_SETUP.md`. Required for production delivery:

- `EMAIL_HOST` = `smtp.gmail.com`
- `EMAIL_HOST_USER` = `updates@elvin-babanli.com`
- `EMAIL_HOST_PASSWORD` = Google Workspace app password
- `DEFAULT_FROM_EMAIL` (optional; default: B Labs \<updates@elvin-babanli.com\>)
- `SERVER_EMAIL` (optional; default: updates@elvin-babanli.com)
- `EMAIL_BACKEND` (optional; auto set to SMTP when credentials present)

## Local Development

Without env vars, Django uses `console.EmailBackend`. Emails are printed to terminal.

## Error Handling

- Service returns `False` on failure; never raises to user
- Views show "We could not send the verification code" instead of 500
- Exceptions are logged
- Register succeeds even if welcome email fails

## Test Checklist

1. **Register** → New user receives welcome email
2. **Forgot password** → OTP email delivered
3. **Resend code** → New OTP email
4. **Wrong env** → User sees friendly error, no 500
5. **Render production** → Set env vars per `EMAIL_SETUP.md`
