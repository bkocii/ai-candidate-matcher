from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from accounts.models import User
from candidates.models import Candidate, CandidateSource
from matching.models import ShortlistEntry
from organizations.permissions import require_organization_object_access
from outreach.generation import assess_outreach_draft_eligibility
from outreach.models import (
    OutreachDraft,
    OutreachDraftAction,
    OutreachDraftApproval,
)


@dataclass(frozen=True)
class OutreachWorkflowEligibility:
    can_proceed: bool
    reason: str = ""


def _latest_draft_id(draft: OutreachDraft) -> int | None:
    return (
        OutreachDraft.objects.filter(shortlist_entry=draft.shortlist_entry)
        .order_by("-version", "-created_at", "-id")
        .values_list("pk", flat=True)
        .first()
    )


def _assess_current_draft_boundary(
    *,
    draft: OutreachDraft,
    user: User,
) -> OutreachWorkflowEligibility:
    require_organization_object_access(user, draft)
    if _latest_draft_id(draft) != draft.pk:
        return OutreachWorkflowEligibility(
            False,
            "Only the latest outreach draft version can be used for this action.",
        )
    source_eligibility = assess_outreach_draft_eligibility(
        decision=draft.review_decision,
        user=user,
    )
    if not source_eligibility.can_generate:
        return OutreachWorkflowEligibility(False, source_eligibility.reason)
    return OutreachWorkflowEligibility(True)


def assess_contact_permission(
    *,
    candidate: Candidate,
) -> OutreachWorkflowEligibility:
    sources = list(candidate.sources.all())
    if not sources:
        return OutreachWorkflowEligibility(
            False,
            "Record the candidate source, reason for storing data, and allowed "
            "contact before final approval.",
        )
    if any(
        source.consent_status == CandidateSource.ConsentStatus.WITHDRAWN
        for source in sources
    ):
        return OutreachWorkflowEligibility(
            False,
            "Consent is Withdrawn. Final outreach approval is blocked.",
        )
    if any(
        source.contact_permission == CandidateSource.ContactPermission.WITHDRAWN
        for source in sources
    ):
        return OutreachWorkflowEligibility(
            False,
            "Allowed contact is Do not contact. Final outreach approval is blocked.",
        )
    if any(
        source.contact_permission == CandidateSource.ContactPermission.RESTRICTED
        for source in sources
    ):
        return OutreachWorkflowEligibility(
            False,
            "Allowed contact is Application only. This rediscovery outreach requires "
            "Future roles allowed.",
        )
    if any(
        source.lawful_basis == CandidateSource.LawfulBasis.NOT_RECORDED
        for source in sources
    ):
        return OutreachWorkflowEligibility(
            False,
            "Record a Reason for storing data for every candidate source before "
            "final outreach approval.",
        )
    if any(
        source.lawful_basis == CandidateSource.LawfulBasis.CONSENT
        and source.consent_status != CandidateSource.ConsentStatus.GRANTED
        for source in sources
    ):
        return OutreachWorkflowEligibility(
            False,
            "Consent is the selected reason for storing data, but Consent is not "
            "recorded as Given.",
        )
    if not any(
        source.contact_permission == CandidateSource.ContactPermission.PERMITTED
        for source in sources
    ):
        return OutreachWorkflowEligibility(
            False,
            "At least one candidate source must record Allowed contact as Future "
            "roles allowed before final outreach approval.",
        )
    return OutreachWorkflowEligibility(True)


def assess_draft_edit_eligibility(
    *,
    draft: OutreachDraft,
    user: User,
) -> OutreachWorkflowEligibility:
    return _assess_current_draft_boundary(draft=draft, user=user)


def assess_final_approval_eligibility(
    *,
    draft: OutreachDraft,
    user: User,
) -> OutreachWorkflowEligibility:
    current = _assess_current_draft_boundary(draft=draft, user=user)
    if not current.can_proceed:
        return current
    if OutreachDraftApproval.objects.filter(draft=draft).exists():
        return OutreachWorkflowEligibility(
            False,
            "This exact draft version already has final approval.",
        )
    return assess_contact_permission(candidate=draft.shortlist_entry.candidate)


