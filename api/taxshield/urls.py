from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health),
    path("businesses", views.businesses),
    path("businesses/<str:key>", views.position),
    path("businesses/<str:key>/what-if", views.what_if),
]
