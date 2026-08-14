from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ai_gateway import AIGatewayError
from matching.models import ReviewDecision
from organizations.models import Organization
from outreach.generation import generate_outreach_draft
from outreach.models import OutreachDraft


@login_required
@require_POST
def outreach_draft_generate(request, organization_slug: str, decision_id: int):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    decision = get_object_or_404(
        ReviewDecision.objects.for_organization(organization).select_related(
            "assessment",
            "shortlist_entry__match_run__requirements__vacancy",
        ),
        pk=decision_id,
        shortlist_entry__match_run__requirements__vacancy__deleted_at__isnull=True,
    )
    try:
        result = generate_outreach_draft(decision=decision, user=request.user)
    except (AIGatewayError, ValidationError) as error:
        public_message = (
            "; ".join(error.messages)
            if isinstance(error, ValidationError)
            else str(error)
        )
        messages.error(request, public_message)
        return redirect(
            "matching:assessment-review-detail",
            organization_slug=organization.slug,
            assessment_id=decision.assessment_id,
        )
    messages.success(
        request,
        f"Outreach draft version {result.draft.version} was generated for review.",
    )
    return redirect(
        "outreach:outreach-draft-detail",
        organization_slug=organization.slug,
        draft_id=result.draft.pk,
    )


@login_required
def outreach_draft_detail(request, organization_slug: str, draft_id: int):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    draft = get_object_or_404(
        OutreachDraft.objects.for_organization(organization).select_related(
            "created_by",
            "review_decision__assessment",
            "shortlist_entry__candidate",
            "shortlist_entry__match_run__requirements__vacancy",
        ),
        pk=draft_id,
        shortlist_entry__match_run__requirements__vacancy__deleted_at__isnull=True,
    )
    history = (
        OutreachDraft.objects.for_organization(organization)
        .filter(shortlist_entry=draft.shortlist_entry)
        .select_related("created_by", "review_decision")
    )
    return render(
        request,
        "outreach/outreach_draft_detail.html",
        {
            "organization": organization,
            "draft": draft,
            "history": history,
            "candidate": draft.shortlist_entry.candidate,
            "vacancy": draft.shortlist_entry.match_run.requirements.vacancy,
        },
    )
