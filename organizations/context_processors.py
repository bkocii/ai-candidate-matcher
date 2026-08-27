from organizations.models import Organization


def workspace_navigation(request):
    """Expose only a safe active-workspace count to shared navigation."""
    if not getattr(request.user, "is_authenticated", False):
        return {"workspace_count": 0}
    return {"workspace_count": Organization.objects.visible_to(request.user).count()}
