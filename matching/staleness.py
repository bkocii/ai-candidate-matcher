import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from accounts.models import User
from candidates.models import Candidate, CandidateProfile
from matching.models import MatchRun
from matching.scoring_policy import ALGORITHM_VERSION
from organizations.permissions import require_organization_object_access
from vacancies.models import VacancyRequirements

INPUT_SNAPSHOT_VERSION = "deterministic_match_inputs.v1"


def _decimal_value(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _signature(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def requirements_input_signature(requirements: VacancyRequirements) -> str:
    """Fingerprint every confirmed vacancy input used by deterministic matching."""
    skills = [
        {
            "id": record.pk,
            "skill_id": record.skill_id,
            "importance": record.importance,
            "source_label": record.source_label,
            "position": record.position,
        }
        for record in requirements.skill_records.all()
    ]
    rules = [
        {
            "id": rule.pk,
            "rule_type": rule.rule_type,
            "operator": rule.operator,
            "source_text": rule.source_text,
            "skill_id": rule.skill_id,
            "expected_value": rule.expected_value,
            "normalized_expected_value": rule.normalized_expected_value,
            "numeric_value": _decimal_value(rule.numeric_value),
            "unknown_outcome": rule.unknown_outcome,
            "position": rule.position,
        }
        for rule in requirements.hard_constraint_rules.all()
    ]
    return _signature(
        {
            "requirements_id": requirements.pk,
            "version": requirements.version,
            "schema_version": requirements.schema_version,
            "skills": skills,
            "rules": rules,
        }
    )


def candidate_input_signature(candidates: Iterable[Candidate]) -> str:
    """Fingerprint active candidate facts used by filtering, scoring, or evidence."""
    payload = []
    for candidate in sorted(candidates, key=lambda item: item.pk):
        profile = next(
            (
                item
                for item in candidate.profile_versions.all()
                if item.status == CandidateProfile.Status.CONFIRMED
            ),
            None,
        )
        skills = [
            {
                "id": record.pk,
                "skill_id": record.skill_id,
                "source_label": record.source_label,
                "evidence": record.evidence,
                "years_experience": _decimal_value(record.years_experience),
                "source_document_id": record.source_document_id,
                "source_profile_id": record.source_profile_id,
            }
            for record in sorted(
                candidate.skill_records.all(),
                key=lambda item: (item.skill_id, item.pk),
            )
        ]
        payload.append(
            {
                "candidate_id": candidate.pk,
                "location": candidate.location,
                "skills": skills,
                "confirmed_profile": (
                    {
                        "id": profile.pk,
                        "version": profile.version,
                        "source_document_id": profile.source_document_id,
                        "source_document_sha256": profile.source_document_sha256,
                        "location": profile.location,
                        "work_mode_preference": profile.work_mode_preference,
                        "languages": profile.languages,
                        "education": profile.education,
                        "certifications": profile.certifications,
                        "employment_type_preferences": (
                            profile.employment_type_preferences
                        ),
                        "fact_evidence": profile.fact_evidence,
                    }
                    if profile is not None
                    else None
                ),
            }
        )
    return _signature(payload)


def _current_requirements(requirements_id: int) -> VacancyRequirements:
    return (
        VacancyRequirements.objects.select_related("vacancy")
        .prefetch_related("skill_records", "hard_constraint_rules")
        .get(pk=requirements_id)
    )


def _current_candidates(run: MatchRun):
    return (
        Candidate.objects.for_organization(run.organization)
        .filter(status=Candidate.Status.ACTIVE)
        .prefetch_related("skill_records", "profile_versions")
        .order_by("id")
    )


@dataclass(frozen=True)
class MatchRunStaleness:
    is_stale: bool
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]


def assess_match_run_staleness(*, run: MatchRun, user: User) -> MatchRunStaleness:
    """Compare an immutable result snapshot with current authorized matching inputs."""
    require_organization_object_access(user, run)
    run = MatchRun.objects.select_related("requirements__vacancy").get(pk=run.pk)
    reason_pairs: list[tuple[str, str]] = []

    if run.algorithm_version != ALGORITHM_VERSION:
        reason_pairs.append(
            (
                "scoring_algorithm_changed",
                "The deterministic scoring method changed after this run was "
                "generated.",
            )
        )

    if (
        run.input_snapshot_version != INPUT_SNAPSHOT_VERSION
        or not run.requirements_input_signature
        or not run.candidate_input_signature
    ):
        reason_pairs.append(
            (
                "input_snapshot_unavailable",
                "This run predates reliable input tracking and must be regenerated.",
            )
        )
    else:
        requirements = _current_requirements(run.requirements_id)
        current_requirements = requirements.vacancy.current_requirements
        if (
            current_requirements is None
            or current_requirements.pk != requirements.pk
            or requirements_input_signature(requirements)
            != run.requirements_input_signature
        ):
            reason_pairs.append(
                (
                    "vacancy_requirements_changed",
                    "The vacancy's confirmed matching requirements changed.",
                )
            )

        current_candidate_signature = candidate_input_signature(
            _current_candidates(run)
        )
        if current_candidate_signature != run.candidate_input_signature:
            reason_pairs.append(
                (
                    "candidate_inputs_changed",
                    "The active candidate pool or candidate matching evidence changed.",
                )
            )

    if run.vacancy.deleted_at is not None:
        reason_pairs.append(
            (
                "vacancy_deleted",
                "The vacancy was deleted from the recruiter workspace.",
            )
        )

    return MatchRunStaleness(
        is_stale=bool(reason_pairs),
        reason_codes=tuple(code for code, _ in reason_pairs),
        reasons=tuple(message for _, message in reason_pairs),
    )
