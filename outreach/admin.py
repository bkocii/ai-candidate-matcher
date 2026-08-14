from django.contrib import admin

from outreach.models import OutreachDraft


@admin.register(OutreachDraft)
class OutreachDraftAdmin(admin.ModelAdmin):
    list_display = (
        "shortlist_entry",
        "version",
        "review_decision",
        "created_by",
        "created_at",
    )
    search_fields = (
        "shortlist_entry__candidate__full_name",
        "shortlist_entry__match_run__requirements__vacancy__title",
        "subject",
    )
    readonly_fields = (
        "shortlist_entry",
        "review_decision",
        "version",
        "schema_version",
        "subject",
        "body",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
