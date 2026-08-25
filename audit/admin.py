from django.contrib import admin

from audit.models import (
    AIUsageEvent,
    AuditEvent,
    DataLifecycleEvent,
    OrganizationTombstone,
)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "action",
        "organization",
        "object_type",
        "object_id",
        "actor",
        "occurred_at",
    )
    list_filter = ("action", "object_type", "organization")
    search_fields = ("object_id",)
    readonly_fields = (
        "organization",
        "actor",
        "action",
        "object_type",
        "object_id",
        "schema_version",
        "occurred_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AIUsageEvent)
class AIUsageEventAdmin(admin.ModelAdmin):
    list_display = (
        "workflow",
        "organization",
        "status",
        "model",
        "duration_ms",
        "retries_used",
        "started_at",
    )
    list_filter = ("workflow", "status", "failure_stage", "failure_code")
    search_fields = ("provider_request_id",)
    readonly_fields = (
        "organization",
        "actor",
        "workflow",
        "target_type",
        "target_id",
        "result_type",
        "result_id",
        "schema_version",
        "status",
        "provider_request_id",
        "model",
        "duration_ms",
        "retries_used",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "estimated_cost_usd",
        "failure_stage",
        "failure_code",
        "started_at",
        "completed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DataLifecycleEvent)
class DataLifecycleEventAdmin(admin.ModelAdmin):
    list_display = (
        "action",
        "organization_id_snapshot",
        "object_type",
        "object_id",
        "policy_version",
        "occurred_at",
    )
    list_filter = ("action", "object_type")
    readonly_fields = tuple(field.name for field in DataLifecycleEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrganizationTombstone)
class OrganizationTombstoneAdmin(admin.ModelAdmin):
    list_display = (
        "organization_id_snapshot",
        "policy_version",
        "deletion_requested_at",
        "purged_at",
    )
    readonly_fields = tuple(field.name for field in OrganizationTombstone._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
