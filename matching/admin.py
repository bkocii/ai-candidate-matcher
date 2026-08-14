from django.contrib import admin

from matching.models import (
    CandidateSkill,
    HardConstraintRule,
    MatchAssessment,
    MatchRun,
    RequirementSkill,
    ReviewDecision,
    ShortlistEntry,
    Skill,
)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "normalized_name", "created_at")
    list_filter = ("organization",)
    search_fields = ("name", "normalized_name")
    autocomplete_fields = ("organization", "created_by")
    readonly_fields = ("normalized_name", "created_at", "updated_at")


@admin.register(CandidateSkill)
class CandidateSkillAdmin(admin.ModelAdmin):
    list_display = ("candidate", "skill", "years_experience", "created_at")
    list_filter = ("skill__organization",)
    search_fields = ("candidate__full_name", "skill__name", "evidence")
    autocomplete_fields = (
        "candidate",
        "skill",
        "source_document",
        "source_profile",
        "created_by",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(RequirementSkill)
class RequirementSkillAdmin(admin.ModelAdmin):
    list_display = ("requirements", "skill", "importance", "position")
    list_filter = ("importance", "skill__organization")
    search_fields = ("requirements__vacancy__title", "skill__name", "source_label")
    autocomplete_fields = ("requirements", "skill")
    readonly_fields = ("created_at",)


@admin.register(HardConstraintRule)
class HardConstraintRuleAdmin(admin.ModelAdmin):
    list_display = (
        "requirements",
        "position",
        "rule_type",
        "operator",
        "unknown_outcome",
    )
    list_filter = ("rule_type", "unknown_outcome")
    search_fields = ("requirements__vacancy__title", "source_text", "expected_value")
    autocomplete_fields = ("requirements", "skill", "created_by")
    readonly_fields = ("normalized_expected_value", "unknown_outcome", "created_at")


@admin.register(MatchRun)
class MatchRunAdmin(admin.ModelAdmin):
    list_display = (
        "requirements",
        "algorithm_version",
        "evaluated_count",
        "eligible_count",
        "shortlisted_count",
        "shortlist_limit",
        "created_at",
    )
    list_filter = ("algorithm_version",)
    search_fields = ("requirements__vacancy__title",)
    autocomplete_fields = ("requirements", "created_by")
    readonly_fields = (
        "requirements",
        "algorithm_version",
        "input_snapshot_version",
        "requirements_input_signature",
        "candidate_input_signature",
        "shortlist_limit",
        "evaluated_count",
        "eligible_count",
        "shortlisted_count",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ShortlistEntry)
class ShortlistEntryAdmin(admin.ModelAdmin):
    list_display = ("match_run", "rank", "candidate", "score", "filter_outcome")
    list_filter = ("filter_outcome",)
    search_fields = ("match_run__requirements__vacancy__title", "candidate__full_name")
    autocomplete_fields = ("match_run", "candidate")
    readonly_fields = (
        "match_run",
        "candidate",
        "rank",
        "score",
        "filter_outcome",
        "matched_must_have",
        "total_must_have",
        "matched_nice_to_have",
        "total_nice_to_have",
        "score_breakdown",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MatchAssessment)
class MatchAssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "shortlist_entry",
        "version",
        "score",
        "traffic_light",
        "created_at",
    )
    list_filter = ("traffic_light", "schema_version")
    search_fields = (
        "shortlist_entry__candidate__full_name",
        "requirements__vacancy__title",
    )
    readonly_fields = (
        "shortlist_entry",
        "requirements",
        "candidate_profile",
        "version",
        "schema_version",
        "score",
        "traffic_light",
        "summary",
        "matching_requirements",
        "gaps",
        "uncertainties",
        "review_recommendation",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReviewDecision)
class ReviewDecisionAdmin(admin.ModelAdmin):
    list_display = (
        "shortlist_entry",
        "version",
        "decision",
        "created_by",
        "created_at",
    )
    list_filter = ("decision",)
    search_fields = (
        "shortlist_entry__candidate__full_name",
        "shortlist_entry__match_run__requirements__vacancy__title",
        "notes",
    )
    readonly_fields = (
        "shortlist_entry",
        "assessment",
        "version",
        "decision",
        "notes",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
