"""Demo data command (REQ-OPS-009)."""

import logging
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import Client

from lessons import demo
from lessons.models import Lesson, LessonImage, Phase, Project

pytestmark = pytest.mark.django_db


@pytest.fixture
def loaded(settings):
    settings.EMAIL_HOST = ""
    call_command("demo_data")


def audit_lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "portal.audit"]


# AC-01: 12-15 lessons across all phases and impacts, with images and a realistic mix.


def test_load_creates_showcase_mix(loaded):
    lessons = Lesson.objects.all()
    assert 12 <= lessons.count() <= 15
    assert set(lessons.values_list("phase__code", flat=True)) == set(
        Phase.objects.values_list("code", flat=True)
    )
    assert set(lessons.values_list("impact", flat=True)) == {"high", "medium", "low"}
    approved = lessons.filter(status=Lesson.Status.APPROVED)
    assert approved.count() >= 10
    assert lessons.filter(status=Lesson.Status.SUBMITTED).count() >= 1
    assert lessons.filter(status=Lesson.Status.REJECTED).count() == 1
    assert approved.filter(anonymise=True).exists()
    assert approved.filter(in_specs=True).exists()
    assert len({lesson.approved_at.date() for lesson in approved}) == approved.count()
    for lesson in lessons:
        assert sorted(lesson.images.values_list("kind", flat=True)) == ["failed", "fixed"]


def test_images_are_real_files(loaded, settings):
    image = LessonImage.objects.first()
    path = Path(settings.MEDIA_ROOT) / image.file.name
    assert path.is_file() and path.read_bytes().startswith(b"\x89PNG")


def test_demo_shows_on_public_pages_and_queue(loaded, django_user_model):
    client = Client()
    assert "Missing parapet flashing at roof edge" in client.get("/").content.decode()
    gallery = client.get("/gallery/").content.decode()
    assert "Curtain wall anchor misses slab edge" in gallery
    assert "Bike rack placed on fire route" not in gallery  # rejected
    assert "Loading dock canopy" not in client.get("/knowledge/").content.decode()  # submitted


def test_anonymised_demo_project_hidden(loaded):
    lesson = Lesson.objects.get(title="Door swing clashes with corridor handrail")
    body = Client().get(f"/lessons/{lesson.pk}/").content.decode()
    assert "Harbour View Condominiums" not in body and Lesson.ANONYMISED_PROJECT in body


# AC-02: demo users can't sign in and hold no roles.


def test_demo_users_cannot_sign_in(loaded):
    for username in [demo.DEMO_STAFF, demo.DEMO_QA]:
        user = get_user_model().objects.get(username=username)
        assert not user.has_usable_password()
        assert not user.groups.exists() and not user.is_staff
    reviewed = Lesson.objects.exclude(status=Lesson.Status.SUBMITTED)
    assert set(reviewed.values_list("reviewed_by__username", flat=True)) == {demo.DEMO_QA}


# AC-03: --remove deletes only the demo data.


def test_remove_deletes_only_demo_data(loaded, make_lesson, settings):
    real = make_lesson(title="Real lesson", project=Project.objects.get(name=demo.DEMO_PROJECTS[0]))
    keep_image = LessonImage.objects.create(lesson=real, kind="failed", file="lessons/keep.png")
    files = [
        Path(settings.MEDIA_ROOT) / i.file.name
        for i in LessonImage.objects.exclude(pk=keep_image.pk)
    ]
    call_command("demo_data", "--remove")
    assert list(Lesson.objects.values_list("title", flat=True)) == ["Real lesson"]
    assert not any(path.exists() for path in files)
    assert LessonImage.objects.get() == keep_image
    # The demo project a real lesson uses is kept; the others go.
    assert list(
        Project.objects.filter(name__in=demo.DEMO_PROJECTS).values_list("name", flat=True)
    ) == [demo.DEMO_PROJECTS[0]]
    assert not get_user_model().objects.filter(username__startswith="demo-").exists()
    assert get_user_model().objects.filter(pk=real.submitted_by_id).exists()


def test_remove_when_nothing_loaded(capsys):
    call_command("demo_data", "--remove")
    assert "Removed 0 demo lessons." in capsys.readouterr().out


def test_can_reload_after_remove(loaded):
    call_command("demo_data", "--remove")
    call_command("demo_data")
    assert Lesson.objects.count() == len(demo.LESSONS)


# AC-04: refuses while email is on, or when already loaded.


def test_refuses_while_email_is_on(settings):
    settings.EMAIL_HOST = "smtp.example.test"
    with pytest.raises(CommandError, match="EMAIL_HOST"):
        call_command("demo_data")
    assert not Lesson.objects.exists()


def test_refuses_when_already_loaded(loaded):
    with pytest.raises(CommandError, match="already loaded"):
        call_command("demo_data")
    assert Lesson.objects.count() == len(demo.LESSONS)


def test_load_is_all_or_nothing(settings, monkeypatch):
    settings.EMAIL_HOST = ""

    def broken(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(demo, "process_image", broken)
    with pytest.raises(RuntimeError):
        call_command("demo_data")
    assert not Lesson.objects.exists() and not demo.is_loaded()


def test_renamed_lookup_falls_back_to_an_active_row(settings):
    settings.EMAIL_HOST = ""
    from lessons.models import Discipline

    Discipline.objects.filter(name="Landscape").update(name="Landscape Architecture")
    call_command("demo_data")
    assert Lesson.objects.get(title="Bike rack placed on fire route").discipline.is_active


# AC-05: load and remove are audit-logged.


def test_load_and_remove_audited(settings, caplog):
    settings.EMAIL_HOST = ""
    with caplog.at_level(logging.INFO, logger="portal.audit"):
        call_command("demo_data")
        call_command("demo_data", "--remove")
    count = len(demo.LESSONS)
    assert f'event=demo_load user="-" count="{count}"' in audit_lines(caplog)
    assert f'event=demo_remove user="-" count="{count}"' in audit_lines(caplog)
