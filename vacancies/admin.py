from django.contrib import admin

from vacancies.models import Vacancy, VacancyRequirements


class VacancyRequirementsInline(admin.TabularInline):
    model = VacancyRequirements
    extra = 0
    fields = (
        "version",
        "status",
        "creation_method",
        "work_mode",
        "employment_type",
        "confirmed_by",
        "confirmed_at",
    )
    readonly_fields = ("created_at",)
    show_change_link = True


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "organization",
        "client_company",
        "status",
        "deleted_at",
        "created_at",
    )
    list_filter = ("status", "deleted_at", "organization")
    search_fields = ("title", "description", "client_company__name")
    autocomplete_fields = (
        "organization",
        "client_company",
        "created_by",
        "deleted_by",
    )
    readonly_fields = ("deleted_at", "deleted_by", "created_at", "updated_at")
    inlines = (VacancyRequirementsInline,)


@admin.register(VacancyRequirements)
class VacancyRequirementsAdmin(admin.ModelAdmin):
    list_display = (
        "vacancy",
        "version",
        "status",
        "creation_method",
        "employment_type",
        "work_mode",
        "created_at",
    )
    list_filter = (
        "status",
        "creation_method",
        "employment_type",
        "work_mode",
    )
    search_fields = ("vacancy__title", "summary", "source_description")
    autocomplete_fields = ("vacancy", "created_by", "confirmed_by")
    readonly_fields = ("created_at",)
