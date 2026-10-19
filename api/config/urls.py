from django.conf import settings
from django.http import FileResponse, Http404
from django.urls import include, path, re_path


def spa(request):
    """Client-side routes (/app/..., /register, ...) all load the React app."""
    index = settings.WEB_DIST / "index.html"
    if not index.exists():
        raise Http404("Web app not built. Run `npm run build` in web/.")
    resp = FileResponse(open(index, "rb"), content_type="text/html")
    resp["Cache-Control"] = "no-cache"
    return resp


urlpatterns = [
    path("api/me/", include("pilot.urls")),
    path("api/auth/", include("pilot.auth_urls")),
    path("api/", include("taxshield.urls")),
    re_path(r"^(?!api/|static/|assets/).*$", spa),
]
