"""Styled dashboard feed, charts and embed ticker (REQ-UI-003)."""

import re
from pathlib import Path

import pytest

from lessons.models import Lesson

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parent.parent


# AC-01: lessons render as cards with phase, impact and date badges; phase filter as tabs.


@pytest.mark.parametrize("impact", [choice.value for choice in Lesson.Impact])
def test_feed_card_has_badges(client, make_lesson, impact):
    lesson = make_lesson(status=Lesson.Status.APPROVED, impact=impact)
    body = client.get("/").content.decode()
    assert 'class="lesson-card"' in body
    label = lesson.get_impact_display()
    assert f'<span class="badge impact-{impact}">{label} impact</span>' in body
    assert f'class="badge badge-phase" title="{lesson.phase.name}">{lesson.phase.code}' in body
    assert "<time datetime=" in body


def test_phase_filter_is_tabs(client):
    body = client.get("/").content.decode()
    assert '<nav aria-label="Filter by phase" class="phase-tabs">' in body


def test_empty_feed_message_styled(client):
    assert 'class="empty-state"' in client.get("/").content.decode()


# AC-02: charts sit in panels beside the feed, in the validated palette without the brand red.


def test_charts_in_panels_beside_feed(client):
    body = client.get("/").content.decode()
    grid = body.index('class="dashboard-grid"')
    assert grid < body.index('id="feed"') < body.index('class="insights"')
    for canvas in ("chart-by-month", "chart-by-phase"):
        panel_start = body.rindex('<article class="panel">', 0, body.index(canvas))
        assert body.index(canvas) > panel_start


def test_chart_palette_avoids_brand_red():
    script = (ROOT / "static" / "js" / "charts.js").read_text(encoding="utf-8")
    palette = re.search(r"var palette = \[(.*?)\];", script).group(1).lower()
    assert "#d22930" not in palette and "#e34948" not in palette
    assert len(re.findall(r"#[0-9a-f]{6}", palette)) >= 6  # one colour per seeded phase


# AC-03: the ticker uses the theme and a compact branded header.


def test_ticker_uses_theme(client, make_lesson):
    make_lesson(status=Lesson.Status.APPROVED)
    body = client.get("/embed/ticker/").content.decode()
    assert "css/portal.css" in body and 'class="ticker"' in body
    assert 'class="ticker-head"' in body and "architecttura-logo.png" in body
    assert 'class="badge badge-phase"' in body
    assert 'class="site-header"' not in body


# AC-04: the HTMX partial keeps returning bare cards.


def test_feed_partial_returns_cards_only(client, make_lesson):
    make_lesson(status=Lesson.Status.APPROVED)
    body = client.get("/feed/").content.decode()
    assert 'class="lesson-card"' in body and "<html" not in body
