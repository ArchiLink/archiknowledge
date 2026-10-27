"""URLs used only by tests/test_auth.py: a view with no decorators, to prove default-deny."""

from django.http import HttpResponse
from django.urls import include, path


def undecorated(request):
    return HttpResponse("secret")


urlpatterns = [
    path("undecorated/", undecorated),
    path("", include("portal.urls")),
]
