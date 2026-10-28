"""Styled Redline Gallery (REQ-UI-005)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from lessons.browse import PAGE_SIZE
from lessons.models import Lesson, LessonImage

pytestmark = pytest.mark.django_db

URL = "/gallery/"


@pytest.fixture
def with_images(make_lesson):
    def make(*kinds, **fields):
        lesson = make_lesson(status=Lesson.Status.APPROVED, **fields)
        images = {
            kind: LessonImage.objects.create(
                lesson=lesson, kind=kind, file=SimpleUploadedFile(f"{kind}.png", b"x")
            )
            for kind in kinds
        }
        return lesson, images

    return make


# AC-01: Failed and Fixed side by side, labelled, with the title linking to the detail page.


def test_entry_pairs_labelled_images(client, with_images):
    lesson, images = with_images(LessonImage.Kind.FAILED, LessonImage.Kind.FIXED)
    body = client.get(URL).content.decode()
    assert 'class="gallery-entry"' in body
    failed = body.index('class="image-column kind-failed"')
    fixed = body.index('class="image-column kind-fixed"')
    assert body.index(images["failed"].file.url) > failed
    assert fixed > body.index(images["failed"].file.url)
    assert body.index(images["fixed"].file.url) > fixed
    assert '<h3 class="kind-label">Failed</h3>' in body
    assert '<h3 class="kind-label">Fixed</h3>' in body
    assert f'<h2><a href="/lessons/{lesson.pk}/">{lesson.title}</a></h2>' in body


# AC-02: consistent size (shared image-column styles); clicking opens the full image.


def test_images_open_full_size(client, with_images):
    _, images = with_images(LessonImage.Kind.FAILED)
    url = images["failed"].file.url
    body = client.get(URL).content.decode()
    assert f'<a href="{url}" target="_blank" rel="noopener"><img src="{url}"' in body
    assert '<div class="placeholder">No Fixed image</div>' in body


# AC-03: filters and pagination styled like the knowledge base.


def test_filters_and_pager_match_knowledge_base(client, with_images):
    for _ in range(PAGE_SIZE + 1):
        with_images(LessonImage.Kind.FAILED)
    body = client.get(URL).content.decode()
    assert '<search class="filter-panel">' in body and 'class="filter-grid"' in body
    assert '<button type="submit">Filter</button>' in body
    assert '<nav aria-label="Pages" class="pager">' in body


def test_empty_gallery_message_styled(client):
    assert '<p class="empty-state">No lessons with images' in client.get(URL).content.decode()
