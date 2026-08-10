from decimal import Decimal
from importlib import import_module

import pytest
from django.apps import apps
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from accounts.models import OrganizationMembership, User
from candidates.models import Candidate, CandidateDocument
from candidates.services import delete_candidate
from matching.models import (
    CandidateSkill,
    HardConstraintRule,
    RequirementSkill,
    Skill,
    normalize_taxonomy_value,
)
from matching.services import (
    assign_candidate_skill,
    create_hard_constraint_rule,
    get_or_create_skill,
    sync_requirement_skills,
)
from organizations.models import Organization
from vacancies.models import Vacancy, VacancyRequirements
from vacancies.services import (
    confirm_requirements_draft,
    create_next_requirements_draft,
)

pytestmark = pytest.mark.django_db


def make_workspace(*, username: str = "recruiter") -> tuple[User, Organization]:
    user = User.objects.create_user(username=username)
    organization = Organization.objects.create(
        name=f"{username.title()} Organization",
        slug=f"{username}-organization",
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )
    return user, organization


def make_requirements(
    organization: Organization,
    *,
    user: User | None = None,
) -> VacancyRequirements:
    vacancy = Vacancy.objects.create(
        organization=organization,
        title="Backend Engineer",
        description="Python and Django are required.",
        created_by=user,
    )
    return VacancyRequirements.objects.create(
        vacancy=vacancy,
        version=1,
        source_description=vacancy.description,
        must_have_skills=["Python", " Django  "],
        nice_to_have_skills=["PostgreSQL"],
        created_by=user,
    )


def test_skill_normalization_is_conservative() -> None:
    assert normalize_taxonomy_value("  PYTHON\tDevelopment ") == "python development"
    assert normalize_taxonomy_value("Ｐｙｔｈｏｎ") == "python"
    assert normalize_taxonomy_value("C") != normalize_taxonomy_value("C++")
    assert normalize_taxonomy_value("C#") != normalize_taxonomy_value("C++")

    with pytest.raises(ValidationError, match="non-blank"):
        normalize_taxonomy_value("  \n ")


def test_skill_identity_is_unique_only_inside_one_organization() -> None:
    user, first = make_workspace(username="first")
    second_user, second = make_workspace(username="second")
    first_skill = get_or_create_skill(
        organization=first,
        user=user,
        label=" Python ",
    )
    same_skill = get_or_create_skill(
        organization=first,
        user=user,
        label="PYTHON",
    )
    other_skill = get_or_create_skill(
        organization=second,
        user=second_user,
        label="python",
    )

    assert first_skill == same_skill
    assert first_skill.name == "Python"
    assert first_skill.normalized_name == "python"
    assert other_skill.pk != first_skill.pk


def test_skill_service_repeats_organization_permission_check() -> None:
    owner, organization = make_workspace(username="owner")
    outsider = User.objects.create_user(username="outsider")

    with pytest.raises(PermissionDenied):
        get_or_create_skill(
            organization=organization,
            user=outsider,
            label="Python",
        )

    assert owner.is_active is True
    assert not Skill.objects.exists()


def test_requirement_skill_sync_preserves_importance_order_and_source_wording() -> None:
    user, organization = make_workspace()
    requirements = make_requirements(organization, user=user)

    records = sync_requirement_skills(requirements=requirements, user=user)

    assert [
        (record.source_label, record.importance, record.position) for record in records
    ] == [
        ("Python", RequirementSkill.Importance.MUST_HAVE, 1),
        ("Django", RequirementSkill.Importance.MUST_HAVE, 2),
        ("PostgreSQL", RequirementSkill.Importance.NICE_TO_HAVE, 1),
    ]
    assert list(
        requirements.skill_records.values_list("skill__normalized_name", flat=True)
    ) == ["python", "django", "postgresql"]


def test_must_have_wins_when_the_same_normalized_skill_is_in_both_lists() -> None:
    user, organization = make_workspace()
    requirements = make_requirements(organization, user=user)
    requirements.must_have_skills = ["Python"]
    requirements.nice_to_have_skills = [" python ", "Django"]
    requirements.save()

    records = sync_requirement_skills(requirements=requirements, user=user)

    assert [
        (record.skill.normalized_name, record.importance) for record in records
    ] == [
        ("python", RequirementSkill.Importance.MUST_HAVE),
        ("django", RequirementSkill.Importance.NICE_TO_HAVE),
    ]


