"""CSV export for QA Reviewers (REQ-REVIEW-003)."""

import csv
import io
import logging

import pytest
from django.contrib.auth.models import Group

from core.roles import QA_GROUP
from lessons.export import safe_cell
from lessons.models import Lesson, Phase, Project

pytestmark = pytest.mark.django_db

URL = "/review/export.csv"


@pytest.fixture
def qa_client(client, django_user_model):
    user = django_user_model.objects.create_user(username="quinn", password="x" * 12)
    user.groups.add(Group.objects.get(name=QA_GROUP))
    client.force_login(user)
    return client


def rows(response):
    text = response.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


# AC-01: QA downloads a CSV, filterable by status and phase.


def test_qa_downloads_csv(qa_client, make_lesson):
    lesson = make_lesson(title="Exported", status=Lesson.Status.APPROVED, cost_impact="12.50")
    response = qa_client.get(URL)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert response["Content-Disposition"].startswith('attachment; filename="lessons-')
    (row,) = rows(response)
    assert row["ID"] == str(lesson.pk) and row["Title"] == "Exported"
    assert row["Status"] == "Approved" and row["Phase"] == "CD"
    assert row["Cost impact"] == "12.50"
    assert row["Link"] == f"http://testserver/lessons/{lesson.pk}/"


def test_filter_by_status_and_phase(qa_client, make_lesson):
    dd = Phase.objects.get(code="DD")
    make_lesson(title="A", status=Lesson.Status.APPROVED, phase=dd)
    make_lesson(title="B", status=Lesson.Status.SUBMITTED, phase=dd)
    make_lesson(title="C", status=Lesson.Status.APPROVED)
    titles = [r["Title"] for r in rows(qa_client.get(URL, {"status": "approved", "phase": dd.pk}))]
    assert titles == ["A"]
    assert len(rows(qa_client.get(URL))) == 3


def test_unpublished_lessons_have_no_link(qa_client, make_lesson):
    make_lesson()
    assert rows(qa_client.get(URL))[0]["Link"] == ""


@pytest.mark.parametrize("params", [{"status": "deleted"}, {"phase": "abc"}])
def test_invalid_filters_rejected(qa_client, params):
    assert qa_client.get(URL, params).status_code == 400


def test_queue_page_links_to_export(qa_client):
    assert 'action="/review/export.csv"' in qa_client.get("/review/").content.decode()


# AC-02: formula injection blocked.


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ('=HYPERLINK("http://x")', '\'=HYPERLINK("http://x")'),
        ("+1+1", "'+1+1"),
        ("-2+3", "'-2+3"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("\t=1", "'\t=1"),
        ("Normal title", "Normal title"),
        (None, ""),
        (42, "42"),
    ],
)
def test_safe_cell(value, expected):
    assert safe_cell(value) == expected


def test_formula_title_escaped_in_export(qa_client, make_lesson):
    make_lesson(title='=HYPERLINK("http://x")', lesson="@cmd")
    (row,) = rows(qa_client.get(URL))
    assert row["Title"] == '\'=HYPERLINK("http://x")'
    assert row["Lesson"] == "'@cmd"


# AC-03: anonymised project names withheld.


def test_anonymised_project_withheld(qa_client, make_lesson):
    secret = Project.objects.create(name="Secret Wing")
    make_lesson(project=secret, anonymise=True)
    response = qa_client.get(URL)
    assert "Secret Wing" not in response.content.decode("utf-8-sig")
    assert rows(response)[0]["Project"] == Lesson.ANONYMISED_PROJECT


# AC-04: Staff and anonymous users can't export.


def test_staff_forbidden(client, staff_member):
    client.force_login(staff_member)
    assert client.get(URL).status_code == 403


def test_anonymous_redirected(client):
    assert client.get(URL)["Location"].startswith("/accounts/login/")


# AC-05: each export is audited with the row count.


def test_export_audited(qa_client, make_lesson, caplog):
    make_lesson()
    make_lesson()
    with caplog.at_level(logging.INFO):
        qa_client.get(URL)
    lines = [r.getMessage() for r in caplog.records if r.name == "portal.audit"]
    assert 'event=export user="quinn" count="2"' in lines
