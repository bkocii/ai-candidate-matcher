from django.core.exceptions import PermissionDenied

from accounts.models import OrganizationMembership
from organizations.models import Organization


def is_platform_owner(user: object) -> bool:
    """Return the explicit platform capability without granting tenant access."""
    return bool(
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and getattr(user, "is_platform_owner", False)
    )


def require_platform_owner(user: object) -> None:
    if not is_platform_owner(user):
        raise PermissionDenied("Platform owner access is required.")


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


def can_manage_organization_lifecycle(user: object, organization: Organization) -> bool:
    """Allow lifecycle actions without treating platform ownership as membership."""
    return is_platform_owner(user) or can_administer_organization(user, organization)


def require_organization_lifecycle_manager(
    user: object, organization: Organization
) -> None:
    if not can_manage_organization_lifecycle(user, organization):
        raise PermissionDenied(
            "Platform owner or organization administrator access is required."
        )


def can_recover_organization(user: object, organization: Organization) -> bool:
    """Allow an active admin member to recover a deletion-suspended tenant."""
    if not (
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and not organization.is_active
        and organization.deletion_requested_at is not None
    ):
        return False
    if is_platform_owner(user):
        return True
    return OrganizationMembership.objects.filter(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.ADMIN,
        is_active=True,
    ).exists()


def has_organization_object_access(user: object, instance: object) -> bool:
    """Check an object exposing an ``organization`` ownership relation."""
    organization = getattr(instance, "organization", None)
    if not isinstance(organization, Organization):
        return False
    return has_organization_access(user, organization)


def require_organization_object_access(user: object, instance: object) -> None:
    if not has_organization_object_access(user, instance):
        raise PermissionDenied("You do not have access to this organization object.")
