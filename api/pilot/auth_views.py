"""Email + password accounts for the pilot (session cookies, CSRF-protected)."""
from __future__ import annotations

import hmac
import json

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import Profile

User = get_user_model()


def _body(request) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return {}


def _me(user) -> dict:
    p, _ = Profile.objects.get_or_create(user=user)
    return {"email": user.email, "name": p.name, "profile_done": p.profile_done,
            "has_transactions": user.transactions.exists()}


def _throttled(request, key: str, limit: int = 10, window: int = 600) -> bool:
    ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "")).split(",")[0].strip()
    k = f"rl:{key}:{ip}"
    n = cache.get(k, 0)
    if n >= limit:
        return True
    cache.set(k, n + 1, window)
    return False


@require_GET
@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({"ok": True, "invite_required": bool(settings.PILOT_INVITE_CODE) or settings.PILOT_REGISTRATION_REQUIRES_CODE})


@require_GET
def me(request):
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False}, status=200)
    return JsonResponse({"authenticated": True, **_me(request.user)})


@require_POST
def register(request):
    if _throttled(request, "register", 8):
        return JsonResponse({"error": "Too many attempts. Try again in a few minutes."}, status=429)
    d = _body(request)
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    name = (d.get("name") or "").strip()[:120]
    code = (d.get("invite_code") or "").strip()
    if settings.PILOT_REGISTRATION_REQUIRES_CODE and not settings.PILOT_INVITE_CODE:
        return JsonResponse({"error": "Pilot registration isn't open yet."}, status=403)
    if settings.PILOT_INVITE_CODE and not hmac.compare_digest(code, settings.PILOT_INVITE_CODE):
        return JsonResponse({"error": "That invite code isn't valid. The pilot is invitation-only for now."}, status=400)
    if not d.get("accept_terms"):
        return JsonResponse({"error": "Please confirm you have read how we handle your data."}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"error": "Enter a valid email address."}, status=400)
    if User.objects.filter(username=email).exists():
        return JsonResponse({"error": "An account with this email already exists. Sign in instead."}, status=400)
    candidate = User(username=email, email=email, first_name=name)
    try:
        validate_password(password, candidate)
    except ValidationError as e:
        return JsonResponse({"error": " ".join(e.messages)}, status=400)
    user = User.objects.create_user(username=email, email=email, password=password, first_name=name)
    Profile.objects.create(user=user, name=name, accepted_terms_at=timezone.now())
    login(request, user)
    return JsonResponse({"authenticated": True, **_me(user)}, status=201)


@require_POST
def sign_in(request):
    if _throttled(request, "login", 10):
        return JsonResponse({"error": "Too many attempts. Try again in a few minutes."}, status=429)
    d = _body(request)
    user = authenticate(request, username=(d.get("email") or "").strip().lower(), password=d.get("password") or "")
    if user is None:
        return JsonResponse({"error": "Email or password is wrong."}, status=400)
    login(request, user)
    return JsonResponse({"authenticated": True, **_me(user)})


@require_POST
def sign_out(request):
    logout(request)
    return JsonResponse({"authenticated": False})
