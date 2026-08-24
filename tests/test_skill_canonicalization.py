from decimal import Decimal

import pytest
from django.utils import timezone

from accounts.models import OrganizationMembership, User
from candidates.models import Candidate
from matching.evaluation import (
    FilterOutcome,
    RuleOutcome,
    evaluate_candidate_constraints,
)
from matching.models import (
    CandidateSkill,
    HardConstraintRule,
    RequirementSkill,
    Skill,
)
from matching.scoring import generate_shortlist
from matching.scoring_policy import ALGORITHM_VERSION
from matching.services import assign_candidate_skill, sync_requirement_skills
from matching.skill_taxonomy import canonicalize_skill
from organizations.models import Organization
from vacancies.models import Vacancy, VacancyRequirements
from vacancies.services import confirm_requirements_draft

pytestmark = pytest.mark.django_db


def make_workspace() -> tuple[User, Organization]:
    user = User.objects.create_user(username="canonical-recruiter")
    organization = Organization.objects.create(
        name="Canonical Skill Test",
        slug="canonical-skill-test",
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )
    return user, organization


def make_requirements(
    *,
    organization: Organization,
    user: User,
    must_have: list[str],
) -> VacancyRequirements:
    vacancy = Vacancy.objects.create(
        organization=organization,
        title="Synthetic Backend Developer",
        description="Synthetic vacancy description.",
        created_by=user,
    )
    return VacancyRequirements.objects.create(
        vacancy=vacancy,
        version=1,
        source_description=vacancy.description,
        must_have_skills=must_have,
        created_by=user,
    )


@pytest.mark.parametrize(
    ("source_label", "expected_key", "expected_display"),
    [
        ("Python", "python", "Python"),
        (" PYTHON   DEVELOPMENT ", "python", "Python"),
        ("Python-development", "python", "Python"),
        ("Python developer", "python", "Python"),
        ("Django development", "django", "Django"),
        ("Java", "java", "Java"),
        ("JavaScript", "javascript", "JavaScript"),
    ],
)
def test_controlled_skill_canonicalization_is_explicit_and_conservative(
    source_label: str,
    expected_key: str,
    expected_display: str,
) -> None:
    canonical = canonicalize_skill(source_label)

    assert canonical.key == expected_key
    assert canonical.display_name == expected_display


def test_requirement_sync_preserves_source_wording_and_canonical_identity() -> None:
    user, organization = make_workspace()
    requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python development", "Django developer"],
    )
    requirements.nice_to_have_skills = ["Python"]
    requirements.save()

    records = sync_requirement_skills(requirements=requirements, user=user)

    assert [(record.source_label, record.skill.name) for record in records] == [
        ("Python development", "Python"),
        ("Django developer", "Django"),
    ]
    assert requirements.must_have_skills == [
        "Python development",
        "Django developer",
    ]


def test_new_candidate_and_requirement_aliases_share_one_skill_identity() -> None:
    user, organization = make_workspace()
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Synthetic Python Candidate",
    )
    candidate_skill, _ = assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="Python",
        evidence="Synthetic source explicitly states Python.",
    )
    requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python development"],
    )
    requirement_skill = sync_requirement_skills(
        requirements=requirements,
        user=user,
    )[0]

    assert candidate_skill.skill == requirement_skill.skill
    assert requirement_skill.skill.name == "Python"
    assert requirement_skill.source_label == "Python development"


def test_existing_saved_aliases_match_for_hard_filter_and_shortlist() -> None:
    user, organization = make_workspace()
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Synthetic Existing Python Candidate",
    )
    candidate_python = Skill.objects.create(
        organization=organization,
        name="Python",
        created_by=user,
    )
    CandidateSkill.objects.create(
        candidate=candidate,
        skill=candidate_python,
        source_label="Python",
        evidence="Synthetic CV states Python.",
        years_experience=Decimal("4.0"),
        created_by=user,
    )
    requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python development"],
    )
    legacy_requirement_skill = Skill.objects.create(
        organization=organization,
        name="Python development",
        created_by=user,
    )
    RequirementSkill.objects.create(
        requirements=requirements,
        skill=legacy_requirement_skill,
        importance=RequirementSkill.Importance.MUST_HAVE,
        source_label="Python development",
        position=1,
    )
    HardConstraintRule.objects.create(
        requirements=requirements,
        rule_type=HardConstraintRule.RuleType.REQUIRED_SKILL,
        operator=HardConstraintRule.Operator.HAS_SKILL,
        source_text="Professional Python development is required.",
        skill=legacy_requirement_skill,
        position=1,
        created_by=user,
    )
    VacancyRequirements.objects.filter(pk=requirements.pk).update(
        status=VacancyRequirements.Status.CONFIRMED,
        confirmed_by=user,
        confirmed_at=timezone.now(),
    )
    requirements.refresh_from_db()

    filter_result = evaluate_candidate_constraints(
        requirements=requirements,
        candidate=candidate,
        user=user,
    )
    run = generate_shortlist(requirements=requirements, user=user)
    entry = run.entries.get()

    assert filter_result.outcome == FilterOutcome.PASSED
    assert filter_result.rule_results[0].outcome == RuleOutcome.PASSED
    assert filter_result.rule_results[0].candidate_value == "Python"
    assert entry.score == Decimal("100.00")
    assert entry.matched_must_have == 1
    assert entry.score_breakdown[0]["skill_label"] == "Python development"
    assert entry.score_breakdown[0]["candidate_label"] == "Python"
    assert run.algorithm_version == ALGORITHM_VERSION
    assert ALGORITHM_VERSION == "deterministic_skill_relevance.v3"


def test_unsafe_near_match_remains_unknown_and_scores_zero() -> None:
    user, organization = make_workspace()
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Synthetic JavaScript Candidate",
    )
    assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="JavaScript",
        evidence="Synthetic CV states JavaScript.",
    )
    requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Java"],
    )
    sync_requirement_skills(requirements=requirements, user=user)
    rule_skill = requirements.skill_records.get().skill
    HardConstraintRule.objects.create(
        requirements=requirements,
        rule_type=HardConstraintRule.RuleType.REQUIRED_SKILL,
        operator=HardConstraintRule.Operator.HAS_SKILL,
        source_text="Java is required.",
        skill=rule_skill,
        position=1,
        created_by=user,
    )
    confirm_requirements_draft(requirements=requirements, user=user)

    filter_result = evaluate_candidate_constraints(
        requirements=requirements,
        candidate=candidate,
        user=user,
    )
    entry = generate_shortlist(requirements=requirements, user=user).entries.get()

    assert filter_result.outcome == FilterOutcome.REVIEW
    assert filter_result.rule_results[0].outcome == RuleOutcome.UNKNOWN
    assert entry.score == Decimal("0.00")
    assert entry.matched_must_have == 0
