"""Account lockout after repeated failed logins (REQ-AUTH-002)."""

import logging
import re
from datetime import timedelta

import pytest
from axes.models import AccessAttempt
from django.utils import timezone

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"
LOGIN_URLS = ["/accounts/login/", "/admin/login/"]


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sam", password=PASSWORD, is_staff=True)


def attempt(client, password, url="/accounts/login/", username="sam"):
    response = client.post(url, {"username": username, "password": password})
    logged_in = client.session.get("_auth_user_id") is not None
    client.logout()
    return response, logged_in


def fail(client, times, **kwargs):
    for _ in range(times):
        attempt(client, "wrong-password", **kwargs)


def page_without_csrf(response):
    return re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', "", response.content.decode())


# AC-01: after 10 failures the correct password is refused.


@pytest.mark.parametrize("url", LOGIN_URLS)
def test_locked_after_ten_failures(client, user, url):
    fail(client, 10, url=url)
    _, logged_in = attempt(client, PASSWORD, url=url)
    assert not logged_in


def test_nine_failures_do_not_lock(client, user):
    fail(client, 9)
    _, logged_in = attempt(client, PASSWORD)
    assert logged_in


# AC-02: after 15 minutes the correct password works again and the counter resets.


def test_unlocked_after_fifteen_minutes(client, user):
    fail(client, 10)
    AccessAttempt.objects.update(attempt_time=timezone.now() - timedelta(minutes=16))
    _, logged_in = attempt(client, PASSWORD)
    assert logged_in
    assert not AccessAttempt.objects.exists()


def test_still_locked_before_fifteen_minutes(client, user):
    fail(client, 10)
    AccessAttempt.objects.update(attempt_time=timezone.now() - timedelta(minutes=14))
    _, logged_in = attempt(client, PASSWORD)
    assert not logged_in


# AC-03: a successful login resets the counter.


def test_success_resets_failure_counter(client, user):
    fail(client, 9)
    assert attempt(client, PASSWORD)[1]
    fail(client, 9)
    assert attempt(client, PASSWORD)[1]


# AC-04: failed logins and lockouts are audited without the password.


def test_lockout_audited_without_password(client, user, caplog):
    with caplog.at_level(logging.INFO):
        fail(client, 10)
    audit = [r.getMessage() for r in caplog.records if r.name == "portal.audit"]
    assert audit.count('event=login_failed user="-" username="sam"') == 10
    assert 'event=lockout user="-" username="sam"' in audit
    assert "wrong-password" not in caplog.text


# Failure behaviour: a locked account looks exactly like a wrong password.


@pytest.mark.parametrize("url", LOGIN_URLS)
def test_locked_page_identical_to_wrong_password_page(client, user, url):
    wrong, _ = attempt(client, "wrong-password", url=url)
    fail(client, 9, url=url)
    locked, _ = attempt(client, PASSWORD, url=url)
    assert locked.status_code == wrong.status_code == 200
    assert page_without_csrf(locked) == page_without_csrf(wrong)


def test_unknown_username_locks_the_same_way(client, user):
    wrong, _ = attempt(client, "x", username="ghost")
    fail(client, 10, username="ghost")
    locked, _ = attempt(client, "x", username="ghost")
    assert page_without_csrf(locked) == page_without_csrf(wrong)


def test_lockout_is_per_account(client, user, django_user_model):
    django_user_model.objects.create_user(username="kim", password=PASSWORD)
    fail(client, 10)
    _, logged_in = attempt(client, PASSWORD, username="kim")
    assert logged_in