def assess_manual_action_eligibility(
    *,
    draft: OutreachDraft,
    user: User,
) -> OutreachWorkflowEligibility:
    current = _assess_current_draft_boundary(draft=draft, user=user)
    if not current.can_proceed:
        return current
    if not OutreachDraftApproval.objects.filter(draft=draft).exists():
        return OutreachWorkflowEligibility(
            False,
            "Approve this exact draft before copying or exporting it.",
        )
    return assess_contact_permission(candidate=draft.shortlist_entry.candidate)


def _load_locked_draft(draft: OutreachDraft) -> OutreachDraft:
    entry = ShortlistEntry.objects.select_for_update().get(pk=draft.shortlist_entry_id)
    Candidate.objects.select_for_update().get(pk=entry.candidate_id)
    list(
        CandidateSource.objects.select_for_update().filter(
            candidate_id=entry.candidate_id
        )
    )
    return OutreachDraft.objects.select_related(
        "review_decision__assessment__candidate_profile",
        "review_decision__assessment__requirements__vacancy__organization",
        "shortlist_entry__candidate",
        "shortlist_entry__match_run__requirements__vacancy",
    ).get(pk=draft.pk, shortlist_entry=entry)


@transaction.atomic
def edit_outreach_draft(
    *,
    draft: OutreachDraft,
    user: User,
    subject: str,
    body: str,
) -> OutreachDraft:
    """Append an immutable recruiter-edited version from the latest current draft."""
    require_organization_object_access(user, draft)
    draft = _load_locked_draft(draft)
    eligibility = assess_draft_edit_eligibility(draft=draft, user=user)
    if not eligibility.can_proceed:
        raise ValidationError(eligibility.reason)
    version = (
        OutreachDraft.objects.filter(shortlist_entry=draft.shortlist_entry).aggregate(
            Max("version")
        )["version__max"]
        or 0
    ) + 1
    return OutreachDraft.objects.create(
        shortlist_entry=draft.shortlist_entry,
        review_decision=draft.review_decision,
        version=version,
        schema_version=draft.schema_version,
        creation_method=OutreachDraft.CreationMethod.RECRUITER_EDITED,
        parent_draft=draft,
        subject=subject.strip(),
        body=body.strip(),
        created_by=user,
    )


@transaction.atomic
def approve_outreach_draft(
    *,
    draft: OutreachDraft,
    user: User,
    notes: str,
    contact_permission_confirmed: bool,
) -> OutreachDraftApproval:
    """Approve the exact latest draft after currentness and permission checks."""
    require_organization_object_access(user, draft)
    draft = _load_locked_draft(draft)
    eligibility = assess_final_approval_eligibility(draft=draft, user=user)
    if not eligibility.can_proceed:
        raise ValidationError(eligibility.reason)
    return OutreachDraftApproval.objects.create(
        draft=draft,
        notes=notes.strip(),
        contact_permission_confirmed=contact_permission_confirmed,
        approved_by=user,
    )


@transaction.atomic
def record_outreach_draft_action(
    *,
    draft: OutreachDraft,
    user: User,
    action_type: str,
) -> OutreachDraftAction:
    """Record one manual copy/export action for an exact approved current draft."""
    require_organization_object_access(user, draft)
    valid_actions = {value for value, _label in OutreachDraftAction.ActionType.choices}
    if action_type not in valid_actions:
        raise ValidationError("Select a supported outreach draft action.")
    draft = _load_locked_draft(draft)
    eligibility = assess_manual_action_eligibility(draft=draft, user=user)
    if not eligibility.can_proceed:
        raise ValidationError(eligibility.reason)
    return OutreachDraftAction.objects.create(
        draft=draft,
        action_type=action_type,
        actor=user,
    )
