from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from accounts.models import OrganizationMembership, User
from candidates.models import Candidate
from matching.evaluation import (
    FilterOutcome,
    RuleOutcome,
    evaluate_candidate_constraints,
    filter_candidates,
)
from matching.models import HardConstraintRule
from matching.services import (
    assign_candidate_skill,
    create_hard_constraint_rule,
    sync_requirement_skills,
)
from organizations.models import Organization
from vacancies.models import Vacancy, VacancyRequirements
from vacancies.services import confirm_requirements_draft

pytestmark = pytest.mark.django_db


def make_workspace(*, username: str = "recruiter") -> tuple[User, Organization]:
    user = User.objects.create_user(username=username, password="test-password")
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
    *,
    organization: Organization,
    user: User,
) -> tuple[Vacancy, VacancyRequirements]:
    vacancy = Vacancy.objects.create(
        organization=organization,
        title="Backend Engineer",
        description="Python role in Prishtina.",
        created_by=user,
    )
    requirements = VacancyRequirements.objects.create(
        vacancy=vacancy,
        version=1,
        source_description=vacancy.description,
        summary="Synthetic backend role",
        must_have_skills=["Python"],
        created_by=user,
    )
    sync_requirement_skills(requirements=requirements, user=user)
    return vacancy, requirements


def add_required_skill_rule(
    *,
    requirements: VacancyRequirements,
    user: User,
    position: int = 1,
) -> HardConstraintRule:
    return create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=HardConstraintRule.RuleType.REQUIRED_SKILL,
        source_text="Python is mandatory.",
        skill_label="Python",
        position=position,
    )


def add_location_rule(
    *,
    requirements: VacancyRequirements,
    user: User,
    position: int = 1,
) -> HardConstraintRule:
    return create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=HardConstraintRule.RuleType.LOCATION,
        source_text="Candidate must be based in Prishtina.",
        expected_value="Prishtina",
        position=position,
    )


def test_matching_skill_and_location_produce_inspectable_passes() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(organization=organization, user=user)
    add_required_skill_rule(requirements=requirements, user=user, position=1)
    add_location_rule(requirements=requirements, user=user, position=2)
    confirm_requirements_draft(requirements=requirements, user=user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Synthetic Match",
        location="  PRISHTINA ",
    )
    assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="python",
        evidence="Built a synthetic Django API.",
    )

    result = evaluate_candidate_constraints(
        requirements=requirements,
        candidate=candidate,
        user=user,
    )

    assert result.outcome == FilterOutcome.PASSED
    assert [rule.outcome for rule in result.rule_results] == [
        RuleOutcome.PASSED,
        RuleOutcome.PASSED,
    ]
    assert result.rule_results[0].expected_value == "Python"
    assert result.rule_results[0].source_text == "Python is mandatory."
    assert result.rule_results[0].evidence == "Built a synthetic Django API."
    assert result.rule_results[1].candidate_value == "PRISHTINA"


def test_missing_skill_is_unknown_and_kept_for_review() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(organization=organization, user=user)
    add_required_skill_rule(requirements=requirements, user=user)
    confirm_requirements_draft(requirements=requirements, user=user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Unknown Skill Candidate",
    )

    result = evaluate_candidate_constraints(
        requirements=requirements,
        candidate=candidate,
        user=user,
    )

    assert result.outcome == FilterOutcome.REVIEW
    assert result.is_eligible is True
    assert result.rule_results[0].outcome == RuleOutcome.UNKNOWN
    assert "Absence is not evidence" in result.rule_results[0].explanation


def test_known_location_mismatch_is_an_explicit_failure() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(organization=organization, user=user)
    add_location_rule(requirements=requirements, user=user)
    confirm_requirements_draft(requirements=requirements, user=user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Different Location",
        location="Peja",
    )

    result = evaluate_candidate_constraints(
        requirements=requirements,
        candidate=candidate,
        user=user,
    )

    assert result.outcome == FilterOutcome.FAILED
    assert result.is_eligible is False
    assert result.rule_results[0].outcome == RuleOutcome.FAILED
    assert result.rule_results[0].candidate_value == "Peja"


def test_missing_location_remains_unknown() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(organization=organization, user=user)
    add_location_rule(requirements=requirements, user=user)
    confirm_requirements_draft(requirements=requirements, user=user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="No Location",
    )

    result = evaluate_candidate_constraints(
        requirements=requirements,
        candidate=candidate,
        user=user,
    )

    assert result.outcome == FilterOutcome.REVIEW
    assert result.rule_results[0].outcome == RuleOutcome.UNKNOWN


