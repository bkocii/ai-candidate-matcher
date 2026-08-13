from django.contrib import admin

from organizations.models import ClientCompany, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ClientCompany)
class ClientCompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "website", "is_active", "created_at")
    list_filter = ("is_active", "organization")
    search_fields = ("name", "slug", "organization__name")
    autocomplete_fields = ("organization",)
    prepopulated_fields = {"slug": ("name",)}
