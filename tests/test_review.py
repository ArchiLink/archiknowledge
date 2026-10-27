"""QA review queue (REQ-REVIEW-001)."""

import logging
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.utils import timezone

from core.roles import QA_GROUP, STAFF_GROUP
from lessons.models import Lesson, Phase

pytestmark = pytest.mark.django_db


@pytest.fixture
def qa(django_user_model):
    user = django_user_model.objects.create_user(username="quinn", password="x" * 12)
    user.groups.add(Group.objects.get(name=QA_GROUP))
    return user


@pytest.fixture
def qa_client(client, qa):
    client.force_login(qa)
    return client


@pytest.fixture
def staff_client(client, staff_member):
    staff_member.groups.add(Group.objects.get(name=STAFF_GROUP))
    client.force_login(staff_member)
    return client


def edit_data(lesson, **overrides):
    data = {
        "title": lesson.title,
        "project": lesson.project_id,
        "phase": lesson.phase_id,
        "discipline": lesson.discipline_id,
        "issue_type": lesson.issue_type_id,
        "building_component": lesson.building_component_id,
        "description": lesson.description,
        "lesson": lesson.lesson,
        "impact": lesson.impact,
        "cost_impact": "",
        "time_impact_days": "",
        "action": "save",
    }
    if lesson.anonymise:
        data["anonymise"] = "on"
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


def audit_lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "portal.audit"]


# AC-01: queue of Submitted lessons, oldest first, QA only.


def test_queue_lists_submitted_oldest_first(qa_client, make_lesson):
    newer = make_lesson(title="Newer")
    older = make_lesson(title="Older")
    Lesson.objects.filter(pk=older.pk).update(submitted_at=timezone.now() - timedelta(days=2))
    make_lesson(title="Already approved", status=Lesson.Status.APPROVED)
    make_lesson(title="Already rejected", status=Lesson.Status.REJECTED)
    body = qa_client.get("/review/").content.decode()
    assert body.index("Older") < body.index(newer.title)
    assert "Already approved" not in body and "Already rejected" not in body


def test_empty_queue(qa_client):
    assert "Nothing is waiting for review." in qa_client.get("/review/").content.decode()


def test_staff_cannot_open_queue(staff_client, make_lesson):
    lesson = make_lesson()
    assert staff_client.get("/review/").status_code == 403
    assert staff_client.get(f"/review/{lesson.pk}/").status_code == 403


def test_anonymous_redirected(client):
    assert client.get("/review/")["Location"].startswith("/accounts/login/")


def test_queue_link_shown_to_qa(qa_client):
    assert 'href="/review/"' in qa_client.get("/my-submissions/").content.decode()


def test_queue_link_hidden_from_staff(staff_client):
    assert 'href="/review/"' not in staff_client.get("/my-submissions/").content.decode()


# AC-02: QA can edit any field and toggle anonymise.


def test_qa_edits_fields_and_anonymises(qa_client, make_lesson, caplog):
    lesson = make_lesson()
    new_phase = Phase.objects.get(code="DD")
    with caplog.at_level(logging.INFO):
        response = qa_client.post(
            f"/review/{lesson.pk}/",
            edit_data(lesson, title="Edited title", phase=new_phase.pk, anonymise="on"),
        )
    assert response.status_code == 302
    lesson.refresh_from_db()
    assert lesson.title == "Edited title" and lesson.phase == new_phase and lesson.anonymise
    assert lesson.status == Lesson.Status.SUBMITTED  # save alone doesn't change status
    assert lesson.reviewed_by is None
    assert f'event=anonymise_change user="quinn" anonymise="True" lesson_id="{lesson.pk}"' in (
        audit_lines(caplog)
    )


def test_inactive_lookup_kept_when_editing(qa_client, make_lesson):
    lesson = make_lesson()
    Phase.objects.filter(pk=lesson.phase_id).update(is_active=False)
    response = qa_client.post(f"/review/{lesson.pk}/", edit_data(lesson, title="Still valid"))
    assert response.status_code == 302


def test_invalid_edit_re_rendered(qa_client, make_lesson):
    lesson = make_lesson()
    response = qa_client.post(f"/review/{lesson.pk}/", edit_data(lesson, title=""))
    assert response.status_code == 200
    lesson.refresh_from_db()
    assert lesson.title != ""


def test_review_page_shows_lesson(qa_client, make_lesson):
    lesson = make_lesson(title="Look at me")
    body = qa_client.get(f"/review/{lesson.pk}/").content.decode()
    assert "Look at me" in body and "Save and approve" in body


# AC-03: approve and reject set status and review audit fields.


