"""Dashboard charts: Approved lessons per month and phase (REQ-FEED-002).

Only counts leave the server; no lesson text or project names. Months are based on
`submitted_at`, i.e. when the issue was logged.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime

from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

from lessons.models import Lesson, Phase

MAX_MONTHS = 36
MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


@dataclass(frozen=True)
class Period:
    start: date  # first day of the first month
    end: date  # first day of the last month
    label: str
    kind: str  # "last12", "year" or "custom"

    @property
    def months(self):
        months, current = [], self.start
        while current <= self.end:
            months.append(current)
            current = add_months(current, 1)
        return months


def add_months(day, count):
    index = day.year * 12 + day.month - 1 + count
    return date(index // 12, index % 12 + 1, 1)


def months_between(start, end):
    return (end.year - start.year) * 12 + end.month - start.month + 1


def default_period(today=None):
    this_month = (today or timezone.localdate()).replace(day=1)
    return Period(add_months(this_month, -11), this_month, "Last 12 months", "last12")


def parse_month(value):
    match = MONTH_RE.match(value or "")
    return date(int(match[1]), int(match[2]), 1) if match else None


def period_from_params(params, today=None):
    """A calendar year, a custom from/to range of up to 36 months, or the last 12 months.

    Anything invalid falls back to the default instead of raising (AC-04).
    """
    today = today or timezone.localdate()
    year = params.get("year", "")
    if year.isdigit() and 2000 <= int(year) <= today.year:
        return Period(date(int(year), 1, 1), date(int(year), 12, 1), year, "year")
    start, end = parse_month(params.get("from")), parse_month(params.get("to"))
    if start and end and start <= end and months_between(start, end) <= MAX_MONTHS:
        label = f"{start:%b %Y} – {end:%b %Y}"
        return Period(start, end, label, "custom")
    return default_period(today)


def chart_data(period):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime(period.start.year, period.start.month, 1), tz)
    after = add_months(period.end, 1)
    end = timezone.make_aware(datetime(after.year, after.month, 1), tz)

    rows = (
        Lesson.objects.approved()
        .filter(submitted_at__gte=start, submitted_at__lt=end)
        .annotate(month=TruncMonth("submitted_at"))
        .values("month", "phase_id")
        .annotate(count=Count("id"))
    )
    counts = {(row["month"].date(), row["phase_id"]): row["count"] for row in rows}

    used_phase_ids = {phase_id for _, phase_id in counts}
    phases = [p for p in Phase.objects.all() if p.is_active or p.pk in used_phase_ids]
    months = period.months
    series = [
        {
            "code": phase.code,
            "label": str(phase),
            "data": [counts.get((month, phase.pk), 0) for month in months],
        }
        for phase in phases
    ]
    totals = sorted(
        ({"code": s["code"], "label": s["label"], "count": sum(s["data"])} for s in series),
        key=lambda t: (-t["count"], t["code"]),
    )
    return {
        "months": [f"{month:%b %Y}" for month in months],
        "series": series,
        "totals": totals,
        "total": sum(t["count"] for t in totals),
    }


def chart_years(today=None):
    """Years offered in the period selector: from the first submission to this year."""
    this_year = (today or timezone.localdate()).year
    first = Lesson.objects.approved().order_by("submitted_at").first()
    first_year = timezone.localtime(first.submitted_at).year if first else this_year
    return list(range(this_year, max(first_year, 2000) - 1, -1))
