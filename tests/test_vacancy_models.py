from decimal import Decimal

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import OrganizationMembership, User
from organizations.models import ClientCompany, Organization
from organizations.permissions import has_organization_object_access
from vacancies.models import Vacancy, VacancyRequirements

pytestmark = pytest.mark.django_db


def add_member(user: User, organization: Organization) -> None:
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )


def create_vacancy(
    organization: Organization,
    *,
    title: str = "Senior Django Developer",
    description: str = "Build and maintain Django services.",
    **kwargs,
) -> Vacancy:
    return Vacancy.objects.create(
        organization=organization,
        title=title,
        description=description,
        **kwargs,
    )


def test_vacancy_belongs_to_organization_and_optional_client() -> None:
    creator = User.objects.create_user(username="creator")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    client = ClientCompany.objects.create(
        organization=organization,
        name="Acme Industries",
        slug="acme-industries",
    )
    vacancy = create_vacancy(
        organization,
        client_company=client,
        created_by=creator,
    )

    assert str(vacancy) == "Senior Django Developer"
    assert vacancy.status == Vacancy.Status.DRAFT
    assert organization.vacancies.get() == vacancy
    assert client.vacancies.get() == vacancy


def test_direct_employer_vacancy_does_not_require_client_company() -> None:
    organization = Organization.objects.create(name="Direct", slug="direct")

    vacancy = create_vacancy(organization)

    assert vacancy.client_company is None


def test_vacancy_rejects_client_from_another_organization() -> None:
    first = Organization.objects.create(name="First", slug="first")
    second = Organization.objects.create(name="Second", slug="second")
    other_client = ClientCompany.objects.create(
        organization=second,
        name="Other Client",
        slug="other-client",
    )

    with pytest.raises(ValidationError, match="vacancy organization"):
        create_vacancy(first, client_company=other_client)


def test_deleting_client_preserves_vacancy() -> None:
    organization = Organization.objects.create(name="Agency", slug="agency")
    client = ClientCompany.objects.create(
        organization=organization,
        name="Temporary Client",
        slug="temporary-client",
    )
    vacancy = create_vacancy(organization, client_company=client)

    client.delete()
    vacancy.refresh_from_db()

    assert vacancy.client_company is None


def test_vacancy_and_requirement_versions_are_organization_scoped() -> None:
    recruiter = User.objects.create_user(username="recruiter")
    first = Organization.objects.create(name="First", slug="first")
    second = Organization.objects.create(name="Second", slug="second")
    add_member(recruiter, first)
    visible_vacancy = create_vacancy(first, title="Visible")
    hidden_vacancy = create_vacancy(second, title="Hidden")
    visible_requirements = VacancyRequirements.objects.create(
        vacancy=visible_vacancy,
        source_description=visible_vacancy.description,
    )
    VacancyRequirements.objects.create(
        vacancy=hidden_vacancy,
        source_description=hidden_vacancy.description,
    )

    assert list(Vacancy.objects.visible_to(recruiter)) == [visible_vacancy]
    assert list(Vacancy.objects.for_organization(first)) == [visible_vacancy]
    assert list(VacancyRequirements.objects.visible_to(recruiter)) == [
        visible_requirements
    ]
    assert list(VacancyRequirements.objects.for_organization(first)) == [
        visible_requirements
    ]
    assert has_organization_object_access(recruiter, visible_requirements) is True


def test_anonymous_user_cannot_see_vacancies_or_requirements() -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")
    vacancy = create_vacancy(organization)
    VacancyRequirements.objects.create(
        vacancy=vacancy,
        source_description=vacancy.description,
    )

    assert not Vacancy.objects.visible_to(AnonymousUser()).exists()
    assert not VacancyRequirements.objects.visible_to(AnonymousUser()).exists()


def test_requirement_version_stores_reproducible_structured_snapshot() -> None:
    creator = User.objects.create_user(username="requirement-author")
    organization = Organization.objects.create(name="Acme", slug="acme")
    vacancy = create_vacancy(organization)
    requirements = VacancyRequirements.objects.create(
        vacancy=vacancy,
        version=1,
        schema_version="vacancy_requirements.v1",
        creation_method=VacancyRequirements.CreationMethod.MANUAL,
        source_description=vacancy.description,
        summary="Experienced Django engineer.",
        must_have_skills=["Python", "Django"],
        nice_to_have_skills=["PostgreSQL"],
        minimum_years_experience=Decimal("4.5"),
        location_requirement="Prishtina or remote",
        work_mode=VacancyRequirements.WorkMode.HYBRID,
        language_requirements=["English"],
        education_requirements=["Bachelor's degree or equivalent experience"],
        certification_requirements=["None required"],
        employment_type=VacancyRequirements.EmploymentType.FULL_TIME,
        hard_constraints=["Eligible to work in Kosovo"],
        ambiguities=["On-call frequency is not specified"],
        created_by=creator,
    )

    assert requirements.organization == organization
    assert requirements.status == VacancyRequirements.Status.DRAFT
    assert requirements.must_have_skills == ["Python", "Django"]
    assert str(requirements) == "Senior Django Developer — requirements v1"


