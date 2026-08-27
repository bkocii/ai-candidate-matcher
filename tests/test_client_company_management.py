import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from accounts.models import OrganizationMembership, User
from organizations.models import ClientCompany, Organization
from organizations.services import (
    create_client_company,
    set_client_company_active,
    update_client_company,
)
from vacancies.forms import VacancyCreateForm, VacancyEditForm
from vacancies.models import Vacancy, VacancyRequirements
from vacancies.services import (
    create_vacancy_with_requirements,
    update_vacancy_details,
)

pytestmark = pytest.mark.django_db


def add_member(
    user: User,
    organization: Organization,
    *,
    role: str = OrganizationMembership.Role.RECRUITER,
) -> None:
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=role,
    )


def workspace():
    admin = User.objects.create_user(username="company-admin", password="test-password")
    recruiter = User.objects.create_user(
        username="company-recruiter", password="test-password"
    )
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(admin, organization, role=OrganizationMembership.Role.ADMIN)
    add_member(recruiter, organization)
    return admin, recruiter, organization


def vacancy_for(
    organization: Organization,
    user: User,
    *,
    company: ClientCompany | None = None,
) -> Vacancy:
    vacancy = Vacancy.objects.create(
        organization=organization,
        client_company=company,
        title="Senior Developer",
        description="Build secure services.",
        created_by=user,
    )
    VacancyRequirements.objects.create(
        vacancy=vacancy,
        source_description=vacancy.description,
        created_by=user,
    )
    return vacancy


def test_only_organization_admins_can_open_client_company_settings(client) -> None:
    admin, recruiter, organization = workspace()
    settings_url = reverse(
        "organizations:organization-settings", args=[organization.slug]
    )
    list_url = reverse("organizations:client-company-list", args=[organization.slug])

    client.force_login(admin)
    assert client.get(settings_url).status_code == 200
    assert client.get(list_url).status_code == 200

    client.force_login(recruiter)
    assert client.get(settings_url).status_code == 403
    assert client.get(list_url).status_code == 403


def test_client_company_routes_do_not_disclose_another_organization(client) -> None:
    admin, _, organization = workspace()
    other = Organization.objects.create(name="Other", slug="other")
    company = ClientCompany.objects.create(
        organization=other,
        name="Hidden Customer",
        slug="hidden-customer",
    )
    client.force_login(admin)

    assert (
        client.get(
            reverse("organizations:client-company-list", args=[other.slug])
        ).status_code
        == 404
    )
    assert (
        client.get(
            reverse(
                "organizations:client-company-edit",
                args=[organization.slug, company.pk],
            )
        ).status_code
        == 404
    )


def test_admin_creates_and_edits_client_company_with_stable_slug(client) -> None:
    admin, _, organization = workspace()
    client.force_login(admin)
    response = client.post(
        reverse("organizations:client-company-create", args=[organization.slug]),
        {"name": "  Acme Industries  ", "website": "https://acme.example.test"},
    )

    company = ClientCompany.objects.get()
    assert response.status_code == 302
    assert company.name == "Acme Industries"
    assert company.slug == "acme-industries"
    assert company.website == "https://acme.example.test"

    response = client.post(
        reverse(
            "organizations:client-company-edit", args=[organization.slug, company.pk]
        ),
        {"name": "Acme Group", "website": ""},
    )
    company.refresh_from_db()
    assert response.status_code == 302
    assert company.name == "Acme Group"
    assert company.slug == "acme-industries"


def test_duplicate_company_names_receive_distinct_organization_slugs() -> None:
    admin, _, organization = workspace()
    first = create_client_company(
        organization=organization,
        user=admin,
        values={"name": "Acme", "website": ""},
    )
    second = create_client_company(
        organization=organization,
        user=admin,
        values={"name": "Acme", "website": ""},
    )

    assert first.slug == "acme"
    assert second.slug == "acme-2"


def test_recruiter_cannot_mutate_client_company_through_service() -> None:
    _, recruiter, organization = workspace()
    company = ClientCompany.objects.create(
        organization=organization, name="Acme", slug="acme"
    )

    with pytest.raises(PermissionDenied):
        update_client_company(
            company=company,
            user=recruiter,
            values={"name": "Changed", "website": ""},
        )
    with pytest.raises(PermissionDenied):
        set_client_company_active(company=company, user=recruiter, is_active=False)


def test_deactivation_preserves_historical_vacancy_and_removes_new_choice(
    client,
) -> None:
    admin, _, organization = workspace()
    company = ClientCompany.objects.create(
        organization=organization, name="Acme", slug="acme"
    )
    vacancy = vacancy_for(organization, admin, company=company)
    client.force_login(admin)

    response = client.post(
        reverse(
            "organizations:client-company-status", args=[organization.slug, company.pk]
        ),
        {"is_active": "false"},
    )
    company.refresh_from_db()
    vacancy.refresh_from_db()

    assert response.status_code == 302
    assert company.is_active is False
    assert vacancy.client_company == company
    assert (
        list(
            VacancyCreateForm(organization=organization)
            .fields["client_company"]
            .queryset
        )
        == []
    )
    detail = client.get(
        reverse("vacancies:vacancy-detail", args=[organization.slug, vacancy.pk])
    )
    assert "Acme" in detail.content.decode()


