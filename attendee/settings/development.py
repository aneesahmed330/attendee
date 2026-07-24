import os

from .base import *

# DEBUG=True leaks memory in long-running Celery/scheduler processes (Django
# stores every SQL query in connection.queries, which only web requests clear).
# Local dev keeps the default; the production server sets DJANGO_DEBUG=false.
# With DEBUG=false, run `manage.py collectstatic` once (whitenoise serves it).
DEBUG = os.getenv("DJANGO_DEBUG", "true") == "true"
SITE_DOMAIN = "localhost:8000"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost").split(",")

# base.py defaults to the console email backend (prints emails, sends nothing).
# When EMAIL_HOST_PASSWORD is set (SendGrid API key), switch to real SMTP so team
# invites / email verification actually get delivered. No key → console fallback.
if os.getenv("EMAIL_HOST_PASSWORD"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.sendgrid.net")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "apikey")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
    DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@techverx.com")

# Set DJANGO_SSL_REQUIRE=true when running behind an HTTPS-terminating reverse
# proxy (nginx + Let's Encrypt) — otherwise Django thinks every request is
# plain HTTP and login/CSRF checks fail. Defaults to false so local dev
# (plain HTTP, no proxy) is unaffected.
if os.getenv("DJANGO_SSL_REQUIRE", "false") == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "attendee_development",
        "USER": "attendee_development_user",
        "PASSWORD": "attendee_development_user",
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": "5432",
    }
}

# Log more stuff in development
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "xmlschema": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        # Uncomment to log database queries
        # "django.db.backends": {
        #    "handlers": ["console"],
        #    "level": "DEBUG",
        #    "propagate": False,
        # },
    },
}