@pytest.mark.parametrize(
    "years",
    [Decimal("5.0"), Decimal("8.5")],
)
def test_recorded_skill_years_can_prove_minimum_experience(
    years: Decimal,
) -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(organization=organization, user=user)
    create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=HardConstraintRule.RuleType.MINIMUM_EXPERIENCE,
        source_text="At least five years of experience.",
        numeric_value=Decimal("5.0"),
        position=1,
    )
    confirm_requirements_draft(requirements=requirements, user=user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Experienced Candidate",
    )
    assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="Python",
        years_experience=years,
        evidence="Synthetic employment history.",
    )

    result = evaluate_candidate_constraints(
        requirements=requirements,
        candidate=candidate,
        user=user,
    )

    assert result.outcome == FilterOutcome.PASSED
    assert result.rule_results[0].candidate_value == (
        f"{format(years.normalize(), 'f')} years with Python"
    )


def test_lower_partial_experience_is_unknown_not_failure() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(organization=organization, user=user)
    create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=HardConstraintRule.RuleType.MINIMUM_EXPERIENCE,
        source_text="At least five years of experience.",
        numeric_value=Decimal("5.0"),
        position=1,
    )
    confirm_requirements_draft(requirements=requirements, user=user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Partial Evidence",
    )
    assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="Python",
        years_experience=Decimal("3.0"),
    )

    result = evaluate_candidate_constraints(
        requirements=requirements,
        candidate=candidate,
        user=user,
    )

    assert result.outcome == FilterOutcome.REVIEW
    assert result.rule_results[0].outcome == RuleOutcome.UNKNOWN
    assert "cannot prove" in result.rule_results[0].explanation


@pytest.mark.parametrize(
    ("rule_type", "expected_value"),
    [
        (HardConstraintRule.RuleType.WORK_MODE, "remote"),
        (HardConstraintRule.RuleType.LANGUAGE, "English B2"),
        (HardConstraintRule.RuleType.EDUCATION, "Computer science degree"),
        (HardConstraintRule.RuleType.CERTIFICATION, "AWS Developer"),
        (HardConstraintRule.RuleType.EMPLOYMENT_TYPE, "full_time"),
    ],
)
def test_unavailable_candidate_profile_facts_remain_unknown(
    rule_type: str,
    expected_value: str,
) -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(organization=organization, user=user)
    create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=rule_type,
        source_text=f"Explicit requirement: {expected_value}",
        expected_value=expected_value,
        position=1,
    )
    confirm_requirements_draft(requirements=requirements, user=user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Unprofiled Candidate",
    )

    result = evaluate_candidate_constraints(
        requirements=requirements,
        candidate=candidate,
        user=user,
    )

    assert result.outcome == FilterOutcome.REVIEW
    assert result.rule_results[0].outcome == RuleOutcome.UNKNOWN
    assert "remains eligible" in result.rule_results[0].explanation


def test_failure_overrides_unknown_in_candidate_outcome() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(organization=organization, user=user)
    add_required_skill_rule(requirements=requirements, user=user, position=1)
    add_location_rule(requirements=requirements, user=user, position=2)
    confirm_requirements_draft(requirements=requirements, user=user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Mixed Outcome",
        location="Peja",
    )

    result = evaluate_candidate_constraints(
        requirements=requirements,
        candidate=candidate,
        user=user,
    )

    assert [rule.outcome for rule in result.rule_results] == [
        RuleOutcome.UNKNOWN,
        RuleOutcome.FAILED,
    ]
    assert result.outcome == FilterOutcome.FAILED


def test_no_explicit_rules_passes_filter_stage_without_inventing_rules() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(organization=organization, user=user)
    confirm_requirements_draft(requirements=requirements, user=user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="No Rule Candidate",
    )

    result = evaluate_candidate_constraints(
        requirements=requirements,
        candidate=candidate,
        user=user,
    )

    assert result.outcome == FilterOutcome.PASSED
    assert result.rule_results == ()


def test_filter_report_evaluates_only_active_candidates_and_summarizes() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(organization=organization, user=user)
    add_location_rule(requirements=requirements, user=user)
    confirm_requirements_draft(requirements=requirements, user=user)
    Candidate.objects.create(
        organization=organization,
        full_name="Pass",
        location="Prishtina",
    )
    Candidate.objects.create(
        organization=organization,
        full_name="Review",
    )
    Candidate.objects.create(
        organization=organization,
        full_name="Fail",
        location="Peja",
    )
    Candidate.objects.create(
        organization=organization,
        full_name="Inactive",
        location="Prishtina",
        status=Candidate.Status.INACTIVE,
    )

    report = filter_candidates(requirements=requirements, user=user)

    assert report.evaluated_count == 3
    assert report.passed_count == 1
    assert report.review_count == 1
    assert report.failed_count == 1
    assert report.eligible_count == 2
    assert [result.candidate.full_name for result in report.results] == [
        "Fail",
        "Pass",
        "Review",
    ]


