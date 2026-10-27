"""Dashboard live feed by phase (REQ-FEED-001)."""

import pytest

from lessons.browse import FEED_SIZE
from lessons.models import Lesson, Phase, Project

pytestmark = pytest.mark.django_db


@pytest.fixture
def approved(make_lesson):
    def make(**fields):
        return make_lesson(status=Lesson.Status.APPROVED, **fields)

    return make


def titles(response):
    return [lesson.title for lesson in response.context["lessons"]]


# AC-01: dashboard shows the latest Approved lessons with a phase filter, no login.


def test_dashboard_lists_latest_approved(client, approved, make_lesson):
    approved(title="Older")
    approved(title="Newer")
    Lesson.objects.filter(title="Older").update(approved_at="2029-01-01T00:00Z")
    Lesson.objects.filter(title="Newer").update(approved_at="2030-01-01T00:00Z")
    make_lesson(title="Pending")
    response = client.get("/")
    assert response.status_code == 200
    assert titles(response) == ["Newer", "Older"]


def test_phase_filter(client, approved):
    sd = Phase.objects.get(code="SD")
    approved(title="Schematic one", phase=sd)
    approved(title="CD one")
    assert titles(client.get("/", {"phase": "SD"})) == ["Schematic one"]
    assert titles(client.get("/", {"phase": "sd"})) == ["Schematic one"]  # case-insensitive


def test_phase_links_for_active_phases(client):
    Phase.objects.filter(code="PC").update(is_active=False)
    body = client.get("/").content.decode()
    assert 'href="?phase=SD"' in body
    assert 'href="?phase=PC"' not in body


def test_feed_size_limited(client, approved):
    for n in range(FEED_SIZE + 2):
        approved(title=f"L{n}")
    assert len(titles(client.get("/"))) == FEED_SIZE


# AC-02: the feed partial re-polls every 30 s and returns Approved lessons only.


def test_dashboard_polls_feed_every_30_seconds(client):
    body = client.get("/", {"phase": "DD"}).content.decode()
    assert 'hx-get="/feed/?phase=DD"' in body
    assert 'hx-trigger="every 30s"' in body


def test_feed_partial_is_fragment_with_approved_only(client, approved, make_lesson):
    approved(title="Live")
    make_lesson(title="Hidden", status=Lesson.Status.SUBMITTED)
    make_lesson(title="Refused", status=Lesson.Status.REJECTED)
    response = client.get("/feed/")
    body = response.content.decode()
    assert response.status_code == 200
    assert "<html" not in body
    assert "Live" in body and "Hidden" not in body and "Refused" not in body


# AC-03: unknown or over-long phase -> 400, never 500.


@pytest.mark.parametrize("value", ["ZZ", "x" * 11, "1 OR 1=1", "<script>"])
@pytest.mark.parametrize("url", ["/", "/feed/"])
def test_invalid_phase_rejected(client, url, value):
    assert client.get(url, {"phase": value}).status_code == 400


def test_inactive_phase_rejected(client):
    Phase.objects.filter(code="PC").update(is_active=False)
    assert client.get("/feed/", {"phase": "PC"}).status_code == 400


# AC-04: anonymised lessons show no project name.


def test_anonymised_project_hidden(client, approved):
    approved(project=Project.objects.create(name="Hidden Hall"), anonymise=True)
    for url in ["/", "/feed/"]:
        body = client.get(url).content.decode()
        assert "Hidden Hall" not in body and Lesson.ANONYMISED_PROJECT in body


# AC-05: HTMX is vendored (no CDN).


def test_htmx_loaded_from_static(client):
    body = client.get("/").content.decode()
    assert '<script src="/static/vendor/htmx/htmx-2.0.11.min.js"' in body
    assert "cdn" not in body.lower() and "unpkg" not in body.lower()


def test_get_only(client):
    assert client.post("/").status_code == 405
    assert client.post("/feed/").status_code == 405


def test_empty_feed_message(client):
    assert (
        "No lessons published for Schematic Design yet."
        in client.get("/feed/", {"phase": "SD"}).content.decode()
    )
