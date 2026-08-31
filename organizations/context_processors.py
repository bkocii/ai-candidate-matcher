from accounts.models import OrganizationMembership
from organizations.models import Organization


def workspace_navigation(request):
    """Expose safe workspace and current-role state to shared navigation."""
    if not getattr(request.user, "is_authenticated", False):
        return {
            "workspace_count": 0,
            "can_view_organization_reports": False,
        }

    resolver_match = getattr(request, "resolver_match", None)
    organization_slug = (
        resolver_match.kwargs.get("organization_slug") if resolver_match else None
    )
    can_view_organization_reports = bool(
        organization_slug
        and OrganizationMembership.objects.filter(
            user=request.user,
            organization__slug=organization_slug,
            organization__is_active=True,
            role=OrganizationMembership.Role.ADMIN,
            is_active=True,
        ).exists()
    )
    return {
        "workspace_count": Organization.objects.visible_to(request.user).count(),
        "can_view_organization_reports": can_view_organization_reports,
    }
