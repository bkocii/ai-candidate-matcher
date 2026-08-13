from dataclasses import dataclass

from django.db.models import OuterRef, Subquery

from accounts.models import User
from candidates.models import CandidateProfile
from matching.models import MatchAssessment
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
        .annotate(current_profile_id=Subquery(current_profile_id))
    )


def _review_item(
    assessment: MatchAssessment,
    *,
    staleness: MatchRunStaleness,
) -> AssessmentReviewItem:
    return AssessmentReviewItem(
        assessment=assessment,
        staleness=staleness,
        current_profile_id=assessment.current_profile_id,
        gap_count=len(assessment.gaps),
        uncertainty_count=len(assessment.uncertainties),
        profile_ambiguity_count=len(assessment.candidate_profile.ambiguities),
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
        if run.pk not in staleness_by_run:
            staleness_by_run[run.pk] = assess_match_run_staleness(run=run, user=user)
        items.append(
            _review_item(
                assessment,
                staleness=staleness_by_run[run.pk],
            )
        )

    items.sort(key=lambda item: item.priority)
    focus_count = sum(item.needs_focus for item in items)
    changed_count = sum(item.inputs_changed for item in items)
    return AssessmentReviewQueue(
        items=tuple(items),
        total_count=len(items),
        focus_count=focus_count,
        changed_count=changed_count,
        routine_count=len(items) - focus_count,
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
    return _review_item(
        assessment,
        staleness=assess_match_run_staleness(
            run=assessment.shortlist_entry.match_run,
            user=user,
        ),
    )