def test_confirming_requirements_materializes_normalized_skills() -> None:
    user, organization = make_workspace()
    requirements = make_requirements(organization, user=user)

    confirm_requirements_draft(requirements=requirements, user=user)
    requirements.refresh_from_db()

    assert requirements.status == VacancyRequirements.Status.CONFIRMED
    assert requirements.skill_records.count() == 3


def test_initial_matching_migration_backfills_existing_requirement_skills() -> None:
    user, organization = make_workspace()
    requirements = make_requirements(organization, user=user)
    migration = import_module("matching.migrations.0001_initial")

    migration.backfill_requirement_skills(apps, None)

    assert list(
        requirements.skill_records.values_list(
            "source_label",
            "importance",
            "position",
        )
    ) == [
        ("Python", RequirementSkill.Importance.MUST_HAVE, 1),
        ("Django", RequirementSkill.Importance.MUST_HAVE, 2),
        ("PostgreSQL", RequirementSkill.Importance.NICE_TO_HAVE, 1),
    ]


def test_confirmed_requirement_skill_links_are_immutable() -> None:
    user, organization = make_workspace()
    requirements = make_requirements(organization, user=user)
    sync_requirement_skills(requirements=requirements, user=user)
    record = requirements.skill_records.get(source_label="Python")
    confirm_requirements_draft(requirements=requirements, user=user)

    record.source_label = "Changed"
    with pytest.raises(ValidationError, match="immutable"):
        record.save()
    with pytest.raises(ValidationError, match="immutable"):
        record.delete()


def test_candidate_skill_keeps_evidence_and_optional_document() -> None:
    user, organization = make_workspace()
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Synthetic Candidate",
    )
    document = CandidateDocument.objects.create(
        candidate=candidate,
        original_filename="synthetic.pdf",
        file="candidate_documents/synthetic.pdf",
    )

    record, created = assign_candidate_skill(
        candidate=candidate,
        user=user,
        label=" Python ",
        evidence="Built Django APIs in a synthetic project.",
        years_experience=Decimal("3.5"),
        source_document=document,
    )

    assert created is True
    assert record.skill.normalized_name == "python"
    assert record.source_label == "Python"
    assert record.evidence == "Built Django APIs in a synthetic project."
    assert record.years_experience == Decimal("3.5")
    assert record.source_document == document


def test_candidate_skill_rejects_cross_organization_skill_and_document() -> None:
    user, organization = make_workspace(username="owner")
    other_user, other = make_workspace(username="other")
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Visible Candidate",
    )
    other_candidate = Candidate.objects.create(
        organization=other,
        full_name="Other Candidate",
    )
    other_skill = get_or_create_skill(
        organization=other,
        user=other_user,
        label="Python",
    )
    other_document = CandidateDocument.objects.create(
        candidate=other_candidate,
        original_filename="other.pdf",
        file="candidate_documents/other.pdf",
    )

    with pytest.raises(ValidationError, match="candidate organization"):
        CandidateSkill.objects.create(
            candidate=candidate,
            skill=other_skill,
            source_label="Python",
        )

    own_skill = get_or_create_skill(
        organization=organization,
        user=user,
        label="Python",
    )
    with pytest.raises(ValidationError, match="belong to this candidate"):
        CandidateSkill.objects.create(
            candidate=candidate,
            skill=own_skill,
            source_label="Python",
            source_document=other_document,
        )


def test_candidate_skill_service_rejects_unauthorized_and_deleted_candidates() -> None:
    owner, organization = make_workspace(username="owner")
    outsider = User.objects.create_user(username="outsider")
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Candidate",
    )

    with pytest.raises(PermissionDenied):
        assign_candidate_skill(candidate=candidate, user=outsider, label="Python")

    candidate.status = Candidate.Status.DELETED
    candidate.deleted_at = candidate.created_at
    candidate.save()
    with pytest.raises(ValidationError, match="Deleted candidates"):
        assign_candidate_skill(candidate=candidate, user=owner, label="Python")


