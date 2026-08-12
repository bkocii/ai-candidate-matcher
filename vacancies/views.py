from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from matching.models import MatchRun
from matching.staleness import assess_match_run_staleness
from organizations.models import Organization
from vacancies.forms import (
    VacancyCreateForm,
    VacancyRequirementsForm,
    requirements_values_from_form,
    vacancy_values_from_form,
)
from vacancies.models import Vacancy, VacancyRequirements
from vacancies.services import (
    available_vacancy_status_transitions,
    change_vacancy_status,
    confirm_requirements_draft,
    create_next_requirements_draft,
    create_vacancy_with_requirements,
    delete_vacancy,
    update_requirements_draft,
)


def _visible_organization(request, organization_slug: str) -> Organization:
    return get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )


def _visible_vacancy(organization: Organization, vacancy_id: int) -> Vacancy:
    return get_object_or_404(
        Vacancy.objects.for_organization(organization).active(),
        pk=vacancy_id,
    )


def _visible_requirements(
    organization: Organization,
    vacancy: Vacancy,
    requirements_id: int,
) -> VacancyRequirements:
    return get_object_or_404(
        VacancyRequirements.objects.for_organization(organization),
        vacancy=vacancy,
        pk=requirements_id,
    )


@login_required
def vacancy_list(request, organization_slug: str):
    organization = _visible_organization(request, organization_slug)
    vacancies = (
        Vacancy.objects.for_organization(organization)
        .active()
        .select_related("client_company")
        .order_by("-created_at", "id")
    )
    page = Paginator(vacancies, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "vacancies/vacancy_list.html",
        {"organization": organization, "page": page},
    )


@login_required
def vacancy_create(request, organization_slug: str):
    organization = _visible_organization(request, organization_slug)
    form = VacancyCreateForm(
        request.POST or None,
        organization=organization,
    )
    if request.method == "POST" and form.is_valid():
        vacancy = create_vacancy_with_requirements(
            organization=organization,
            user=request.user,
            vacancy_values=vacancy_values_from_form(form),
        )
        requirements = vacancy.requirement_versions.get(version=1)
        messages.success(
            request,
            "Vacancy created. Review and complete requirements version 1.",
        )
        return redirect(
            "vacancies:requirements-edit",
            organization_slug=organization.slug,
            vacancy_id=vacancy.pk,
            requirements_id=requirements.pk,
        )

    return render(
        request,
        "vacancies/vacancy_form.html",
        {"organization": organization, "form": form},
    )


@login_required
def vacancy_detail(request, organization_slug: str, vacancy_id: int):
    organization = _visible_organization(request, organization_slug)
    vacancy = _visible_vacancy(organization, vacancy_id)
    versions = vacancy.requirement_versions.select_related("created_by", "confirmed_by")
    draft = versions.filter(status=VacancyRequirements.Status.DRAFT).first()
    current_requirements = vacancy.current_requirements
    latest_match_run = (
        MatchRun.objects.for_organization(organization)
        .filter(requirements__vacancy=vacancy)
        .first()
    )
    latest_match_run_staleness = (
        assess_match_run_staleness(run=latest_match_run, user=request.user)
        if latest_match_run is not None
        else None
    )
    confirmed_hard_constraint_rules = (
        current_requirements.hard_constraint_rules.select_related("skill")
        if current_requirements is not None
        else ()
    )
    return render(
        request,
        "vacancies/vacancy_detail.html",
        {
            "organization": organization,
            "vacancy": vacancy,
            "current_requirements": current_requirements,
            "confirmed_hard_constraint_rules": confirmed_hard_constraint_rules,
            "latest_match_run": latest_match_run,
            "latest_match_run_staleness": latest_match_run_staleness,
            "draft": draft,
            "versions": versions,
            "status_transitions": available_vacancy_status_transitions(vacancy),
        },
    )


