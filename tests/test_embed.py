"""Embeddable ticker for the WordPress intranet (REQ-FEED-003).

Framing headers are enforced by Caddy and tested end to end in tests/test_proxy.py
(test_embed_frameable_by_configured_origin, test_framing_denied_when_frame_ancestors_empty).
"""

import pytest

from lessons.models import Lesson, Project
from lessons.views import TICKER_SIZE

pytestmark = pytest.mark.django_db

URL = "/embed/ticker/"


# AC-01: recent Approved lessons, linking to the permalink in a new tab, no login.


def test_ticker_lists_recent_approved_lessons(client, make_lesson):
    lesson = make_lesson(title="Ticker item", status=Lesson.Status.APPROVED)
    make_lesson(title="Not yet", status=Lesson.Status.SUBMITTED)
    response = client.get(URL)
    body = response.content.decode()
    assert response.status_code == 200
    assert "Ticker item" in body and "Not yet" not in body
    assert f'href="/lessons/{lesson.pk}/" target="_blank" rel="noopener"' in body


def test_ticker_is_standalone_and_limited(client, make_lesson):
    for n in range(TICKER_SIZE + 3):
        make_lesson(title=f"T{n}", status=Lesson.Status.APPROVED)
    body = client.get(URL).content.decode()
    assert body.count("<li>") == TICKER_SIZE
    assert "Sign in" not in body  # no portal header inside the iframe


def test_ticker_refreshes_itself(client):
    body = client.get(URL).content.decode()
    assert 'hx-trigger="every 60s"' in body and 'hx-select="#ticker"' in body


# AC-02: framing is decided by Caddy; Django's own response still says DENY, which Caddy
# replaces for /embed/* only when FRAME_ANCESTORS is set.


def test_django_response_denies_framing_by_default(client):
    assert client.get(URL)["X-Frame-Options"] == "DENY"


# AC-03: anonymised lessons show no project name.


def test_anonymised_project_hidden(client, make_lesson):
    make_lesson(
        project=Project.objects.create(name="Quiet Library"),
        anonymise=True,
        status=Lesson.Status.APPROVED,
    )
    body = client.get(URL).content.decode()
    assert "Quiet Library" not in body and Lesson.ANONYMISED_PROJECT in body


def test_get_only(client):
    assert client.post(URL).status_code == 405
