import pytest
from django.urls import reverse

from accounts.models import OrganizationMembership, User
from candidates.models import Candidate
from organizations.models import ClientCompany, Organization

pytestmark = pytest.mark.django_db


def add_membership(
    user: User,
    organization: Organization,
    *,
    role: str = OrganizationMembership.Role.RECRUITER,
    is_active: bool = True,
) -> OrganizationMembership:
    return OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=role,
        is_active=is_active,
    )


def test_dashboard_requires_authentication(client) -> None:
    response = client.get(reverse("organizations:dashboard"))

    assert response.status_code == 302
    assert response.url == f"{reverse('accounts:login')}?next=/"


def test_single_visible_organization_redirects_to_its_dashboard(client) -> None:
    user = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_membership(user, organization)
    client.force_login(user)

    response = client.get(reverse("organizations:dashboard"))

    assert response.status_code == 302
    assert response.url == reverse(
        "organizations:organization-dashboard",
        kwargs={"organization_slug": organization.slug},
    )


def test_multiple_visible_organizations_show_a_selection_page(client) -> None:
    user = User.objects.create_user(username="multi-organization-recruiter")
    first = Organization.objects.create(name="First Agency", slug="first-agency")
    second = Organization.objects.create(name="Second Agency", slug="second-agency")
    hidden = Organization.objects.create(name="Hidden Agency", slug="hidden-agency")
    add_membership(user, first)
    add_membership(user, second)
    add_membership(user, hidden, is_active=False)
    client.force_login(user)

    response = client.get(reverse("organizations:dashboard"))

    assert response.status_code == 200
    assert list(response.context["organizations"]) == [first, second]
    assert "First Agency" in response.content.decode()
    assert "Second Agency" in response.content.decode()
    assert "Hidden Agency" not in response.content.decode()


def test_user_without_active_membership_gets_safe_access_page(client) -> None:
    user = User.objects.create_user(username="unassigned")
    Organization.objects.create(name="Private Agency", slug="private-agency")
    client.force_login(user)

    response = client.get(reverse("organizations:dashboard"))

    assert response.status_code == 403
    assert "No active organization membership" in response.content.decode()
    assert "Private Agency" not in response.content.decode()


def test_dashboard_is_scoped_to_the_requested_organization(client) -> None:
    user = User.objects.create_user(username="organization-admin")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    other = Organization.objects.create(name="Other Agency", slug="other-agency")
    add_membership(user, organization, role=OrganizationMembership.Role.ADMIN)
    ClientCompany.objects.create(
        organization=organization,
        name="Active Client",
        slug="active-client",
    )
    ClientCompany.objects.create(
        organization=organization,
        name="Inactive Client",
        slug="inactive-client",
        is_active=False,
    )
    ClientCompany.objects.create(
        organization=other,
        name="Other Client",
        slug="other-client",
    )
    Candidate.objects.create(
        organization=organization,
        full_name="Active Candidate",
    )
    Candidate.objects.create(
        organization=organization,
        full_name="Inactive Candidate",
        status=Candidate.Status.INACTIVE,
    )
    Candidate.objects.create(
        organization=other,
        full_name="Other Candidate",
    )
    client.force_login(user)

    response = client.get(
        reverse(
            "organizations:organization-dashboard",
            kwargs={"organization_slug": organization.slug},
        )
    )

    assert response.status_code == 200
    assert response.context["organization"] == organization
    assert response.context["active_client_count"] == 1
    assert response.context["active_candidate_count"] == 1
    assert response.context["membership"].role == OrganizationMembership.Role.ADMIN
    assert "Northstar" in response.content.decode()
    assert "Administrator" in response.content.decode()
    assert (
        reverse(
            "candidates:candidate-list",
            kwargs={"organization_slug": organization.slug},
        )
        in response.content.decode()
    )


def test_dashboard_hides_another_organizations_existence(client) -> None:
    user = User.objects.create_user(username="first-recruiter")
    first = Organization.objects.create(name="First", slug="first")
    second = Organization.objects.create(name="Second", slug="second")
    add_membership(user, first)
    client.force_login(user)

    response = client.get(
        reverse(
            "organizations:organization-dashboard",
            kwargs={"organization_slug": second.slug},
        )
    )

    assert response.status_code == 404
    assert "Second" not in response.content.decode()


def test_inactive_organization_is_not_available_from_dashboard(client) -> None:
    user = User.objects.create_user(username="inactive-organization-member")
    organization = Organization.objects.create(
        name="Inactive Agency",
        slug="inactive-agency",
        is_active=False,
    )
    add_membership(user, organization)
    client.force_login(user)

    response = client.get(
        reverse(
            "organizations:organization-dashboard",
            kwargs={"organization_slug": organization.slug},
        )
    )

    assert response.status_code == 404


def test_navigation_exposes_django_admin_only_to_staff(client) -> None:
    recruiter = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_membership(recruiter, organization)
    dashboard_url = reverse(
        "organizations:organization-dashboard",
        kwargs={"organization_slug": organization.slug},
    )

    client.force_login(recruiter)
    response = client.get(dashboard_url)
    assert "Django admin" not in response.content.decode()

    recruiter.is_staff = True
    recruiter.save(update_fields=["is_staff"])
    response = client.get(dashboard_url)
    assert "Django admin" in response.content.decode()


def test_logout_requires_post_and_returns_to_login(client) -> None:
    user = User.objects.create_user(username="signed-in-user")
    client.force_login(user)
    logout_url = reverse("accounts:logout")

    assert client.get(logout_url).status_code == 405

    response = client.post(logout_url)

    assert response.status_code == 302
    assert response.url == reverse("accounts:login")
