"""Public browsing of Approved lessons: knowledge base filters and search (REQ-KB-001)."""

from django import forms
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F

from lessons.models import BuildingComponent, Discipline, IssueType, Lesson, Phase

PAGE_SIZE = 20  # fixed on the server (SECURITY.md); no page_size parameter
MAX_SEARCH_LENGTH = 200


class LessonFilterForm(forms.Form):
    """Validates public query parameters against the lookup tables and length limits."""

    q = forms.CharField(label="Search", required=False, max_length=MAX_SEARCH_LENGTH, strip=True)
    phase = forms.ModelChoiceField(queryset=Phase.objects.active(), required=False)
    discipline = forms.ModelChoiceField(queryset=Discipline.objects.active(), required=False)
    issue_type = forms.ModelChoiceField(queryset=IssueType.objects.active(), required=False)
    building_component = forms.ModelChoiceField(
        queryset=BuildingComponent.objects.active(), required=False
    )
    impact = forms.ChoiceField(choices=[("", "Any impact"), *Lesson.Impact.choices], required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["q"].widget.attrs.update(
            {"maxlength": MAX_SEARCH_LENGTH, "type": "search", "placeholder": "Search lessons"}
        )
        for name in ["phase", "discipline", "issue_type", "building_component"]:
            self.fields[name].empty_label = "Any"

    def filter(self, queryset):
        """Apply the cleaned filters to an Approved-only queryset."""
        data = self.cleaned_data
        for name in ["phase", "discipline", "issue_type", "building_component"]:
            if data.get(name):
                queryset = queryset.filter(**{name: data[name]})
        if data.get("impact"):
            queryset = queryset.filter(impact=data["impact"])
        if data.get("q"):
            query = SearchQuery(data["q"], config="english", search_type="websearch")
            queryset = (
                queryset.filter(search_vector=query)
                .annotate(rank=SearchRank(F("search_vector"), query))
                .order_by("-rank", "-approved_at")
            )
        else:
            queryset = queryset.order_by("-approved_at")
        return queryset


def approved_lessons():
    return Lesson.objects.approved().select_related(
        "project", "phase", "discipline", "issue_type", "building_component"
    )
