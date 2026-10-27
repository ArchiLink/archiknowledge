from django import forms
from django.core.exceptions import ValidationError

from lessons.images import LessonImagesField, check_image_count
from lessons.models import BuildingComponent, Discipline, IssueType, Lesson, Phase, Project

LOOKUP_FIELDS = [
    ("project", Project),
    ("phase", Phase),
    ("discipline", Discipline),
    ("issue_type", IssueType),
    ("building_component", BuildingComponent),
]

LESSON_FIELDS = [
    "title",
    "project",
    "phase",
    "discipline",
    "issue_type",
    "building_component",
    "description",
    "lesson",
    "impact",
    "cost_impact",
    "time_impact_days",
]

TEXT_WIDGETS = {
    "description": forms.Textarea(attrs={"rows": 5}),
    "lesson": forms.Textarea(attrs={"rows": 4}),
}


def limit_to_active(form):
    """Offer only active rows (REQ-ADMIN-001), plus the lesson's current row when editing."""
    for name, model in LOOKUP_FIELDS:
        queryset = model.objects.active()
        current = getattr(form.instance, f"{name}_id", None)
        if current:
            queryset = queryset | model.objects.filter(pk=current)
        form.fields[name].queryset = queryset.distinct()


class ReviewForm(forms.ModelForm):
    """QA edit form: every lesson field plus anonymise. Status changes are separate actions."""

    class Meta:
        model = Lesson
        fields = LESSON_FIELDS + ["anonymise"]
        widgets = TEXT_WIDGETS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        limit_to_active(self)


class LessonSubmitForm(forms.ModelForm):
    """Staff submission. Status, submitter, anonymise and review fields are never form fields."""

    failed_images = LessonImagesField(
        required=False, label="Failed images", help_text="What went wrong: photos or redlines."
    )
    fixed_images = LessonImagesField(
        required=False, label="Fixed images", help_text="The corrected detail or condition."
    )

    class Meta:
        model = Lesson
        fields = LESSON_FIELDS
        widgets = TEXT_WIDGETS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        limit_to_active(self)

    def clean(self):
        cleaned = super().clean()
        images = cleaned.get("failed_images", []) + cleaned.get("fixed_images", [])
        if not self.has_error("failed_images") and not self.has_error("fixed_images"):
            if not images:
                raise ValidationError("Add at least one Failed or Fixed image.")
            check_image_count(len(images))
        return cleaned
