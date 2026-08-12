from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from matching.evaluation import filter_candidates
from matching.forms import HardConstraintRuleForm, hard_constraint_values_from_form
from matching.models import HardConstraintRule, MatchRun
from matching.scoring import generate_shortlist
from matching.services import (
    create_hard_constraint_rule,
    delete_hard_constraint_rule,
    update_hard_constraint_rule,
)
from matching.staleness import assess_match_run_staleness
from organizations.models import Organization
from vacancies.models import Vacancy, VacancyRequirements


def _rule_editor_objects(
    request,
    organization_slug: str,
    vacancy_id: int,
    requirements_id: int,
) -> tuple[Organization, Vacancy, VacancyRequirements]:
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    vacancy = get_object_or_404(
        Vacancy.objects.for_organization(organization).active(),
        pk=vacancy_id,
    )
    requirements = get_object_or_404(
        VacancyRequirements.objects.for_organization(organization),
        pk=requirements_id,
        vacancy=vacancy,
    )
    return organization, vacancy, requirements


def _redirect_if_confirmed(request, organization, vacancy, requirements):
    if requirements.status == VacancyRequirements.Status.DRAFT:
        return None
    messages.error(
        request,
        "Confirmed requirements are read-only. Create a new draft to correct them.",
    )
    return redirect(
        "vacancies:vacancy-detail",
        organization_slug=organization.slug,
        vacancy_id=vacancy.pk,
    )


@login_required
def hard_constraint_add(
    request,
    organization_slug: str,
    vacancy_id: int,
    requirements_id: int,
):
    organization, vacancy, requirements = _rule_editor_objects(
        request,
        organization_slug,
        vacancy_id,
        requirements_id,
    )
    redirect_response = _redirect_if_confirmed(
        request, organization, vacancy, requirements
    )
    if redirect_response is not None:
        return redirect_response

    form = HardConstraintRuleForm(
        request.POST or None,
        requirements=requirements,
    )
    if request.method == "POST" and form.is_valid():
        try:
            create_hard_constraint_rule(
                requirements=requirements,
                user=request.user,
                **hard_constraint_values_from_form(form),
            )
        except ValidationError as error:
            form.add_error(None, "; ".join(error.messages))
        else:
            messages.success(request, "Added typed hard-constraint rule.")
            return redirect(
                "vacancies:requirements-edit",
                organization_slug=organization.slug,
                vacancy_id=vacancy.pk,
                requirements_id=requirements.pk,
            )
    return render(
        request,
        "matching/hard_constraint_form.html",
        {
            "organization": organization,
            "vacancy": vacancy,
            "requirements": requirements,
            "form": form,
            "rule": None,
        },
    )


@login_required
def hard_constraint_edit(
    request,
    organization_slug: str,
    vacancy_id: int,
    requirements_id: int,
    rule_id: int,
):
    organization, vacancy, requirements = _rule_editor_objects(
        request,
        organization_slug,
        vacancy_id,
        requirements_id,
    )
    rule = get_object_or_404(
        HardConstraintRule.objects.for_organization(organization).select_related(
            "skill"
        ),
        pk=rule_id,
        requirements=requirements,
    )
    redirect_response = _redirect_if_confirmed(
        request, organization, vacancy, requirements
    )
    if redirect_response is not None:
        return redirect_response

    form = HardConstraintRuleForm(
        request.POST or None,
        requirements=requirements,
        rule=rule,
    )
    if request.method == "POST" and form.is_valid():
        try:
            update_hard_constraint_rule(
                rule=rule,
                user=request.user,
                **hard_constraint_values_from_form(form),
            )
        except ValidationError as error:
            form.add_error(None, "; ".join(error.messages))
        else:
            messages.success(request, "Updated typed hard-constraint rule.")
            return redirect(
                "vacancies:requirements-edit",
                organization_slug=organization.slug,
                vacancy_id=vacancy.pk,
                requirements_id=requirements.pk,
            )
    return render(
        request,
        "matching/hard_constraint_form.html",
        {
            "organization": organization,
            "vacancy": vacancy,
            "requirements": requirements,
            "form": form,
            "rule": rule,
        },
    )


