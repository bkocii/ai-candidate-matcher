from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from accounts.models import OrganizationMembership, User
from matching.forms import HardConstraintRuleForm
from matching.models import HardConstraintRule
from matching.services import (
    create_hard_constraint_rule,
    delete_hard_constraint_rule,
    update_hard_constraint_rule,
)
from organizations.models import Organization
from vacancies.models import Vacancy, VacancyRequirements
from vacancies.services import (
    confirm_requirements_draft,
    update_requirements_draft,
)

pytestmark = pytest.mark.django_db


def make_workspace(*, username: str = "recruiter"):
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
    vacancy = Vacancy.objects.create(
        organization=organization,
        title="Senior Django Developer",
        description="Python is mandatory. Remote work is required.",
        created_by=user,
    )
    requirements = VacancyRequirements.objects.create(
        vacancy=vacancy,
        source_description=vacancy.description,
        created_by=user,
    )
    update_requirements_draft(
        requirements=requirements,
        user=user,
        values=requirements_values(),
    )
    return user, organization, vacancy, requirements


def requirements_values(**overrides) -> dict:
    values = {
        "summary": "Senior backend role",
        "must_have_skills": ["Python", "Django"],
        "nice_to_have_skills": ["PostgreSQL"],
        "minimum_years_experience": Decimal("3.0"),
        "location_requirement": "Prishtina",
        "work_mode": VacancyRequirements.WorkMode.REMOTE,
        "language_requirements": ["English B2"],
        "education_requirements": [],
        "certification_requirements": [],
        "employment_type": VacancyRequirements.EmploymentType.FULL_TIME,
        "hard_constraints": ["Python is mandatory"],
        "ambiguities": [],
    }
    values.update(overrides)
    return values


def rule_form_data(requirements: VacancyRequirements, **overrides) -> dict:
    python_skill_id = requirements.skill_records.get(source_label="Python").skill_id
    values = {
        "rule_type": HardConstraintRule.RuleType.REQUIRED_SKILL,
        "source_text": "Python is mandatory.",
        "skill": str(python_skill_id),
        "numeric_value": "",
        "expected_value": "",
    }
    values.update(overrides)
    return values


def add_url(organization, vacancy, requirements) -> str:
    return reverse(
        "matching:hard-constraint-add",
        args=[organization.slug, vacancy.pk, requirements.pk],
    )


def edit_url(organization, vacancy, requirements, rule) -> str:
    return reverse(
        "matching:hard-constraint-edit",
        args=[organization.slug, vacancy.pk, requirements.pk, rule.pk],
    )


def delete_url(organization, vacancy, requirements, rule) -> str:
    return reverse(
        "matching:hard-constraint-delete",
        args=[organization.slug, vacancy.pk, requirements.pk, rule.pk],
    )


def test_rule_form_offers_only_saved_must_have_skills() -> None:
    _, _, _, requirements = make_workspace()

    form = HardConstraintRuleForm(requirements=requirements)

    choices = dict(form.fields["skill"].choices)
    assert "Python" in choices.values()
    assert "Django" in choices.values()
    assert "PostgreSQL" not in choices.values()


