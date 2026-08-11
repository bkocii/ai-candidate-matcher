from django.urls import path

from matching import views

app_name = "matching"

urlpatterns = [
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