@login_required
def hard_constraint_delete(
    request,
    organization_slug: str,
    vacancy_id: int,
    requirements_id: int,
    rule_id: int,
):
    organization, vacancy, requirements = _rule_editor_objects(
        request,
        organization_slug,
        vacancy_id,
        requirements_id,
    )
    rule = get_object_or_404(
        HardConstraintRule.objects.for_organization(organization).select_related(
            "skill"
        ),
        pk=rule_id,
        requirements=requirements,
    )
    redirect_response = _redirect_if_confirmed(
        request, organization, vacancy, requirements
    )
    if redirect_response is not None:
        return redirect_response

    if request.method == "POST":
        try:
            delete_hard_constraint_rule(rule=rule, user=request.user)
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            messages.success(request, "Deleted typed hard-constraint rule.")
        return redirect(
            "vacancies:requirements-edit",
            organization_slug=organization.slug,
            vacancy_id=vacancy.pk,
            requirements_id=requirements.pk,
        )
    return render(
        request,
        "matching/hard_constraint_confirm_delete.html",
        {
            "organization": organization,
            "vacancy": vacancy,
            "requirements": requirements,
            "rule": rule,
        },
    )


@login_required
def candidate_filter_report(request, organization_slug: str, vacancy_id: int):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    vacancy = get_object_or_404(
        Vacancy.objects.for_organization(organization).active(),
        pk=vacancy_id,
    )
    requirements = vacancy.current_requirements
    report = None
    page = None
    latest_run = None
    latest_run_staleness = None
    if requirements is not None:
        report = filter_candidates(requirements=requirements, user=request.user)
        page = Paginator(report.results, 25).get_page(request.GET.get("page"))
        latest_run = (
            MatchRun.objects.for_organization(organization)
            .filter(requirements__vacancy=vacancy)
            .first()
        )
        if latest_run is not None:
            latest_run_staleness = assess_match_run_staleness(
                run=latest_run,
                user=request.user,
            )

    return render(
        request,
        "matching/candidate_filter_report.html",
        {
            "organization": organization,
            "vacancy": vacancy,
            "requirements": requirements,
            "report": report,
            "page": page,
            "latest_run": latest_run,
            "latest_run_staleness": latest_run_staleness,
        },
    )


@login_required
@require_POST
def shortlist_generate(request, organization_slug: str, vacancy_id: int):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    vacancy = get_object_or_404(
        Vacancy.objects.for_organization(organization).active(),
        pk=vacancy_id,
    )
    requirements = vacancy.current_requirements
    if requirements is None:
        messages.error(request, "Confirm requirements before generating a shortlist.")
        return redirect(
            "vacancies:vacancy-detail",
            organization_slug=organization.slug,
            vacancy_id=vacancy.pk,
        )

    run = generate_shortlist(requirements=requirements, user=request.user)
    messages.success(
        request,
        f"Generated a shortlist of {run.entries.count()} candidates.",
    )
    return redirect(
        "matching:shortlist-detail",
        organization_slug=organization.slug,
        vacancy_id=vacancy.pk,
        match_run_id=run.pk,
    )


@login_required
def shortlist_detail(
    request,
    organization_slug: str,
    vacancy_id: int,
    match_run_id: int,
):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    vacancy = get_object_or_404(
        Vacancy.objects.for_organization(organization).active(),
        pk=vacancy_id,
    )
    run = get_object_or_404(
        MatchRun.objects.for_organization(organization).select_related(
            "requirements", "created_by"
        ),
        pk=match_run_id,
        requirements__vacancy=vacancy,
    )
    entries = run.entries.select_related("candidate").order_by("rank", "id")
    available_entry_count = entries.count()
    staleness = assess_match_run_staleness(run=run, user=request.user)
    return render(
        request,
        "matching/shortlist_detail.html",
        {
            "organization": organization,
            "vacancy": vacancy,
            "run": run,
            "entries": entries,
            "staleness": staleness,
            "omitted_count": max(
                run.eligible_count - run.shortlisted_count,
                0,
            ),
            "removed_count": max(
                run.shortlisted_count - available_entry_count,
                0,
            ),
        },
    )
