from django.urls import path

from matching import views

app_name = "matching"

urlpatterns = [
    path(
        "organizations/<slug:organization_slug>/vacancies/<int:vacancy_id>/"
        "requirements/<int:requirements_id>/hard-constraints/new/",
        views.hard_constraint_add,
        name="hard-constraint-add",
    ),
    path(
        "organizations/<slug:organization_slug>/vacancies/<int:vacancy_id>/"
        "requirements/<int:requirements_id>/hard-constraints/<int:rule_id>/edit/",
        views.hard_constraint_edit,
        name="hard-constraint-edit",
    ),
    path(
        "organizations/<slug:organization_slug>/vacancies/<int:vacancy_id>/"
        "requirements/<int:requirements_id>/hard-constraints/<int:rule_id>/delete/",
        views.hard_constraint_delete,
        name="hard-constraint-delete",
    ),
    path(
        "organizations/<slug:organization_slug>/vacancies/<int:vacancy_id>/filter/",
        views.candidate_filter_report,
        name="candidate-filter-report",
    ),
    path(
        "organizations/<slug:organization_slug>/vacancies/<int:vacancy_id>/shortlists/generate/",
        views.shortlist_generate,
        name="shortlist-generate",
    ),
    path(
        "organizations/<slug:organization_slug>/vacancies/<int:vacancy_id>/shortlists/<int:match_run_id>/",
        views.shortlist_detail,
        name="shortlist-detail",
    ),
]
