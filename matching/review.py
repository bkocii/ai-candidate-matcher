from dataclasses import dataclass

from django.db.models import OuterRef, Prefetch, Subquery

from accounts.models import User
from candidates.models import CandidateProfile
from matching.models import MatchAssessment, ReviewDecision
from matching.staleness import MatchRunStaleness, assess_match_run_staleness
from organizations.models import Organization
from organizations.permissions import require_organization_access


@dataclass(frozen=True)
class AssessmentReviewItem:
    """Compact, derived review state for one entry's latest assessment."""

    assessment: MatchAssessment
    staleness: MatchRunStaleness
    current_profile_id: int | None
    gap_count: int
    uncertainty_count: int
    profile_ambiguity_count: int
    latest_decision: ReviewDecision | None

    @property
    def profile_changed(self) -> bool:
        return self.current_profile_id != self.assessment.candidate_profile_id

    @property
    def inputs_changed(self) -> bool:
        return self.staleness.is_stale or self.profile_changed

    @property
    def deterministic_review_needed(self) -> bool:
        return self.assessment.shortlist_entry.filter_outcome == "review"

    @property
    def current_decision(self) -> ReviewDecision | None:
        if (
            self.latest_decision is not None
            and self.latest_decision.assessment_id == self.assessment.pk
        ):
            return self.latest_decision
        return None

    @property
    def decision_pending(self) -> bool:
        return self.current_decision is None

    @property
    def needs_focus(self) -> bool:
        return any(
            (
                self.inputs_changed,
                self.gap_count,
                self.uncertainty_count,
                self.profile_ambiguity_count,
                self.deterministic_review_needed,
            )
        )

    @property
    def priority(self) -> tuple[int, int, int, int, float]:
        if self.inputs_changed:
            category = 0
        elif self.gap_count:
            category = 1
        elif self.uncertainty_count:
            category = 2
        elif self.profile_ambiguity_count or self.deterministic_review_needed:
            category = 3
        else:
            category = 4
        return (
            category,
            -self.gap_count,
            -self.uncertainty_count,
            -self.profile_ambiguity_count,
            -self.assessment.created_at.timestamp(),
        )


@dataclass(frozen=True)
class AssessmentReviewQueue:
    items: tuple[AssessmentReviewItem, ...]
    total_count: int
    focus_count: int
    changed_count: int
    routine_count: int
    pending_count: int
    approved_count: int
    rejected_count: int
    revisit_count: int


def _latest_assessments(organization: Organization):
    latest_assessment_id = (
        MatchAssessment.objects.filter(
            shortlist_entry_id=OuterRef("shortlist_entry_id")
        )
        .order_by("-version", "-created_at", "-id")
        .values("pk")[:1]
    )
    current_profile_id = (
        CandidateProfile.objects.filter(
            candidate_id=OuterRef("shortlist_entry__candidate_id"),
            status=CandidateProfile.Status.CONFIRMED,
        )
        .order_by("-version", "-created_at", "-id")
        .values("pk")[:1]
    )
    return (
        MatchAssessment.objects.for_organization(organization)
        .filter(
            pk=Subquery(latest_assessment_id),
            shortlist_entry__match_run__requirements__vacancy__deleted_at__isnull=True,
        )
        .select_related(
            "candidate_profile",
            "created_by",
            "requirements",
            "shortlist_entry__candidate",
            "shortlist_entry__match_run__requirements__vacancy",
        )
        .prefetch_related(
            Prefetch(
                "shortlist_entry__review_decisions",
                queryset=ReviewDecision.objects.select_related(
                    "assessment", "created_by"
                ).order_by("-version", "-created_at", "-id"),
                to_attr="decision_history_for_review",
            )
        )
        .annotate(current_profile_id=Subquery(current_profile_id))
    )


def _review_item(
    assessment: MatchAssessment,
    *,
    staleness: MatchRunStaleness,
    latest_decision: ReviewDecision | None,
) -> AssessmentReviewItem:
    return AssessmentReviewItem(
        assessment=assessment,
        staleness=staleness,
        current_profile_id=assessment.current_profile_id,
        gap_count=len(assessment.gaps),
        uncertainty_count=len(assessment.uncertainties),
        profile_ambiguity_count=len(assessment.candidate_profile.ambiguities),
        latest_decision=latest_decision,
    )


def build_assessment_review_queue(
    *,
    organization: Organization,
    user: User,
) -> AssessmentReviewQueue:
    """Return latest assessments with changed and exception-heavy items first."""
    require_organization_access(user, organization)
    staleness_by_run: dict[int, MatchRunStaleness] = {}
    items: list[AssessmentReviewItem] = []
    for assessment in _latest_assessments(organization):
        run = assessment.shortlist_entry.match_run
        decision_history = assessment.shortlist_entry.decision_history_for_review
        latest_decision = decision_history[0] if decision_history else None
        if run.pk not in staleness_by_run:
            staleness_by_run[run.pk] = assess_match_run_staleness(run=run, user=user)
        items.append(
            _review_item(
                assessment,
                staleness=staleness_by_run[run.pk],
                latest_decision=latest_decision,
            )
        )

    items.sort(key=lambda item: item.priority)
    focus_count = sum(item.needs_focus for item in items)
    changed_count = sum(item.inputs_changed for item in items)
    pending_count = sum(item.decision_pending for item in items)
    approved_count = sum(
        item.current_decision is not None
        and item.current_decision.decision == ReviewDecision.Decision.APPROVED
        for item in items
    )
    rejected_count = sum(
        item.current_decision is not None
        and item.current_decision.decision == ReviewDecision.Decision.REJECTED
        for item in items
    )
    revisit_count = sum(
        item.current_decision is not None
        and item.current_decision.decision == ReviewDecision.Decision.REVISIT
        for item in items
    )
    return AssessmentReviewQueue(
        items=tuple(items),
        total_count=len(items),
        focus_count=focus_count,
        changed_count=changed_count,
        routine_count=len(items) - focus_count,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        revisit_count=revisit_count,
    )


def build_assessment_review_item(
    *,
    assessment: MatchAssessment,
    user: User,
) -> AssessmentReviewItem:
    """Build currentness and exception state for an authorized assessment."""
    require_organization_access(user, assessment.organization)
    current_profile_id = (
        CandidateProfile.objects.filter(
            candidate=assessment.shortlist_entry.candidate,
            status=CandidateProfile.Status.CONFIRMED,
        )
        .order_by("-version", "-created_at", "-id")
        .values_list("pk", flat=True)
        .first()
    )
    assessment.current_profile_id = current_profile_id
    latest_decision = (
        ReviewDecision.objects.filter(shortlist_entry=assessment.shortlist_entry)
        .select_related("assessment", "created_by")
        .order_by("-version", "-created_at", "-id")
        .first()
    )
    return _review_item(
        assessment,
        staleness=assess_match_run_staleness(
            run=assessment.shortlist_entry.match_run,
            user=user,
        ),
        latest_decision=latest_decision,
    )
