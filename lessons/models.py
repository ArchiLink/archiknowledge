from django.db import models
from django.db.models.functions import Lower


class ActiveQuerySet(models.QuerySet):
    def active(self):
        """Rows offered in forms and filters. Inactive rows stay on existing lessons."""
        return self.filter(is_active=True)


class Lookup(models.Model):
    """A list managed in Django admin instead of hard-coded choices (CLAUDE.md)."""

    name = models.CharField(max_length=100)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField("active", default=True)

    objects = ActiveQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


def unique_name(model_name):
    return models.UniqueConstraint(
        Lower("name"),
        name=f"{model_name}_name_unique_ci",
        violation_error_message="This name already exists (names are not case-sensitive).",
    )


class Phase(Lookup):
    code = models.CharField(max_length=10, help_text="Short code shown on the feed, e.g. SD.")

    class Meta(Lookup.Meta):
        constraints = [
            unique_name("phase"),
            models.UniqueConstraint(
                Lower("code"),
                name="phase_code_unique_ci",
                violation_error_message="A phase with this code already exists.",
            ),
        ]

    def __str__(self):
        return f"{self.code} – {self.name}"


class Discipline(Lookup):
    class Meta(Lookup.Meta):
        constraints = [unique_name("discipline")]


class IssueType(Lookup):
    class Meta(Lookup.Meta):
        verbose_name = "issue type"
        constraints = [unique_name("issuetype")]


class BuildingComponent(Lookup):
    class Meta(Lookup.Meta):
        verbose_name = "building component"
        constraints = [unique_name("buildingcomponent")]


class Project(models.Model):
    name = models.CharField(max_length=200)
    is_active = models.BooleanField("active", default=True)

    objects = ActiveQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        constraints = [unique_name("project")]

    def __str__(self):
        return self.name
