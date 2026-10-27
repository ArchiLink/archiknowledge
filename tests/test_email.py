"""Email setup and submit/approval notifications (REQ-EMAIL-001)."""

import io
import logging
import smtplib
from pathlib import Path
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from core import email
from core.roles import QA_GROUP, STAFF_GROUP
from lessons.models import Discipline, IssueType, Lesson, Phase, Project

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def smtp_on(settings):
    settings.EMAIL_HOST = "smtp.example.test"


@pytest.fixture
def qa(django_user_model):
    user = django_user_model.objects.create_user(
        username="quinn", password="x" * 12, email="qa@example.test"
    )
    user.groups.add(Group.objects.get(name=QA_GROUP))
    return user


@pytest.fixture
def submitter(django_user_model):
    user = django_user_model.objects.create_user(
        username="sam", password="x" * 12, email="sam@example.test"
    )
    user.groups.add(Group.objects.get(name=STAFF_GROUP))
    return user


def png():
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buffer, format="PNG")
    return SimpleUploadedFile("p.png", buffer.getvalue())


def submit(client, user, captured, **overrides):
    client.force_login(user)
    data = {
        "title": "Flashing\nmissing",
        "project": Project.objects.get_or_create(name="Harbour Tower")[0].pk,
        "phase": Phase.objects.get(code="CD").pk,
        "discipline": Discipline.objects.get(name="Architecture").pk,
        "issue_type": IssueType.objects.get(name="Omission").pk,
        "building_component": 1,
        "description": "<script>alert(1)</script>",
        "lesson": "Detail it.",
        "impact": "high",
        "failed_images": [png()],
        **overrides,
    }
    with captured(execute=True):
        return client.post("/submit/", data)


def review(client, qa_user, lesson, action, captured):
    client.force_login(qa_user)
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
        "action": action,
    }
    if lesson.anonymise:
        data["anonymise"] = "on"
    with captured(execute=True):
        return client.post(f"/review/{lesson.pk}/", data)


def email_lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "portal.email"]


# AC-01: with EMAIL_HOST empty, nothing is sent and one line is logged.


def test_skipped_and_logged_without_email_host(
    client, submitter, qa, caplog, django_capture_on_commit_callbacks
):
    with caplog.at_level(logging.INFO):
        response = submit(client, submitter, django_capture_on_commit_callbacks)
    assert response.status_code == 302
    assert mail.outbox == []
    assert email_lines(caplog) == ["email skipped type=submitted recipients=1 reason=no EMAIL_HOST"]
    assert "alert(1)" not in caplog.text


# AC-02: a submission emails all QA Reviewers with a link to the review page.


def test_submission_emails_qa_reviewers(
    client, smtp_on, submitter, qa, django_user_model, django_capture_on_commit_callbacks
):
    second = django_user_model.objects.create_user(username="q2", email="qa2@example.test")
    second.groups.add(Group.objects.get(name=QA_GROUP))
    submit(client, submitter, django_capture_on_commit_callbacks)
    lesson = Lesson.objects.get()
    (message,) = mail.outbox
    assert sorted(message.to) == ["qa2@example.test", "qa@example.test"]
    assert f"http://testserver/review/{lesson.pk}/" in message.body
    assert message.subject == "New lesson to review: Flashing missing"  # newline removed


def test_no_reviewer_addresses_logged(
    client, smtp_on, submitter, caplog, django_capture_on_commit_callbacks
):
    with caplog.at_level(logging.INFO):
        submit(client, submitter, django_capture_on_commit_callbacks)
    assert mail.outbox == []
    assert "email skipped type=submitted recipients=0 reason=no addresses" in email_lines(caplog)


# AC-03: approval/rejection emails the submitter with the right link.


def test_approval_emails_submitter_with_permalink(
    client, smtp_on, qa, submitter, make_lesson, django_capture_on_commit_callbacks
):
    lesson = make_lesson(submitted_by=submitter)
    review(client, qa, lesson, "approve", django_capture_on_commit_callbacks)
    (message,) = mail.outbox
    assert message.to == ["sam@example.test"]
    assert "approved and published" in message.body
    assert f"http://testserver/lessons/{lesson.pk}/" in message.body


def test_rejection_emails_submitter_with_my_submissions_link(
    client, smtp_on, qa, submitter, make_lesson, django_capture_on_commit_callbacks
):
    lesson = make_lesson(submitted_by=submitter)
    review(client, qa, lesson, "reject", django_capture_on_commit_callbacks)
    (message,) = mail.outbox
    assert "not approved" in message.subject
    assert f"http://testserver/my-submissions/{lesson.pk}/" in message.body


def test_save_only_sends_nothing(
    client, smtp_on, qa, submitter, make_lesson, django_capture_on_commit_callbacks
):
    review(
        client, qa, make_lesson(submitted_by=submitter), "save", django_capture_on_commit_callbacks
    )
    assert mail.outbox == []


# AC-04: plain text, no attachments, anonymised project names withheld.


def test_plain_text_no_attachments_project_withheld(
    client, smtp_on, qa, submitter, make_lesson, django_capture_on_commit_callbacks
):
    lesson = make_lesson(
        submitted_by=submitter,
        project=Project.objects.create(name="Covert Clinic"),
        anonymise=True,
        title="<b>R&D</b> lesson",
    )
    review(client, qa, lesson, "approve", django_capture_on_commit_callbacks)
    (message,) = mail.outbox
    assert message.content_subtype == "plain"
    assert message.attachments == [] and not getattr(message, "alternatives", [])
    assert "Covert Clinic" not in message.body and Lesson.ANONYMISED_PROJECT in message.body
    assert "<b>R&D</b> lesson" in message.body  # inert in plain text, shown as typed


# AC-05: SMTP settings come from the EMAIL_* keys.


def test_email_settings_documented_and_read_from_env(settings):
    example = (ROOT / ".env.example").read_text()
    for key in [
        "EMAIL_HOST",
        "EMAIL_PORT",
        "EMAIL_HOST_USER",
        "EMAIL_HOST_PASSWORD",
        "EMAIL_USE_TLS",
        "DEFAULT_FROM_EMAIL",
    ]:
        assert f"\n{key}=" in example
    assert settings.EMAIL_HOST == "" and settings.EMAIL_PORT == 25
    assert settings.EMAIL_USE_TLS is False and settings.EMAIL_TIMEOUT == 10


# Failure behaviour: an SMTP error is logged and the action still succeeds.


def test_smtp_failure_logged_and_submission_kept(
    client, smtp_on, submitter, qa, caplog, django_capture_on_commit_callbacks
):
    with mock.patch("core.email.send_mail", side_effect=smtplib.SMTPException("relay down")):
        with caplog.at_level(logging.INFO):
            response = submit(client, submitter, django_capture_on_commit_callbacks)
    assert response.status_code == 302
    assert Lesson.objects.count() == 1
    assert "email failed type=submitted recipients=1 error=SMTPException" in email_lines(caplog)
    assert "relay down" not in caplog.text and "qa@example.test" not in caplog.text


def test_one_line():
    assert email.one_line("a\r\nb\tc  d") == "a b c d"
