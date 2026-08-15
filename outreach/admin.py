from django.contrib import admin

from outreach.models import OutreachDraft, OutreachDraftAction, OutreachDraftApproval


@admin.register(OutreachDraft)
class OutreachDraftAdmin(admin.ModelAdmin):
    list_display = (
        "shortlist_entry",
        "version",
        "creation_method",
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
        "creation_method",
        "parent_draft",
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


@admin.register(OutreachDraftApproval)
class OutreachDraftApprovalAdmin(admin.ModelAdmin):
    list_display = ("draft", "approved_by", "approved_at")
    search_fields = (
        "draft__shortlist_entry__candidate__full_name",
        "draft__shortlist_entry__match_run__requirements__vacancy__title",
        "notes",
    )
    readonly_fields = (
        "draft",
        "notes",
        "contact_permission_confirmed",
        "approved_by",
        "approved_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OutreachDraftAction)
class OutreachDraftActionAdmin(admin.ModelAdmin):
    list_display = ("draft", "action_type", "actor", "created_at")
    list_filter = ("action_type",)
    search_fields = (
        "draft__shortlist_entry__candidate__full_name",
        "draft__shortlist_entry__match_run__requirements__vacancy__title",
    )
    readonly_fields = ("draft", "action_type", "actor", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
