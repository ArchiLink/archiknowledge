"""URLs used only by tests/test_errors.py to trigger error pages."""

from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import PermissionDenied
from django.urls import include, path


@login_not_required
def boom(request):
    raise RuntimeError("boom-test-exception")


@login_not_required
def forbidden(request):
    raise PermissionDenied


urlpatterns = [
    path("boom/", boom),
    path("forbidden/", forbidden),
    path("", include("portal.urls")),
]
