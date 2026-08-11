from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from matching.evaluation import filter_candidates
from matching.models import MatchRun
from matching.scoring import generate_shortlist
from organizations.models import Organization
from vacancies.models import Vacancy


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
    if requirements is not None:
        report = filter_candidates(requirements=requirements, user=request.user)
        page = Paginator(report.results, 25).get_page(request.GET.get("page"))
        latest_run = (
            MatchRun.objects.for_organization(organization)
            .filter(requirements=requirements)
            .first()
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
    return render(
        request,
        "matching/shortlist_detail.html",
        {
            "organization": organization,
            "vacancy": vacancy,
            "run": run,
            "entries": entries,
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
