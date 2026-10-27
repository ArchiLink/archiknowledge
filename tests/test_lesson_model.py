"""Lesson and LessonImage data model (REQ-LESSON-001)."""

import re

import pytest
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import F, ProtectedError
from django.forms import modelform_factory

from lessons.models import Lesson, LessonImage, Phase

pytestmark = pytest.mark.django_db

PROTECTED_FIELDS = {"status", "submitted_by", "reviewed_by", "reviewed_at", "approved_at"}


# AC-01: fields and defaults.


def test_lesson_fields_and_defaults(make_lesson):
    lesson = make_lesson(cost_impact="1250.50", time_impact_days=3)
    lesson.refresh_from_db()
    assert lesson.status == Lesson.Status.SUBMITTED
    assert lesson.impact == Lesson.Impact.MEDIUM
    assert lesson.anonymise is False
    assert not (lesson.in_specs or lesson.in_standard_details or lesson.in_onboarding)
    assert lesson.submitted_at is not None
    assert lesson.reviewed_by is None and lesson.reviewed_at is None and lesson.approved_at is None
    assert str(lesson.cost_impact) == "1250.50"
    assert str(lesson) == lesson.title


def test_impact_levels():
    assert Lesson.Impact.values == ["high", "medium", "low"]


def test_workflow_fields_not_editable_through_forms():
    form_class = modelform_factory(Lesson, fields="__all__")
    assert PROTECTED_FIELDS.isdisjoint(form_class.base_fields)
    assert "search_vector" not in form_class.base_fields


def test_lookup_rows_in_use_cannot_be_deleted(make_lesson):
    lesson = make_lesson()
    with pytest.raises(ProtectedError):
        Phase.objects.filter(pk=lesson.phase_id).delete()


# AC-02: LessonImage kind and UUID file names.


@pytest.mark.parametrize(
    ("client_name", "suffix"),
    [("site photo.JPG", ".jpg"), ("../../etc/passwd.png", ".png"), ("shell.php", "")],
)
def test_image_stored_under_uuid_name(make_lesson, client_name, suffix):
    image = LessonImage.objects.create(
        lesson=make_lesson(),
        kind=LessonImage.Kind.FAILED,
        file=SimpleUploadedFile(client_name, b"not checked until REQ-MEDIA-001"),
    )
    assert re.fullmatch(rf"lessons/[0-9a-f]{{32}}{re.escape(suffix)}", image.file.name)


def test_images_cascade_with_lesson(make_lesson):
    lesson = make_lesson()
    LessonImage.objects.create(
        lesson=lesson, kind=LessonImage.Kind.FIXED, file=SimpleUploadedFile("a.png", b"x")
    )
    lesson.delete()
    assert not LessonImage.objects.exists()


# AC-03: indexed full-text search over the lesson text.


def test_full_text_search_finds_stemmed_words(make_lesson):
    match = make_lesson(description="The waterproofing membranes were lapped the wrong way.")
    make_lesson(description="Door hardware schedule was incomplete.", title="Hardware")
    found = Lesson.objects.filter(search_vector=SearchQuery("membrane", config="english"))
    assert list(found) == [match]


def test_title_matches_rank_first(make_lesson):
    in_body = make_lesson(title="Parapet coping", description="Check the sealant joints.")
    in_title = make_lesson(title="Sealant failure at windows", description="See photos.")
    query = SearchQuery("sealant", config="english")
    ranked = (
        Lesson.objects.filter(search_vector=query)
        .annotate(rank=SearchRank(F("search_vector"), query))
        .order_by("-rank")
    )
    assert list(ranked) == [in_title, in_body]


def test_search_vector_updates_on_edit(make_lesson):
    lesson = make_lesson()
    lesson.lesson = "Coordinate sprinkler heads with ceiling grid."
    lesson.save()
    assert Lesson.objects.filter(search_vector=SearchQuery("sprinkler")).exists()


# AC-04: approved() returns Approved lessons only.


def test_approved_returns_only_approved(make_lesson):
    approved = make_lesson(status=Lesson.Status.APPROVED)
    make_lesson(status=Lesson.Status.SUBMITTED)
    make_lesson(status=Lesson.Status.REJECTED)
    assert list(Lesson.objects.approved()) == [approved]
