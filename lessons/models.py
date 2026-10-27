import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
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


class LessonQuerySet(models.QuerySet):
    def approved(self):
        """The only queryset public views may use (SECURITY.md)."""
        return self.filter(status=Lesson.Status.APPROVED)


class Lesson(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class Impact(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    title = models.CharField(max_length=200)
    description = models.TextField(help_text="What happened: the omission, error or site issue.")
    lesson = models.TextField(help_text="What to do differently next time.")

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="lessons")
    phase = models.ForeignKey(Phase, on_delete=models.PROTECT, related_name="lessons")
    discipline = models.ForeignKey(Discipline, on_delete=models.PROTECT, related_name="lessons")
    issue_type = models.ForeignKey(IssueType, on_delete=models.PROTECT, related_name="lessons")
    building_component = models.ForeignKey(
        BuildingComponent, on_delete=models.PROTECT, related_name="lessons"
    )

    impact = models.CharField(max_length=10, choices=Impact.choices, default=Impact.MEDIUM)
    cost_impact = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, help_text="Estimated cost."
    )
    time_impact_days = models.PositiveIntegerField(
        "time impact (days)", null=True, blank=True, help_text="Estimated delay in days."
    )
    anonymise = models.BooleanField(
        default=False, help_text="Hide the project name everywhere outside the review queue."
    )

    # Incorporation tracking (REQ-REVIEW-002).
    in_specs = models.BooleanField("incorporated into specs", default=False)
    in_standard_details = models.BooleanField("incorporated into standard details", default=False)
    in_onboarding = models.BooleanField("incorporated into onboarding", default=False)

    # Workflow and audit fields: never editable through forms; set in code by the
    # submit and review actions only.
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.SUBMITTED, editable=False
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="submitted_lessons",
        editable=False,
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_lessons",
        null=True,
        editable=False,
    )
    reviewed_at = models.DateTimeField(null=True, editable=False)
    approved_at = models.DateTimeField(null=True, editable=False)

    # Kept up to date by Postgres; weights rank title matches first.
    search_vector = models.GeneratedField(
        expression=(
            SearchVector("title", weight="A", config="english")
            + SearchVector("lesson", weight="B", config="english")
            + SearchVector("description", weight="C", config="english")
        ),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    objects = LessonQuerySet.as_manager()

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [
            GinIndex(fields=["search_vector"], name="lesson_search_idx"),
            models.Index(fields=["status", "-approved_at"], name="lesson_status_approved_idx"),
        ]

    def __str__(self):
        return self.title


ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def image_upload_path(instance, filename):
    """Random UUID file name; the client's file name is never used (SECURITY.md)."""
    suffix = Path(filename).suffix.lower()
    return f"lessons/{uuid.uuid4().hex}{suffix if suffix in ALLOWED_IMAGE_SUFFIXES else ''}"


class LessonImage(models.Model):
    class Kind(models.TextChoices):
        FAILED = "failed", "Failed"
        FIXED = "fixed", "Fixed"

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="images")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    file = models.FileField(upload_to=image_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind", "uploaded_at"]

    def __str__(self):
        return f"{self.get_kind_display()} image for lesson {self.lesson_id}"
