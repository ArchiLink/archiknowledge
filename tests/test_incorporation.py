"""Tracking incorporation into specs, standard details and onboarding (REQ-REVIEW-002)."""

import logging

import pytest
from django.contrib.auth.models import Group
from django.test import Client

from core.roles import QA_GROUP
from lessons.models import Lesson

pytestmark = pytest.mark.django_db


@pytest.fixture
def qa(django_user_model):
    user = django_user_model.objects.create_user(username="quinn", password="x" * 12)
    user.groups.add(Group.objects.get(name=QA_GROUP))
    return user


@pytest.fixture
def approved(make_lesson):
    return make_lesson(status=Lesson.Status.APPROVED)


def url(lesson):
    return f"/review/{lesson.pk}/incorporation/"


# AC-01: QA sets and clears each flag on an Approved lesson.


def test_qa_sets_and_clears_flags(client, qa, approved, caplog):
    client.force_login(qa)
    with caplog.at_level(logging.INFO):
        response = client.post(url(approved), {"in_specs": "on", "in_onboarding": "on"})
    assert response["Location"] == f"/lessons/{approved.pk}/"
    approved.refresh_from_db()
    assert approved.in_specs and approved.in_onboarding and not approved.in_standard_details
    lines = [r.getMessage() for r in caplog.records if r.name == "portal.audit"]
    assert (
        f'event=incorporation_change user="quinn" lesson_id="{approved.pk}"'
        ' status="in_specs,in_onboarding"' in lines
    )

    client.post(url(approved), {})
    approved.refresh_from_db()
    assert not (approved.in_specs or approved.in_standard_details or approved.in_onboarding)


def test_unchanged_form_not_audited(client, qa, approved, caplog):
    client.force_login(qa)
    with caplog.at_level(logging.INFO):
        client.post(url(approved), {})
    assert not [r for r in caplog.records if "incorporation_change" in r.getMessage()]


@pytest.mark.parametrize("status", [Lesson.Status.SUBMITTED, Lesson.Status.REJECTED])
def test_only_approved_lessons(client, qa, make_lesson, status):
    lesson = make_lesson(status=status)
    client.force_login(qa)
    assert client.post(url(lesson), {"in_specs": "on"}).status_code == 404
    lesson.refresh_from_db()
    assert not lesson.in_specs


# AC-02: Staff and anonymous users can't change the flags.


def test_staff_forbidden(client, staff_member, approved):
    client.force_login(staff_member)
    assert client.post(url(approved), {"in_specs": "on"}).status_code == 403
    approved.refresh_from_db()
    assert not approved.in_specs


def test_anonymous_redirected(client, approved):
    response = client.post(url(approved), {"in_specs": "on"})
    assert response["Location"].startswith("/accounts/login/")
    approved.refresh_from_db()
    assert not approved.in_specs


def test_get_not_allowed(client, qa, approved):
    client.force_login(qa)
    assert client.get(url(approved)).status_code == 405


def test_csrf_required(qa, approved):
    client = Client(enforce_csrf_checks=True)
    client.force_login(qa)
    assert client.post(url(approved), {"in_specs": "on"}).status_code == 403


# AC-03: the detail page shows the statuses; the form only for QA.


def test_detail_page_shows_statuses(client, make_lesson):
    lesson = make_lesson(status=Lesson.Status.APPROVED, in_standard_details=True)
    body = client.get(f"/lessons/{lesson.pk}/").content.decode()
    assert "Standard details: Yes" in body
    assert "Specifications: Not yet" in body
    assert "Update incorporation" not in body


def test_detail_page_form_for_qa(client, qa, approved):
    client.force_login(qa)
    assert "Update incorporation" in client.get(f"/lessons/{approved.pk}/").content.decode()


# AC-04: knowledge base filter.


def test_knowledge_base_incorporation_filter(client, make_lesson):
    make_lesson(title="Untouched", status=Lesson.Status.APPROVED)
    make_lesson(title="In specs", status=Lesson.Status.APPROVED, in_specs=True)
    make_lesson(
        title="Everywhere",
        status=Lesson.Status.APPROVED,
        in_specs=True,
        in_standard_details=True,
        in_onboarding=True,
    )

    def titles(value):
        response = client.get("/knowledge/", {"incorporated": value})
        return sorted(lesson.title for lesson in response.context["page"])

    assert titles("no") == ["Untouched"]
    assert titles("yes") == ["Everywhere", "In specs"]
    assert titles("") == ["Everywhere", "In specs", "Untouched"]
    assert client.get("/knowledge/", {"incorporated": "maybe"}).status_code == 400
