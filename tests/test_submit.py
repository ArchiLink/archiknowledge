"""Lesson submission form (REQ-SUBMIT-001)."""

import io
import logging
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from PIL import Image

from core.roles import QA_GROUP, STAFF_GROUP
from lessons.models import Discipline, IssueType, Lesson, LessonImage, Phase, Project

pytestmark = pytest.mark.django_db

URL = "/submit/"


def png(name="photo.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "green").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@pytest.fixture
def staff(django_user_model):
    user = django_user_model.objects.create_user(username="sam", password="x" * 12)
    user.groups.add(Group.objects.get(name=STAFF_GROUP))
    return user


@pytest.fixture
def staff_client(client, staff):
    client.force_login(staff)
    return client


def form_data(**overrides):
    data = {
        "title": "Missing parapet flashing",
        "project": Project.objects.get_or_create(name="Harbour Tower")[0].pk,
        "phase": Phase.objects.get(code="CD").pk,
        "discipline": Discipline.objects.get(name="Architecture").pk,
        "issue_type": IssueType.objects.get(name="Omission").pk,
        "building_component": 1,
        "description": "Flashing was not detailed.",
        "lesson": "Detail parapet flashing on every roof plan.",
        "impact": "high",
        "cost_impact": "",
        "time_impact_days": "",
        "failed_images": [png()],
        "fixed_images": [png("after.png")],
    }
    data.update(overrides)
    return data


# AC-01: logged-in Staff can submit with active lookups and at least one image.


def test_staff_can_submit(staff_client, staff):
    response = staff_client.post(URL, form_data())
    lesson = Lesson.objects.get()
    assert response.status_code == 302
    assert response["Location"] == f"/submit/{lesson.pk}/done/"
    kinds = sorted(lesson.images.values_list("kind", flat=True))
    assert kinds == [LessonImage.Kind.FAILED, LessonImage.Kind.FIXED]


def test_form_page_renders(staff_client):
    body = staff_client.get(URL).content.decode()
    assert 'enctype="multipart/form-data"' in body
    assert "Failed images" in body and "Fixed images" in body


def test_only_active_lookups_offered(staff_client):
    Phase.objects.filter(code="PC").update(is_active=False)
    retired = Phase.objects.get(code="PC")
    body = staff_client.get(URL).content.decode()
    assert "Post-Construction" not in body
    assert "Construction Administration" in body
    response = staff_client.post(URL, form_data(phase=retired.pk))
    assert response.status_code == 200
    assert not Lesson.objects.exists()


def test_at_least_one_image_required(staff_client):
    response = staff_client.post(URL, form_data(failed_images=[], fixed_images=[]))
    assert response.status_code == 200
    assert "Add at least one Failed or Fixed image." in response.content.decode()
    assert not Lesson.objects.exists()


def test_qa_reviewers_can_submit_too(client, django_user_model):
    user = django_user_model.objects.create_user(username="qa", password="x" * 12)
    user.groups.add(Group.objects.get(name=QA_GROUP))
    client.force_login(user)
    assert client.post(URL, form_data()).status_code == 302


def test_user_without_role_cannot_submit(client, django_user_model):
    client.force_login(django_user_model.objects.create_user(username="x", password="x" * 12))
    assert client.get(URL).status_code == 403
    assert client.post(URL, form_data()).status_code == 403
    assert not Lesson.objects.exists()


def test_anonymous_redirected_to_login(client):
    response = client.get(URL)
    assert response.status_code == 302
    assert response["Location"].startswith("/accounts/login/")


# AC-02: status, submitter, anonymise and review fields can't be set by the client.


def test_extra_post_fields_ignored(staff_client, staff, django_user_model):
    other = django_user_model.objects.create_user(username="other", password="x" * 12)
    staff_client.post(
        URL,
        form_data(
            status="approved",
            submitted_by=other.pk,
            reviewed_by=other.pk,
            reviewed_at="2020-01-01T00:00",
            approved_at="2020-01-01T00:00",
            anonymise="on",
            in_specs="on",
        ),
    )
    lesson = Lesson.objects.get()
    assert lesson.status == Lesson.Status.SUBMITTED
    assert lesson.submitted_by == staff
    assert lesson.reviewed_by is None and lesson.reviewed_at is None
    assert lesson.approved_at is None
    assert lesson.anonymise is False and lesson.in_specs is False


# AC-03: POST without a CSRF token is rejected.


def test_post_without_csrf_rejected(staff):
    client = Client(enforce_csrf_checks=True)
    client.force_login(staff)
    assert client.post(URL, form_data()).status_code == 403
    assert not Lesson.objects.exists()


# AC-04: image rules apply; errors keep the typed text.


def test_invalid_image_rejected_and_text_kept(staff_client):
    bad = SimpleUploadedFile("photo.jpg", b"<?php echo 1; ?>")
    response = staff_client.post(URL, form_data(failed_images=[bad], title="Keep this title"))
    body = response.content.decode()
    assert response.status_code == 200
    assert "Upload a JPEG, PNG or WebP image." in body
    assert 'value="Keep this title"' in body
    assert not Lesson.objects.exists()


@override_settings(MAX_IMAGES_PER_LESSON=2)
def test_total_image_count_limited_across_both_fields(staff_client):
    response = staff_client.post(URL, form_data(failed_images=[png(), png()], fixed_images=[png()]))
    assert "at most 2 images" in response.content.decode()
    assert not Lesson.objects.exists()


def test_stored_images_are_reencoded_with_uuid_names(staff_client, media_root):
    staff_client.post(URL, form_data(failed_images=[png("../../evil name.png")], fixed_images=[]))
    image = LessonImage.objects.get()
    assert "evil" not in image.file.name
    assert (media_root / image.file.name).is_file()


# AC-05: audited; confirmation page.


def test_submission_audited(staff_client, caplog):
    with caplog.at_level(logging.INFO):
        staff_client.post(URL, form_data())
    lesson = Lesson.objects.get()
    lines = [r.getMessage() for r in caplog.records if r.name == "portal.audit"]
    assert f'event=submission user="sam" lesson_id="{lesson.pk}"' in lines


def test_confirmation_page(staff_client):
    response = staff_client.post(URL, form_data(), follow=True)
    body = response.content.decode()
    assert "has been submitted and is waiting for QA review" in body


def test_confirmation_page_only_for_own_lesson(client, staff_client, django_user_model):
    staff_client.post(URL, form_data())
    lesson = Lesson.objects.get()
    client.force_login(django_user_model.objects.create_user(username="z", password="x" * 12))
    assert client.get(f"/submit/{lesson.pk}/done/").status_code == 404


# Failure behaviour: nothing half-saved.


def test_failed_save_rolls_back_and_removes_files(staff_client, media_root):
    with mock.patch.object(LessonImage, "save", side_effect=RuntimeError("db down")):
        with pytest.raises(RuntimeError):
            staff_client.post(URL, form_data())
    assert not Lesson.objects.exists()
    lessons_dir = media_root / "lessons"
    assert not lessons_dir.exists() or not any(lessons_dir.iterdir())
