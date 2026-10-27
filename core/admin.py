from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User

from core.audit import audit


class AuditedAdmin(admin.ModelAdmin):
    """Base for every ModelAdmin: writes admin changes to the audit log.

    Hooks the admin's own logging methods rather than LogEntry signals, because bulk
    deletions are written with bulk_create and send no signals. Object names are left out
    since they may contain an anonymised project name.
    """

    def _audit(self, request, action, obj):
        audit(
            "admin_change",
            request.user,
            action=action,
            object_type=obj._meta.model_name,
            object_id=obj.pk,
        )

    def log_addition(self, request, obj, message):
        self._audit(request, "add", obj)
        return super().log_addition(request, obj, message)

    def log_change(self, request, obj, message):
        self._audit(request, "change", obj)
        return super().log_change(request, obj, message)

    def log_deletions(self, request, queryset):
        for obj in queryset:
            self._audit(request, "delete", obj)
        return super().log_deletions(request, queryset)


admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class AuditedUserAdmin(AuditedAdmin, UserAdmin):
    pass


@admin.register(Group)
class AuditedGroupAdmin(AuditedAdmin, GroupAdmin):
    pass
