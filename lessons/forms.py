from django import forms
from django.core.exceptions import ValidationError

from lessons.images import LessonImagesField, check_image_count
from lessons.models import BuildingComponent, Discipline, IssueType, Lesson, Phase, Project


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
        fields = [
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
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "lesson": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only active rows are offered (REQ-ADMIN-001).
        for name, model in [
            ("project", Project),
            ("phase", Phase),
            ("discipline", Discipline),
            ("issue_type", IssueType),
            ("building_component", BuildingComponent),
        ]:
            self.fields[name].queryset = model.objects.active()

    def clean(self):
        cleaned = super().clean()
        images = cleaned.get("failed_images", []) + cleaned.get("fixed_images", [])
        if not self.has_error("failed_images") and not self.has_error("fixed_images"):
            if not images:
                raise ValidationError("Add at least one Failed or Fixed image.")
            check_image_count(len(images))
        return cleaned
