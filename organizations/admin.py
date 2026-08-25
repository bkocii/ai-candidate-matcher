from django.contrib import admin

from organizations.models import (
    ClientCompany,
    Organization,
    OrganizationRetentionPolicy,
    RetentionException,
)


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


@admin.register(OrganizationRetentionPolicy)
class OrganizationRetentionPolicyAdmin(admin.ModelAdmin):
    list_display = ("organization", "policy_version", "legal_hold", "updated_at")
    list_filter = ("legal_hold",)
    autocomplete_fields = ("organization", "updated_by")


@admin.register(RetentionException)
class RetentionExceptionAdmin(admin.ModelAdmin):
    list_display = ("organization", "scope", "object_id", "is_active", "expires_at")
    list_filter = ("scope", "is_active")
    autocomplete_fields = ("organization", "created_by")
