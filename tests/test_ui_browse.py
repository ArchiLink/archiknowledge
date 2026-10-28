"""Styled knowledge base and lesson detail page (REQ-UI-004)."""

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile

from core.roles import QA_GROUP
from lessons.browse import PAGE_SIZE
from lessons.models import Lesson, LessonImage, Project

pytestmark = pytest.mark.django_db

KB = "/knowledge/"


@pytest.fixture
def approved(make_lesson):
    def make(**fields):
        return make_lesson(status=Lesson.Status.APPROVED, **fields)

    return make


def add_image(lesson, kind):
    return LessonImage.objects.create(
        lesson=lesson, kind=kind, file=SimpleUploadedFile(f"{kind}.png", b"x")
    )


# AC-01: search and filters in one panel; results as cards; styled pager.


def test_search_and_filters_in_one_panel(client):
    body = client.get(KB).content.decode()
    panel = body[body.index('<search class="filter-panel">') : body.index("</search>")]
    assert 'class="filter-search"' in panel and 'name="q"' in panel
    assert 'class="filter-grid"' in panel
    for name in ["phase", "discipline", "issue_type", "building_component", "impact"]:
        assert f'name="{name}"' in panel


def test_results_are_lesson_cards(client, approved):
    approved(title="Card me")
    body = client.get(KB).content.decode()
    assert 'class="result-count"><strong>1</strong> lesson<' in body
    assert 'class="lesson-card"' in body and "Card me" in body


def test_no_results_message_styled(client):
    assert '<p class="empty-state">No lessons match' in client.get(KB).content.decode()


def test_pager_styled(client, approved):
    for _ in range(PAGE_SIZE + 1):
        approved()
    body = client.get(KB).content.decode()
    assert '<nav aria-label="Pages" class="pager">' in body
    assert 'role="button" class="secondary outline">Next</a>' in body


# AC-02: detail page shows badges, facts, labelled Failed and Fixed images; anonymised stays hidden.


def test_detail_layout(client, approved):
    lesson = approved(impact=Lesson.Impact.HIGH)
    add_image(lesson, LessonImage.Kind.FIXED)
    add_image(lesson, LessonImage.Kind.FAILED)
    body = client.get(f"/lessons/{lesson.pk}/").content.decode()
    assert '<span class="badge impact-high">High impact</span>' in body
    assert '<dl class="facts">' in body and "<dt>Building component</dt>" in body
    assert '<p class="lesson-callout">' in body
    failed = body.index('class="image-column kind-failed"')
    fixed = body.index('class="image-column kind-fixed"')
    assert failed < fixed  # Failed on the left, Fixed on the right
    assert '<h2 class="kind-label">Failed</h2>' in body
    assert '<h2 class="kind-label">Fixed</h2>' in body


def test_detail_without_images_has_no_image_section(client, approved):
    lesson = approved()
    assert 'class="image-pair"' not in client.get(f"/lessons/{lesson.pk}/").content.decode()


def test_detail_hides_anonymised_project(client, approved):
    lesson = approved(project=Project.objects.create(name="Quiet Quay"), anonymise=True)
    body = client.get(f"/lessons/{lesson.pk}/").content.decode()
    assert "Quiet Quay" not in body and Lesson.ANONYMISED_PROJECT in body


def test_incorporation_checklist_and_inline_checkboxes(client, approved, django_user_model):
    lesson = approved(in_specs=True)
    qa = django_user_model.objects.create_user(username="quinn", password="x" * 12)
    qa.groups.add(Group.objects.get(name=QA_GROUP))
    client.force_login(qa)
    body = client.get(f"/lessons/{lesson.pk}/").content.decode()
    assert '<li class="done">Specifications: Yes</li>' in body
    assert '<li class="todo">Onboarding: Not yet</li>' in body
    assert '<label><input type="checkbox" name="in_specs"' in body


# AC-03: HTMX filtering keeps working with the new markup.


def test_htmx_form_and_partial(client, approved):
    approved(title="Live result")
    body = client.get(KB).content.decode()
    assert 'hx-get="/knowledge/" hx-target="#results"' in body
    partial = client.get(KB, {"q": "Live"}, HTTP_HX_REQUEST="true").content.decode()
    assert 'class="lesson-card"' in partial and "<html" not in partial
