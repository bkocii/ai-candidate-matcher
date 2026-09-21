from urllib.parse import quote, urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ai_gateway import AIGatewayError
from matching.models import ReviewDecision
from organizations.models import Organization
from outreach.forms import OutreachDraftApprovalForm, OutreachDraftEditForm
from outreach.generation import generate_outreach_draft
from outreach.models import OutreachDraft, OutreachDraftAction
from outreach.workflow import (
    approve_outreach_draft,
    assess_contact_permission,
    assess_draft_edit_eligibility,
    assess_email_app_eligibility,
    assess_manual_action_eligibility,
    edit_outreach_draft,
    record_outreach_draft_action,
)


def _organization_and_draft(request, organization_slug: str, draft_id: int):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    draft = get_object_or_404(
        OutreachDraft.objects.for_organization(organization).select_related(
            "created_by",
            "parent_draft",
            "review_decision__assessment",
            "shortlist_entry__candidate",
            "shortlist_entry__match_run__requirements__vacancy",
        ),
        pk=draft_id,
        shortlist_entry__match_run__requirements__vacancy__deleted_at__isnull=True,
    )
    return organization, draft


def _validation_message(error: ValidationError) -> str:
    return "; ".join(error.messages)


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
    candidate = decision.shortlist_entry.candidate
    contact_eligibility = assess_contact_permission(candidate=candidate)
    if not candidate.email.strip():
        messages.error(
            request,
            "Add the candidate's email address before preparing an email draft.",
        )
        return redirect(
            "matching:assessment-review-detail",
            organization_slug=organization.slug,
            assessment_id=decision.assessment_id,
        )
    if not contact_eligibility.can_proceed:
        messages.error(request, contact_eligibility.reason)
        return redirect(
            "matching:assessment-review-detail",
            organization_slug=organization.slug,
            assessment_id=decision.assessment_id,
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
    organization, draft = _organization_and_draft(
        request,
        organization_slug,
        draft_id,
    )
    history = (
        OutreachDraft.objects.for_organization(organization)
        .filter(shortlist_entry=draft.shortlist_entry)
        .select_related(
            "created_by",
            "review_decision",
            "final_approval__approved_by",
        )
    )
    approval = getattr(draft, "final_approval", None)
    action_history = list(
        OutreachDraftAction.objects.for_organization(organization)
        .filter(draft=draft)
        .select_related("actor")
    )
    edit_eligibility = assess_draft_edit_eligibility(
        draft=draft,
        user=request.user,
    )
    action_eligibility = assess_manual_action_eligibility(
        draft=draft,
        user=request.user,
    )
    email_app_eligibility = assess_email_app_eligibility(
        draft=draft,
        user=request.user,
    )
    contact_eligibility = assess_contact_permission(
        candidate=draft.shortlist_entry.candidate
    )
    candidate_sources = list(draft.shortlist_entry.candidate.sources.all())
    lawful_basis_summary = ", ".join(
        dict.fromkeys(source.recruiter_lawful_basis for source in candidate_sources)
    )
    consent_summary = ", ".join(
        dict.fromkeys(source.recruiter_consent_status for source in candidate_sources)
    )
    response = render(
        request,
        "outreach/outreach_draft_detail.html",
        {
            "organization": organization,
            "draft": draft,
            "history": history,
            "candidate": draft.shortlist_entry.candidate,
            "vacancy": draft.shortlist_entry.match_run.requirements.vacancy,
            "candidate_sources": candidate_sources,
            "approval": approval,
            "edit_form": OutreachDraftEditForm(
                initial={"subject": draft.subject, "body": draft.body}
            ),
            "action_history": action_history,
            "edit_eligibility": edit_eligibility,
            "action_eligibility": action_eligibility,
            "email_app_eligibility": email_app_eligibility,
            "contact_eligibility": contact_eligibility,
            "lawful_basis_summary": lawful_basis_summary,
            "consent_summary": consent_summary,
            "composer_focus": (
                request.GET.get("prepared") == "1"
                or request.GET.get("edited") == str(draft.version)
            ),
        },
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def outreach_draft_edit(request, organization_slug: str, draft_id: int):
    organization, draft = _organization_and_draft(
        request,
        organization_slug,
        draft_id,
    )
    eligibility = assess_draft_edit_eligibility(draft=draft, user=request.user)
    if not eligibility.can_proceed:
        messages.error(request, eligibility.reason)
        return redirect(
            "outreach:outreach-draft-detail",
            organization_slug=organization.slug,
            draft_id=draft.pk,
        )
    form = OutreachDraftEditForm(
        request.POST or None,
        initial={"subject": draft.subject, "body": draft.body},
    )
    if request.method == "POST" and form.is_valid():
        try:
            edited = edit_outreach_draft(
                draft=draft,
                user=request.user,
                subject=form.cleaned_data["subject"],
                body=form.cleaned_data["body"],
            )
        except ValidationError as error:
            form.add_error(None, _validation_message(error))
        else:
            messages.success(
                request,
                f"Outreach draft version {edited.version} was saved for final review.",
            )
            detail_url = reverse(
                "outreach:outreach-draft-detail",
                args=[organization.slug, edited.pk],
            )
            return redirect(f"{detail_url}?edited={edited.version}#email-composer")
    response = render(
        request,
        "outreach/outreach_draft_form.html",
        {
            "organization": organization,
            "draft": draft,
            "form": form,
            "candidate": draft.shortlist_entry.candidate,
            "vacancy": draft.shortlist_entry.match_run.requirements.vacancy,
        },
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_POST
def outreach_draft_approve(request, organization_slug: str, draft_id: int):
    organization, draft = _organization_and_draft(
        request,
        organization_slug,
        draft_id,
    )
    form = OutreachDraftApprovalForm(request.POST)
    if not form.is_valid():
        messages.error(
            request,
            "Record final approval notes and confirm the source, consent when "
            "required, and allowed contact.",
        )
    else:
        try:
            approve_outreach_draft(
                draft=draft,
                user=request.user,
                notes=form.cleaned_data["notes"],
                contact_permission_confirmed=form.cleaned_data[
                    "contact_permission_confirmed"
                ],
            )
        except ValidationError as error:
            messages.error(request, _validation_message(error))
        else:
            messages.success(
                request,
                f"Draft version {draft.version} received final approval. Nothing "
                "was sent.",
            )
    return redirect(
        "outreach:outreach-draft-detail",
        organization_slug=organization.slug,
        draft_id=draft.pk,
    )


@login_required
@require_POST
def outreach_draft_copy(request, organization_slug: str, draft_id: int):
    _organization, draft = _organization_and_draft(
        request,
        organization_slug,
        draft_id,
    )
    try:
        record_outreach_draft_action(
            draft=draft,
            user=request.user,
            action_type=OutreachDraftAction.ActionType.COPY,
        )
    except ValidationError as error:
        response = JsonResponse({"error": _validation_message(error)}, status=400)
    else:
        response = JsonResponse(
            {
                "recorded": True,
                "copy_text": f"Subject: {draft.subject}\n\n{draft.body}",
            }
        )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_POST
def outreach_draft_email_app(request, organization_slug: str, draft_id: int):
    _organization, draft = _organization_and_draft(
        request,
        organization_slug,
        draft_id,
    )
    try:
        record_outreach_draft_action(
            draft=draft,
            user=request.user,
            action_type=OutreachDraftAction.ActionType.EMAIL_APP,
        )
    except ValidationError as error:
        response = JsonResponse({"error": _validation_message(error)}, status=400)
    else:
        recipient = quote(draft.shortlist_entry.candidate.email, safe="@._+-")
        query = urlencode(
            {"subject": draft.subject, "body": draft.body},
            quote_via=quote,
        )
        response = JsonResponse(
            {
                "recorded": True,
                "mailto_url": f"mailto:{recipient}?{query}",
            }
        )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_POST
def outreach_draft_export(request, organization_slug: str, draft_id: int):
    organization, draft = _organization_and_draft(
        request,
        organization_slug,
        draft_id,
    )
    try:
        record_outreach_draft_action(
            draft=draft,
            user=request.user,
            action_type=OutreachDraftAction.ActionType.EXPORT,
        )
    except ValidationError as error:
        messages.error(request, _validation_message(error))
        return redirect(
            "outreach:outreach-draft-detail",
            organization_slug=organization.slug,
            draft_id=draft.pk,
        )
    content = f"Subject: {draft.subject}\n\n{draft.body}\n"
    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="outreach-draft-{draft.pk}-v{draft.version}.txt"'
    )
    response["Cache-Control"] = "private, no-store"
    return response
