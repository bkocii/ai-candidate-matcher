from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import User
from candidates.models import Candidate
from matching.evaluation import CandidateFilterResult, FilterOutcome, filter_candidates
from matching.models import (
    MatchRun,
    RequirementSkill,
    ShortlistEntry,
)
from matching.scoring_policy import ALGORITHM_VERSION
from matching.skill_matching import (
    candidate_skills_by_canonical_key,
    unique_requirement_skills,
)
from matching.skill_taxonomy import canonical_skill_key
from matching.staleness import (
    INPUT_SNAPSHOT_VERSION,
    candidate_input_signature,
    requirements_input_signature,
)
from organizations.permissions import require_organization_object_access
from vacancies.models import VacancyRequirements

SHORTLIST_LIMIT = 20
MUST_HAVE_UNITS = 2
NICE_TO_HAVE_UNITS = 1
FULL_SCORE_CENTS = 10_000
SCORE_QUANTUM = Decimal("0.01")


@dataclass(frozen=True)
class SkillScore:
    requirement_skill_id: int
    skill_label: str
    importance: str
    importance_label: str
    matched: bool
    candidate_label: str
    evidence: str
    awarded_points: Decimal
    possible_points: Decimal

    def as_snapshot(self) -> dict[str, object]:
        return {
            "requirement_skill_id": self.requirement_skill_id,
            "skill_label": self.skill_label,
            "importance": self.importance,
            "importance_label": self.importance_label,
            "matched": self.matched,
            "candidate_label": self.candidate_label,
            "evidence": self.evidence,
            "awarded_points": str(self.awarded_points),
            "possible_points": str(self.possible_points),
        }


@dataclass(frozen=True)
class CandidateRelevanceScore:
    candidate: Candidate
    filter_outcome: str
    score: Decimal
    matched_must_have: int
    total_must_have: int
    matched_nice_to_have: int
    total_nice_to_have: int
    skill_scores: tuple[SkillScore, ...]


def _allocate_skill_points(
    requirement_skills: tuple[RequirementSkill, ...],
) -> dict[int, Decimal]:
    """Apportion exactly 100 points with a 2:1 must-have/nice-to-have ratio."""
    if not requirement_skills:
        return {}

    weighted_skills = [
        (
            item,
            MUST_HAVE_UNITS
            if item.importance == RequirementSkill.Importance.MUST_HAVE
            else NICE_TO_HAVE_UNITS,
        )
        for item in requirement_skills
    ]
    total_units = sum(units for _, units in weighted_skills)
    cent_allocations: dict[int, int] = {}
    remainders: list[tuple[int, int, int]] = []
    allocated_cents = 0

    for stable_order, (item, units) in enumerate(weighted_skills):
        cents, remainder = divmod(FULL_SCORE_CENTS * units, total_units)
        cent_allocations[item.pk] = cents
        allocated_cents += cents
        remainders.append((remainder, -stable_order, item.pk))

    remaining_cents = FULL_SCORE_CENTS - allocated_cents
    for _, _, item_id in sorted(remainders, reverse=True)[:remaining_cents]:
        cent_allocations[item_id] += 1

    return {
        item_id: (Decimal(cents) / 100).quantize(SCORE_QUANTUM)
        for item_id, cents in cent_allocations.items()
    }


