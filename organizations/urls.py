from django.urls import path

from organizations import views

app_name = "organizations"

urlpatterns = [
    path("", views.dashboard_home, name="dashboard"),
    path(
        "organizations/recovery/",
        views.organization_recovery,
        name="organization-recovery",
    ),
    path(
        "organizations/recovery/<int:organization_id>/restore/",
        views.organization_recover,
        name="organization-recover",
    ),
    path(
        "organizations/<slug:organization_slug>/",
        views.organization_dashboard,
        name="organization-dashboard",
    ),
    path(
        "organizations/<slug:organization_slug>/settings/",
        views.organization_settings,
        name="organization-settings",
    ),
    path(
        "organizations/<slug:organization_slug>/settings/client-companies/",
        views.client_company_list,
        name="client-company-list",
    ),
    path(
        "organizations/<slug:organization_slug>/settings/client-companies/new/",
        views.client_company_create,
        name="client-company-create",
    ),
    path(
        "organizations/<slug:organization_slug>/settings/client-companies/"
        "<int:company_id>/edit/",
        views.client_company_edit,
        name="client-company-edit",
    ),
    path(
        "organizations/<slug:organization_slug>/settings/client-companies/"
        "<int:company_id>/status/",
        views.client_company_status,
        name="client-company-status",
    ),
    path(
        "organizations/<slug:organization_slug>/retention/",
        views.retention_dashboard,
        name="retention-dashboard",
    ),
    path(
        "organizations/<slug:organization_slug>/delete/",
        views.organization_delete_request,
        name="organization-delete-request",
    ),
]
