from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError

from accounts.models import User
from candidates.models import Candidate, CandidateProfile
from matching.models import CandidateSkill, HardConstraintRule, normalize_taxonomy_value
from organizations.permissions import require_organization_object_access
from vacancies.models import VacancyRequirements


@dataclass(frozen=True)
class RuleEvaluation:
    """One inspectable deterministic rule result."""

    rule_id: int
    rule_type: str
    rule_label: str
    source_text: str
    outcome: str
    expected_value: str
    candidate_value: str
    explanation: str
    evidence: str


@dataclass(frozen=True)
class CandidateFilterResult:
    """Aggregated hard-constraint result for one candidate."""

    candidate: Candidate
    outcome: str
    rule_results: tuple[RuleEvaluation, ...]

    @property
    def is_eligible(self) -> bool:
        return self.outcome != FilterOutcome.FAILED


@dataclass(frozen=True)
class CandidateFilterReport:
    """A non-persisted, version-specific deterministic filtering report."""

    requirements: VacancyRequirements
    results: tuple[CandidateFilterResult, ...]

    @property
    def evaluated_count(self) -> int:
        return len(self.results)

    @property
    def passed_count(self) -> int:
        return sum(result.outcome == FilterOutcome.PASSED for result in self.results)

    @property
    def review_count(self) -> int:
        return sum(result.outcome == FilterOutcome.REVIEW for result in self.results)

    @property
    def failed_count(self) -> int:
        return sum(result.outcome == FilterOutcome.FAILED for result in self.results)

    @property
    def eligible_count(self) -> int:
        return self.passed_count + self.review_count


class RuleOutcome:
    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class FilterOutcome:
    PASSED = "passed"
    REVIEW = "review"
    FAILED = "failed"


def _display_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _expected_value(rule: HardConstraintRule) -> str:
    if rule.rule_type == HardConstraintRule.RuleType.REQUIRED_SKILL:
        return rule.skill.name
    if rule.rule_type == HardConstraintRule.RuleType.MINIMUM_EXPERIENCE:
        return f"At least {_display_decimal(rule.numeric_value)} years"
    return rule.expected_value


def _unknown(
    rule: HardConstraintRule,
    *,
    explanation: str,
    candidate_value: str = "Not recorded",
    evidence: str = "",
) -> RuleEvaluation:
    return RuleEvaluation(
        rule_id=rule.pk,
        rule_type=rule.rule_type,
        rule_label=rule.get_rule_type_display(),
        source_text=rule.source_text,
        outcome=RuleOutcome.UNKNOWN,
        expected_value=_expected_value(rule),
        candidate_value=candidate_value,
        explanation=explanation,
        evidence=evidence,
    )


def _evaluate_required_skill(
    rule: HardConstraintRule,
    candidate_skills: dict[int, CandidateSkill],
) -> RuleEvaluation:
    candidate_skill = candidate_skills.get(rule.skill_id)
    if candidate_skill is None:
        return _unknown(
            rule,
            explanation=(
                f"No structured {rule.skill.name} skill fact is recorded. "
                "Absence is not evidence that the candidate lacks the skill."
            ),
        )
    return RuleEvaluation(
        rule_id=rule.pk,
        rule_type=rule.rule_type,
        rule_label=rule.get_rule_type_display(),
        source_text=rule.source_text,
        outcome=RuleOutcome.PASSED,
        expected_value=_expected_value(rule),
        candidate_value=candidate_skill.source_label,
        explanation=f"The recorded skill matches {rule.skill.name}.",
        evidence=candidate_skill.evidence,
    )


def _evaluate_minimum_experience(
    rule: HardConstraintRule,
    candidate_skills: dict[int, CandidateSkill],
) -> RuleEvaluation:
    known_years = [
        record
        for record in candidate_skills.values()
        if record.years_experience is not None
    ]
    if not known_years:
        return _unknown(
            rule,
            explanation="No structured candidate experience duration is recorded.",
        )

    strongest = max(known_years, key=lambda record: record.years_experience)
    observed = strongest.years_experience
    candidate_value = f"{_display_decimal(observed)} years with {strongest.skill.name}"
    if observed >= rule.numeric_value:
        return RuleEvaluation(
            rule_id=rule.pk,
            rule_type=rule.rule_type,
            rule_label=rule.get_rule_type_display(),
            source_text=rule.source_text,
            outcome=RuleOutcome.PASSED,
            expected_value=_expected_value(rule),
            candidate_value=candidate_value,
            explanation=(
                "Recorded skill experience proves the minimum duration is met."
            ),
            evidence=strongest.evidence,
        )
    return _unknown(
        rule,
        candidate_value=candidate_value,
        explanation=(
            "Recorded skill experience is below the threshold, but partial skill "
            "evidence cannot prove the candidate's total experience is insufficient."
        ),
        evidence=strongest.evidence,
    )


