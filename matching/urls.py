from django.urls import path

from matching import views

app_name = "matching"

urlpatterns = [
    path(
        "organizations/<slug:organization_slug>/vacancies/<int:vacancy_id>/filter/",
        views.candidate_filter_report,
        name="candidate-filter-report",
    ),
]
