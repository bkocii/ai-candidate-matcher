from django.contrib import admin

from matching.models import (
    CandidateSkill,
    HardConstraintRule,
    RequirementSkill,
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
    autocomplete_fields = ("candidate", "skill", "source_document", "created_by")
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