def test_candidate_deletion_removes_derived_skill_evidence() -> None:
    user, organization = make_workspace()
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Candidate",
    )
    assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="Python",
        evidence="Private CV evidence",
    )

    delete_candidate(candidate=candidate, user=user)

    assert not CandidateSkill.objects.filter(candidate=candidate).exists()


@pytest.mark.parametrize(
    ("rule_type", "expected_value"),
    [
        (HardConstraintRule.RuleType.LOCATION, "Prishtina"),
        (HardConstraintRule.RuleType.WORK_MODE, "remote"),
        (HardConstraintRule.RuleType.LANGUAGE, "English B2"),
        (HardConstraintRule.RuleType.EDUCATION, "Computer science degree"),
        (HardConstraintRule.RuleType.CERTIFICATION, "AWS Developer"),
        (HardConstraintRule.RuleType.EMPLOYMENT_TYPE, "full_time"),
    ],
)
def test_text_hard_constraint_rules_have_explicit_equality_semantics(
    rule_type: str,
    expected_value: str,
) -> None:
    user, organization = make_workspace()
    requirements = make_requirements(organization, user=user)

    rule = create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=rule_type,
        source_text=f"Explicit requirement: {expected_value}",
        expected_value=expected_value,
        position=1,
    )

    assert rule.operator == HardConstraintRule.Operator.EQUALS
    assert rule.normalized_expected_value == expected_value.casefold()
    assert rule.unknown_outcome == HardConstraintRule.UnknownOutcome.KEEP_FOR_REVIEW


def test_required_skill_rule_uses_the_organization_skill_identity() -> None:
    user, organization = make_workspace()
    requirements = make_requirements(organization, user=user)
    sync_requirement_skills(requirements=requirements, user=user)

    rule = create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=HardConstraintRule.RuleType.REQUIRED_SKILL,
        source_text="Python is mandatory.",
        skill_label="PYTHON",
        position=1,
    )

    assert rule.operator == HardConstraintRule.Operator.HAS_SKILL
    assert rule.skill == requirements.skill_records.get(source_label="Python").skill
    assert rule.expected_value == ""
    assert rule.numeric_value is None


def test_required_skill_rule_must_reference_a_must_have_skill() -> None:
    user, organization = make_workspace()
    requirements = make_requirements(organization, user=user)
    sync_requirement_skills(requirements=requirements, user=user)

    with pytest.raises(ValidationError, match="must-have skill"):
        create_hard_constraint_rule(
            requirements=requirements,
            user=user,
            rule_type=HardConstraintRule.RuleType.REQUIRED_SKILL,
            source_text="Redis is mandatory.",
            skill_label="Redis",
            position=1,
        )


def test_minimum_experience_rule_uses_a_nonnegative_numeric_threshold() -> None:
    user, organization = make_workspace()
    requirements = make_requirements(organization, user=user)

    rule = create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=HardConstraintRule.RuleType.MINIMUM_EXPERIENCE,
        source_text="At least three years of relevant experience.",
        numeric_value=Decimal("3.0"),
        position=1,
    )

    assert rule.operator == HardConstraintRule.Operator.AT_LEAST
    assert rule.numeric_value == Decimal("3.0")
    assert rule.skill is None


def test_rule_payload_validation_rejects_implicit_or_mismatched_meaning() -> None:
    user, organization = make_workspace()
    requirements = make_requirements(organization, user=user)

    with pytest.raises(ValidationError, match="number"):
        create_hard_constraint_rule(
            requirements=requirements,
            user=user,
            rule_type=HardConstraintRule.RuleType.MINIMUM_EXPERIENCE,
            source_text="Experience required.",
            position=1,
        )

    with pytest.raises(ValidationError, match="work-mode"):
        create_hard_constraint_rule(
            requirements=requirements,
            user=user,
            rule_type=HardConstraintRule.RuleType.WORK_MODE,
            source_text="Flexible arrangement.",
            expected_value="sometimes from home",
            position=1,
        )

    assert "age" not in HardConstraintRule.RuleType.values
    assert "gender" not in HardConstraintRule.RuleType.values
    assert "ethnicity" not in HardConstraintRule.RuleType.values


