import itertools

import pytest

from lessons.models import BuildingComponent, Discipline, IssueType, Lesson, Phase, Project

_counter = itertools.count(1)


@pytest.fixture(autouse=True)
def fast_password_hasher(settings):
    # Tests only: production keeps Django's default PBKDF2 hasher.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


@pytest.fixture
def error_urls(settings):
    settings.ROOT_URLCONF = "tests.error_urls"
    settings.DEBUG = False


@pytest.fixture
def staff_member(django_user_model):
    return django_user_model.objects.create_user(username="staffer", password="x" * 12)


@pytest.fixture
def make_lesson(staff_member):
    """Create a lesson with sensible defaults; override any field with keyword arguments."""

    def make(**fields):
        n = next(_counter)
        defaults = {
            "title": f"Lesson {n}",
            "description": "Roof flashing was missing at the parapet.",
            "lesson": "Detail the parapet flashing on every roof plan.",
            "project": Project.objects.get_or_create(name="Harbour Tower")[0],
            "phase": Phase.objects.get(code="CD"),
            "discipline": Discipline.objects.get(name="Architecture"),
            "issue_type": IssueType.objects.get(name="Omission"),
            "building_component": BuildingComponent.objects.get(name="Roofing"),
            "submitted_by": staff_member,
        }
        status = fields.pop("status", Lesson.Status.SUBMITTED)
        lesson = Lesson.objects.create(**{**defaults, **fields})
        if status != Lesson.Status.SUBMITTED:
            Lesson.objects.filter(pk=lesson.pk).update(status=status)
            lesson.refresh_from_db()
        return lesson

    return make
