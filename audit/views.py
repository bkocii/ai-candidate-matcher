from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from audit.reporting import (
    build_audit_history,
    build_retention_and_minimization_report,
)
from organizations.models import Organization
from organizations.permissions import can_administer_organization


@login_required
def privacy_dashboard(request, organization_slug: str):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    return render(
        request,
        "audit/privacy_dashboard.html",
        {
            "organization": organization,
            "can_administer": can_administer_organization(request.user, organization),
            "retention": build_retention_and_minimization_report(
                organization=organization,
                user=request.user,
                as_of=timezone.localdate(),
            ),
            "history": build_audit_history(
                organization=organization,
                user=request.user,
            ),
        },
    )