def test_database_prevents_unknown_facts_from_becoming_automatic_failures() -> None:
    user, organization = make_workspace()
    requirements = make_requirements(organization, user=user)
    rule = create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=HardConstraintRule.RuleType.LOCATION,
        source_text="Must be in Prishtina.",
        expected_value="Prishtina",
        position=1,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        HardConstraintRule.objects.filter(pk=rule.pk).update(unknown_outcome="fail")


def test_confirmed_hard_constraint_rules_are_immutable() -> None:
    user, organization = make_workspace()
    requirements = make_requirements(organization, user=user)
    rule = create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=HardConstraintRule.RuleType.LOCATION,
        source_text="Must be in Prishtina.",
        expected_value="Prishtina",
        position=1,
    )
    confirm_requirements_draft(requirements=requirements, user=user)

    rule.source_text = "Changed after confirmation"
    with pytest.raises(ValidationError, match="immutable"):
        rule.save()
    with pytest.raises(ValidationError, match="immutable"):
        rule.delete()
    with pytest.raises(ValidationError, match="immutable"):
        create_hard_constraint_rule(
            requirements=requirements,
            user=user,
            rule_type=HardConstraintRule.RuleType.LOCATION,
            source_text="Another rule",
            expected_value="Prishtina",
            position=2,
        )
    with pytest.raises(ValidationError, match="immutable"):
        HardConstraintRule.objects.filter(pk=rule.pk).update(source_text="Bulk change")
    with pytest.raises(ValidationError, match="immutable"):
        HardConstraintRule.objects.filter(pk=rule.pk).delete()


def test_new_requirements_version_copies_skills_and_typed_rules() -> None:
    user, organization = make_workspace()
    requirements = make_requirements(organization, user=user)
    sync_requirement_skills(requirements=requirements, user=user)
    create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=HardConstraintRule.RuleType.REQUIRED_SKILL,
        source_text="Python is mandatory.",
        skill_label="Python",
        position=1,
    )
    confirm_requirements_draft(requirements=requirements, user=user)

    draft, created = create_next_requirements_draft(
        vacancy=requirements.vacancy,
        user=user,
    )

    assert created is True
    assert draft.version == 2
    assert list(
        draft.skill_records.values_list("skill__normalized_name", flat=True)
    ) == ["python", "django", "postgresql"]
    copied_rule = draft.hard_constraint_rules.get()
    assert copied_rule.pk != requirements.hard_constraint_rules.get().pk
    assert copied_rule.skill == requirements.hard_constraint_rules.get().skill
    assert copied_rule.source_text == "Python is mandatory."


def test_matching_records_are_organization_scoped() -> None:
    user, organization = make_workspace(username="visible")
    other_user, other = make_workspace(username="hidden")
    visible_candidate = Candidate.objects.create(
        organization=organization,
        full_name="Visible Candidate",
    )
    hidden_candidate = Candidate.objects.create(
        organization=other,
        full_name="Hidden Candidate",
    )
    visible_skill, _ = assign_candidate_skill(
        candidate=visible_candidate,
        user=user,
        label="Python",
    )
    assign_candidate_skill(
        candidate=hidden_candidate,
        user=other_user,
        label="Python",
    )
    visible_requirements = make_requirements(organization, user=user)
    hidden_requirements = make_requirements(other, user=other_user)
    visible_requirement_skills = sync_requirement_skills(
        requirements=visible_requirements,
        user=user,
    )
    sync_requirement_skills(requirements=hidden_requirements, user=other_user)

    assert list(CandidateSkill.objects.visible_to(user)) == [visible_skill]
    assert list(CandidateSkill.objects.for_organization(organization)) == [
        visible_skill
    ]
    assert list(RequirementSkill.objects.visible_to(user)) == list(
        visible_requirement_skills
    )
    assert not CandidateSkill.objects.visible_to(AnonymousUser()).exists()
    assert not RequirementSkill.objects.visible_to(AnonymousUser()).exists()
