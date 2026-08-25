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