def test_requirement_version_number_is_unique_per_vacancy() -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")
    first_vacancy = create_vacancy(organization, title="First")
    second_vacancy = create_vacancy(organization, title="Second")
    VacancyRequirements.objects.create(
        vacancy=first_vacancy,
        version=1,
        source_description=first_vacancy.description,
    )
    VacancyRequirements.objects.create(
        vacancy=second_vacancy,
        version=1,
        source_description=second_vacancy.description,
    )

    with pytest.raises(ValidationError, match="already exists"):
        VacancyRequirements.objects.create(
            vacancy=first_vacancy,
            version=1,
            source_description=first_vacancy.description,
        )


def test_database_rejects_non_positive_requirement_version() -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")
    vacancy = create_vacancy(organization)

    with pytest.raises(IntegrityError), transaction.atomic():
        VacancyRequirements.objects.bulk_create(
            [
                VacancyRequirements(
                    vacancy=vacancy,
                    version=0,
                    source_description=vacancy.description,
                )
            ]
        )


def test_confirmed_requirements_require_recruiter_and_timestamp() -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")
    vacancy = create_vacancy(organization)

    with pytest.raises(ValidationError, match="confirmation"):
        VacancyRequirements.objects.create(
            vacancy=vacancy,
            source_description=vacancy.description,
            status=VacancyRequirements.Status.CONFIRMED,
        )


def test_current_requirements_returns_latest_confirmed_version() -> None:
    confirmer = User.objects.create_user(username="confirmer")
    organization = Organization.objects.create(name="Acme", slug="acme")
    vacancy = create_vacancy(organization)
    first = VacancyRequirements.objects.create(
        vacancy=vacancy,
        version=1,
        source_description=vacancy.description,
        status=VacancyRequirements.Status.CONFIRMED,
        confirmed_by=confirmer,
        confirmed_at=timezone.now(),
    )
    latest = VacancyRequirements.objects.create(
        vacancy=vacancy,
        version=2,
        source_description=vacancy.description,
        summary="Recruiter-corrected requirements.",
        status=VacancyRequirements.Status.CONFIRMED,
        confirmed_by=confirmer,
        confirmed_at=timezone.now(),
    )
    VacancyRequirements.objects.create(
        vacancy=vacancy,
        version=3,
        source_description=vacancy.description,
        summary="Unconfirmed draft.",
    )

    assert vacancy.current_requirements == latest
    assert vacancy.current_requirements != first


def test_confirmed_requirement_snapshot_is_immutable() -> None:
    confirmer = User.objects.create_user(username="confirmer")
    organization = Organization.objects.create(name="Acme", slug="acme")
    vacancy = create_vacancy(organization)
    requirements = VacancyRequirements.objects.create(
        vacancy=vacancy,
        source_description=vacancy.description,
        summary="Confirmed snapshot",
        status=VacancyRequirements.Status.CONFIRMED,
        confirmed_by=confirmer,
        confirmed_at=timezone.now(),
    )

    requirements.summary = "Changed in place"

    with pytest.raises(ValidationError, match="create a new version"):
        requirements.save()

    requirements.refresh_from_db()
    assert requirements.summary == "Confirmed snapshot"


def test_draft_can_be_edited_and_then_confirmed() -> None:
    confirmer = User.objects.create_user(username="confirmer")
    organization = Organization.objects.create(name="Acme", slug="acme")
    vacancy = create_vacancy(organization)
    requirements = VacancyRequirements.objects.create(
        vacancy=vacancy,
        source_description=vacancy.description,
        summary="Initial draft",
    )

    requirements.summary = "Recruiter-corrected draft"
    requirements.save()
    requirements.status = VacancyRequirements.Status.CONFIRMED
    requirements.confirmed_by = confirmer
    requirements.confirmed_at = timezone.now()
    requirements.save()

    requirements.refresh_from_db()
    assert requirements.summary == "Recruiter-corrected draft"
    assert requirements.status == VacancyRequirements.Status.CONFIRMED


@pytest.mark.parametrize(
    "invalid_value",
    ["Python", ["Python", ""], ["Python", 3]],
)
def test_requirement_list_fields_accept_only_non_blank_strings(
    invalid_value: object,
) -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")
    vacancy = create_vacancy(organization)

    with pytest.raises(ValidationError, match="non-blank strings"):
        VacancyRequirements.objects.create(
            vacancy=vacancy,
            source_description=vacancy.description,
            must_have_skills=invalid_value,
        )


def test_deleting_vacancy_removes_requirement_versions() -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")
    vacancy = create_vacancy(organization)
    VacancyRequirements.objects.create(
        vacancy=vacancy,
        source_description=vacancy.description,
    )

    vacancy.delete()

    assert not VacancyRequirements.objects.exists()
