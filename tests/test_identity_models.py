import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from accounts.models import OrganizationMembership, User
from organizations.models import Organization

pytestmark = pytest.mark.django_db


def test_configured_user_model_is_application_user() -> None:
    assert get_user_model() is User


def test_organization_has_stable_display_name() -> None:
    organization = Organization.objects.create(
        name="Northstar Recruitment",
        slug="northstar-recruitment",
    )

    assert str(organization) == "Northstar Recruitment"
    assert organization.is_active is True


@pytest.mark.parametrize(
    ("role", "is_administrator"),
    [
        (OrganizationMembership.Role.ADMIN, True),
        (OrganizationMembership.Role.RECRUITER, False),
    ],
)
def test_membership_roles(role: str, is_administrator: bool) -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")
    user = User.objects.create_user(username=f"user-{role}")
    membership = OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=role,
    )

    assert membership.is_administrator is is_administrator
    assert role in OrganizationMembership.Role.values


def test_inactive_admin_membership_has_no_administrator_capability() -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")
    user = User.objects.create_user(username="inactive-admin")
    membership = OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.ADMIN,
        is_active=False,
    )

    assert membership.is_administrator is False


def test_user_can_have_different_roles_in_different_organizations() -> None:
    user = User.objects.create_user(username="multi-org-user")
    first = Organization.objects.create(name="First Agency", slug="first-agency")
    second = Organization.objects.create(name="Second Agency", slug="second-agency")

    OrganizationMembership.objects.create(
        user=user,
        organization=first,
        role=OrganizationMembership.Role.ADMIN,
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=second,
        role=OrganizationMembership.Role.RECRUITER,
    )

    assert user.organization_memberships.count() == 2


def test_membership_is_unique_for_each_user_and_organization() -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")
    user = User.objects.create_user(username="member")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrganizationMembership.Role.ADMIN,
        )


def test_database_rejects_unknown_membership_role() -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")
    user = User.objects.create_user(username="invalid-role")

    with pytest.raises(IntegrityError), transaction.atomic():
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role="owner",
        )
