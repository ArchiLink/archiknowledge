"""Login, groups and default-deny access (REQ-AUTH-001)."""

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.urls import URLPattern, URLResolver, get_resolver

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"

# Every view reachable without login. Add a name here only for the public read-only views
# listed in SECURITY.md (dashboard, knowledge base, gallery, lesson detail, embed, /health/).
PUBLIC_VIEWS = {
    "health",
    "login",
    "admin:login",
    "media_auth",
    "lesson_detail",
    "knowledge_base",
    "dashboard",
    "feed",
}


def iter_patterns(patterns, namespace=""):
    for entry in patterns:
        if isinstance(entry, URLResolver):
            prefix = f"{namespace}{entry.namespace}:" if entry.namespace else namespace
            yield from iter_patterns(entry.url_patterns, prefix)
        elif isinstance(entry, URLPattern):
            yield f"{namespace}{entry.name}", entry.callback


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sam", password=PASSWORD)


# AC-01: LoginRequiredMiddleware on; only the listed views are public.


def test_login_required_middleware_enabled():
    assert "django.contrib.auth.middleware.LoginRequiredMiddleware" in settings.MIDDLEWARE


def test_only_listed_views_are_public():
    public = {
        name
        for name, view in iter_patterns(get_resolver().url_patterns)
        if getattr(view, "login_required", True) is False
    }
    assert public <= PUBLIC_VIEWS, f"unexpected public views: {public - PUBLIC_VIEWS}"


# AC-02: groups exist.


def test_groups_created_by_migration():
    assert set(Group.objects.values_list("name", flat=True)) >= {"Staff", "QA Reviewers"}


# AC-03: password rules.


@pytest.mark.parametrize("password", ["short-pw-11", "password1234", "123456789012"])
def test_weak_passwords_rejected(password):
    with pytest.raises(ValidationError):
        validate_password(password)


def test_twelve_character_password_accepted():
    validate_password("tidal-orbit7")


# AC-04: session rotation, expiry and cookie names.


def test_session_rotated_on_login(client, user):
    session = client.session
    session["before_login"] = True
    session.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
    before = session.session_key
    client.post("/accounts/login/", {"username": "sam", "password": PASSWORD})
    after = client.cookies[settings.SESSION_COOKIE_NAME].value
    assert after and after != before


def test_session_expires_after_ten_hours_of_inactivity():
    assert settings.SESSION_COOKIE_AGE == 36000
    assert settings.SESSION_SAVE_EVERY_REQUEST is True  # the 10 hours restart on each request


def test_cookie_names(client, user):
    client.get("/accounts/login/")
    assert "qp_csrf" in client.cookies
    client.post("/accounts/login/", {"username": "sam", "password": PASSWORD})
    assert "qp_session" in client.cookies


# AC-05: login page warning; generic failure message.


def test_login_page_warns_against_password_reuse(client):
    body = client.get("/accounts/login/").content.decode()
    assert "Don't use your Windows or Microsoft 365 password" in body


def test_failed_login_message_does_not_reveal_whether_user_exists(client, user):
    wrong_password = client.post("/accounts/login/", {"username": "sam", "password": "nope"})
    no_such_user = client.post("/accounts/login/", {"username": "ghost", "password": "nope"})
    assert wrong_password.status_code == no_such_user.status_code == 200
    message = "Your username and password didn't match."
    assert message in wrong_password.content.decode()
    assert message in no_such_user.content.decode()


def test_login_and_logout(client, user):
    response = client.post("/accounts/login/", {"username": "sam", "password": PASSWORD})
    assert response.status_code == 302
    assert client.session.get("_auth_user_id") == str(user.pk)
    client.post("/accounts/logout/")
    assert "_auth_user_id" not in client.session


# AC-06: anonymous users are redirected to login from any non-public view.


def test_undecorated_view_redirects_anonymous_to_login(client, settings):
    settings.ROOT_URLCONF = "tests.protected_urls"
    response = client.get("/undecorated/")
    assert response.status_code == 302
    assert response["Location"].startswith("/accounts/login/?next=/undecorated/")


def test_undecorated_view_allowed_after_login(client, settings, user):
    settings.ROOT_URLCONF = "tests.protected_urls"
    client.force_login(user)
    assert client.get("/undecorated/").content == b"secret"


def test_admin_redirects_anonymous(client):
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "login" in response["Location"]
