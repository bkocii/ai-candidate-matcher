from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from accounts.models import OrganizationMembership, User
from audit.models import TenantManagementEvent
from organizations.models import ClientCompany, Organization
from organizations.permissions import (
    require_organization_admin,
    require_platform_owner,
)


def _record_tenant_event(
    *,
    organization: Organization,
    actor: User,
    action: str,
    membership: OrganizationMembership | None = None,
) -> TenantManagementEvent:
    return TenantManagementEvent.objects.create(
        organization_id_snapshot=organization.pk,
        actor=actor,
        action=action,
        subject_user_id_snapshot=membership.user_id if membership else None,
        membership_role=membership.role if membership else "",
    )


def _available_organization_slug(name: str) -> str:
    base = slugify(name)[:180] or "organization"
    slug = base
    suffix = 2
    while Organization.objects.filter(slug=slug).exists():
        marker = f"-{suffix}"
        slug = f"{base[: 200 - len(marker)]}{marker}"
        suffix += 1
    return slug


def _resolve_managed_user(values: dict) -> tuple[User, bool]:
    username = values["username"].strip()
    existing = User.objects.filter(username__iexact=username).first()
    if existing is not None:
        if not existing.is_active:
            raise ValidationError("The existing user account is inactive.")
        if values.get("temporary_password"):
            raise ValidationError(
                "Do not supply a password when linking an existing account."
            )
        return existing, False

    password = values.get("temporary_password", "")
    email = values.get("email", "").strip()
    if not email:
        raise ValidationError("Email is required for a new account.")
    user = User(
        username=username,
        email=email,
        first_name=values.get("first_name", "").strip(),
        last_name=values.get("last_name", "").strip(),
    )
    validate_password(password, user=user)
    user.set_password(password)
    user.must_change_password = True
    user.full_clean()
    user.save()
    return user, True


@transaction.atomic
def provision_organization(
    *,
    platform_owner: User,
    organization_name: str,
    administrator_values: dict,
) -> tuple[Organization, OrganizationMembership, bool]:
    """Create one tenant and its first active administrator atomically."""
    require_platform_owner(platform_owner)
    organization_name = organization_name.strip()
    organization = Organization(
        name=organization_name,
        slug=_available_organization_slug(organization_name),
    )
    organization.full_clean()
    organization.save()
    administrator, created_user = _resolve_managed_user(administrator_values)
    if OrganizationMembership.objects.filter(
        user=administrator,
        organization=organization,
    ).exists():
        raise ValidationError("This administrator already belongs to the organization.")
    membership = OrganizationMembership(
        user=administrator,
        organization=organization,
        role=OrganizationMembership.Role.ADMIN,
    )
    membership.full_clean()
    membership.save()
    _record_tenant_event(
        organization=organization,
        actor=platform_owner,
        action=TenantManagementEvent.Action.ORGANIZATION_CREATED,
    )
    _record_tenant_event(
        organization=organization,
        actor=platform_owner,
        action=TenantManagementEvent.Action.MEMBERSHIP_CREATED,
        membership=membership,
    )
    return organization, membership, created_user


@transaction.atomic
def add_organization_member(
    *,
    organization: Organization,
    actor: User,
    role: str,
    values: dict,
) -> tuple[OrganizationMembership, bool]:
    """Create or link an account through the role's authorized manager."""
    if role == OrganizationMembership.Role.ADMIN:
        require_platform_owner(actor)
    elif role == OrganizationMembership.Role.RECRUITER:
        require_organization_admin(actor, organization)
    else:
        raise ValidationError("Select a supported organization role.")

    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    if not organization.is_active:
        raise ValidationError(
            "Memberships cannot be added to a suspended organization."
        )
    member_user, created_user = _resolve_managed_user(values)
    existing = OrganizationMembership.objects.filter(
        user=member_user,
        organization=organization,
    ).first()
    if existing is not None:
        state = "active" if existing.is_active else "inactive"
        raise ValidationError(
            f"This user already has an {state} {existing.get_role_display().lower()} "
            "membership in the organization."
        )
    membership = OrganizationMembership(
        user=member_user,
        organization=organization,
        role=role,
    )
    membership.full_clean()
    membership.save()
    _record_tenant_event(
        organization=organization,
        actor=actor,
        action=TenantManagementEvent.Action.MEMBERSHIP_CREATED,
        membership=membership,
    )
    return membership, created_user


