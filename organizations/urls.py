from django.urls import path

from organizations import views

app_name = "organizations"

urlpatterns = [
    path("", views.dashboard_home, name="dashboard"),
    path(
        "organizations/<slug:organization_slug>/",
        views.organization_dashboard,
        name="organization-dashboard",
    ),
]
