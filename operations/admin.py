from django.contrib import admin

from operations.models import BackgroundJob, BackgroundTask


class BackgroundTaskInline(admin.TabularInline):
    model = BackgroundTask
    extra = 0
    can_delete = False
    fields = (
        "target_type",
        "target_id",
        "status",
        "attempt_count",
        "outcome",
        "failure_code",
        "result_type",
        "result_id",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(BackgroundJob)
class BackgroundJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "workflow",
        "status",
        "total_count",
        "succeeded_count",
        "skipped_count",
        "failed_count",
        "created_at",
    )
    list_filter = ("workflow", "status", "organization")
    readonly_fields = (
        "organization",
        "workflow",
        "scope_type",
        "scope_id",
        "idempotency_key",
        "status",
        "total_count",
        "succeeded_count",
        "skipped_count",
        "failed_count",
        "schema_version",
        "created_by",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    )
    inlines = (BackgroundTaskInline,)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BackgroundTask)
class BackgroundTaskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "job",
        "target_type",
        "target_id",
        "status",
        "attempt_count",
        "outcome",
    )
    list_filter = ("target_type", "status", "outcome")
    readonly_fields = (
        "job",
        "target_type",
        "target_id",
        "status",
        "attempt_count",
        "result_type",
        "result_id",
        "outcome",
        "failure_code",
        "lease_expires_at",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
