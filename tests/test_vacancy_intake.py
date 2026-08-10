from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from accounts.models import OrganizationMembership, User
from organizations.models import ClientCompany, Organization
from vacancies.forms import VacancyCreateForm, VacancyRequirementsForm
from vacancies.models import Vacancy, VacancyRequirements
from vacancies.services import (
    confirm_requirements_draft,
    create_next_requirements_draft,
    create_vacancy_with_requirements,
    update_requirements_draft,
)

pytestmark = pytest.mark.django_db


def add_member(user: User, organization: Organization) -> None:
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )


def make_workspace(*, username: str = "recruiter"):
    user = User.objects.create_user(username=username, password="test-password")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    return user, organization


def make_vacancy(
    organization: Organization,
    *,
    user: User | None = None,
    with_draft: bool = True,
    title: str = "Senior Django Developer",
) -> tuple[Vacancy, VacancyRequirements | None]:
    vacancy = Vacancy.objects.create(
        organization=organization,
        title=title,
        description="Build secure Django applications.",
        created_by=user,
    )
    requirements = None
    if with_draft:
        requirements = VacancyRequirements.objects.create(
            vacancy=vacancy,
            source_description=vacancy.description,
            created_by=user,
        )
    return vacancy, requirements


def requirements_values(**overrides) -> dict:
    values = {
        "summary": "Senior backend role",
        "must_have_skills": ["Python", "Django"],
        "nice_to_have_skills": ["PostgreSQL"],
        "minimum_years_experience": Decimal("4.0"),
        "location_requirement": "Prishtina or remote",
        "work_mode": VacancyRequirements.WorkMode.HYBRID,
        "language_requirements": ["English"],
        "education_requirements": [],
        "certification_requirements": [],
        "employment_type": VacancyRequirements.EmploymentType.FULL_TIME,
        "hard_constraints": ["Eligible to work in Kosovo"],
        "ambiguities": ["On-call frequency is not stated"],
    }
    values.update(overrides)
    return values


def test_vacancy_pages_require_login(client) -> None:
    organization = Organization.objects.create(name="Northstar", slug="northstar")

    response = client.get(reverse("vacancies:vacancy-list", args=[organization.slug]))

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))


def test_vacancy_list_is_scoped_to_requested_organization(client) -> None:
    user, organization = make_workspace()
    other = Organization.objects.create(name="Other", slug="other")
    visible, _ = make_vacancy(organization, user=user, title="Visible vacancy")
    hidden, _ = make_vacancy(other, title="Hidden vacancy")
    client.force_login(user)

    response = client.get(reverse("vacancies:vacancy-list", args=[organization.slug]))

    assert response.status_code == 200
    assert visible.title in response.content.decode()
    assert hidden.title not in response.content.decode()


def test_inaccessible_organization_and_vacancy_return_404(client) -> None:
    user, organization = make_workspace()
    other = Organization.objects.create(name="Other", slug="other")
    hidden, hidden_requirements = make_vacancy(other)
    client.force_login(user)

    organization_response = client.get(
        reverse("vacancies:vacancy-list", args=[other.slug])
    )
    object_response = client.get(
        reverse(
            "vacancies:requirements-edit",
            args=[organization.slug, hidden.pk, hidden_requirements.pk],
        )
    )

    assert organization_response.status_code == 404
    assert object_response.status_code == 404


def test_create_form_lists_only_active_clients_in_organization() -> None:
    _, organization = make_workspace()
    visible = ClientCompany.objects.create(
        organization=organization,
        name="Visible Client",
        slug="visible-client",
    )
    ClientCompany.objects.create(
        organization=organization,
        name="Inactive Client",
        slug="inactive-client",
        is_active=False,
    )
    other = Organization.objects.create(name="Other", slug="other")
    ClientCompany.objects.create(
        organization=other,
        name="Other Client",
        slug="other-client",
    )

    form = VacancyCreateForm(organization=organization)

    assert list(form.fields["client_company"].queryset) == [visible]


def test_recruiter_creates_vacancy_and_initial_draft_atomically(client) -> None:
    user, organization = make_workspace()
    client_company = ClientCompany.objects.create(
        organization=organization,
        name="Acme",
        slug="acme",
    )
    client.force_login(user)

    response = client.post(
        reverse("vacancies:vacancy-create", args=[organization.slug]),
        {
            "title": "  Senior Python Engineer  ",
            "client_company": client_company.pk,
            "description": "  Build reliable Python services.  ",
        },
    )

    vacancy = Vacancy.objects.get()
    requirements = vacancy.requirement_versions.get()
    assert response.status_code == 302
    assert response.url == reverse(
        "vacancies:requirements-edit",
        args=[organization.slug, vacancy.pk, requirements.pk],
    )
    assert vacancy.title == "Senior Python Engineer"
    assert vacancy.description == "Build reliable Python services."
    assert vacancy.client_company == client_company
    assert vacancy.created_by == user
    assert requirements.version == 1
    assert requirements.status == VacancyRequirements.Status.DRAFT
    assert requirements.source_description == vacancy.description
    assert requirements.created_by == user


