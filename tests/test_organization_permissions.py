import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction

from accounts.models import OrganizationMembership, User
from organizations.models import ClientCompany, Organization
from organizations.permissions import (
    can_administer_organization,
    has_organization_access,
    has_organization_object_access,
    require_organization_access,
    require_organization_admin,
    require_organization_object_access,
)

pytestmark = pytest.mark.django_db


def add_member(
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


def test_client_company_belongs_to_an_organization() -> None:
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    company = ClientCompany.objects.create(
        organization=organization,
        name="Acme Industries",
        slug="acme-industries",
    )

    assert str(company) == "Acme Industries"
    assert company.is_active is True
    assert organization.client_companies.get() == company


def test_client_company_slug_is_unique_only_within_organization() -> None:
    first = Organization.objects.create(name="First", slug="first")
    second = Organization.objects.create(name="Second", slug="second")
    ClientCompany.objects.create(
        organization=first,
        name="Acme",
        slug="acme",
    )
    ClientCompany.objects.create(
        organization=second,
        name="Acme",
        slug="acme",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ClientCompany.objects.create(
            organization=first,
            name="Another Acme",
            slug="acme",
        )


def test_organization_querysets_prevent_cross_organization_visibility() -> None:
    user = User.objects.create_user(username="recruiter")
    first = Organization.objects.create(name="First", slug="first")
    second = Organization.objects.create(name="Second", slug="second")
    add_member(user, first)
    visible_company = ClientCompany.objects.create(
        organization=first,
        name="Visible Client",
        slug="visible-client",
    )
    ClientCompany.objects.create(
        organization=second,
        name="Hidden Client",
        slug="hidden-client",
    )

    assert list(Organization.objects.visible_to(user)) == [first]
    assert list(ClientCompany.objects.visible_to(user)) == [visible_company]
    assert list(ClientCompany.objects.for_organization(first)) == [visible_company]


@pytest.mark.parametrize("inactive_part", ["user", "organization", "membership"])
def test_inactive_identity_state_removes_organization_access(
    inactive_part: str,
) -> None:
    user = User.objects.create_user(
        username=f"inactive-{inactive_part}",
        is_active=inactive_part != "user",
    )
    organization = Organization.objects.create(
        name=f"Organization {inactive_part}",
        slug=f"organization-{inactive_part}",
        is_active=inactive_part != "organization",
    )
    add_member(user, organization, is_active=inactive_part != "membership")

    assert has_organization_access(user, organization) is False
    assert not Organization.objects.visible_to(user).exists()


def test_anonymous_user_has_no_organization_visibility() -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")
    ClientCompany.objects.create(
        organization=organization,
        name="Hidden Client",
        slug="hidden-client",
    )

    assert not Organization.objects.visible_to(AnonymousUser()).exists()
    assert not ClientCompany.objects.visible_to(AnonymousUser()).exists()


def test_django_superuser_has_no_implicit_organization_scope_bypass() -> None:
    superuser = User.objects.create_superuser(
        username="django-superuser",
        password="not-used-in-this-test",
    )
    organization = Organization.objects.create(name="Acme", slug="acme")

    assert has_organization_access(superuser, organization) is False
    assert not Organization.objects.visible_to(superuser).exists()


def test_admin_capability_is_scoped_by_membership_role() -> None:
    admin = User.objects.create_user(username="organization-admin")
    recruiter = User.objects.create_user(username="organization-recruiter")
    organization = Organization.objects.create(name="Acme", slug="acme")
    add_member(admin, organization, role=OrganizationMembership.Role.ADMIN)
    add_member(recruiter, organization)

    assert can_administer_organization(admin, organization) is True
    assert can_administer_organization(recruiter, organization) is False
    assert has_organization_access(recruiter, organization) is True


def test_object_access_uses_the_objects_organization() -> None:
    user = User.objects.create_user(username="member")
    first = Organization.objects.create(name="First", slug="first")
    second = Organization.objects.create(name="Second", slug="second")
    add_member(user, first)
    visible_company = ClientCompany.objects.create(
        organization=first,
        name="Visible",
        slug="visible",
    )
    hidden_company = ClientCompany.objects.create(
        organization=second,
        name="Hidden",
        slug="hidden",
    )

    assert has_organization_object_access(user, visible_company) is True
    assert has_organization_object_access(user, hidden_company) is False
    assert has_organization_object_access(user, object()) is False


def test_require_helpers_raise_permission_denied() -> None:
    recruiter = User.objects.create_user(username="recruiter")
    outsider = User.objects.create_user(username="outsider")
    organization = Organization.objects.create(name="Acme", slug="acme")
    add_member(recruiter, organization)
    company = ClientCompany.objects.create(
        organization=organization,
        name="Client",
        slug="client",
    )

    require_organization_access(recruiter, organization)
    require_organization_object_access(recruiter, company)

    with pytest.raises(PermissionDenied):
        require_organization_access(outsider, organization)
    with pytest.raises(PermissionDenied):
        require_organization_admin(recruiter, organization)
    with pytest.raises(PermissionDenied):
        require_organization_object_access(outsider, company)
