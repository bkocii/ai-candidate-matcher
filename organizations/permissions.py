from django.core.exceptions import PermissionDenied

from accounts.models import OrganizationMembership
from organizations.models import Organization


def has_organization_access(user: object, organization: Organization) -> bool:
    """Check active user, organization, and membership state."""
    if not (
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and organization.is_active
    ):
        return False

    return OrganizationMembership.objects.filter(
        user=user,
        organization=organization,
        is_active=True,
    ).exists()


def can_administer_organization(user: object, organization: Organization) -> bool:
    """Allow organization administration only through an active admin membership."""
    if not (
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and organization.is_active
    ):
        return False

    return OrganizationMembership.objects.filter(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.ADMIN,
        is_active=True,
    ).exists()


def require_organization_access(user: object, organization: Organization) -> None:
    if not has_organization_access(user, organization):
        raise PermissionDenied("You do not have access to this organization.")


def require_organization_admin(user: object, organization: Organization) -> None:
    if not can_administer_organization(user, organization):
        raise PermissionDenied("Organization administrator access is required.")


def has_organization_object_access(user: object, instance: object) -> bool:
    """Check an object exposing an ``organization`` ownership relation."""
    organization = getattr(instance, "organization", None)
    if not isinstance(organization, Organization):
        return False
    return has_organization_access(user, organization)


def require_organization_object_access(user: object, instance: object) -> None:
    if not has_organization_object_access(user, instance):
        raise PermissionDenied("You do not have access to this organization object.")
