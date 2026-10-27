from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from core import views
from lessons.media import media_auth

urlpatterns = [
    path("health/", views.health, name="health"),
    path("internal/media-auth/", media_auth, name="media_auth"),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
    path("", include("lessons.urls")),
]
