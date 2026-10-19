"""Django settings for the Clarivance prototype API. Prototype only: synthetic data, no customer accounts."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIST = BASE_DIR.parent / "web" / "dist"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-not-secret")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
if os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(os.environ["RENDER_EXTERNAL_HOSTNAME"])

INSTALLED_APPS = ["django.contrib.contenttypes", "django.contrib.staticfiles", "taxshield"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "taxshield.middleware.DemoPasswordMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
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
    SECURE_HSTS_SECONDS = 3600
    SESSION_COOKIE_SECURE = True