def test_approve_sets_audit_fields(qa_client, qa, make_lesson):
    lesson = make_lesson()
    response = qa_client.post(f"/review/{lesson.pk}/", edit_data(lesson, action="approve"))
    assert response["Location"] == "/review/"
    lesson.refresh_from_db()
    assert lesson.status == Lesson.Status.APPROVED
    assert lesson.reviewed_by == qa
    assert lesson.reviewed_at is not None and lesson.approved_at is not None


def test_reject_sets_audit_fields(qa_client, qa, make_lesson):
    lesson = make_lesson()
    qa_client.post(f"/review/{lesson.pk}/", edit_data(lesson, action="reject"))
    lesson.refresh_from_db()
    assert lesson.status == Lesson.Status.REJECTED
    assert lesson.reviewed_by == qa and lesson.reviewed_at is not None
    assert lesson.approved_at is None


def test_reapproval_keeps_first_publication_time(qa_client, make_lesson):
    lesson = make_lesson()
    qa_client.post(f"/review/{lesson.pk}/", edit_data(lesson, action="approve"))
    lesson.refresh_from_db()
    first = lesson.approved_at
    qa_client.post(f"/review/{lesson.pk}/", edit_data(lesson, action="approve"))
    lesson.refresh_from_db()
    assert lesson.approved_at == first


def test_rejecting_approved_lesson_unpublishes_it(qa_client, make_lesson):
    lesson = make_lesson()
    qa_client.post(f"/review/{lesson.pk}/", edit_data(lesson, action="approve"))
    qa_client.post(f"/review/{lesson.pk}/", edit_data(lesson, action="reject"))
    assert not Lesson.objects.approved().filter(pk=lesson.pk).exists()


def test_unknown_action_rejected(qa_client, make_lesson):
    lesson = make_lesson()
    response = qa_client.post(f"/review/{lesson.pk}/", edit_data(lesson, action="publish"))
    assert response.status_code == 400
    lesson.refresh_from_db()
    assert lesson.status == Lesson.Status.SUBMITTED


# AC-04: Staff can't approve by posting directly.


@pytest.mark.parametrize("action", ["approve", "reject", "save"])
def test_staff_post_forbidden_and_nothing_changes(staff_client, make_lesson, action):
    lesson = make_lesson()
    response = staff_client.post(
        f"/review/{lesson.pk}/", edit_data(lesson, action=action, title="Hacked", anonymise="on")
    )
    assert response.status_code == 403
    lesson.refresh_from_db()
    assert lesson.status == Lesson.Status.SUBMITTED
    assert lesson.title != "Hacked" and not lesson.anonymise


# AC-05: approvals, rejections and anonymise changes are audited.


@pytest.mark.parametrize(("action", "event"), [("approve", "approval"), ("reject", "rejection")])
def test_status_changes_audited(qa_client, make_lesson, caplog, action, event):
    lesson = make_lesson()
    with caplog.at_level(logging.INFO):
        qa_client.post(f"/review/{lesson.pk}/", edit_data(lesson, action=action))
    status = "approved" if action == "approve" else "rejected"
    assert f'event={event} user="quinn" lesson_id="{lesson.pk}" status="{status}"' in (
        audit_lines(caplog)
    )


def test_no_anonymise_event_when_unchanged(qa_client, make_lesson, caplog):
    lesson = make_lesson()
    with caplog.at_level(logging.INFO):
        qa_client.post(f"/review/{lesson.pk}/", edit_data(lesson))
    assert not [line for line in audit_lines(caplog) if "anonymise_change" in line]


# AC-06: state changes need POST with CSRF; HTMX sends the token as a header.


def test_get_changes_nothing(qa_client, make_lesson):
    lesson = make_lesson()
    qa_client.get(f"/review/{lesson.pk}/?action=approve")
    lesson.refresh_from_db()
    assert lesson.status == Lesson.Status.SUBMITTED


def test_post_without_csrf_rejected(qa, make_lesson):
    lesson = make_lesson()
    client = Client(enforce_csrf_checks=True)
    client.force_login(qa)
    assert (
        client.post(f"/review/{lesson.pk}/", edit_data(lesson, action="approve")).status_code == 403
    )
    lesson.refresh_from_db()
    assert lesson.status == Lesson.Status.SUBMITTED


def test_csrf_token_accepted_as_htmx_header(qa, make_lesson):
    lesson = make_lesson()
    client = Client(enforce_csrf_checks=True)
    client.force_login(qa)
    page = client.get(f"/review/{lesson.pk}/").content.decode()
    assert 'hx-headers=\'{"X-CSRFToken": "' in page
    token = client.cookies["qp_csrf"].value
    response = client.post(
        f"/review/{lesson.pk}/", edit_data(lesson, action="approve"), HTTP_X_CSRFTOKEN=token
    )
    assert response.status_code == 302
    lesson.refresh_from_db()
    assert lesson.status == Lesson.Status.APPROVED
