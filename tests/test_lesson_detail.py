"""Public lesson detail page (REQ-LESSON-002)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from lessons.models import Lesson, LessonImage, Project

pytestmark = pytest.mark.django_db


def url(lesson):
    return f"/lessons/{lesson.pk}/"


# AC-01: Approved lesson visible without login, with fields and images.


def test_approved_lesson_public(client, make_lesson):
    lesson = make_lesson(title="Parapet flashing", status=Lesson.Status.APPROVED)
    image = LessonImage.objects.create(
        lesson=lesson, kind=LessonImage.Kind.FAILED, file=SimpleUploadedFile("a.png", b"x")
    )
    response = client.get(url(lesson))
    body = response.content.decode()
    assert response.status_code == 200
    for text in ["Parapet flashing", "Harbour Tower", lesson.description, lesson.lesson, "Failed"]:
        assert text in body
    assert image.file.url in body


# AC-02: Submitted and Rejected lessons are 404 to anonymous users.


@pytest.mark.parametrize("status", [Lesson.Status.SUBMITTED, Lesson.Status.REJECTED])
def test_unapproved_lesson_404(client, make_lesson, status):
    assert client.get(url(make_lesson(status=status))).status_code == 404


@pytest.mark.parametrize("status", [Lesson.Status.SUBMITTED, Lesson.Status.REJECTED])
def test_unapproved_lesson_404_even_for_submitter(client, staff_member, make_lesson, status):
    # The public page only ever shows Approved lessons; submitters use My submissions.
    client.force_login(staff_member)
    assert client.get(url(make_lesson(status=status))).status_code == 404


# AC-03: anonymised lessons never show the project name.


def test_anonymised_project_name_absent(client, make_lesson):
    project = Project.objects.create(name="Secret Hospital Wing")
    lesson = make_lesson(project=project, anonymise=True, status=Lesson.Status.APPROVED)
    body = client.get(url(lesson)).content.decode()
    assert "Secret Hospital Wing" not in body
    assert Lesson.ANONYMISED_PROJECT in body


def test_public_project_property(make_lesson):
    lesson = make_lesson()
    assert lesson.public_project == "Harbour Tower"
    lesson.anonymise = True
    assert lesson.public_project == Lesson.ANONYMISED_PROJECT


# AC-04: user text is escaped.


def test_script_in_lesson_text_escaped(client, make_lesson):
    lesson = make_lesson(
        title="<script>alert(1)</script>",
        lesson="<img src=x onerror=alert(2)>",
        status=Lesson.Status.APPROVED,
    )
    body = client.get(url(lesson)).content.decode()
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert "<img src=x" not in body


# AC-05: POST returns 405.


def test_post_not_allowed(client, make_lesson):
    lesson = make_lesson(status=Lesson.Status.APPROVED)
    assert client.post(url(lesson)).status_code == 405


def test_optional_impacts_shown_when_set(client, make_lesson):
    lesson = make_lesson(cost_impact="2500.00", time_impact_days=1, status=Lesson.Status.APPROVED)
    body = client.get(url(lesson)).content.decode()
    assert "2500.00" in body and "1 day" in body
