"""Dashboard charts by month and phase (REQ-FEED-002)."""

import json
import re
from datetime import date, datetime

import pytest
from django.utils import timezone

from lessons.charts import chart_data, chart_years, default_period, period_from_params
from lessons.models import Lesson, Phase, Project

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 27)


@pytest.fixture
def lesson_in(make_lesson):
    def make(year, month, phase="CD", status=Lesson.Status.APPROVED, **fields):
        lesson = make_lesson(status=status, phase=Phase.objects.get(code=phase), **fields)
        when = timezone.make_aware(datetime(year, month, 15, 12))
        Lesson.objects.filter(pk=lesson.pk).update(submitted_at=when)
        return lesson

    return make


def series(data, code):
    return next(s for s in data["series"] if s["code"] == code)["data"]


# AC-01: stacked counts per month and phase, by submission month, zero months included.


def test_counts_per_month_and_phase(lesson_in):
    lesson_in(2026, 1, "SD")
    lesson_in(2026, 1, "SD")
    lesson_in(2026, 1, "CD")
    lesson_in(2026, 3, "CD")
    data = chart_data(period_from_params({"year": "2026"}, TODAY))
    assert data["months"][:3] == ["Jan 2026", "Feb 2026", "Mar 2026"]
    assert len(data["months"]) == 12
    assert series(data, "SD")[:3] == [2, 0, 0]
    assert series(data, "CD")[:3] == [1, 0, 1]
    assert data["total"] == 4


def test_one_series_per_active_phase(lesson_in):
    Phase.objects.filter(code="PC").update(is_active=False)
    data = chart_data(default_period(TODAY))
    assert [s["code"] for s in data["series"]] == ["SD", "DD", "CD", "TA", "CA"]


def test_inactive_phase_with_data_still_shown(lesson_in):
    lesson_in(2026, 5, "PC")
    Phase.objects.filter(code="PC").update(is_active=False)
    data = chart_data(period_from_params({"year": "2026"}, TODAY))
    assert sum(series(data, "PC")) == 1


def test_only_approved_lessons_counted(lesson_in):
    lesson_in(2026, 2, status=Lesson.Status.APPROVED)
    lesson_in(2026, 2, status=Lesson.Status.SUBMITTED)
    lesson_in(2026, 2, status=Lesson.Status.REJECTED)
    assert chart_data(period_from_params({"year": "2026"}, TODAY))["total"] == 1


def test_lessons_outside_period_excluded(lesson_in):
    lesson_in(2025, 12)
    lesson_in(2027, 1)
    assert chart_data(period_from_params({"year": "2026"}, TODAY))["total"] == 0


# AC-02: totals per phase, highest first.


def test_totals_sorted_highest_first(lesson_in):
    lesson_in(2026, 4, "DD")
    lesson_in(2026, 5, "CA")
    lesson_in(2026, 6, "CA")
    totals = chart_data(period_from_params({"year": "2026"}, TODAY))["totals"]
    assert [(t["code"], t["count"]) for t in totals[:2]] == [("CA", 2), ("DD", 1)]


# AC-03: last 12 months (default), a calendar year, or a custom range of up to 36 months.


def test_default_is_last_twelve_months():
    period = period_from_params({}, TODAY)
    assert (period.start, period.end, period.kind) == (
        date(2025, 11, 1),
        date(2026, 10, 1),
        "last12",
    )
    assert len(period.months) == 12


def test_calendar_year():
    period = period_from_params({"year": "2025"}, TODAY)
    assert (period.start, period.end) == (date(2025, 1, 1), date(2025, 12, 1))


def test_custom_range():
    period = period_from_params({"from": "2024-03", "to": "2025-02"}, TODAY)
    assert (period.start, period.end, period.kind) == (date(2024, 3, 1), date(2025, 2, 1), "custom")
    assert period.label == "Mar 2024 – Feb 2025"


def test_custom_range_of_exactly_36_months_allowed():
    period = period_from_params({"from": "2023-01", "to": "2025-12"}, TODAY)
    assert period.kind == "custom" and len(period.months) == 36


# AC-04: invalid or out-of-range periods fall back to the default.


@pytest.mark.parametrize(
    "params",
    [
        {"year": "1999"},
        {"year": "2027"},
        {"year": "abc"},
        {"from": "2023-01", "to": "2026-01"},  # 37 months
        {"from": "2026-05", "to": "2026-01"},  # backwards
        {"from": "2026-13", "to": "2026-14"},
        {"from": "2026-1", "to": "2026-2"},
        {"from": "'; DROP TABLE x; --", "to": "2026-02"},
    ],
)
def test_invalid_period_falls_back(params):
    assert period_from_params(params, TODAY) == default_period(TODAY)


@pytest.mark.parametrize("query", ["?year=abc", "?from=x&to=y", "?from=1900-01&to=2900-01"])
def test_dashboard_never_errors_on_bad_period(client, query):
    response = client.get("/" + query)
    assert response.status_code == 200
    assert "Last 12 months" in response.content.decode()


# AC-05 and AC-06: data via json_script, no inline code, counts only.


def test_chart_data_in_json_script(client, lesson_in):
    secret = Project.objects.create(name="Do Not Leak")
    lesson_in(2026, 9, title="Secret title text", project=secret)
    body = client.get("/").content.decode()
    match = re.search(r'<script id="chart-data" type="application/json">(.*?)</script>', body)
    data = json.loads(match[1])
    assert set(data) == {"months", "series", "totals", "total"}
    payload = match[1]
    assert "Secret title text" not in payload and "Do Not Leak" not in payload


def test_no_inline_scripts(client):
    body = client.get("/").content.decode()
    for tag in re.findall(r"<script[^>]*>", body):
        assert "src=" in tag or 'type="application/json"' in tag, tag


# AC-07: Chart.js vendored.


def test_chartjs_loaded_from_static(client):
    body = client.get("/").content.decode()
    assert "/static/vendor/chartjs/chart-4.5.1.umd.min.js" in body
    assert "/static/js/charts.js" in body


def test_period_form_and_table(client, lesson_in):
    lesson_in(2026, 9, "SD")
    body = client.get("/", {"year": "2026", "phase": "SD"}).content.decode()
    assert '<option value="2026" selected>' in body
    assert '<input type="hidden" name="phase" value="SD">' in body
    assert "<td>SD – Schematic Design</td><td>1</td>" in body


def test_chart_years_start_at_first_lesson(lesson_in):
    lesson_in(2024, 6)
    assert chart_years(TODAY) == [2026, 2025, 2024]