def test_direct_employer_creation_accepts_no_client(client) -> None:
    user, organization = make_workspace()
    client.force_login(user)

    response = client.post(
        reverse("vacancies:vacancy-create", args=[organization.slug]),
        {
            "title": "Data Analyst",
            "client_company": "",
            "description": "Analyze business data.",
        },
    )

    assert response.status_code == 302
    assert Vacancy.objects.get().client_company is None


def test_forged_cross_organization_client_is_rejected_by_form(client) -> None:
    user, organization = make_workspace()
    other = Organization.objects.create(name="Other", slug="other")
    other_client = ClientCompany.objects.create(
        organization=other,
        name="Other Client",
        slug="other-client",
    )
    client.force_login(user)

    response = client.post(
        reverse("vacancies:vacancy-create", args=[organization.slug]),
        {
            "title": "Data Analyst",
            "client_company": other_client.pk,
            "description": "Analyze business data.",
        },
    )

    assert response.status_code == 200
    assert "Select a valid choice" in response.content.decode()
    assert not Vacancy.objects.exists()


def test_vacancy_creation_service_repeats_membership_check() -> None:
    user = User.objects.create_user(username="outsider")
    organization = Organization.objects.create(name="Northstar", slug="northstar")

    with pytest.raises(PermissionDenied):
        create_vacancy_with_requirements(
            organization=organization,
            user=user,
            vacancy_values={
                "title": "Data Analyst",
                "description": "Analyze business data.",
                "client_company": None,
            },
        )

    assert not Vacancy.objects.exists()


