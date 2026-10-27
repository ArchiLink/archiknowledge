"""URLs used only by tests/test_errors.py to trigger error pages."""

from django.core.exceptions import PermissionDenied
from django.urls import include, path


def boom(request):
    raise RuntimeError("boom-test-exception")


def forbidden(request):
    raise PermissionDenied


urlpatterns = [
    path("boom/", boom),
    path("forbidden/", forbidden),
    path("", include("portal.urls")),
]
