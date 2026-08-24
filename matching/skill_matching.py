from collections.abc import Iterable
from decimal import Decimal

from matching.models import CandidateSkill, RequirementSkill, normalize_taxonomy_value
from matching.skill_taxonomy import canonical_skill_key


def _candidate_skill_priority(
    record: CandidateSkill,
    *,
    canonical_key: str,
) -> tuple[int, int, Decimal, int, int]:
    """Prefer the most useful inspectable assertion for one canonical skill."""
    has_evidence = bool(record.evidence.strip())
    has_years = record.years_experience is not None
    years = record.years_experience or Decimal("0")
    exact_identity = normalize_taxonomy_value(record.skill.name) == canonical_key
    return (
        0 if has_evidence else 1,
        0 if has_years else 1,
        -years,
        0 if exact_identity else 1,
        record.pk or 0,
    )


def candidate_skills_by_canonical_key(
    records: Iterable[CandidateSkill],
) -> dict[str, CandidateSkill]:
    """Index saved assertions by safe canonical identity for runtime matching."""
    indexed: dict[str, CandidateSkill] = {}
    for record in records:
        key = canonical_skill_key(record.skill.name)
        existing = indexed.get(key)
        if existing is None or _candidate_skill_priority(
            record, canonical_key=key
        ) < _candidate_skill_priority(existing, canonical_key=key):
            indexed[key] = record
    return indexed


def unique_requirement_skills(
    records: Iterable[RequirementSkill],
) -> tuple[RequirementSkill, ...]:
    """Keep one weighted row per canonical requirement; must-have wins."""
    ordered = sorted(
        records,
        key=lambda record: (
            0 if record.importance == RequirementSkill.Importance.MUST_HAVE else 1,
            record.position,
            record.pk,
        ),
    )
    unique: list[RequirementSkill] = []
    seen: set[str] = set()
    for record in ordered:
        key = canonical_skill_key(record.skill.name)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return tuple(unique)
