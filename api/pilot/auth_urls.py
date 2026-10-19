from django.urls import path

from . import auth_views as v

urlpatterns = [
    path("csrf", v.csrf),
    path("me", v.me),
    path("register", v.register),
    path("login", v.sign_in),
    path("logout", v.sign_out),
]
