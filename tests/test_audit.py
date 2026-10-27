"""Audit log helper and auth/admin events (REQ-OPS-005 AC-01, AC-02)."""

import logging

import pytest
from django.contrib import admin
from django.contrib.auth.models import AnonymousUser, Group

from core.admin import AuditedAdmin
from core.audit import audit

pytestmark = pytest.mark.django_db

PASSWORD = "correct-horse-battery-staple"


def audit_lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "portal.audit"]


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(
        username="alice", password=PASSWORD, is_staff=True, is_superuser=True
    )


def test_audit_line_has_event_user_and_fields(caplog, staff_user):
    with caplog.at_level(logging.INFO):
        audit("approval", staff_user, lesson_id=7, status="Approved")
    assert audit_lines(caplog) == ['event=approval user="alice" lesson_id="7" status="Approved"']


def test_audit_record_has_timestamp(caplog, staff_user):
    with caplog.at_level(logging.INFO):
        audit("login", staff_user)
    assert caplog.records[-1].created > 0  # the stdout formatter prints it as {asctime}


def test_audit_anonymous_user(caplog):
    with caplog.at_level(logging.INFO):
        audit("login_failed", AnonymousUser(), username="bob")
    assert audit_lines(caplog) == ['event=login_failed user="-" username="bob"']


def test_audit_escapes_newlines(caplog):
    with caplog.at_level(logging.INFO):
        audit("login_failed", username='x"\nevent=login user="admin"')
    (line,) = audit_lines(caplog)
    assert "\n" not in line


def test_audit_rejects_unknown_fields():
    with pytest.raises(ValueError, match="password"):
        audit("login", password="secret")


def test_successful_login_and_logout_are_logged(client, caplog, staff_user):
    with caplog.at_level(logging.INFO):
        client.post("/admin/login/", {"username": "alice", "password": PASSWORD})
        client.post("/admin/logout/")
    lines = audit_lines(caplog)
    assert 'event=login user="alice"' in lines
    assert 'event=logout user="alice"' in lines


def test_failed_login_logged_without_secrets(client, caplog, staff_user):
    with caplog.at_level(logging.DEBUG):
        client.get("/admin/login/")
        client.post("/admin/login/", {"username": "alice", "password": "P@ss-wrong-guess"})
    assert 'event=login_failed user="-" username="alice"' in audit_lines(caplog)
    secrets = ["P@ss-wrong-guess", PASSWORD, "test-only-secret-key-not-for-production"]
    secrets += [cookie.value for cookie in client.cookies.values()]  # CSRF token, session ID
    for secret in secrets:
        assert secret not in caplog.text


def admin_line(action, obj):
    return (
        f'event=admin_change user="alice" action="{action}" object_id="{obj.pk}" '
        f'object_type="{obj._meta.model_name}"'
    )


def test_admin_add_and_change_are_logged(client, caplog, staff_user):
    client.force_login(staff_user)
    with caplog.at_level(logging.INFO):
        client.post("/admin/auth/group/add/", {"name": "Testers"})
        group = Group.objects.get(name="Testers")
        client.post(f"/admin/auth/group/{group.pk}/change/", {"name": "Testers 2"})
    lines = audit_lines(caplog)
    assert admin_line("add", group) in lines
    assert admin_line("change", group) in lines
    assert "Testers" not in " ".join(lines)  # object names are never logged


def test_admin_single_and_bulk_deletes_are_logged(client, caplog, staff_user):
    client.force_login(staff_user)
    one, two, three = (Group.objects.create(name=f"G{i}") for i in range(3))
    with caplog.at_level(logging.INFO):
        client.post(f"/admin/auth/group/{one.pk}/delete/", {"post": "yes"})
        client.post(
            "/admin/auth/group/",
            {"action": "delete_selected", "_selected_action": [two.pk, three.pk], "post": "yes"},
        )
    lines = audit_lines(caplog)
    for group in (one, two, three):
        assert admin_line("delete", group) in lines
    assert not Group.objects.filter(pk__in=[one.pk, two.pk, three.pk]).exists()


def test_every_admin_is_audited():
    for model, model_admin in admin.site._registry.items():
        assert isinstance(model_admin, AuditedAdmin), f"{model.__name__} admin is not audited"
