from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import OrganizationMembership, User


@admin.register(User)
class ApplicationUserAdmin(UserAdmin):
    pass


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "is_active")
    list_filter = ("role", "is_active", "organization")
    search_fields = ("user__username", "user__email", "organization__name")
    autocomplete_fields = ("user", "organization")
