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
    path(
        "organizations/<slug:organization_slug>/outreach/drafts/<int:draft_id>/edit/",
        views.outreach_draft_edit,
        name="outreach-draft-edit",
    ),
    path(
        "organizations/<slug:organization_slug>/outreach/drafts/"
        "<int:draft_id>/approve/",
        views.outreach_draft_approve,
        name="outreach-draft-approve",
    ),
    path(
        "organizations/<slug:organization_slug>/outreach/drafts/<int:draft_id>/copy/",
        views.outreach_draft_copy,
        name="outreach-draft-copy",
    ),
    path(
        "organizations/<slug:organization_slug>/outreach/drafts/<int:draft_id>/export/",
        views.outreach_draft_export,
        name="outreach-draft-export",
    ),
]
