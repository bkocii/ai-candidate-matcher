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
