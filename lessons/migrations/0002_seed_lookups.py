"""Starter rows for the lookup lists (agreed 2026-10-27). Admins can rename or deactivate them."""

from django.db import migrations

PHASES = [
    ("SD", "Schematic Design"),
    ("DD", "Design Development"),
    ("CD", "Construction Documents"),
    ("TA", "Tender & Award"),
    ("CA", "Construction Administration"),
    ("PC", "Post-Construction"),
]

LISTS = {
    "Discipline": [
        "Architecture",
        "Structural",
        "Mechanical",
        "Electrical",
        "Plumbing",
        "Civil",
        "Landscape",
        "Interiors",
    ],
    "IssueType": ["Omission", "Error", "Coordination clash", "Site lesson"],
    "BuildingComponent": [
        "Foundations",
        "Structure",
        "Envelope/Facade",
        "Roofing",
        "Interiors",
        "MEP services",
        "Site works",
        "Vertical transport",
    ],
}


def seed(apps, schema_editor):
    Phase = apps.get_model("lessons", "Phase")
    for order, (code, name) in enumerate(PHASES, start=1):
        Phase.objects.get_or_create(code=code, defaults={"name": name, "sort_order": order})
    for model_name, names in LISTS.items():
        model = apps.get_model("lessons", model_name)
        for order, name in enumerate(names, start=1):
            model.objects.get_or_create(name=name, defaults={"sort_order": order})


def unseed(apps, schema_editor):
    apps.get_model("lessons", "Phase").objects.filter(code__in=[c for c, _ in PHASES]).delete()
    for model_name, names in LISTS.items():
        apps.get_model("lessons", model_name).objects.filter(name__in=names).delete()


class Migration(migrations.Migration):
    dependencies = [("lessons", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
