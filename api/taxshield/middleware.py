"""Optional shared-password gate for the demo businesses only (/demo and /api/businesses...).

Pilot users have their own accounts (and an invite code), so the rest of the site is not behind this gate.
"""
import base64
import hmac

from django.conf import settings
from django.http import HttpResponse

OPEN_PATHS = {"/api/health"}


class DemoPasswordMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        password = settings.DEMO_PASSWORD
        gated = request.path.startswith("/demo") or request.path.startswith("/api/businesses")
        if not password or not gated or request.path in OPEN_PATHS:
            return self.get_response(request)
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if header.startswith("Basic "):
            try:
                _, _, supplied = base64.b64decode(header[6:]).decode("utf-8").partition(":")
            except (ValueError, UnicodeDecodeError):
                supplied = ""
            if hmac.compare_digest(supplied, password):
                return self.get_response(request)
        response = HttpResponse("Clarivance prototype: password required.", status=401)
        response["WWW-Authenticate"] = 'Basic realm="Clarivance prototype", charset="UTF-8"'
        return response
