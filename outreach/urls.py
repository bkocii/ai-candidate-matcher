from django.urls import path

from outreach import views

app_name = "outreach"

urlpatterns = [
    path(
        "organizations/<slug:organization_slug>/outreach/decisions/"
        "<int:decision_id>/generate/",
        views.outreach_draft_generate,
        name="outreach-draft-generate",
    ),
    path(
        "organizations/<slug:organization_slug>/outreach/drafts/<int:draft_id>/",
        views.outreach_draft_detail,
        name="outreach-draft-detail",
    ),
]