def test_client_company_status_change_is_post_only(client) -> None:
    admin, _, organization = workspace()
    company = ClientCompany.objects.create(
        organization=organization, name="Acme", slug="acme"
    )
    client.force_login(admin)

    response = client.get(
        reverse(
            "organizations:client-company-status", args=[organization.slug, company.pk]
        )
    )

    assert response.status_code == 405
    company.refresh_from_db()
    assert company.is_active is True


def test_admin_add_client_shortcut_returns_to_vacancy_with_selection(client) -> None:
    admin, _, organization = workspace()
    vacancy_url = reverse("vacancies:vacancy-create", args=[organization.slug])
    create_url = reverse(
        "organizations:client-company-create", args=[organization.slug]
    )
    client.force_login(admin)

    vacancy_page = client.get(vacancy_url)
    assert create_url in vacancy_page.content.decode()

    vacancy = vacancy_for(organization, admin)
    edit_url = reverse("vacancies:vacancy-edit", args=[organization.slug, vacancy.pk])
    assert create_url in client.get(edit_url).content.decode()

    response = client.post(
        create_url,
        {"name": "Shortcut Client", "website": "", "next": vacancy_url},
    )
    company = ClientCompany.objects.get(name="Shortcut Client")
    assert response.status_code == 302
    assert response.url == f"{vacancy_url}?client_company={company.pk}"

    returned = client.get(response.url)
    assert returned.context["form"]["client_company"].value() == company.pk


def test_recruiter_can_select_clients_but_does_not_see_add_shortcut(client) -> None:
    _, recruiter, organization = workspace()
    company = ClientCompany.objects.create(
        organization=organization, name="Acme", slug="acme"
    )
    client.force_login(recruiter)

    response = client.get(reverse("vacancies:vacancy-create", args=[organization.slug]))

    assert company in response.context["form"].fields["client_company"].queryset
    assert (
        "Add a client company in organization settings" not in response.content.decode()
    )


def test_external_add_client_return_url_is_ignored(client) -> None:
    admin, _, organization = workspace()
    client.force_login(admin)
    create_url = reverse(
        "organizations:client-company-create", args=[organization.slug]
    )

    response = client.post(
        create_url,
        {
            "name": "Safe Client",
            "website": "",
            "next": "https://attacker.example.test/steal",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse(
        "organizations:client-company-list", args=[organization.slug]
    )


def test_recruiter_edits_vacancy_title_and_active_client(client) -> None:
    _, recruiter, organization = workspace()
    company = ClientCompany.objects.create(
        organization=organization, name="Acme", slug="acme"
    )
    vacancy = vacancy_for(organization, recruiter)
    source_description = vacancy.requirement_versions.get().source_description
    client.force_login(recruiter)

    response = client.post(
        reverse("vacancies:vacancy-edit", args=[organization.slug, vacancy.pk]),
        {"title": "Updated role", "client_company": company.pk},
    )
    vacancy.refresh_from_db()

    assert response.status_code == 302
    assert vacancy.title == "Updated role"
    assert vacancy.client_company == company
    assert vacancy.description == "Build secure services."
    assert vacancy.requirement_versions.get().source_description == source_description


def test_edit_form_can_retain_only_its_current_inactive_client() -> None:
    _, recruiter, organization = workspace()
    current = ClientCompany.objects.create(
        organization=organization,
        name="Historical Client",
        slug="historical-client",
        is_active=False,
    )
    unrelated = ClientCompany.objects.create(
        organization=organization,
        name="Other Inactive",
        slug="other-inactive",
        is_active=False,
    )
    active = ClientCompany.objects.create(
        organization=organization,
        name="Active Client",
        slug="active-client",
    )
    vacancy = vacancy_for(organization, recruiter, company=current)

    form = VacancyEditForm(organization=organization, vacancy=vacancy)

    assert list(form.fields["client_company"].queryset) == [active, current]
    assert "inactive — current vacancy only" in form.fields[
        "client_company"
    ].label_from_instance(current)
    assert unrelated not in form.fields["client_company"].queryset


def test_services_reject_new_assignment_to_inactive_or_foreign_client() -> None:
    _, recruiter, organization = workspace()
    inactive = ClientCompany.objects.create(
        organization=organization,
        name="Inactive",
        slug="inactive",
        is_active=False,
    )
    other = Organization.objects.create(name="Other", slug="other")
    foreign = ClientCompany.objects.create(
        organization=other, name="Foreign", slug="foreign"
    )
    vacancy = vacancy_for(organization, recruiter)

    with pytest.raises(ValidationError, match="active client"):
        create_vacancy_with_requirements(
            organization=organization,
            user=recruiter,
            vacancy_values={
                "title": "Blocked",
                "description": "Blocked assignment.",
                "client_company": inactive,
            },
        )
    with pytest.raises(ValidationError, match="not in this organization"):
        update_vacancy_details(
            vacancy=vacancy,
            user=recruiter,
            values={"title": vacancy.title, "client_company": foreign},
        )


def test_service_allows_existing_inactive_relationship_to_be_retained() -> None:
    _, recruiter, organization = workspace()
    company = ClientCompany.objects.create(
        organization=organization,
        name="Historical",
        slug="historical",
        is_active=False,
    )
    vacancy = vacancy_for(organization, recruiter, company=company)

    updated = update_vacancy_details(
        vacancy=vacancy,
        user=recruiter,
        values={"title": "Renamed historical role", "client_company": company},
    )

    assert updated.client_company == company
    assert updated.title == "Renamed historical role"