@login_required
@require_POST
def vacancy_status_change(request, organization_slug: str, vacancy_id: int):
    organization = _visible_organization(request, organization_slug)
    vacancy = _visible_vacancy(organization, vacancy_id)
    try:
        vacancy = change_vacancy_status(
            vacancy=vacancy,
            user=request.user,
            new_status=request.POST.get("status", ""),
        )
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
    else:
        messages.success(
            request,
            f"Vacancy status changed to {vacancy.get_status_display()}.",
        )
    return redirect(
        "vacancies:vacancy-detail",
        organization_slug=organization.slug,
        vacancy_id=vacancy.pk,
    )


@login_required
def vacancy_delete(request, organization_slug: str, vacancy_id: int):
    organization = _visible_organization(request, organization_slug)
    vacancy = _visible_vacancy(organization, vacancy_id)
    if request.method == "POST":
        delete_vacancy(vacancy=vacancy, user=request.user)
        messages.success(
            request,
            f'Deleted vacancy "{vacancy.title}" from the recruiter workspace.',
        )
        return redirect(
            "vacancies:vacancy-list",
            organization_slug=organization.slug,
        )

    return render(
        request,
        "vacancies/vacancy_confirm_delete.html",
        {"organization": organization, "vacancy": vacancy},
    )


@login_required
def requirements_edit(
    request,
    organization_slug: str,
    vacancy_id: int,
    requirements_id: int,
):
    organization = _visible_organization(request, organization_slug)
    vacancy = _visible_vacancy(organization, vacancy_id)
    requirements = _visible_requirements(organization, vacancy, requirements_id)
    if requirements.status != VacancyRequirements.Status.DRAFT:
        messages.error(
            request,
            "Confirmed requirements are read-only. Create a new draft to correct them.",
        )
        return redirect(
            "vacancies:vacancy-detail",
            organization_slug=organization.slug,
            vacancy_id=vacancy.pk,
        )

    form = VacancyRequirementsForm(
        request.POST or None,
        requirements=requirements,
    )
    if request.method == "POST" and form.is_valid():
        try:
            update_requirements_draft(
                requirements=requirements,
                user=request.user,
                values=requirements_values_from_form(form),
            )
        except ValidationError as error:
            form.add_error(None, "; ".join(error.messages))
        else:
            messages.success(
                request,
                f"Saved requirements version {requirements.version}.",
            )
            return redirect(
                "vacancies:requirements-edit",
                organization_slug=organization.slug,
                vacancy_id=vacancy.pk,
                requirements_id=requirements.pk,
            )

    return render(
        request,
        "vacancies/requirements_form.html",
        {
            "organization": organization,
            "vacancy": vacancy,
            "requirements": requirements,
            "form": form,
            "hard_constraint_rules": requirements.hard_constraint_rules.select_related(
                "skill"
            ),
        },
    )


@login_required
@require_POST
def requirements_confirm(
    request,
    organization_slug: str,
    vacancy_id: int,
    requirements_id: int,
):
    organization = _visible_organization(request, organization_slug)
    vacancy = _visible_vacancy(organization, vacancy_id)
    requirements = _visible_requirements(organization, vacancy, requirements_id)
    try:
        confirm_requirements_draft(requirements=requirements, user=request.user)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
    else:
        messages.success(
            request,
            f"Confirmed requirements version {requirements.version}.",
        )
    return redirect(
        "vacancies:vacancy-detail",
        organization_slug=organization.slug,
        vacancy_id=vacancy.pk,
    )


@login_required
@require_POST
def requirements_new_draft(request, organization_slug: str, vacancy_id: int):
    organization = _visible_organization(request, organization_slug)
    vacancy = _visible_vacancy(organization, vacancy_id)
    requirements, created = create_next_requirements_draft(
        vacancy=vacancy,
        user=request.user,
    )
    if created:
        messages.success(
            request,
            f"Created editable requirements version {requirements.version}.",
        )
    else:
        messages.info(request, "Opened the existing requirements draft.")
    return redirect(
        "vacancies:requirements-edit",
        organization_slug=organization.slug,
        vacancy_id=vacancy.pk,
        requirements_id=requirements.pk,
    )