def test_requirements_form_normalizes_lists_and_duplicate_lines() -> None:
    form = VacancyRequirementsForm(
        data={
            "summary": "  Backend role  ",
            "must_have_skills": " Python\nDjango\npython\n\n",
            "nice_to_have_skills": "PostgreSQL",
            "minimum_years_experience": "3.5",
            "location_requirement": "  Prishtina  ",
            "work_mode": VacancyRequirements.WorkMode.HYBRID,
            "language_requirements": "English\nAlbanian",
            "education_requirements": "",
            "certification_requirements": "",
            "employment_type": VacancyRequirements.EmploymentType.FULL_TIME,
            "hard_constraints": "Eligible to work in Kosovo",
            "ambiguities": "",
        }
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["summary"] == "Backend role"
    assert form.cleaned_data["must_have_skills"] == ["Python", "Django"]
    assert form.cleaned_data["location_requirement"] == "Prishtina"


def test_recruiter_edits_requirements_draft(client) -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_vacancy(organization, user=user)
    client.force_login(user)

    response = client.post(
        reverse(
            "vacancies:requirements-edit",
            args=[organization.slug, vacancy.pk, requirements.pk],
        ),
        {
            "summary": "Senior backend role",
            "must_have_skills": "Python\nDjango",
            "nice_to_have_skills": "PostgreSQL",
            "minimum_years_experience": "4.0",
            "location_requirement": "Prishtina or remote",
            "work_mode": VacancyRequirements.WorkMode.HYBRID,
            "language_requirements": "English",
            "education_requirements": "",
            "certification_requirements": "",
            "employment_type": VacancyRequirements.EmploymentType.FULL_TIME,
            "hard_constraints": "Eligible to work in Kosovo",
            "ambiguities": "On-call frequency is not stated",
        },
    )

    requirements.refresh_from_db()
    assert response.status_code == 302
    assert requirements.must_have_skills == ["Python", "Django"]
    assert requirements.minimum_years_experience == Decimal("4.0")
    assert requirements.status == VacancyRequirements.Status.DRAFT


def test_update_service_rejects_cross_organization_user() -> None:
    owner, organization = make_workspace(username="owner")
    outsider = User.objects.create_user(username="outsider")
    vacancy, requirements = make_vacancy(organization, user=owner)

    with pytest.raises(PermissionDenied):
        update_requirements_draft(
            requirements=requirements,
            user=outsider,
            values=requirements_values(),
        )


def test_requirements_confirmation_is_post_only(client) -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_vacancy(organization, user=user)
    client.force_login(user)

    response = client.get(
        reverse(
            "vacancies:requirements-confirm",
            args=[organization.slug, vacancy.pk, requirements.pk],
        )
    )

    assert response.status_code == 405


def test_empty_requirements_draft_cannot_be_confirmed(client) -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_vacancy(organization, user=user)
    client.force_login(user)

    response = client.post(
        reverse(
            "vacancies:requirements-confirm",
            args=[organization.slug, vacancy.pk, requirements.pk],
        ),
        follow=True,
    )

    requirements.refresh_from_db()
    assert response.status_code == 200
    assert "Add at least one structured requirement" in response.content.decode()
    assert requirements.status == VacancyRequirements.Status.DRAFT


def test_recruiter_confirms_meaningful_requirements(client) -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_vacancy(organization, user=user)
    update_requirements_draft(
        requirements=requirements,
        user=user,
        values=requirements_values(),
    )
    client.force_login(user)

    response = client.post(
        reverse(
            "vacancies:requirements-confirm",
            args=[organization.slug, vacancy.pk, requirements.pk],
        )
    )

    requirements.refresh_from_db()
    assert response.status_code == 302
    assert requirements.status == VacancyRequirements.Status.CONFIRMED
    assert requirements.confirmed_by == user
    assert requirements.confirmed_at is not None
    assert vacancy.current_requirements == requirements


def test_confirm_service_repeats_object_permission_check() -> None:
    owner, organization = make_workspace(username="owner")
    outsider = User.objects.create_user(username="outsider")
    vacancy, requirements = make_vacancy(organization, user=owner)
    requirements.summary = "Meaningful requirements"
    requirements.save()

    with pytest.raises(PermissionDenied):
        confirm_requirements_draft(requirements=requirements, user=outsider)


def test_confirmed_version_cannot_be_opened_for_editing(client) -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_vacancy(organization, user=user)
    requirements.summary = "Confirmed snapshot"
    requirements.status = VacancyRequirements.Status.CONFIRMED
    requirements.confirmed_by = user
    requirements.confirmed_at = timezone.now()
    requirements.save()
    client.force_login(user)

    response = client.get(
        reverse(
            "vacancies:requirements-edit",
            args=[organization.slug, vacancy.pk, requirements.pk],
        )
    )

    assert response.status_code == 302
    assert response.url == reverse(
        "vacancies:vacancy-detail", args=[organization.slug, vacancy.pk]
    )


def test_new_draft_copies_confirmed_version_and_increments_number(client) -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_vacancy(organization, user=user)
    update_requirements_draft(
        requirements=requirements,
        user=user,
        values=requirements_values(),
    )
    confirm_requirements_draft(requirements=requirements, user=user)
    client.force_login(user)

    response = client.post(
        reverse(
            "vacancies:requirements-new-draft",
            args=[organization.slug, vacancy.pk],
        )
    )

    draft = vacancy.requirement_versions.get(status=VacancyRequirements.Status.DRAFT)
    assert response.status_code == 302
    assert draft.version == 2
    assert draft.must_have_skills == ["Python", "Django"]
    assert draft.source_description == requirements.source_description
    assert draft.confirmed_by is None
    assert draft.confirmed_at is None


def test_new_draft_route_reuses_existing_draft(client) -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_vacancy(organization, user=user)
    client.force_login(user)

    response = client.post(
        reverse(
            "vacancies:requirements-new-draft",
            args=[organization.slug, vacancy.pk],
        )
    )

    assert response.status_code == 302
    assert vacancy.requirement_versions.count() == 1
    assert response.url == reverse(
        "vacancies:requirements-edit",
        args=[organization.slug, vacancy.pk, requirements.pk],
    )


def test_new_draft_service_rejects_cross_organization_user() -> None:
    owner, organization = make_workspace(username="owner")
    outsider = User.objects.create_user(username="outsider")
    vacancy, _ = make_vacancy(organization, user=owner)

    with pytest.raises(PermissionDenied):
        create_next_requirements_draft(vacancy=vacancy, user=outsider)


def test_vacancy_detail_never_renders_another_organizations_data(client) -> None:
    user, organization = make_workspace()
    visible, visible_requirements = make_vacancy(organization, user=user)
    visible_requirements.summary = "Visible requirement"
    visible_requirements.save()
    other = Organization.objects.create(name="Other", slug="other")
    hidden, hidden_requirements = make_vacancy(other)
    hidden.description = "Secret vacancy description"
    hidden.save()
    hidden_requirements.summary = "Secret requirements"
    hidden_requirements.save()
    client.force_login(user)

    response = client.get(
        reverse(
            "vacancies:vacancy-detail",
            args=[organization.slug, visible.pk],
        )
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Visible requirement" not in content  # Drafts are not matching input.
    assert "Secret vacancy description" not in content
    assert "Secret requirements" not in content
