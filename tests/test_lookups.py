"""Lookup tables and projects in Django admin (REQ-ADMIN-001)."""

import logging

import pytest
from django.core.exceptions import ValidationError

from lessons.models import BuildingComponent, Discipline, IssueType, Phase, Project

pytestmark = pytest.mark.django_db

LOOKUPS = [Phase, Discipline, IssueType, BuildingComponent]


@pytest.fixture
def admin_user(django_user_model):
    return django_user_model.objects.create_superuser(username="ada", password="x" * 12)


# AC-01: name, code, sort order, active flag; inactive rows hidden from active().


@pytest.mark.parametrize("model", LOOKUPS + [Project])
def test_active_excludes_inactive_rows(model):
    extra = {"code": "ZZ"} if model is Phase else {}
    hidden = model.objects.create(name="Retired row", is_active=False, **extra)
    assert hidden not in model.objects.active()
    assert hidden in model.objects.all()  # still available to existing lessons


def test_lookups_ordered_by_sort_order_then_name():
    Discipline.objects.all().delete()
    for name, order in [("B", 2), ("A", 2), ("C", 1)]:
        Discipline.objects.create(name=name, sort_order=order)
    assert [d.name for d in Discipline.objects.all()] == ["C", "A", "B"]


# AC-02: phases seeded in order (the other lists are seeded too).


def test_phases_seeded_in_order():
    assert [p.code for p in Phase.objects.all()] == ["SD", "DD", "CD", "TA", "CA", "PC"]


@pytest.mark.parametrize(
    ("model", "count", "example"),
    [
        (Discipline, 8, "Architecture"),
        (IssueType, 4, "Omission"),
        (BuildingComponent, 8, "Roofing"),
    ],
)
def test_starter_lists_seeded(model, count, example):
    assert model.objects.active().count() == count
    assert model.objects.filter(name=example).exists()


# AC-03: projects.


def test_project_str_and_order():
    Project.objects.create(name="Tower B")
    Project.objects.create(name="Annex A")
    assert [str(p) for p in Project.objects.all()] == ["Annex A", "Tower B"]


# Failure behaviour: duplicate names/codes rejected, ignoring case.


@pytest.mark.parametrize("model", [Discipline, IssueType, BuildingComponent, Project])
def test_duplicate_name_rejected_case_insensitively(model):
    model.objects.create(name="Duplicate me")
    with pytest.raises(ValidationError):
        model(name="DUPLICATE ME").full_clean()


def test_duplicate_phase_code_rejected():
    with pytest.raises(ValidationError):
        Phase(code="sd", name="Another schematic").full_clean()


def test_phase_str():
    assert str(Phase.objects.get(code="SD")) == "SD – Schematic Design"


# AC-04: non-staff users have no admin access.


def test_non_staff_user_cannot_use_admin(client, django_user_model):
    user = django_user_model.objects.create_user(username="sam", password="x" * 12)
    client.force_login(user)
    response = client.get("/admin/lessons/phase/")
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


def test_staff_admin_can_list_and_add(client, admin_user):
    client.force_login(admin_user)
    for path in ["phase", "discipline", "issuetype", "buildingcomponent", "project"]:
        assert client.get(f"/admin/lessons/{path}/").status_code == 200
    response = client.post("/admin/lessons/project/add/", {"name": "Library", "is_active": "on"})
    assert response.status_code == 302
    assert Project.objects.filter(name="Library").exists()


def test_admin_rejects_duplicate(client, admin_user):
    client.force_login(admin_user)
    response = client.post(
        "/admin/lessons/discipline/add/", {"name": "architecture", "sort_order": 1}
    )
    assert response.status_code == 200  # form re-shown with an error
    assert "already exists" in response.content.decode()


# AC-05: admin changes are audited.


def test_admin_changes_audited(client, admin_user, caplog):
    client.force_login(admin_user)
    with caplog.at_level(logging.INFO):
        client.post(
            "/admin/lessons/phase/add/", {"code": "PD", "name": "Pre-Design", "sort_order": 0}
        )
    phase = Phase.objects.get(code="PD")
    lines = [r.getMessage() for r in caplog.records if r.name == "portal.audit"]
    assert (
        f'event=admin_change user="ada" action="add" object_id="{phase.pk}" object_type="phase"'
        in lines
    )
