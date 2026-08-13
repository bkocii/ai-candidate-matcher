from django.contrib import admin

from audit.models import AIUsageEvent


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
