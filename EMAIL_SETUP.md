# Email Setup — Verification Code (Forgot Password)

## Gmail SMTP (Production)

### 1. Gmail App Password

1. Google Account → Security → 2-Step Verification (açık olmalı)
2. Security → App passwords → Create
3. Uygulama: Mail, Cihaz: Other → "Django" yazın
4. Oluşan 16 haneli şifreyi kopyalayın

### 2. Environment Variables

Render Dashboard veya `.env` dosyasında:

| Key | Value |
|-----|-------|
| `EMAIL_HOST` | `smtp.gmail.com` |
| `EMAIL_HOST_USER` | `elvinbabanli0@gmail.com` |
| `EMAIL_HOST_PASSWORD` | 16 haneli App Password |
| veya `GMAIL_APP_PASSWORD` | 16 haneli App Password |
| `DEFAULT_FROM_EMAIL` | `elvinbabanli0@gmail.com` |
| `EMAIL_PORT` | `587` (opsiyonel, varsayılan) |
| `EMAIL_USE_TLS` | `True` (opsiyonel) |

### 3. Örnek (.env)

```
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=elvinbabanli0@gmail.com
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop
DEFAULT_FROM_EMAIL=elvinbabanli0@gmail.com
```

### 4. Local Development

Env değişkenleri ayarlanmazsa e-posta **konsola** yazılır (gerçek gönderim yok). Doğrulama kodunu terminal çıktısından alabilirsiniz.
