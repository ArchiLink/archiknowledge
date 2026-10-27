"""CSV export for QA Reviewers (REQ-REVIEW-003)."""

import csv

from django import forms
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone

from lessons.models import Lesson, Phase

# Spreadsheet apps treat these leading characters as a formula (CWE-1236). SECURITY.md names
# the first four; tab and carriage return are also recommended by OWASP.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

COLUMNS = [
    ("ID", lambda lesson, request: lesson.pk),
    ("Title", lambda lesson, request: lesson.title),
    ("Status", lambda lesson, request: lesson.get_status_display()),
    ("Project", lambda lesson, request: lesson.public_project),
    ("Phase", lambda lesson, request: lesson.phase.code),
    ("Discipline", lambda lesson, request: lesson.discipline.name),
    ("Issue type", lambda lesson, request: lesson.issue_type.name),
    ("Building component", lambda lesson, request: lesson.building_component.name),
    ("Impact", lambda lesson, request: lesson.get_impact_display()),
    ("Cost impact", lambda lesson, request: lesson.cost_impact),
    ("Time impact (days)", lambda lesson, request: lesson.time_impact_days),
    ("What happened", lambda lesson, request: lesson.description),
    ("Lesson", lambda lesson, request: lesson.lesson),
    ("Submitted by", lambda lesson, request: lesson.submitted_by.get_username()),
    ("Submitted", lambda lesson, request: lesson.submitted_at),
    (
        "Reviewed by",
        lambda lesson, request: lesson.reviewed_by.get_username() if lesson.reviewed_by else "",
    ),
    ("Reviewed", lambda lesson, request: lesson.reviewed_at),
    ("Published", lambda lesson, request: lesson.approved_at),
    ("In specs", lambda lesson, request: lesson.in_specs),
    ("In standard details", lambda lesson, request: lesson.in_standard_details),
    ("In onboarding", lambda lesson, request: lesson.in_onboarding),
    (
        "Link",
        lambda lesson, request: (
            request.build_absolute_uri(reverse("lesson_detail", args=[lesson.pk]))
            if lesson.status == Lesson.Status.APPROVED
            else ""
        ),
    ),
]


def safe_cell(value):
    if value is None:
        return ""
    text = str(value)
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text


class ExportFilterForm(forms.Form):
    status = forms.ChoiceField(choices=[("", "Any"), *Lesson.Status.choices], required=False)
    phase = forms.ModelChoiceField(queryset=Phase.objects.all(), required=False)

    def lessons(self):
        queryset = Lesson.objects.select_related(
            "project",
            "phase",
            "discipline",
            "issue_type",
            "building_component",
            "submitted_by",
            "reviewed_by",
        ).order_by("pk")
        if self.cleaned_data.get("status"):
            queryset = queryset.filter(status=self.cleaned_data["status"])
        if self.cleaned_data.get("phase"):
            queryset = queryset.filter(phase=self.cleaned_data["phase"])
        return queryset


def csv_response(lessons, request):
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="lessons-{stamp}.csv"'
    response.write("﻿")  # BOM so Excel opens UTF-8 correctly
    writer = csv.writer(response)
    writer.writerow([name for name, _ in COLUMNS])
    count = 0
    for lesson in lessons:
        writer.writerow([safe_cell(get(lesson, request)) for _, get in COLUMNS])
        count += 1
    return response, count
