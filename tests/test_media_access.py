"""Access check for uploaded images (REQ-MEDIA-002), at the Django level."""

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile

from core.roles import QA_GROUP
from lessons.models import Lesson, LessonImage

pytestmark = pytest.mark.django_db

URL = "/internal/media-auth/"


@pytest.fixture
def image_for(make_lesson):
    def make(status):
        lesson = make_lesson(status=status)
        return LessonImage.objects.create(
            lesson=lesson, kind=LessonImage.Kind.FAILED, file=SimpleUploadedFile("a.png", b"x")
        )

    return make


@pytest.fixture
def other_staff(django_user_model):
    return django_user_model.objects.create_user(username="other", password="x" * 12)


@pytest.fixture
def qa_reviewer(django_user_model):
    user = django_user_model.objects.create_user(username="qa", password="x" * 12)
    user.groups.add(Group.objects.get(name=QA_GROUP))
    return user


def check(client, image_or_uri, user=None):
    if user is not None:
        client.force_login(user)
    uri = image_or_uri if isinstance(image_or_uri, str) else image_or_uri.file.url
    return client.get(URL, HTTP_X_FORWARDED_URI=uri).status_code


# AC-01: Approved images are public.


def test_approved_image_public(client, image_for):
    assert check(client, image_for(Lesson.Status.APPROVED)) == 204


# AC-02: anonymous users can't see Submitted or Rejected images.


@pytest.mark.parametrize("status", [Lesson.Status.SUBMITTED, Lesson.Status.REJECTED])
def test_unapproved_image_hidden_from_anonymous(client, image_for, status):
    assert check(client, image_for(status)) == 404


# AC-03: the submitter and QA Reviewers can; other Staff can't.


@pytest.mark.parametrize("status", [Lesson.Status.SUBMITTED, Lesson.Status.REJECTED])
def test_submitter_sees_own_unapproved_image(client, image_for, staff_member, status):
    assert check(client, image_for(status), staff_member) == 204


@pytest.mark.parametrize("status", [Lesson.Status.SUBMITTED, Lesson.Status.REJECTED])
def test_qa_reviewer_sees_unapproved_image(client, image_for, qa_reviewer, status):
    assert check(client, image_for(status), qa_reviewer) == 204


@pytest.mark.parametrize("status", [Lesson.Status.SUBMITTED, Lesson.Status.REJECTED])
def test_other_staff_cannot_see_unapproved_image(client, image_for, other_staff, status):
    assert check(client, image_for(status), other_staff) == 404


def test_superuser_without_qa_group_cannot_see_unapproved_image(
    client, image_for, django_user_model
):
    admin = django_user_model.objects.create_superuser(username="root", password="x" * 12)
    assert check(client, image_for(Lesson.Status.SUBMITTED), admin) == 404


# AC-04: unknown files are 404, the same as a hidden one.


@pytest.mark.parametrize(
    "uri",
    [
        "/media/lessons/00000000000000000000000000000000.png",
        "/media/../portal/settings.py",
        "/static/admin/css/base.css",
        "",
    ],
)
def test_unknown_or_foreign_paths_404(client, uri):
    assert check(client, uri) == 404


def test_encoded_uri_and_query_string_handled(client, image_for):
    image = image_for(Lesson.Status.APPROVED)
    name = image.file.name.replace("lessons/", "lessons%2F")
    assert check(client, f"/media/{name}?v=1") == 204


# AC-05: GET only, no state change.


def test_post_not_allowed(client, image_for):
    image = image_for(Lesson.Status.APPROVED)
    response = client.post(URL, HTTP_X_FORWARDED_URI=image.file.url)
    assert response.status_code in (403, 405)  # CSRF or method check; never 2xx