def _evaluate_location(
    rule: HardConstraintRule,
    candidate: Candidate,
    profile: CandidateProfile | None,
) -> RuleEvaluation:
    candidate_location = candidate.location.strip()
    evidence = "Candidate record location"
    if not candidate_location and profile is not None:
        candidate_location = profile.location.strip()
        evidence = profile.fact_evidence.get("location", "")
    if not candidate_location:
        return _unknown(
            rule,
            explanation="No structured candidate location is recorded.",
        )

    candidate_location = " ".join(candidate_location.split())
    outcome = (
        RuleOutcome.PASSED
        if normalize_taxonomy_value(candidate_location)
        == rule.normalized_expected_value
        else RuleOutcome.FAILED
    )
    explanation = (
        "The recorded candidate location matches the required location."
        if outcome == RuleOutcome.PASSED
        else "The recorded candidate location does not match the required location."
    )
    return RuleEvaluation(
        rule_id=rule.pk,
        rule_type=rule.rule_type,
        rule_label=rule.get_rule_type_display(),
        source_text=rule.source_text,
        outcome=outcome,
        expected_value=_expected_value(rule),
        candidate_value=candidate_location,
        explanation=explanation,
        evidence=evidence,
    )


def _profile_items_for_rule(
    *,
    rule: HardConstraintRule,
    profile: CandidateProfile,
) -> tuple[tuple[str, str], ...]:
    if rule.rule_type == HardConstraintRule.RuleType.WORK_MODE:
        if profile.work_mode_preference == CandidateProfile.WorkMode.UNKNOWN:
            return ()
        return (
            (
                profile.work_mode_preference,
                profile.fact_evidence.get("work_mode_preference", ""),
            ),
        )
    if rule.rule_type == HardConstraintRule.RuleType.LANGUAGE:
        values = []
        for item in profile.languages:
            label = item["language"]
            if item.get("proficiency"):
                label = f"{label} {item['proficiency']}"
            values.append((label, item["evidence"]))
            values.append((item["language"], item["evidence"]))
        return tuple(values)
    if rule.rule_type == HardConstraintRule.RuleType.EDUCATION:
        return tuple(
            (item["qualification"], item["evidence"]) for item in profile.education
        )
    if rule.rule_type == HardConstraintRule.RuleType.CERTIFICATION:
        return tuple(
            (item["name"], item["evidence"]) for item in profile.certifications
        )
    if rule.rule_type == HardConstraintRule.RuleType.EMPLOYMENT_TYPE:
        evidence = profile.fact_evidence.get("employment_type_preferences", "")
        return tuple(
            (preference, evidence) for preference in profile.employment_type_preferences
        )
    return ()


def _evaluate_profile_fact(
    *,
    rule: HardConstraintRule,
    profile: CandidateProfile | None,
) -> RuleEvaluation:
    if profile is None:
        return _unknown(
            rule,
            explanation=(
                f"No confirmed candidate profile supplies a structured "
                f"{rule.get_rule_type_display().lower()} fact. The candidate "
                "remains eligible for recruiter review."
            ),
        )
    facts = _profile_items_for_rule(rule=rule, profile=profile)
    for candidate_value, evidence in facts:
        if normalize_taxonomy_value(candidate_value) == rule.normalized_expected_value:
            return RuleEvaluation(
                rule_id=rule.pk,
                rule_type=rule.rule_type,
                rule_label=rule.get_rule_type_display(),
                source_text=rule.source_text,
                outcome=RuleOutcome.PASSED,
                expected_value=_expected_value(rule),
                candidate_value=candidate_value,
                explanation=(
                    "The confirmed candidate profile contains a matching "
                    "source-grounded fact."
                ),
                evidence=evidence,
            )
    if not facts:
        explanation = (
            f"No structured candidate {rule.get_rule_type_display().lower()} fact "
            "is recorded."
        )
    else:
        explanation = (
            "The confirmed profile has related facts, but they do not prove this "
            "requirement. Absence is not treated as a failure."
        )
    return _unknown(rule, explanation=explanation)


