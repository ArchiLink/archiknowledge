"""Styled Staff and QA pages (REQ-UI-006)."""

import re

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from core.roles import QA_GROUP, STAFF_GROUP
from lessons.models import Lesson, LessonImage

pytestmark = pytest.mark.django_db


def signed_in(django_user_model, username, group):
    user = django_user_model.objects.create_user(username=username, password="x" * 12)
    user.groups.add(Group.objects.get(name=group))
    client = Client()
    client.force_login(user)
    return client, user


@pytest.fixture
def staff(django_user_model):
    return signed_in(django_user_model, "sam", STAFF_GROUP)


@pytest.fixture
def qa(django_user_model):
    return signed_in(django_user_model, "quinn", QA_GROUP)


# AC-01: the submission form groups fields, with help text and errors beside each field.


def test_submit_form_sections(staff):
    client, _ = staff
    body = client.get("/submit/").content.decode()
    legends = re.findall(r"<legend>(.*?)</legend>", body)
    assert legends == ["The lesson", "Classification", "Impact", "Images"]
    assert '<span class="required" aria-hidden="true">*</span>' in body
    assert 'id="id_description_helptext"' in body
    assert 'class="field upload kind-failed"' in body and 'class="field upload kind-fixed"' in body


def test_field_errors_shown_beside_fields(staff):
    client, _ = staff
    body = client.post("/submit/", {"title": "Only a title"}).content.decode()
    assert '<small class="field-error">This field is required.</small>' in body
    assert 'aria-invalid="true"' in body
    assert '<div role="alert"><p>Add at least one Failed or Fixed image.</p></div>' in body
    assert 'value="Only a title"' in body


def test_submit_done_has_next_steps(staff, make_lesson):
    client, user = staff
    lesson = make_lesson(submitted_by=user)
    body = client.get(f"/submit/{lesson.pk}/done/").content.decode()
    assert 'class="narrow-card success-card"' in body
    assert 'href="/my-submissions/" role="button"' in body


# AC-02: My submissions and the review queue are styled tables with status badges.


@pytest.mark.parametrize("status", [choice.value for choice in Lesson.Status])
def test_my_submissions_status_badges(staff, make_lesson, status):
    client, user = staff
    lesson = make_lesson(submitted_by=user, status=status)
    body = client.get("/my-submissions/").content.decode()
    assert '<div class="table-card">' in body
    assert f'<span class="badge status-{status}">{lesson.get_status_display()}</span>' in body


def test_my_submission_detail_uses_layout(staff, make_lesson):
    client, user = staff
    lesson = make_lesson(submitted_by=user)
    LessonImage.objects.create(lesson=lesson, kind="failed", file=SimpleUploadedFile("a.png", b"x"))
    body = client.get(f"/my-submissions/{lesson.pk}/").content.decode()
    assert '<span class="badge status-submitted">Submitted</span>' in body
    assert 'class="image-column kind-failed"' in body and '<dl class="facts">' in body


def test_review_queue_table(qa, make_lesson):
    client, _ = qa
    lesson = make_lesson()
    body = client.get("/review/").content.decode()
    assert '<div class="table-card">' in body
    assert (
        f'<a href="/review/{lesson.pk}/" role="button" class="secondary outline">Review</a>' in body
    )


def test_empty_queue_styled(qa):
    client, _ = qa
    assert '<p class="empty-state">Nothing is waiting' in client.get("/review/").content.decode()


# AC-03: the review page shows the lesson beside the form, with distinct actions; CSV is a button.


def test_review_page_layout_and_actions(qa, make_lesson):
    client, _ = qa
    lesson = make_lesson()
    LessonImage.objects.create(lesson=lesson, kind="fixed", file=SimpleUploadedFile("b.png", b"x"))
    body = client.get(f"/review/{lesson.pk}/").content.decode()
    assert body.index('<div class="review-grid">') < body.index('class="review-images"')
    assert 'class="image-column kind-fixed"' in body
    for value, css in [("save", "secondary outline"), ("reject", "reject"), ("approve", "approve")]:
        assert f'name="action" value="{value}" class="{css}"' in body
    assert '<label class="checkbox-field"><input type="checkbox" name="anonymise"' in body


def test_review_page_without_images(qa, make_lesson):
    client, _ = qa
    lesson = make_lesson()
    assert "No images were uploaded." in client.get(f"/review/{lesson.pk}/").content.decode()


def test_csv_export_is_inline_button(qa):
    client, _ = qa
    body = client.get("/review/").content.decode()
    assert 'action="/review/export.csv" class="inline-form"' in body
    assert '<button type="submit" class="secondary outline">Download CSV</button>' in body


# AC-04: CSRF tokens and the HTMX header still reach the forms.


def test_csrf_present_on_staff_and_qa_forms(staff, qa, make_lesson):
    staff_client, _ = staff
    qa_client, _ = qa
    lesson = make_lesson()
    for client, url in [(staff_client, "/submit/"), (qa_client, f"/review/{lesson.pk}/")]:
        body = client.get(url).content.decode()
        assert 'name="csrfmiddlewaretoken"' in body
        assert 'hx-headers=\'{"X-CSRFToken": "' in body
