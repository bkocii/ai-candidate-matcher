from django.urls import path

from candidates import views

app_name = "candidates"

urlpatterns = [
    path(
        "organizations/<slug:organization_slug>/candidates/",
        views.candidate_list,
        name="candidate-list",
    ),
    path(
        "organizations/<slug:organization_slug>/candidates/new/",
        views.candidate_create,
        name="candidate-create",
    ),
    path(
        "organizations/<slug:organization_slug>/candidates/<int:candidate_id>/",
        views.candidate_detail,
        name="candidate-detail",
    ),
    path(
        "organizations/<slug:organization_slug>/candidates/<int:candidate_id>/delete/",
        views.candidate_delete,
        name="candidate-delete",
    ),
    path(
        "organizations/<slug:organization_slug>/candidates/"
        "<int:candidate_id>/documents/upload/",
        views.candidate_cv_upload,
        name="candidate-cv-upload",
    ),
    path(
        "organizations/<slug:organization_slug>/candidates/"
        "<int:candidate_id>/documents/<int:document_id>/download/",
        views.candidate_document_download,
        name="candidate-document-download",
    ),
    path(
        "organizations/<slug:organization_slug>/candidates/"
        "<int:candidate_id>/documents/<int:document_id>/extract-profile/",
        views.candidate_profile_extract,
        name="candidate-profile-extract",
    ),
    path(
        "organizations/<slug:organization_slug>/candidates/"
        "<int:candidate_id>/profiles/<int:profile_id>/",
        views.candidate_profile_detail,
        name="candidate-profile-detail",
    ),
    path(
        "organizations/<slug:organization_slug>/candidates/"
        "<int:candidate_id>/profiles/<int:profile_id>/confirm/",
        views.candidate_profile_confirm,
        name="candidate-profile-confirm",
    ),
    path(
        "organizations/<slug:organization_slug>/candidates/import/",
        views.candidate_import,
        name="candidate-import",
    ),
    path(
        "organizations/<slug:organization_slug>/candidates/import/template.csv",
        views.candidate_import_template,
        name="candidate-import-template",
    ),
]
