"""My submissions list (REQ-SUBMIT-002)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from lessons.models import Lesson, LessonImage

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_user(django_user_model):
    return django_user_model.objects.create_user(username="other", password="x" * 12)


# AC-01: the list shows only the current user's lessons, with status and dates.


def test_list_shows_only_own_lessons(client, staff_member, other_user, make_lesson):
    mine = make_lesson(title="My roof lesson", status=Lesson.Status.APPROVED)
    make_lesson(title="Someone else's lesson", submitted_by=other_user)
    client.force_login(staff_member)
    body = client.get("/my-submissions/").content.decode()
    assert "My roof lesson" in body
    assert "Someone else" not in body
    assert "Approved" in body
    assert mine.submitted_at.strftime("%Y") in body


def test_list_shows_every_status(client, staff_member, make_lesson):
    for status in Lesson.Status:
        make_lesson(title=f"{status.label} one", status=status)
    client.force_login(staff_member)
    body = client.get("/my-submissions/").content.decode()
    for status in Lesson.Status:
        assert f"{status.label} one" in body


def test_empty_list(client, staff_member):
    client.force_login(staff_member)
    assert (
        "You haven't submitted any lessons yet." in client.get("/my-submissions/").content.decode()
    )


def test_own_detail_shows_lesson_and_images(client, staff_member, make_lesson):
    lesson = make_lesson(title="Detail me")
    image = LessonImage.objects.create(
        lesson=lesson, kind=LessonImage.Kind.FIXED, file=SimpleUploadedFile("a.png", b"x")
    )
    client.force_login(staff_member)
    body = client.get(f"/my-submissions/{lesson.pk}/").content.decode()
    assert "Detail me" in body and "Submitted" in body
    assert image.file.url in body


def test_confirmation_page_links_to_my_submissions(client, staff_member, make_lesson):
    lesson = make_lesson()
    client.force_login(staff_member)
    assert 'href="/my-submissions/"' in client.get(f"/submit/{lesson.pk}/done/").content.decode()


# AC-02: another user's lesson by ID is a 404.


@pytest.mark.parametrize("status", list(Lesson.Status))
def test_other_users_lesson_is_404(client, other_user, make_lesson, status):
    lesson = make_lesson(status=status)
    client.force_login(other_user)
    assert client.get(f"/my-submissions/{lesson.pk}/").status_code == 404


def test_missing_lesson_is_404(client, staff_member):
    client.force_login(staff_member)
    assert client.get("/my-submissions/999999/").status_code == 404


# AC-03: anonymous users are redirected to login.


@pytest.mark.parametrize("url", ["/my-submissions/", "/my-submissions/1/"])
def test_anonymous_redirected(client, url):
    response = client.get(url)
    assert response.status_code == 302
    assert response["Location"].startswith("/accounts/login/")


def test_post_not_allowed(client, staff_member):
    client.force_login(staff_member)
    assert client.post("/my-submissions/").status_code == 405
