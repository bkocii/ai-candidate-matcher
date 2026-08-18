from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError

from accounts.models import User
from candidates.models import Candidate, CandidateProfile
from evaluation.dataset import EvaluationDataset, canonical_dataset_json
from matching.models import MatchAssessment, MatchRun, ShortlistEntry
from matching.staleness import assess_match_run_staleness
from organizations.models import Organization
from organizations.permissions import require_organization_access
from vacancies.models import Vacancy

MEASUREMENT_CUTOFF = 5
RELEVANT_GRADE_THRESHOLD = 2
_METRIC_QUANTUM = Decimal("0.0001")


class EvaluationMeasurementError(ValidationError):
    """The installed workspace cannot produce a trustworthy quality report."""


@dataclass(frozen=True)
class RankingMetrics:
    ndcg_at_k: Decimal
    precision_at_k: Decimal
    expected_top_overlap_at_k: Decimal


@dataclass(frozen=True)
class RankingMeasurement:
    status: str
    ranked_count: int
    expected_count: int
    metrics: RankingMetrics | None


@dataclass(frozen=True)
class VacancyQualityMeasurement:
    vacancy_code: str
    deterministic: RankingMeasurement
    ai_assisted: RankingMeasurement


@dataclass(frozen=True)
class EvaluationQualityReport:
    dataset_id: str
    dataset_sha256: str
    organization_slug: str
    cutoff: int
    vacancies: tuple[VacancyQualityMeasurement, ...]
    deterministic_macro: RankingMetrics
    ai_assisted_macro: RankingMetrics | None
    ai_assessed_count: int
    ai_expected_count: int

    @property
    def ai_assisted_complete(self) -> bool:
        return self.ai_assessed_count == self.ai_expected_count


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_METRIC_QUANTUM, rounding=ROUND_HALF_UP)


def _ranking_metrics(
    *,
    ranked_codes: list[str],
    relevance_judgments: dict[str, int],
    expected_top_codes: list[str],
    cutoff: int,
) -> RankingMetrics:
    top_codes = ranked_codes[:cutoff]
    if len(top_codes) != cutoff:
        raise EvaluationMeasurementError(
            f"A measured ranking must contain at least {cutoff} candidates."
        )
    if any(code not in relevance_judgments for code in top_codes):
        raise EvaluationMeasurementError(
            "A measured ranking contains a candidate outside the dataset."
        )

    def discounted_gain(grades: list[int]) -> float:
        return sum(
            ((2**grade) - 1) / math.log2(position + 2)
            for position, grade in enumerate(grades)
        )

    actual_grades = [relevance_judgments[code] for code in top_codes]
    ideal_grades = sorted(relevance_judgments.values(), reverse=True)[:cutoff]
    ideal_gain = discounted_gain(ideal_grades)
    ndcg = discounted_gain(actual_grades) / ideal_gain if ideal_gain else 0.0
    relevant_count = sum(grade >= RELEVANT_GRADE_THRESHOLD for grade in actual_grades)
    overlap_count = len(set(top_codes) & set(expected_top_codes[:cutoff]))
    return RankingMetrics(
        ndcg_at_k=_quantize(Decimal(str(ndcg))),
        precision_at_k=_quantize(Decimal(relevant_count) / Decimal(cutoff)),
        expected_top_overlap_at_k=_quantize(Decimal(overlap_count) / Decimal(cutoff)),
    )


def _macro_average(metrics: list[RankingMetrics]) -> RankingMetrics:
    if not metrics:
        raise EvaluationMeasurementError("No ranking metrics were available.")
    count = Decimal(len(metrics))
    return RankingMetrics(
        ndcg_at_k=_quantize(sum(item.ndcg_at_k for item in metrics) / count),
        precision_at_k=_quantize(sum(item.precision_at_k for item in metrics) / count),
        expected_top_overlap_at_k=_quantize(
            sum(item.expected_top_overlap_at_k for item in metrics) / count
        ),
    )


