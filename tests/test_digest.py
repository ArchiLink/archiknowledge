"""Fortnightly High-impact digest and scheduler (REQ-EMAIL-002)."""

import logging
import re
from datetime import timedelta
from pathlib import Path
from unittest import mock

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from lessons.models import DigestRun, Lesson, Project
from tests.test_deployment import compose_services

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def digest_on(settings):
    settings.EMAIL_HOST = "smtp.example.test"
    settings.QUALITY_ALERT_RECIPIENTS = ["all-staff@example.test"]


@pytest.fixture
def published(make_lesson):
    def make(days_ago=1, impact=Lesson.Impact.HIGH, status=Lesson.Status.APPROVED, **fields):
        lesson = make_lesson(impact=impact, status=status, **fields)
        Lesson.objects.filter(pk=lesson.pk).update(
            approved_at=timezone.now() - timedelta(days=days_ago)
        )
        return lesson

    return make


def digest_lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "portal.digest"]


# AC-01: Approved, High-impact lessons since the last run; the run is recorded.


def test_digest_selects_new_high_impact_approved(digest_on, published):
    published(title="High one")
    published(title="Medium one", impact=Lesson.Impact.MEDIUM)
    published(title="Pending high", status=Lesson.Status.SUBMITTED)
    published(title="Old high", days_ago=30)
    call_command("send_digest")
    (message,) = mail.outbox
    assert message.to == ["all-staff@example.test"]
    assert "High one" in message.body
    for absent in ["Medium one", "Pending high", "Old high"]:
        assert absent not in message.body
    run = DigestRun.objects.get()
    assert run.lesson_count == 1


def test_digest_starts_after_last_run(digest_on, published):
    DigestRun.objects.create(run_at=timezone.now() - timedelta(days=3), lesson_count=0)
    published(title="Before last run", days_ago=5)
    published(title="After last run", days_ago=1)
    call_command("send_digest")
    assert "After last run" in mail.outbox[0].body
    assert "Before last run" not in mail.outbox[0].body


def test_digest_links_and_withholds_anonymised_projects(digest_on, published):
    lesson = published(project=Project.objects.create(name="Veiled Arena"), anonymise=True)
    call_command("send_digest")
    body = mail.outbox[0].body
    assert f"http://192.0.2.10/lessons/{lesson.pk}/" in body
    assert "Veiled Arena" not in body and Lesson.ANONYMISED_PROJECT in body
    assert mail.outbox[0].attachments == []


# AC-02: running twice in a row sends nothing the second time.


def test_second_run_sends_nothing(digest_on, published):
    published()
    call_command("send_digest")
    call_command("send_digest")
    assert len(mail.outbox) == 1


# AC-03: no new lessons -> no email, one log line.


def test_no_new_lessons_logged(digest_on, caplog):
    with caplog.at_level(logging.INFO):
        call_command("send_digest")
    assert mail.outbox == []
    (line,) = digest_lines(caplog)
    assert line.startswith("digest: no new High-impact lessons since")
    assert DigestRun.objects.count() == 1


# AC-04: EMAIL_HOST empty -> skipped and logged; the window is kept for later.


def test_skipped_without_email_host_keeps_window(settings, published, caplog):
    settings.QUALITY_ALERT_RECIPIENTS = ["all-staff@example.test"]
    published()
    with caplog.at_level(logging.INFO):
        call_command("send_digest")
    assert mail.outbox == []
    assert not DigestRun.objects.exists()
    assert any("email skipped type=digest recipients=1" in r.getMessage() for r in caplog.records)


def test_no_recipients_configured_keeps_window(settings, published):
    settings.EMAIL_HOST = "smtp.example.test"
    settings.QUALITY_ALERT_RECIPIENTS = []
    published()
    call_command("send_digest")
    assert mail.outbox == [] and not DigestRun.objects.exists()


def test_failed_send_not_recorded(digest_on, published):
    published()
    with mock.patch("core.email.send_mail", side_effect=OSError("down")):
        call_command("send_digest")
    assert not DigestRun.objects.exists()
    call_command("send_digest")  # retried next time
    assert len(mail.outbox) == 1


# AC-05: the scheduler runs it every two weeks.


def test_if_due_skips_within_interval(digest_on, published, caplog):
    DigestRun.objects.create(run_at=timezone.now() - timedelta(days=7), lesson_count=0)
    published()
    with caplog.at_level(logging.INFO):
        call_command("send_digest", "--if-due")
    assert mail.outbox == []
    assert digest_lines(caplog)[0].startswith("digest not due")


def test_if_due_sends_after_interval(digest_on, published):
    DigestRun.objects.create(
        run_at=timezone.now() - timedelta(days=14, minutes=-30), lesson_count=0
    )
    published()
    call_command("send_digest", "--if-due")
    assert len(mail.outbox) == 1


def test_if_due_sends_on_first_ever_run(digest_on, published):
    published()
    call_command("send_digest", "--if-due")
    assert len(mail.outbox) == 1


def test_scheduler_service_and_crontab():
    services = compose_services((ROOT / "docker-compose.yml").read_text())
    scheduler = "\n".join(services["scheduler"])
    assert '["supercronic", "/app/scheduler/crontab"]' in scheduler
    assert "ports:" not in scheduler and "logging: *logging" in scheduler
    crontab = (ROOT / "scheduler" / "crontab").read_text()
    jobs = [line for line in crontab.splitlines() if line and not line.startswith("#")]
    assert jobs == ["0 6 * * 1 python manage.py send_digest --if-due"]


def test_supercronic_pinned_and_checksummed():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert re.search(
        r"ADD --checksum=sha256:[0-9a-f]{64} .*\n.*supercronic/releases/download/v\d", dockerfile
    )
