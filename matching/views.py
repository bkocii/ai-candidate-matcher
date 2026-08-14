from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ai_gateway import AIGatewayError
from matching.ai_assessment import assess_shortlist_entry
from matching.decisions import (
    assess_review_decision_eligibility,
    record_review_decision,
)
from matching.evaluation import filter_candidates
from matching.forms import (
    HardConstraintRuleForm,
    ReviewDecisionForm,
    hard_constraint_values_from_form,
)
from matching.models import (
    HardConstraintRule,
    MatchAssessment,
    MatchRun,
    ReviewDecision,
    ShortlistEntry,
)
from matching.review import (
    build_assessment_review_item,
    build_assessment_review_queue,
)
from matching.scoring import generate_shortlist
from matching.services import (
    create_hard_constraint_rule,
    delete_hard_constraint_rule,
    update_hard_constraint_rule,
)
from matching.staleness import assess_match_run_staleness
from organizations.models import Organization
from vacancies.models import Vacancy, VacancyRequirements

REVIEW_QUEUE_SCOPES = {"pending", "exceptions", "changed", "all"}


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
    entries = list(
        run.entries.select_related("candidate")
        .prefetch_related("candidate__profile_versions", "assessments")
        .order_by("rank", "id")
    )
    available_entry_count = len(entries)
    for entry in entries:
        entry.confirmed_profile = next(
            (
                profile
                for profile in entry.candidate.profile_versions.all()
                if profile.status == "confirmed"
            ),
            None,
        )
        entry.latest_assessment = next(iter(entry.assessments.all()), None)
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


@login_required
@require_POST
def shortlist_assessment_generate(
    request,
    organization_slug: str,
    vacancy_id: int,
    match_run_id: int,
    entry_id: int,
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
        MatchRun.objects.for_organization(organization),
        pk=match_run_id,
        requirements__vacancy=vacancy,
    )
    entry = get_object_or_404(
        ShortlistEntry.objects.for_organization(organization),
        pk=entry_id,
        match_run=run,
    )
    try:
        result = assess_shortlist_entry(entry=entry, user=request.user)
    except (AIGatewayError, ValidationError) as error:
        public_message = (
            "; ".join(error.messages)
            if isinstance(error, ValidationError)
            else str(error)
        )
        messages.error(request, public_message)
    else:
        messages.success(
            request,
            f"AI assessment version {result.assessment.version} was saved as "
            "recruiter decision support.",
        )
    detail_url = reverse(
        "matching:shortlist-detail",
        args=[organization.slug, vacancy.pk, run.pk],
    )
    return redirect(f"{detail_url}#assessment-entry-{entry.pk}")


@login_required
def assessment_review_queue(request, organization_slug: str):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    queue = build_assessment_review_queue(
        organization=organization,
        user=request.user,
    )
    scope = request.GET.get("scope", "pending")
    if scope not in REVIEW_QUEUE_SCOPES:
        scope = "pending"
    if scope == "pending":
        selected_items = [item for item in queue.items if item.decision_pending]
    elif scope == "changed":
        selected_items = [item for item in queue.items if item.inputs_changed]
    elif scope == "all":
        selected_items = list(queue.items)
    else:
        selected_items = [item for item in queue.items if item.needs_focus]
    page = Paginator(selected_items, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "matching/assessment_review_queue.html",
        {
            "organization": organization,
            "queue": queue,
            "scope": scope,
            "page": page,
        },
    )


@login_required
def assessment_review_detail(
    request,
    organization_slug: str,
    assessment_id: int,
):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    assessment = get_object_or_404(
        MatchAssessment.objects.for_organization(organization).select_related(
            "candidate_profile",
            "created_by",
            "requirements",
            "shortlist_entry__candidate",
            "shortlist_entry__match_run__requirements__vacancy",
        ),
        pk=assessment_id,
        shortlist_entry__match_run__requirements__vacancy__deleted_at__isnull=True,
    )
    review_item = build_assessment_review_item(
        assessment=assessment,
        user=request.user,
    )
    assessment_history = list(
        MatchAssessment.objects.for_organization(organization)
        .filter(shortlist_entry=assessment.shortlist_entry)
        .select_related("candidate_profile", "created_by")
        .order_by("-version", "-created_at", "-id")
    )
    decision_history = list(
        ReviewDecision.objects.for_organization(organization)
        .filter(shortlist_entry=assessment.shortlist_entry)
        .select_related("assessment", "created_by")
        .order_by("-version", "-created_at", "-id")
    )
    decision_eligibility = assess_review_decision_eligibility(
        assessment=assessment,
        user=request.user,
    )
    return render(
        request,
        "matching/assessment_review_detail.html",
        {
            "organization": organization,
            "assessment": assessment,
            "review_item": review_item,
            "assessment_history": assessment_history,
            "decision_history": decision_history,
            "decision_eligibility": decision_eligibility,
            "decision_form": ReviewDecisionForm(),
            "vacancy": assessment.requirements.vacancy,
            "entry": assessment.shortlist_entry,
            "run": assessment.shortlist_entry.match_run,
        },
    )


@login_required
@require_POST
def assessment_review_decide(
    request,
    organization_slug: str,
    assessment_id: int,
):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    assessment = get_object_or_404(
        MatchAssessment.objects.for_organization(organization).select_related(
            "candidate_profile",
            "shortlist_entry__candidate",
            "shortlist_entry__match_run__requirements__vacancy",
        ),
        pk=assessment_id,
        shortlist_entry__match_run__requirements__vacancy__deleted_at__isnull=True,
    )
    form = ReviewDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(
            request,
            "Select a decision and record recruiter notes before saving.",
        )
    else:
        try:
            decision = record_review_decision(
                assessment=assessment,
                user=request.user,
                decision=form.cleaned_data["decision"],
                notes=form.cleaned_data["notes"],
            )
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            messages.success(
                request,
                f"Decision version {decision.version} was recorded as "
                f"{decision.get_decision_display().lower()}.",
            )
    return redirect(
        "matching:assessment-review-detail",
        organization_slug=organization.slug,
        assessment_id=assessment.pk,
    )