def test_rule_form_accepts_controlled_choice_labels() -> None:
    _, _, _, requirements = make_workspace()
    form = HardConstraintRuleForm(
        data=rule_form_data(
            requirements,
            rule_type=HardConstraintRule.RuleType.WORK_MODE,
            skill="",
            expected_value="Remote",
        ),
        requirements=requirements,
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["expected_value"] == VacancyRequirements.WorkMode.REMOTE


def test_rule_form_rejects_unknown_as_a_required_controlled_value() -> None:
    _, _, _, requirements = make_workspace()
    form = HardConstraintRuleForm(
        data=rule_form_data(
            requirements,
            rule_type=HardConstraintRule.RuleType.WORK_MODE,
            skill="",
            expected_value="Unknown",
        ),
        requirements=requirements,
    )

    assert not form.is_valid()
    assert "Select a supported work mode" in form.errors["expected_value"][0]


def test_recruiter_adds_required_skill_rule_from_draft_editor(client) -> None:
    user, organization, vacancy, requirements = make_workspace()
    client.force_login(user)

    response = client.post(
        add_url(organization, vacancy, requirements),
        rule_form_data(requirements),
    )

    rule = requirements.hard_constraint_rules.get()
    assert response.status_code == 302
    assert response.url == reverse(
        "vacancies:requirements-edit",
        args=[organization.slug, vacancy.pk, requirements.pk],
    )
    assert rule.rule_type == HardConstraintRule.RuleType.REQUIRED_SKILL
    assert rule.operator == HardConstraintRule.Operator.HAS_SKILL
    assert rule.skill.name == "Python"
    assert rule.position == 1

    editor = client.get(response.url)
    content = editor.content.decode()
    assert "Typed hard-constraint rules" in content
    assert "Python is mandatory." in content
    assert "Free-text notes above do not affect filtering" not in content

    add_page = client.get(add_url(organization, vacancy, requirements))
    assert 'name="operator"' not in add_page.content.decode()
    assert 'name="unknown_outcome"' not in add_page.content.decode()


def test_rule_positions_are_assigned_automatically(client) -> None:
    user, organization, vacancy, requirements = make_workspace()
    client.force_login(user)
    client.post(
        add_url(organization, vacancy, requirements),
        rule_form_data(requirements),
    )
    client.post(
        add_url(organization, vacancy, requirements),
        rule_form_data(
            requirements,
            rule_type=HardConstraintRule.RuleType.LOCATION,
            source_text="Candidate must be in Prishtina.",
            skill="",
            expected_value="Prishtina",
        ),
    )

    assert list(
        requirements.hard_constraint_rules.values_list("position", flat=True)
    ) == [1, 2]


def test_recruiter_edits_rule_type_and_payload_from_app(client) -> None:
    user, organization, vacancy, requirements = make_workspace()
    rule = create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=HardConstraintRule.RuleType.LOCATION,
        source_text="Prishtina required.",
        expected_value="Prishtina",
    )
    client.force_login(user)

    response = client.post(
        edit_url(organization, vacancy, requirements, rule),
        rule_form_data(
            requirements,
            rule_type=HardConstraintRule.RuleType.MINIMUM_EXPERIENCE,
            source_text="At least four years required.",
            skill="",
            numeric_value="4.0",
        ),
    )

    rule.refresh_from_db()
    assert response.status_code == 302
    assert rule.rule_type == HardConstraintRule.RuleType.MINIMUM_EXPERIENCE
    assert rule.operator == HardConstraintRule.Operator.AT_LEAST
    assert rule.numeric_value == Decimal("4.0")
    assert rule.expected_value == ""


def test_rule_delete_requires_confirmation_page(client) -> None:
    user, organization, vacancy, requirements = make_workspace()
    rule = create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=HardConstraintRule.RuleType.LOCATION,
        source_text="Prishtina required.",
        expected_value="Prishtina",
    )
    client.force_login(user)

    confirmation = client.get(delete_url(organization, vacancy, requirements, rule))
    assert confirmation.status_code == 200
    assert "Delete typed hard constraint?" in confirmation.content.decode()
    assert HardConstraintRule.objects.filter(pk=rule.pk).exists()

    response = client.post(delete_url(organization, vacancy, requirements, rule))
    assert response.status_code == 302
    assert not HardConstraintRule.objects.filter(pk=rule.pk).exists()


