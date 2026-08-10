from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import User
from candidates.models import Candidate, CandidateDocument
from matching.models import (
    CandidateSkill,
    HardConstraintRule,
    RequirementSkill,
    Skill,
    normalize_taxonomy_value,
)
from organizations.models import Organization
from organizations.permissions import (
    require_organization_access,
    require_organization_object_access,
)
from vacancies.models import VacancyRequirements


def _clean_display_value(value: str) -> str:
    return " ".join(value.split())


def get_or_create_skill(
    *,
    organization: Organization,
    user: User,
    label: str,
) -> Skill:
    """Resolve one skill inside the authorized organization's vocabulary."""
    require_organization_access(user, organization)
    normalized_name = normalize_taxonomy_value(label)
    skill = Skill.objects.filter(
        organization=organization,
        normalized_name=normalized_name,
    ).first()
    if skill:
        return skill
    return Skill.objects.create(
        organization=organization,
        name=_clean_display_value(label),
        created_by=user,
    )


@transaction.atomic
def assign_candidate_skill(
    *,
    candidate: Candidate,
    user: User,
    label: str,
    evidence: str = "",
    years_experience: Decimal | None = None,
    source_document: CandidateDocument | None = None,
) -> tuple[CandidateSkill, bool]:
    """Add an inspectable skill assertion without crossing tenant boundaries."""
    require_organization_object_access(user, candidate)
    if candidate.status == Candidate.Status.DELETED:
        raise ValidationError("Deleted candidates cannot receive skill records.")
    skill = get_or_create_skill(
        organization=candidate.organization,
        user=user,
        label=label,
    )
    record, created = CandidateSkill.objects.get_or_create(
        candidate=candidate,
        skill=skill,
        defaults={
            "source_label": _clean_display_value(label),
            "evidence": evidence.strip(),
            "years_experience": years_experience,
            "source_document": source_document,
            "created_by": user,
        },
    )
    return record, created


@transaction.atomic
def sync_requirement_skills(
    *,
    requirements: VacancyRequirements,
    user: User,
) -> tuple[RequirementSkill, ...]:
    """Replace draft skill links from the recruiter-visible list fields."""
    require_organization_object_access(user, requirements)
    requirements = VacancyRequirements.objects.select_for_update().get(
        pk=requirements.pk
    )
    if requirements.status != VacancyRequirements.Status.DRAFT:
        raise ValidationError(
            "Confirmed requirements skill links are immutable; create a new version."
        )

    requirements.skill_records.all().delete()
    created_records = []
    seen = set()
    groups = (
        (RequirementSkill.Importance.MUST_HAVE, requirements.must_have_skills),
        (RequirementSkill.Importance.NICE_TO_HAVE, requirements.nice_to_have_skills),
    )
    for importance, labels in groups:
        position = 0
        for label in labels:
            normalized_name = normalize_taxonomy_value(label)
            if normalized_name in seen:
                continue
            seen.add(normalized_name)
            position += 1
            skill = get_or_create_skill(
                organization=requirements.organization,
                user=user,
                label=label,
            )
            created_records.append(
                RequirementSkill.objects.create(
                    requirements=requirements,
                    skill=skill,
                    importance=importance,
                    source_label=_clean_display_value(label),
                    position=position,
                )
            )
    return tuple(created_records)


@transaction.atomic
def create_hard_constraint_rule(
    *,
    requirements: VacancyRequirements,
    user: User,
    rule_type: str,
    source_text: str,
    position: int,
    skill_label: str = "",
    expected_value: str = "",
    numeric_value: Decimal | None = None,
) -> HardConstraintRule:
    """Create one typed rule while its requirements version is still a draft."""
    require_organization_object_access(user, requirements)
    requirements = VacancyRequirements.objects.select_for_update().get(
        pk=requirements.pk
    )
    if requirements.status != VacancyRequirements.Status.DRAFT:
        raise ValidationError(
            "Confirmed hard-constraint rules are immutable; create a new version."
        )

    skill = None
    operator = HardConstraintRule.Operator.EQUALS
    if rule_type == HardConstraintRule.RuleType.REQUIRED_SKILL:
        if not skill_label.strip():
            raise ValidationError("Enter the required skill.")
        skill = get_or_create_skill(
            organization=requirements.organization,
            user=user,
            label=skill_label,
        )
        operator = HardConstraintRule.Operator.HAS_SKILL
    elif rule_type == HardConstraintRule.RuleType.MINIMUM_EXPERIENCE:
        operator = HardConstraintRule.Operator.AT_LEAST

    return HardConstraintRule.objects.create(
        requirements=requirements,
        rule_type=rule_type,
        operator=operator,
        source_text=source_text,
        skill=skill,
        expected_value=expected_value,
        numeric_value=numeric_value,
        position=position,
        created_by=user,
    )


@transaction.atomic
def copy_hard_constraint_rules(
    *,
    source: VacancyRequirements,
    target: VacancyRequirements,
    user: User,
) -> tuple[HardConstraintRule, ...]:
    """Copy typed rules into a new draft without mutating confirmed history."""
    require_organization_object_access(user, source)
    require_organization_object_access(user, target)
    if source.organization.pk != target.organization.pk:
        raise ValidationError("Requirement versions must belong to one organization.")
    if target.status != VacancyRequirements.Status.DRAFT:
        raise ValidationError("Hard-constraint rules can only be copied to a draft.")

    copies = []
    for rule in source.hard_constraint_rules.all():
        copies.append(
            HardConstraintRule.objects.create(
                requirements=target,
                rule_type=rule.rule_type,
                operator=rule.operator,
                source_text=rule.source_text,
                skill=rule.skill,
                expected_value=rule.expected_value,
                numeric_value=rule.numeric_value,
                unknown_outcome=rule.unknown_outcome,
                position=rule.position,
                created_by=user,
            )
        )
    return tuple(copies)
