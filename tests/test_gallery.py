"""Redline Gallery: Failed vs Fixed side by side (REQ-GALLERY-001)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from lessons.browse import PAGE_SIZE
from lessons.models import Lesson, LessonImage, Phase, Project

pytestmark = pytest.mark.django_db

URL = "/gallery/"


def add_image(lesson, kind):
    return LessonImage.objects.create(
        lesson=lesson, kind=kind, file=SimpleUploadedFile("x.png", b"x")
    )


@pytest.fixture
def approved_with(make_lesson):
    def make(*kinds, **fields):
        lesson = make_lesson(status=Lesson.Status.APPROVED, **fields)
        images = [add_image(lesson, kind) for kind in kinds]
        return lesson, images

    return make


# AC-01: Approved lessons with images, as a Failed/Fixed pair linking to the detail page.


def test_pair_shown_with_link(client, approved_with):
    lesson, (failed, fixed) = approved_with(LessonImage.Kind.FAILED, LessonImage.Kind.FIXED)
    body = client.get(URL).content.decode()
    assert f'href="/lessons/{lesson.pk}/"' in body
    assert body.index(failed.file.url) < body.index(fixed.file.url)  # Failed on the left


def test_lessons_without_images_omitted(client, make_lesson, approved_with):
    make_lesson(title="No pictures", status=Lesson.Status.APPROVED)
    approved_with(LessonImage.Kind.FAILED, title="Has pictures")
    body = client.get(URL).content.decode()
    assert "Has pictures" in body and "No pictures" not in body


def test_lesson_with_several_images_listed_once(client, approved_with):
    approved_with(LessonImage.Kind.FAILED, LessonImage.Kind.FAILED, LessonImage.Kind.FIXED)
    assert client.get(URL).context["page"].paginator.count == 1


# AC-02: a placeholder for a missing side.


@pytest.mark.parametrize(
    ("kind", "missing"),
    [(LessonImage.Kind.FAILED, "No Fixed image"), (LessonImage.Kind.FIXED, "No Failed image")],
)
def test_placeholder_for_missing_side(client, approved_with, kind, missing):
    approved_with(kind)
    assert missing in client.get(URL).content.decode()


# AC-03: the same validated filters as the knowledge base.


def test_filters_apply(client, approved_with):
    approved_with(LessonImage.Kind.FAILED, title="Schematic", phase=Phase.objects.get(code="SD"))
    approved_with(LessonImage.Kind.FAILED, title="Construction docs")
    titles = [
        lesson.title
        for lesson in client.get(URL, {"phase": Phase.objects.get(code="SD").pk}).context["page"]
    ]
    assert titles == ["Schematic"]


@pytest.mark.parametrize("params", [{"phase": "abc"}, {"q": "x" * 201}, {"impact": "huge"}])
def test_invalid_filters_rejected(client, params):
    assert client.get(URL, params).status_code == 400


def test_fixed_page_size(client, approved_with):
    for n in range(PAGE_SIZE + 1):
        approved_with(LessonImage.Kind.FIXED, title=f"G{n}")
    assert len(client.get(URL, {"page_size": 500}).context["page"]) == PAGE_SIZE


# AC-04: never Submitted/Rejected lessons or images; anonymised projects withheld.


@pytest.mark.parametrize("status", [Lesson.Status.SUBMITTED, Lesson.Status.REJECTED])
def test_unapproved_lessons_excluded(client, make_lesson, status):
    lesson = make_lesson(title="Unpublished", status=status)
    image = add_image(lesson, LessonImage.Kind.FAILED)
    body = client.get(URL).content.decode()
    assert "Unpublished" not in body and image.file.url not in body


def test_anonymised_project_hidden(client, approved_with):
    approved_with(
        LessonImage.Kind.FAILED, project=Project.objects.create(name="Hush Tower"), anonymise=True
    )
    body = client.get(URL).content.decode()
    assert "Hush Tower" not in body and Lesson.ANONYMISED_PROJECT in body


def test_public_get_only(client):
    assert client.get(URL).status_code == 200
    assert client.post(URL).status_code == 405


def test_search_with_several_images(client, approved_with):
    # DISTINCT plus ranking must work together in Postgres.
    approved_with(LessonImage.Kind.FAILED, LessonImage.Kind.FIXED, title="Sealant joints")
    approved_with(LessonImage.Kind.FAILED, title="Door hardware", lesson="hinges")
    titles = [lesson.title for lesson in client.get(URL, {"q": "sealant"}).context["page"]]
    assert titles == ["Sealant joints"]
