"""
Django settings for core project.
Production-ready: env-based config, PostgreSQL, security.
"""
from pathlib import Path
import os
import dj_database_url
from decouple import config
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ==================== SECURITY ====================
SECRET_KEY = config("SECRET_KEY", default="django-insecure-dev-key-change-in-production")
DEBUG = config("DEBUG", default="False") == "True"

_hosts = config("ALLOWED_HOSTS", default="localhost,127.0.0.1,.onrender.com,elvin-babanli.com,www.elvin-babanli.com")
ALLOWED_HOSTS = [h.strip() for h in _hosts.split(",") if h.strip()]

# CSRF for production (Render, custom domains)
_csrf_origins = config("CSRF_TRUSTED_ORIGINS", default="https://elvin-babanli.com,https://www.elvin-babanli.com")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(",") if o.strip()]

# Render/proxy: trust X-Forwarded-Proto for HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ==================== DATABASE ====================
# Render provides DATABASE_URL for PostgreSQL. Local uses SQLite.
_db_url = config("DATABASE_URL", default="")
if _db_url:
    DATABASES = {"default": dj_database_url.config(default=_db_url, conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ==================== APPLICATIONS ====================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "main",
    "accounts",
    "django.contrib.sitemaps",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.linkedin_oauth2",
]

SITE_ID = 1

LOGIN_URL = "/auth/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/auth/login/"

ACCOUNT_EMAIL_VERIFICATION = "optional"

AUTHENTICATION_BACKENDS = [
    "accounts.backend.EmailOrUsernameBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
    "django.contrib.auth.backends.ModelBackend",
]

SOCIALACCOUNT_PROVIDERS = {
    "google": {"SCOPE": ["profile", "email"], "AUTH_PARAMS": {"access_type": "online"}},
    "linkedin_oauth2": {"SCOPE": ["r_liteprofile", "r_emailaddress"]},
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "main.context_processors.chat_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

# ==================== PASSWORD VALIDATION ====================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ==================== I18N ====================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ==================== STATIC FILES ====================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# CompressedStaticFilesStorage avoids Manifest (which can fail on missing refs)
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==================== APP CONFIG ====================
OPENWEATHER_API_KEY = config("OPENWEATHER_API_KEY", default="")
CHAT_API_URL = config("CHAT_API_URL", default="http://127.0.0.1:8001/chat")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "home-feed-cache",
    }
}

# ==================== EMAIL ====================
# Gmail: EMAIL_HOST=smtp.gmail.com, EMAIL_HOST_USER=elvinbabanli0@gmail.com, GMAIL_APP_PASSWORD=...
# Local: leave unset → console backend (prints to terminal)
_email_backend = config("EMAIL_BACKEND", default="")
_email_host = config("EMAIL_HOST", default="")
_email_user = config("EMAIL_HOST_USER", default="")
_email_pwd = config("EMAIL_HOST_PASSWORD", default="") or config("GMAIL_APP_PASSWORD", default="")
_use_smtp = _email_host and _email_user and _email_pwd

if _email_backend:
    EMAIL_BACKEND = _email_backend
elif _use_smtp:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

EMAIL_HOST = _email_host or ""
EMAIL_PORT = int(config("EMAIL_PORT", default="587"))
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default="True") == "True"
EMAIL_HOST_USER = _email_user
EMAIL_HOST_PASSWORD = _email_pwd
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="elvinbabanli0@gmail.com")

# ==================== LOGGING ====================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(levelname)s %(asctime)s %(module)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
