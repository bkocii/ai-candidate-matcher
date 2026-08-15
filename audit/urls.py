from django.urls import path

from audit import views

app_name = "audit"

urlpatterns = [
    path(
        "organizations/<slug:organization_slug>/ai-usage/",
        views.ai_usage_report,
        name="ai-usage-report",
    ),
    path(
        "organizations/<slug:organization_slug>/privacy/",
        views.privacy_dashboard,
        name="privacy-dashboard",
    ),
]
