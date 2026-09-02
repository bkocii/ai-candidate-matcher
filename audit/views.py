from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from audit.models import AIUsageEvent
from audit.reporting import (
    AUDIT_CATEGORY_OPTIONS,
    AUDIT_PERIOD_OPTIONS,
    AUDIT_STATUS_OPTIONS,
    build_audit_history,
    build_retention_and_minimization_report,
)
from audit.usage_reporting import (
    ALL_WORKFLOWS,
    REPORTING_PERIODS,
    build_ai_usage_report,
)
from organizations.models import Organization
from organizations.permissions import require_organization_admin


@login_required
def privacy_dashboard(request, organization_slug: str):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    require_organization_admin(request.user, organization)
    history = build_audit_history(
        organization=organization,
        user=request.user,
        limit=100,
        category=request.GET.get("activity"),
        status=request.GET.get("result"),
        period=request.GET.get("period"),
    )
    return render(
        request,
        "audit/privacy_dashboard.html",
        {
            "organization": organization,
            "can_administer": True,
            "retention": build_retention_and_minimization_report(
                organization=organization,
                user=request.user,
                as_of=timezone.localdate(),
            ),
            "history": history,
            "audit_category_options": AUDIT_CATEGORY_OPTIONS,
            "audit_status_options": AUDIT_STATUS_OPTIONS,
            "audit_period_options": AUDIT_PERIOD_OPTIONS,
            "workflow_audit_page": Paginator(history.workflow_entries, 25).get_page(
                request.GET.get("page")
            ),
        },
    )


@login_required
def ai_usage_report(request, organization_slug: str):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    require_organization_admin(request.user, organization)
    report = build_ai_usage_report(
        organization=organization,
        user=request.user,
        period=request.GET.get("period"),
        workflow=request.GET.get("workflow"),
    )
    return render(
        request,
        "audit/ai_usage_report.html",
        {
            "organization": organization,
            "report": report,
            "period_options": REPORTING_PERIODS,
            "workflow_options": ((ALL_WORKFLOWS, "All workflows"),)
            + tuple(AIUsageEvent.Workflow.choices),
        },
    )
