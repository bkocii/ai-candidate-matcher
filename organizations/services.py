from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from accounts.models import User
from organizations.models import ClientCompany, Organization
from organizations.permissions import require_organization_admin


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