@transaction.atomic
def set_organization_membership_active(
    *,
    membership: OrganizationMembership,
    actor: User,
    is_active: bool,
) -> OrganizationMembership:
    """Change tenant access without changing or disabling a shared user account."""
    if membership.role == OrganizationMembership.Role.ADMIN:
        require_platform_owner(actor)
    else:
        require_organization_admin(actor, membership.organization)

    membership = (
        OrganizationMembership.objects.select_for_update()
        .select_related("organization", "user")
        .get(pk=membership.pk)
    )
    if membership.is_active == is_active:
        state = "active" if is_active else "inactive"
        raise ValidationError(f"This membership is already {state}.")
    if (
        not is_active
        and membership.role == OrganizationMembership.Role.ADMIN
        and not OrganizationMembership.objects.filter(
            organization=membership.organization,
            role=OrganizationMembership.Role.ADMIN,
            is_active=True,
        )
        .exclude(pk=membership.pk)
        .exists()
    ):
        raise ValidationError(
            "Add another active administrator before deactivating this one."
        )
    membership.is_active = is_active
    membership.save(update_fields=("is_active", "updated_at"))
    _record_tenant_event(
        organization=membership.organization,
        actor=actor,
        action=(
            TenantManagementEvent.Action.MEMBERSHIP_ACTIVATED
            if is_active
            else TenantManagementEvent.Action.MEMBERSHIP_DEACTIVATED
        ),
        membership=membership,
    )
    return membership


def _available_company_slug(*, organization: Organization, name: str) -> str:
    base = slugify(name)[:180] or "client-company"
    slug = base
    suffix = 2
    while (
        ClientCompany.objects.for_organization(organization).filter(slug=slug).exists()
    ):
        marker = f"-{suffix}"
        slug = f"{base[: 200 - len(marker)]}{marker}"
        suffix += 1
    return slug


@transaction.atomic
def create_client_company(
    *,
    organization: Organization,
    user: User,
    values: dict,
) -> ClientCompany:
    """Create one organization-owned client through an administrator action."""
    require_organization_admin(user, organization)
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    company = ClientCompany(
        organization=organization,
        name=values["name"],
        website=values.get("website", ""),
        slug=_available_company_slug(organization=organization, name=values["name"]),
    )
    company.full_clean()
    company.save()
    return company


@transaction.atomic
def update_client_company(
    *,
    company: ClientCompany,
    user: User,
    values: dict,
) -> ClientCompany:
    """Update reference metadata without changing the stable organization slug."""
    require_organization_admin(user, company.organization)
    company = (
        ClientCompany.objects.select_for_update()
        .select_related("organization")
        .get(pk=company.pk)
    )
    company.name = values["name"]
    company.website = values.get("website", "")
    company.full_clean()
    company.save(update_fields=("name", "website", "updated_at"))
    return company


@transaction.atomic
def set_client_company_active(
    *,
    company: ClientCompany,
    user: User,
    is_active: bool,
) -> ClientCompany:
    """Change availability while preserving every historical vacancy relation."""
    require_organization_admin(user, company.organization)
    company = (
        ClientCompany.objects.select_for_update()
        .select_related("organization")
        .get(pk=company.pk)
    )
    if company.is_active == is_active:
        state = "active" if is_active else "inactive"
        raise ValidationError(f"This client company is already {state}.")
    company.is_active = is_active
    company.save(update_fields=("is_active", "updated_at"))
    return company
