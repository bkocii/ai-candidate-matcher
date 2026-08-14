from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import User
from candidates.models import Candidate, CandidateProfile
from matching.models import MatchAssessment, ReviewDecision, ShortlistEntry
from matching.staleness import assess_match_run_staleness
from organizations.permissions import require_organization_object_access


@dataclass(frozen=True)
class ReviewDecisionEligibility:
    can_record: bool
    reason: str = ""


def assess_review_decision_eligibility(
    *,
    assessment: MatchAssessment,
    user: User,
) -> ReviewDecisionEligibility:
    """Check that a human decision would refer to the current evidence boundary."""
    require_organization_object_access(user, assessment)
    entry = assessment.shortlist_entry
    candidate = entry.candidate

    if candidate.status != Candidate.Status.ACTIVE:
        return ReviewDecisionEligibility(
            False,
            "Only an active candidate can receive a current review decision.",
        )
    if entry.match_run.vacancy.deleted_at is not None:
        return ReviewDecisionEligibility(
            False,
            "The vacancy was deleted from the recruiter workspace.",
        )

    latest_assessment = (
        MatchAssessment.objects.filter(shortlist_entry=entry)
        .order_by("-version", "-created_at", "-id")
        .first()
    )
    if latest_assessment is None or latest_assessment.pk != assessment.pk:
        return ReviewDecisionEligibility(
            False,
            "Open the latest assessment version before recording a decision.",
        )

    current_profile_id = (
        CandidateProfile.objects.filter(
            candidate=candidate,
            status=CandidateProfile.Status.CONFIRMED,
        )
        .order_by("-version", "-created_at", "-id")
        .values_list("pk", flat=True)
        .first()
    )
    if current_profile_id != assessment.candidate_profile_id:
        return ReviewDecisionEligibility(
            False,
            "The candidate's confirmed profile changed. Generate a current "
            "shortlist and assessment before deciding.",
        )

    staleness = assess_match_run_staleness(run=entry.match_run, user=user)
    if staleness.is_stale:
        return ReviewDecisionEligibility(
            False,
            "The shortlist inputs changed. Generate a current shortlist and "
            "assessment before deciding.",
        )
    return ReviewDecisionEligibility(True)


@transaction.atomic
def record_review_decision(
    *,
    assessment: MatchAssessment,
    user: User,
    decision: str,
    notes: str,
) -> ReviewDecision:
    """Append one immutable, actor-attributed human decision version."""
    require_organization_object_access(user, assessment)
    valid_decisions = {value for value, _label in ReviewDecision.Decision.choices}
    if decision not in valid_decisions:
        raise ValidationError({"decision": "Select a supported recruiter decision."})
    notes = notes.strip()
    if not notes:
        raise ValidationError({"notes": "Record recruiter notes for the decision."})

    entry = ShortlistEntry.objects.select_for_update().get(
        pk=assessment.shortlist_entry_id
    )
    assessment = MatchAssessment.objects.select_related(
        "candidate_profile",
        "shortlist_entry__candidate",
        "shortlist_entry__match_run__requirements__vacancy",
    ).get(pk=assessment.pk, shortlist_entry=entry)
    eligibility = assess_review_decision_eligibility(
        assessment=assessment,
        user=user,
    )
    if not eligibility.can_record:
        raise ValidationError(eligibility.reason)

    latest_decision = (
        ReviewDecision.objects.filter(shortlist_entry=entry)
        .order_by("-version", "-created_at", "-id")
        .first()
    )
    version = latest_decision.version + 1 if latest_decision is not None else 1
    return ReviewDecision.objects.create(
        shortlist_entry=entry,
        assessment=assessment,
        version=version,
        decision=decision,
        notes=notes,
        created_by=user,
    )