def test_confirmed_rules_are_visible_but_not_editable(client) -> None:
    user, organization, vacancy, requirements = make_workspace()
    rule = create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=HardConstraintRule.RuleType.LOCATION,
        source_text="Prishtina required.",
        expected_value="Prishtina",
    )
    confirm_requirements_draft(requirements=requirements, user=user)
    client.force_login(user)

    detail = client.get(
        reverse(
            "vacancies:vacancy-detail",
            args=[organization.slug, vacancy.pk],
        )
    )
    content = detail.content.decode()
    assert "Typed hard-constraint rules · v1" in content
    assert "Prishtina required." in content
    assert edit_url(organization, vacancy, requirements, rule) not in content

    edit_response = client.get(edit_url(organization, vacancy, requirements, rule))
    assert edit_response.status_code == 302
    assert edit_response.url == reverse(
        "vacancies:vacancy-detail",
        args=[organization.slug, vacancy.pk],
    )


def test_service_mutations_reject_confirmed_rules() -> None:
    user, _, _, requirements = make_workspace()
    rule = create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=HardConstraintRule.RuleType.LOCATION,
        source_text="Prishtina required.",
        expected_value="Prishtina",
    )
    confirm_requirements_draft(requirements=requirements, user=user)

    with pytest.raises(ValidationError, match="immutable"):
        update_hard_constraint_rule(
            rule=rule,
            user=user,
            rule_type=HardConstraintRule.RuleType.LOCATION,
            source_text="Remote required.",
            expected_value="Remote",
        )
    with pytest.raises(ValidationError, match="immutable"):
        delete_hard_constraint_rule(rule=rule, user=user)


def test_cross_organization_rule_routes_and_services_are_protected(client) -> None:
    owner, organization, vacancy, requirements = make_workspace(username="owner")
    outsider, other, _, _ = make_workspace(username="outsider")
    rule = create_hard_constraint_rule(
        requirements=requirements,
        user=owner,
        rule_type=HardConstraintRule.RuleType.LOCATION,
        source_text="Prishtina required.",
        expected_value="Prishtina",
    )
    client.force_login(outsider)

    assert client.get(add_url(organization, vacancy, requirements)).status_code == 404
    assert (
        client.get(edit_url(organization, vacancy, requirements, rule)).status_code
        == 404
    )

    with pytest.raises(PermissionDenied):
        update_hard_constraint_rule(
            rule=rule,
            user=outsider,
            rule_type=HardConstraintRule.RuleType.LOCATION,
            source_text="Remote required.",
            expected_value="Remote",
        )
    assert other != organization


def test_removing_skill_used_by_rule_is_rejected_and_rolled_back(client) -> None:
    user, organization, vacancy, requirements = make_workspace()
    create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=HardConstraintRule.RuleType.REQUIRED_SKILL,
        source_text="Python is mandatory.",
        skill_label="Python",
    )
    client.force_login(user)

    response = client.post(
        reverse(
            "vacancies:requirements-edit",
            args=[organization.slug, vacancy.pk, requirements.pk],
        ),
        {
            "summary": "Senior backend role",
            "must_have_skills": "Django",
            "nice_to_have_skills": "PostgreSQL",
            "minimum_years_experience": "3.0",
            "location_requirement": "Prishtina",
            "work_mode": VacancyRequirements.WorkMode.REMOTE,
            "language_requirements": "English B2",
            "education_requirements": "",
            "certification_requirements": "",
            "employment_type": VacancyRequirements.EmploymentType.FULL_TIME,
            "hard_constraints": "Python is mandatory",
            "ambiguities": "",
        },
    )

    requirements.refresh_from_db()
    assert response.status_code == 200
    assert "must-have skill" in response.content.decode()
    assert requirements.must_have_skills == ["Python", "Django"]
    assert requirements.skill_records.filter(source_label="Python").exists()


def test_confirmation_revalidates_typed_rules_before_locking_version() -> None:
    user, _, _, requirements = make_workspace()
    create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type=HardConstraintRule.RuleType.REQUIRED_SKILL,
        source_text="Python is mandatory.",
        skill_label="Python",
    )
    requirements.must_have_skills = ["Django"]
    requirements.save()

    with pytest.raises(ValidationError, match="must-have skill"):
        confirm_requirements_draft(requirements=requirements, user=user)

    requirements.refresh_from_db()
    assert requirements.status == VacancyRequirements.Status.DRAFT