def test_filtering_repeats_permissions_and_tenant_boundary() -> None:
    owner, organization = make_workspace(username="owner")
    outsider, other = make_workspace(username="outsider")
    _, requirements = make_requirements(organization=organization, user=owner)
    confirm_requirements_draft(requirements=requirements, user=owner)
    other_candidate = Candidate.objects.create(
        organization=other,
        full_name="Other Candidate",
    )

    with pytest.raises(PermissionDenied):
        filter_candidates(requirements=requirements, user=outsider)
    with pytest.raises(PermissionDenied):
        evaluate_candidate_constraints(
            requirements=requirements,
            candidate=other_candidate,
            user=owner,
        )


def test_draft_requirements_cannot_be_evaluated() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(organization=organization, user=user)

    with pytest.raises(ValidationError, match="confirmed requirements"):
        filter_candidates(requirements=requirements, user=user)


def test_inactive_candidate_cannot_be_evaluated_directly() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(organization=organization, user=user)
    confirm_requirements_draft(requirements=requirements, user=user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Inactive Candidate",
        status=Candidate.Status.INACTIVE,
    )

    with pytest.raises(ValidationError, match="active candidates"):
        evaluate_candidate_constraints(
            requirements=requirements,
            candidate=candidate,
            user=user,
        )


def test_deleted_vacancy_cannot_be_evaluated_directly() -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_requirements(organization=organization, user=user)
    confirm_requirements_draft(requirements=requirements, user=user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Candidate",
    )
    vacancy.deleted_at = vacancy.created_at
    vacancy.deleted_by = user
    vacancy.status = Vacancy.Status.CLOSED
    vacancy.save()

    with pytest.raises(ValidationError, match="Deleted vacancies"):
        evaluate_candidate_constraints(
            requirements=requirements,
            candidate=candidate,
            user=user,
        )


def test_filter_page_requires_login_and_hides_other_organizations(client) -> None:
    user, organization = make_workspace()
    other_user, other = make_workspace(username="other")
    visible, requirements = make_requirements(organization=organization, user=user)
    confirm_requirements_draft(requirements=requirements, user=user)
    hidden, hidden_requirements = make_requirements(
        organization=other,
        user=other_user,
    )
    confirm_requirements_draft(requirements=hidden_requirements, user=other_user)
    visible_url = reverse(
        "matching:candidate-filter-report",
        args=[organization.slug, visible.pk],
    )

    anonymous_response = client.get(visible_url)
    client.force_login(user)
    hidden_response = client.get(
        reverse(
            "matching:candidate-filter-report",
            args=[other.slug, hidden.pk],
        )
    )

    assert anonymous_response.status_code == 302
    assert hidden_response.status_code == 404


def test_filter_page_shows_version_summary_results_and_evidence(client) -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_requirements(organization=organization, user=user)
    add_required_skill_rule(requirements=requirements, user=user, position=1)
    add_location_rule(requirements=requirements, user=user, position=2)
    confirm_requirements_draft(requirements=requirements, user=user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Visible Candidate",
        email="private@example.test",
        location="Prishtina",
    )
    assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="Python",
        evidence="Inspectable synthetic evidence.",
    )
    client.force_login(user)

    response = client.get(
        reverse(
            "matching:candidate-filter-report",
            args=[organization.slug, vacancy.pk],
        )
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "confirmed requirements version 1" in content
    assert "Visible Candidate" in content
    assert "Inspectable synthetic evidence." in content
    assert "Candidate record location" in content
    assert "private@example.test" not in content
    assert "1 candidate remains eligible" in content


def test_filter_page_without_confirmed_requirements_is_safe(client) -> None:
    user, organization = make_workspace()
    vacancy, _ = make_requirements(organization=organization, user=user)
    client.force_login(user)

    response = client.get(
        reverse(
            "matching:candidate-filter-report",
            args=[organization.slug, vacancy.pk],
        )
    )

    assert response.status_code == 200
    assert "No confirmed requirements" in response.content.decode()


def test_vacancy_detail_links_to_filter_only_after_confirmation(client) -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_requirements(organization=organization, user=user)
    client.force_login(user)
    detail_url = reverse(
        "vacancies:vacancy-detail",
        args=[organization.slug, vacancy.pk],
    )

    draft_response = client.get(detail_url)
    confirm_requirements_draft(requirements=requirements, user=user)
    confirmed_response = client.get(detail_url)

    assert "Evaluate candidates" not in draft_response.content.decode()
    assert "Evaluate candidates" in confirmed_response.content.decode()