def score_candidate_relevance(
    *,
    filter_result: CandidateFilterResult,
    requirement_skills: tuple[RequirementSkill, ...],
) -> CandidateRelevanceScore:
    """Score recorded skill matches without treating missing evidence as failure."""
    requirement_skills = unique_requirement_skills(requirement_skills)
    candidate_skills = candidate_skills_by_canonical_key(
        filter_result.candidate.skill_records.all()
    )
    must_have = tuple(
        record
        for record in requirement_skills
        if record.importance == RequirementSkill.Importance.MUST_HAVE
    )
    nice_to_have = tuple(
        record
        for record in requirement_skills
        if record.importance == RequirementSkill.Importance.NICE_TO_HAVE
    )
    per_skill_weights = _allocate_skill_points(requirement_skills)

    skill_scores = []
    for requirement_skill in requirement_skills:
        candidate_skill = candidate_skills.get(
            canonical_skill_key(requirement_skill.skill.name)
        )
        possible_points = per_skill_weights[requirement_skill.pk]
        awarded_points = possible_points if candidate_skill else Decimal("0")
        skill_scores.append(
            SkillScore(
                requirement_skill_id=requirement_skill.pk,
                skill_label=requirement_skill.source_label,
                importance=requirement_skill.importance,
                importance_label=requirement_skill.get_importance_display(),
                matched=candidate_skill is not None,
                candidate_label=(
                    candidate_skill.source_label if candidate_skill else "Not recorded"
                ),
                evidence=candidate_skill.evidence if candidate_skill else "",
                awarded_points=awarded_points.quantize(
                    SCORE_QUANTUM, rounding=ROUND_HALF_UP
                ),
                possible_points=possible_points.quantize(
                    SCORE_QUANTUM, rounding=ROUND_HALF_UP
                ),
            )
        )

    matched_must_have = sum(
        item.matched
        for item in skill_scores
        if item.importance == RequirementSkill.Importance.MUST_HAVE
    )
    matched_nice_to_have = sum(
        item.matched
        for item in skill_scores
        if item.importance == RequirementSkill.Importance.NICE_TO_HAVE
    )
    score = sum(
        (item.awarded_points for item in skill_scores),
        start=Decimal("0"),
    ).quantize(SCORE_QUANTUM, rounding=ROUND_HALF_UP)
    return CandidateRelevanceScore(
        candidate=filter_result.candidate,
        filter_outcome=filter_result.outcome,
        score=score,
        matched_must_have=matched_must_have,
        total_must_have=len(must_have),
        matched_nice_to_have=matched_nice_to_have,
        total_nice_to_have=len(nice_to_have),
        skill_scores=tuple(skill_scores),
    )


def _ranking_key(score: CandidateRelevanceScore) -> tuple[Decimal, int, int]:
    filter_priority = 0 if score.filter_outcome == FilterOutcome.PASSED else 1
    return (-score.score, filter_priority, score.candidate.pk)


@transaction.atomic
def generate_shortlist(
    *,
    requirements: VacancyRequirements,
    user: User,
) -> MatchRun:
    """Persist one bounded, explainable shortlist for current confirmed inputs."""
    require_organization_object_access(user, requirements)
    requirements = (
        VacancyRequirements.objects.select_related("vacancy")
        .prefetch_related("skill_records__skill")
        .get(pk=requirements.pk)
    )
    if requirements.status != VacancyRequirements.Status.CONFIRMED:
        raise ValidationError("Only confirmed requirements can produce a shortlist.")
    if requirements.vacancy.deleted_at is not None:
        raise ValidationError("Deleted vacancies cannot produce a shortlist.")
    current_requirements = requirements.vacancy.current_requirements
    if current_requirements is None or current_requirements.pk != requirements.pk:
        raise ValidationError(
            "Only the vacancy's current confirmed requirements can produce a shortlist."
        )

    filter_report = filter_candidates(requirements=requirements, user=user)
    requirement_skills = tuple(
        requirements.skill_records.select_related("skill").order_by(
            "importance", "position", "id"
        )
    )
    scores = [
        score_candidate_relevance(
            filter_result=result,
            requirement_skills=requirement_skills,
        )
        for result in filter_report.results
        if result.is_eligible
    ]
    scores.sort(key=_ranking_key)

    run = MatchRun.objects.create(
        requirements=requirements,
        algorithm_version=ALGORITHM_VERSION,
        input_snapshot_version=INPUT_SNAPSHOT_VERSION,
        requirements_input_signature=requirements_input_signature(requirements),
        candidate_input_signature=candidate_input_signature(
            result.candidate for result in filter_report.results
        ),
        shortlist_limit=SHORTLIST_LIMIT,
        evaluated_count=filter_report.evaluated_count,
        eligible_count=filter_report.eligible_count,
        shortlisted_count=min(len(scores), SHORTLIST_LIMIT),
        created_by=user,
    )
    for rank, score in enumerate(scores[:SHORTLIST_LIMIT], start=1):
        ShortlistEntry.objects.create(
            match_run=run,
            candidate=score.candidate,
            rank=rank,
            score=score.score,
            filter_outcome=score.filter_outcome,
            matched_must_have=score.matched_must_have,
            total_must_have=score.total_must_have,
            matched_nice_to_have=score.matched_nice_to_have,
            total_nice_to_have=score.total_nice_to_have,
            score_breakdown=[item.as_snapshot() for item in score.skill_scores],
        )
    return run
