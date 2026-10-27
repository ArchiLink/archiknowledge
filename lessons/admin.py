from django.contrib import admin

from core.admin import AuditedAdmin
from lessons.models import BuildingComponent, Discipline, IssueType, Phase, Project


class LookupAdmin(AuditedAdmin):
    list_display = ["name", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]


@admin.register(Phase)
class PhaseAdmin(LookupAdmin):
    list_display = ["code", "name", "sort_order", "is_active"]
    search_fields = ["code", "name"]


admin.site.register([Discipline, IssueType, BuildingComponent], LookupAdmin)


@admin.register(Project)
class ProjectAdmin(AuditedAdmin):
    list_display = ["name", "is_active"]
    list_editable = ["is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]