def _candidate_map(
    *, organization: Organization, dataset: EvaluationDataset
) -> dict[int, str]:
    candidates = list(
        Candidate.objects.for_organization(organization)
        .filter(status=Candidate.Status.ACTIVE)
        .prefetch_related("sources", "profile_versions")
        .order_by("id")
    )
    if len(candidates) != len(dataset.candidates):
        raise EvaluationMeasurementError(
            "The evaluation candidate pool differs from the packaged dataset."
        )

    candidate_by_reference: dict[str, Candidate] = {}
    for candidate in candidates:
        for source in candidate.sources.all():
            if source.source_reference.startswith("EVAL-001-"):
                if source.source_reference in candidate_by_reference:
                    raise EvaluationMeasurementError(
                        "An evaluation candidate reference is not unique."
                    )
                candidate_by_reference[source.source_reference] = candidate

    candidate_codes_by_id: dict[int, str] = {}
    for spec in dataset.candidates:
        reference = f"EVAL-001-{spec.code}"
        candidate = candidate_by_reference.get(reference)
        if candidate is None:
            raise EvaluationMeasurementError(
                "The evaluation candidate references are incomplete."
            )
        candidate_codes_by_id[candidate.pk] = spec.code

    if len(candidate_codes_by_id) != len(candidates):
        raise EvaluationMeasurementError(
            "The evaluation candidate references do not match the active pool."
        )
    return candidate_codes_by_id


def _vacancy_map(
    *, organization: Organization, dataset: EvaluationDataset
) -> dict[str, Vacancy]:
    vacancies = list(
        Vacancy.objects.for_organization(organization)
        .active()
        .prefetch_related("requirement_versions")
    )
    if len(vacancies) != len(dataset.vacancies):
        raise EvaluationMeasurementError(
            "The evaluation vacancy set differs from the packaged dataset."
        )
    by_title: dict[str, list[Vacancy]] = {}
    for vacancy in vacancies:
        by_title.setdefault(vacancy.title, []).append(vacancy)
    if any(len(items) != 1 for items in by_title.values()):
        raise EvaluationMeasurementError("Evaluation vacancy titles must be unique.")
    try:
        return {spec.code: by_title[spec.title][0] for spec in dataset.vacancies}
    except (KeyError, IndexError) as error:
        raise EvaluationMeasurementError(
            "The evaluation vacancy titles are incomplete."
        ) from error


def _current_profile_ids(entries: list[ShortlistEntry]) -> dict[int, int]:
    candidate_ids = {entry.candidate_id for entry in entries}
    profiles = CandidateProfile.objects.filter(
        candidate_id__in=candidate_ids,
        status=CandidateProfile.Status.CONFIRMED,
    ).order_by("candidate_id", "-version", "-created_at", "-id")
    result: dict[int, int] = {}
    for profile in profiles:
        result.setdefault(profile.candidate_id, profile.pk)
    return result


def _latest_assessments(entries: list[ShortlistEntry]) -> dict[int, MatchAssessment]:
    entry_ids = [entry.pk for entry in entries]
    assessments = MatchAssessment.objects.filter(
        shortlist_entry_id__in=entry_ids
    ).order_by("shortlist_entry_id", "-version", "-created_at", "-id")
    result: dict[int, MatchAssessment] = {}
    for assessment in assessments:
        result.setdefault(assessment.shortlist_entry_id, assessment)
    return result


