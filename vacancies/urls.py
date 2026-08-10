from django.urls import path

from vacancies import views

app_name = "vacancies"

urlpatterns = [
    path(
        "organizations/<slug:organization_slug>/vacancies/",
        views.vacancy_list,
        name="vacancy-list",
    ),
    path(
        "organizations/<slug:organization_slug>/vacancies/new/",
        views.vacancy_create,
        name="vacancy-create",
    ),
    path(
        "organizations/<slug:organization_slug>/vacancies/<int:vacancy_id>/",
        views.vacancy_detail,
        name="vacancy-detail",
    ),
    path(
        "organizations/<slug:organization_slug>/vacancies/<int:vacancy_id>/"
        "requirements/<int:requirements_id>/edit/",
        views.requirements_edit,
        name="requirements-edit",
    ),
    path(
        "organizations/<slug:organization_slug>/vacancies/<int:vacancy_id>/"
        "requirements/<int:requirements_id>/confirm/",
        views.requirements_confirm,
        name="requirements-confirm",
    ),
    path(
        "organizations/<slug:organization_slug>/vacancies/<int:vacancy_id>/"
        "requirements/new/",
        views.requirements_new_draft,
        name="requirements-new-draft",
    ),
]
