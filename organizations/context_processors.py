from organizations.models import Organization
from organizations.permissions import can_administer_organization


def workspace_navigation(request):
    """Expose only a safe active-workspace count to shared navigation."""
    if not getattr(request.user, "is_authenticated", False):
        return {"workspace_count": 0}
    context = {"workspace_count": Organization.objects.visible_to(request.user).count()}
    organization = getattr(request, "organization", None)
    if organization is None:
        resolver_match = getattr(request, "resolver_match", None)
        slug = (
            resolver_match.kwargs.get("organization_slug") if resolver_match else None
        )
        if slug:
            organization = (
                Organization.objects.visible_to(request.user).filter(slug=slug).first()
            )
    context["can_view_organization_reports"] = bool(
        organization and can_administer_organization(request.user, organization)
    )
    return context