def evaluate_rule(
    *,
    rule: HardConstraintRule,
    candidate: Candidate,
    candidate_skills: dict[int, CandidateSkill],
    candidate_profile: CandidateProfile | None = None,
) -> RuleEvaluation:
    if rule.rule_type == HardConstraintRule.RuleType.REQUIRED_SKILL:
        return _evaluate_required_skill(rule, candidate_skills)
    if rule.rule_type == HardConstraintRule.RuleType.MINIMUM_EXPERIENCE:
        return _evaluate_minimum_experience(rule, candidate_skills)
    if rule.rule_type == HardConstraintRule.RuleType.LOCATION:
        return _evaluate_location(rule, candidate, candidate_profile)
    return _evaluate_profile_fact(rule=rule, profile=candidate_profile)


def _aggregate_outcome(rule_results: tuple[RuleEvaluation, ...]) -> str:
    if any(result.outcome == RuleOutcome.FAILED for result in rule_results):
        return FilterOutcome.FAILED
    if any(result.outcome == RuleOutcome.UNKNOWN for result in rule_results):
        return FilterOutcome.REVIEW
    return FilterOutcome.PASSED


def _evaluate_candidate(
    *,
    candidate: Candidate,
    rules: tuple[HardConstraintRule, ...],
) -> CandidateFilterResult:
    skills = {record.skill_id: record for record in candidate.skill_records.all()}
    profile = next(
        (
            item
            for item in candidate.profile_versions.all()
            if item.status == CandidateProfile.Status.CONFIRMED
        ),
        None,
    )
    results = tuple(
        evaluate_rule(
            rule=rule,
            candidate=candidate,
            candidate_skills=skills,
            candidate_profile=profile,
        )
        for rule in rules
    )
    return CandidateFilterResult(
        candidate=candidate,
        outcome=_aggregate_outcome(results),
        rule_results=results,
    )


def evaluate_candidate_constraints(
    *,
    requirements: VacancyRequirements,
    candidate: Candidate,
    user: User,
) -> CandidateFilterResult:
    """Evaluate one candidate without inferring unrecorded facts."""
    require_organization_object_access(user, requirements)
    require_organization_object_access(user, candidate)
    requirements = VacancyRequirements.objects.select_related("vacancy").get(
        pk=requirements.pk
    )
    candidate = Candidate.objects.prefetch_related(
        "skill_records__skill",
        "profile_versions",
    ).get(pk=candidate.pk)
    if requirements.status != VacancyRequirements.Status.CONFIRMED:
        raise ValidationError("Only confirmed requirements can be evaluated.")
    if requirements.vacancy.deleted_at is not None:
        raise ValidationError("Deleted vacancies cannot be evaluated.")
    if requirements.vacancy.organization_id != candidate.organization_id:
        raise ValidationError(
            "Candidate and requirements must belong to one organization."
        )
    if candidate.status != Candidate.Status.ACTIVE:
        raise ValidationError("Only active candidates can be evaluated.")

    rules = tuple(
        requirements.hard_constraint_rules.select_related("skill").order_by(
            "position", "id"
        )
    )
    return _evaluate_candidate(candidate=candidate, rules=rules)


def filter_candidates(
    *,
    requirements: VacancyRequirements,
    user: User,
) -> CandidateFilterReport:
    """Evaluate all active candidates in the authorized organization."""
    require_organization_object_access(user, requirements)
    requirements = VacancyRequirements.objects.select_related("vacancy").get(
        pk=requirements.pk
    )
    if requirements.status != VacancyRequirements.Status.CONFIRMED:
        raise ValidationError("Only confirmed requirements can be evaluated.")
    if requirements.vacancy.deleted_at is not None:
        raise ValidationError("Deleted vacancies cannot be evaluated.")

    candidates = (
        Candidate.objects.for_organization(requirements.organization)
        .filter(status=Candidate.Status.ACTIVE)
        .prefetch_related("skill_records__skill", "profile_versions")
        .order_by("full_name", "id")
    )
    rules = tuple(
        requirements.hard_constraint_rules.select_related("skill").order_by(
            "position", "id"
        )
    )
    results = tuple(
        _evaluate_candidate(candidate=candidate, rules=rules)
        for candidate in candidates
    )
    return CandidateFilterReport(requirements=requirements, results=results)
