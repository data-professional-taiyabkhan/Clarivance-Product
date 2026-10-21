"""Django settings for the Clarivance prototype API. Prototype only: synthetic data, no customer accounts."""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIST = BASE_DIR.parent / "web" / "dist"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-not-secret")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
# Always allow local names (Render health checks, tests); add public hosts via DJANGO_ALLOWED_HOSTS.
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver", "healthcheck.railway.app"] + [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o]
for _var in ("RAILWAY_PUBLIC_DOMAIN",):           # Railway sets this when a public domain is generated
    if os.environ.get(_var):
        ALLOWED_HOSTS.append(os.environ[_var])
        CSRF_TRUSTED_ORIGINS.append("https://" + os.environ[_var])
if os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(os.environ["RENDER_EXTERNAL_HOSTNAME"])
    CSRF_TRUSTED_ORIGINS.append("https://" + os.environ["RENDER_EXTERNAL_HOSTNAME"])

INSTALLED_APPS = ["django.contrib.contenttypes", "django.contrib.auth", "django.contrib.sessions",
                  "django.contrib.staticfiles", "taxshield", "pilot"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "taxshield.middleware.DemoPasswordMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default": dj_database_url.config(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=60)}
USE_TZ = True
TIME_ZONE = "Europe/London"
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Serve the built React app (web/dist) from the same service.
WHITENOISE_ROOT = WEB_DIST if WEB_DIST.exists() else None
WHITENOISE_INDEX_FILE = True

# Optional shared password for the hosted demo (HTTP Basic auth). Unset = open (local dev).
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "")

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^api/health$"]      # platform health checks call over plain HTTP
    SECURE_HSTS_SECONDS = 3600
    SESSION_COOKIE_SECURE = True

# Pilot accounts
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PILOT_INVITE_CODE = os.environ.get("PILOT_INVITE_CODE", "")
# In production, sign-up stays closed until an invite code is set. Locally (DEBUG) it is open.
PILOT_REGISTRATION_REQUIRES_CODE = not DEBUG
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
MAX_STATEMENT_BYTES = 5 * 1024 * 1024
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
if not DEBUG:
    CSRF_COOKIE_SECURE = True
