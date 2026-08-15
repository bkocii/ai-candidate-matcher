from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from accounts.models import OrganizationMembership, User
from audit.models import AuditEvent
from organizations.models import ClientCompany, Organization
from vacancies.forms import VacancyCreateForm, VacancyRequirementsForm
from vacancies.models import Vacancy, VacancyRequirements
from vacancies.services import (
    available_vacancy_status_transitions,
    change_vacancy_status,
    confirm_requirements_draft,
    create_next_requirements_draft,
    create_vacancy_with_requirements,
    delete_vacancy,
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


def confirm_requirements_for_status(
    *,
    vacancy: Vacancy,
    requirements: VacancyRequirements,
    user: User,
) -> None:
    requirements.summary = "Confirmed requirements"
    requirements.save()
    confirm_requirements_draft(requirements=requirements, user=user)
    vacancy.refresh_from_db()


def test_draft_vacancy_cannot_open_without_confirmed_requirements(client) -> None:
    user, organization = make_workspace()
    vacancy, _ = make_vacancy(organization, user=user)
    client.force_login(user)

    response = client.post(
        reverse(
            "vacancies:vacancy-status-change",
            args=[organization.slug, vacancy.pk],
        ),
        {"status": Vacancy.Status.OPEN},
        follow=True,
    )

    vacancy.refresh_from_db()
    assert response.status_code == 200
    assert vacancy.status == Vacancy.Status.DRAFT
    assert "Confirm a requirements version before opening" in response.content.decode()


def test_recruiter_can_open_pause_resume_and_close_vacancy(client) -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_vacancy(organization, user=user)
    confirm_requirements_for_status(
        vacancy=vacancy,
        requirements=requirements,
        user=user,
    )
    client.force_login(user)
    route = reverse(
        "vacancies:vacancy-status-change",
        args=[organization.slug, vacancy.pk],
    )

    for new_status in (
        Vacancy.Status.OPEN,
        Vacancy.Status.PAUSED,
        Vacancy.Status.OPEN,
        Vacancy.Status.CLOSED,
        Vacancy.Status.OPEN,
    ):
        response = client.post(route, {"status": new_status})
        vacancy.refresh_from_db()
        assert response.status_code == 302
        assert vacancy.status == new_status


def test_status_route_is_post_only_and_rejects_invalid_transition(client) -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_vacancy(organization, user=user)
    confirm_requirements_for_status(
        vacancy=vacancy,
        requirements=requirements,
        user=user,
    )
    client.force_login(user)
    route = reverse(
        "vacancies:vacancy-status-change",
        args=[organization.slug, vacancy.pk],
    )

    get_response = client.get(route)
    post_response = client.post(
        route,
        {"status": Vacancy.Status.PAUSED},
        follow=True,
    )

    vacancy.refresh_from_db()
    assert get_response.status_code == 405
    assert post_response.status_code == 200
    assert vacancy.status == Vacancy.Status.DRAFT
    assert "cannot move directly from Draft to Paused" in post_response.content.decode()


def test_status_service_repeats_object_permission_check() -> None:
    owner, organization = make_workspace(username="owner")
    outsider = User.objects.create_user(username="outsider")
    vacancy, requirements = make_vacancy(organization, user=owner)
    confirm_requirements_for_status(
        vacancy=vacancy,
        requirements=requirements,
        user=owner,
    )

    with pytest.raises(PermissionDenied):
        change_vacancy_status(
            vacancy=vacancy,
            user=outsider,
            new_status=Vacancy.Status.OPEN,
        )

    vacancy.refresh_from_db()
    assert vacancy.status == Vacancy.Status.DRAFT


def test_status_route_hides_cross_organization_vacancy(client) -> None:
    user, organization = make_workspace()
    other = Organization.objects.create(name="Other", slug="other")
    hidden, _ = make_vacancy(other)
    client.force_login(user)

    response = client.post(
        reverse(
            "vacancies:vacancy-status-change",
            args=[organization.slug, hidden.pk],
        ),
        {"status": Vacancy.Status.OPEN},
    )

    assert response.status_code == 404


def test_detail_shows_only_currently_valid_status_controls(client) -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_vacancy(organization, user=user)
    client.force_login(user)
    detail_route = reverse(
        "vacancies:vacancy-detail",
        args=[organization.slug, vacancy.pk],
    )

    draft_response = client.get(detail_route)
    assert available_vacancy_status_transitions(vacancy) == ()
    assert "Confirm a requirements version before opening" in (
        draft_response.content.decode()
    )
    assert "Change to Open" not in draft_response.content.decode()

    confirm_requirements_for_status(
        vacancy=vacancy,
        requirements=requirements,
        user=user,
    )
    confirmed_response = client.get(detail_route)

    assert available_vacancy_status_transitions(vacancy) == (
        (Vacancy.Status.OPEN, "Open"),
    )
    assert "Change to Open" in confirmed_response.content.decode()
    assert "Change to Paused" not in confirmed_response.content.decode()


def test_recruiter_soft_deletes_vacancy_after_confirmation(client) -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_vacancy(organization, user=user)
    requirements.summary = "Preserved requirement history"
    requirements.save()
    confirm_requirements_draft(requirements=requirements, user=user)
    change_vacancy_status(
        vacancy=vacancy,
        user=user,
        new_status=Vacancy.Status.OPEN,
    )
    client.force_login(user)
    route = reverse(
        "vacancies:vacancy-delete",
        args=[organization.slug, vacancy.pk],
    )

    confirmation = client.get(route)
    response = client.post(route)

    vacancy.refresh_from_db()
    assert confirmation.status_code == 200
    assert "Requirement history will be preserved" in confirmation.content.decode()
    assert response.status_code == 302
    assert response.url == reverse("vacancies:vacancy-list", args=[organization.slug])
    assert vacancy.deleted_at is not None
    assert vacancy.deleted_by == user
    assert vacancy.status == Vacancy.Status.CLOSED
    assert vacancy.requirement_versions.get() == requirements

    listing = client.get(response.url)
    detail = client.get(
        reverse("vacancies:vacancy-detail", args=[organization.slug, vacancy.pk])
    )
    assert list(listing.context["page"].object_list) == []
    assert detail.status_code == 404
    dashboard = client.get(
        reverse("organizations:organization-dashboard", args=[organization.slug])
    )
    assert dashboard.context["open_vacancy_count"] == 0
    event = AuditEvent.objects.get(action=AuditEvent.Action.VACANCY_DELETED)
    assert event.organization == organization
    assert event.actor == user
    assert event.object_type == AuditEvent.ObjectType.VACANCY
    assert event.object_id == vacancy.pk


def test_vacancy_delete_service_repeats_permission_check() -> None:
    owner, organization = make_workspace(username="owner")
    outsider = User.objects.create_user(username="outsider")
    vacancy, _ = make_vacancy(organization, user=owner)

    with pytest.raises(PermissionDenied):
        delete_vacancy(vacancy=vacancy, user=outsider)

    vacancy.refresh_from_db()
    assert vacancy.deleted_at is None


def test_deleted_vacancy_cannot_change_status_through_service() -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_vacancy(organization, user=user)
    confirm_requirements_for_status(
        vacancy=vacancy,
        requirements=requirements,
        user=user,
    )
    delete_vacancy(vacancy=vacancy, user=user)

    with pytest.raises(ValidationError, match="has been deleted"):
        change_vacancy_status(
            vacancy=vacancy,
            user=user,
            new_status=Vacancy.Status.OPEN,
        )