def _measure_vacancy(
    *,
    vacancy_code: str,
    vacancy: Vacancy,
    relevance_judgments: dict[str, int],
    expected_top_codes: list[str],
    candidate_codes_by_id: dict[int, str],
    user: User,
    cutoff: int,
) -> VacancyQualityMeasurement:
    requirements = vacancy.current_requirements
    if requirements is None:
        raise EvaluationMeasurementError(
            f"{vacancy_code} has no current confirmed requirements."
        )
    run = (
        MatchRun.objects.for_organization(vacancy.organization)
        .filter(requirements=requirements)
        .order_by("-created_at", "-id")
        .first()
    )
    if run is None:
        raise EvaluationMeasurementError(
            f"{vacancy_code} has no current deterministic shortlist."
        )
    if assess_match_run_staleness(run=run, user=user).is_stale:
        raise EvaluationMeasurementError(
            f"{vacancy_code} has a stale deterministic shortlist."
        )

    entries = list(run.entries.select_related("candidate").order_by("rank", "id"))
    if len(entries) != len(candidate_codes_by_id):
        raise EvaluationMeasurementError(
            f"{vacancy_code} does not rank the complete evaluation candidate pool."
        )
    try:
        deterministic_codes = [
            candidate_codes_by_id[entry.candidate_id] for entry in entries
        ]
    except KeyError as error:
        raise EvaluationMeasurementError(
            f"{vacancy_code} ranks a candidate outside the evaluation dataset."
        ) from error

    deterministic_metrics = _ranking_metrics(
        ranked_codes=deterministic_codes,
        relevance_judgments=relevance_judgments,
        expected_top_codes=expected_top_codes,
        cutoff=cutoff,
    )
    deterministic = RankingMeasurement(
        status="complete",
        ranked_count=len(entries),
        expected_count=len(entries),
        metrics=deterministic_metrics,
    )

    current_profile_ids = _current_profile_ids(entries)
    latest_assessments = _latest_assessments(entries)
    current_assessments: list[tuple[ShortlistEntry, MatchAssessment]] = []
    for entry in entries:
        assessment = latest_assessments.get(entry.pk)
        if (
            assessment is not None
            and assessment.requirements_id == run.requirements_id
            and assessment.candidate_profile_id
            == current_profile_ids.get(entry.candidate_id)
        ):
            current_assessments.append((entry, assessment))

    if len(current_assessments) != len(entries):
        ai_assisted = RankingMeasurement(
            status="unavailable",
            ranked_count=len(current_assessments),
            expected_count=len(entries),
            metrics=None,
        )
    else:
        current_assessments.sort(
            key=lambda item: (-item[1].score, item[0].rank, item[0].pk)
        )
        ai_codes = [
            candidate_codes_by_id[entry.candidate_id]
            for entry, _assessment in current_assessments
        ]
        ai_assisted = RankingMeasurement(
            status="complete",
            ranked_count=len(current_assessments),
            expected_count=len(entries),
            metrics=_ranking_metrics(
                ranked_codes=ai_codes,
                relevance_judgments=relevance_judgments,
                expected_top_codes=expected_top_codes,
                cutoff=cutoff,
            ),
        )

    return VacancyQualityMeasurement(
        vacancy_code=vacancy_code,
        deterministic=deterministic,
        ai_assisted=ai_assisted,
    )


def measure_evaluation_quality(
    *,
    dataset: EvaluationDataset,
    organization: Organization,
    user: User,
    cutoff: int = MEASUREMENT_CUTOFF,
) -> EvaluationQualityReport:
    """Measure deterministic and current AI rankings without blending scores."""
    require_organization_access(user, organization)
    if cutoff != MEASUREMENT_CUTOFF:
        raise EvaluationMeasurementError(
            f"This frozen evaluation requires a cutoff of {MEASUREMENT_CUTOFF}."
        )
    if any(len(spec.expected_top) != cutoff for spec in dataset.vacancies):
        raise EvaluationMeasurementError(
            "Every evaluation vacancy must define the complete expected top set."
        )

    candidate_codes_by_id = _candidate_map(
        organization=organization,
        dataset=dataset,
    )
    vacancies = _vacancy_map(organization=organization, dataset=dataset)
    measurements = tuple(
        _measure_vacancy(
            vacancy_code=spec.code,
            vacancy=vacancies[spec.code],
            relevance_judgments=spec.relevance_judgments,
            expected_top_codes=[item.candidate_code for item in spec.expected_top],
            candidate_codes_by_id=candidate_codes_by_id,
            user=user,
            cutoff=cutoff,
        )
        for spec in dataset.vacancies
    )
    deterministic_macro = _macro_average(
        [item.deterministic.metrics for item in measurements]
    )
    ai_metrics = [
        item.ai_assisted.metrics
        for item in measurements
        if item.ai_assisted.metrics is not None
    ]
    ai_assessed_count = sum(item.ai_assisted.ranked_count for item in measurements)
    ai_expected_count = sum(item.ai_assisted.expected_count for item in measurements)
    ai_assisted_macro = (
        _macro_average(ai_metrics) if len(ai_metrics) == len(measurements) else None
    )
    dataset_sha256 = hashlib.sha256(
        canonical_dataset_json(dataset).encode("utf-8")
    ).hexdigest()
    return EvaluationQualityReport(
        dataset_id=dataset.dataset_id,
        dataset_sha256=dataset_sha256,
        organization_slug=organization.slug,
        cutoff=cutoff,
        vacancies=measurements,
        deterministic_macro=deterministic_macro,
        ai_assisted_macro=ai_assisted_macro,
        ai_assessed_count=ai_assessed_count,
        ai_expected_count=ai_expected_count,
    )
