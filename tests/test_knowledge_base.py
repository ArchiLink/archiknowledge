"""Searchable, filterable knowledge base (REQ-KB-001)."""

import pytest

from lessons.browse import PAGE_SIZE
from lessons.models import Discipline, Lesson, Phase, Project

pytestmark = pytest.mark.django_db

URL = "/knowledge/"


@pytest.fixture
def approved(make_lesson):
    def make(**fields):
        return make_lesson(status=Lesson.Status.APPROVED, **fields)

    return make


def titles(response):
    return [lesson.title for lesson in response.context["page"]]


# AC-01: full-text search returns Approved lessons ranked by relevance.


def test_search_finds_stemmed_word(client, approved):
    match = approved(title="Membrane laps", description="Waterproofing membranes reversed.")
    approved(title="Door hardware", description="Schedule incomplete.", lesson="Check it.")
    assert titles(client.get(URL, {"q": "membrane"})) == [match.title]


def test_search_ranks_title_matches_first(client, approved):
    approved(title="Parapet coping", description="Sealant joints cracked.", lesson="x")
    approved(title="Sealant failure", description="See photos.", lesson="y")
    assert titles(client.get(URL, {"q": "sealant"})) == ["Sealant failure", "Parapet coping"]


def test_without_search_newest_first(client, approved):
    approved(title="First")
    approved(title="Second")
    Lesson.objects.filter(title="Second").update(approved_at="2030-01-01T00:00Z")
    Lesson.objects.filter(title="First").update(approved_at="2029-01-01T00:00Z")
    assert titles(client.get(URL)) == ["Second", "First"]


# AC-02: filters combine with search; only active lookup rows are offered.


def test_filters_combine(client, approved):
    dd = Phase.objects.get(code="DD")
    mech = Discipline.objects.get(name="Mechanical")
    approved(title="Wanted", phase=dd, discipline=mech, impact="high", lesson="duct clash")
    approved(title="Wrong phase", discipline=mech, impact="high", lesson="duct clash")
    approved(title="Wrong impact", phase=dd, discipline=mech, impact="low", lesson="duct clash")
    approved(title="Wrong words", phase=dd, discipline=mech, impact="high", lesson="paint")
    response = client.get(
        URL, {"q": "duct", "phase": dd.pk, "discipline": mech.pk, "impact": "high"}
    )
    assert titles(response) == ["Wanted"]


def test_only_active_lookup_rows_offered(client):
    Phase.objects.filter(code="PC").update(is_active=False)
    body = client.get(URL).content.decode()
    assert "Post-Construction" not in body
    assert "Schematic Design" in body


# AC-03: invalid parameters give 400, never 500.


@pytest.mark.parametrize(
    "params",
    [
        {"phase": "abc"},
        {"phase": "999999"},
        {"discipline": "-1"},
        {"impact": "catastrophic"},
        {"q": "x" * 201},
        {"q": "'; DROP TABLE lessons_lesson; --", "phase": "1 OR 1=1"},
    ],
)
def test_invalid_parameters_rejected(client, params):
    response = client.get(URL, params)
    assert response.status_code == 400
    assert "weren't valid" in response.content.decode()


def test_inactive_phase_filter_rejected(client):
    Phase.objects.filter(code="PC").update(is_active=False)
    assert client.get(URL, {"phase": Phase.objects.get(code="PC").pk}).status_code == 400


def test_search_syntax_never_errors(client, approved):
    approved()
    for q in ['"unclosed', "a & | ! b", "-", "OR OR", "(((", "x" * 200]:
        assert client.get(URL, {"q": q}).status_code == 200


# AC-04: fixed page size; page_size parameter ignored.


def test_fixed_page_size(client, approved):
    for n in range(PAGE_SIZE + 3):
        approved(title=f"Lesson {n:02}")
    first = client.get(URL, {"page_size": 1000})
    assert len(titles(first)) == PAGE_SIZE
    second = client.get(URL, {"page": 2})
    assert len(titles(second)) == 3
    assert client.get(URL, {"page": "zzz"}).status_code == 200  # bad page -> first page


def test_pagination_links_keep_filters(client, approved):
    phase = Phase.objects.get(code="CD")
    for n in range(PAGE_SIZE + 1):
        approved(title=f"L{n}", phase=phase)
    body = client.get(URL, {"phase": phase.pk}).content.decode()
    assert f"?phase={phase.pk}&amp;page=2" in body


# AC-05: never Submitted/Rejected lessons or anonymised project names.


def test_only_approved_lessons_listed(client, make_lesson):
    make_lesson(title="Published", status=Lesson.Status.APPROVED)
    make_lesson(title="Pending", status=Lesson.Status.SUBMITTED)
    make_lesson(title="Refused", status=Lesson.Status.REJECTED)
    assert titles(client.get(URL)) == ["Published"]
    assert titles(client.get(URL, {"q": "parapet"})) == ["Published"]


def test_anonymised_project_hidden_and_not_searchable(client, approved):
    secret = Project.objects.create(name="Zephyr Clinic")
    approved(title="Anon lesson", project=secret, anonymise=True)
    body = client.get(URL).content.decode()
    assert "Zephyr" not in body and Lesson.ANONYMISED_PROJECT in body
    assert titles(client.get(URL, {"q": "Zephyr"})) == []


def test_lesson_text_escaped(client, approved):
    approved(title="<b>bold</b>", lesson="<script>alert(1)</script>")
    body = client.get(URL).content.decode()
    assert "<script>alert(1)" not in body and "<b>bold</b>" not in body


# AC-06: HTMX gets just the results; the page wires up HTMX and the URL.


def test_htmx_request_gets_partial(client, approved):
    approved(title="Partial me")
    response = client.get(URL, HTTP_HX_REQUEST="true")
    body = response.content.decode()
    assert "Partial me" in body
    assert "<html" not in body
    assert "HX-Request" in response["Vary"]


def test_full_page_wires_htmx(client):
    body = client.get(URL).content.decode()
    assert 'hx-get="/knowledge/"' in body and 'hx-target="#results"' in body
    assert 'hx-push-url="true"' in body
    assert "/static/vendor/htmx/htmx-2.0.11.min.js" in body
    assert '"allowEval": false' in body


def test_public_and_get_only(client):
    assert client.get(URL).status_code == 200
    assert client.post(URL).status_code == 405
