from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from accounts.models import OrganizationMembership, User
from ai_gateway import (
    AIGatewayMetadata,
    AIGatewayTokenUsage,
    AIGatewayUnavailableError,
)
from audit.models import AIUsageEvent
from audit.services import (
    complete_ai_usage_failure,
    complete_ai_usage_success,
    start_ai_usage_event,
)
from audit.usage_reporting import (
    ALL_WORKFLOWS,
    build_ai_usage_report,
)
from organizations.models import Organization

pytestmark = pytest.mark.django_db


def make_workspace(
    username="administrator",
    *,
    role=OrganizationMembership.Role.ADMIN,
):
    user = User.objects.create_user(username=username)
    organization = Organization.objects.create(
        name=f"{username.title()} Organization",
        slug=f"{username}-organization",
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=role,
    )
    return user, organization


def metadata(
    *,
    request_id="request-1",
    model="model-a",
    duration_ms=100,
    retries=0,
    tokens=None,
    cost=None,
):
    return AIGatewayMetadata(
        request_id=request_id,
        model=model,
        duration_ms=duration_ms,
        retries_used=retries,
        token_usage=(
            AIGatewayTokenUsage(
                input_tokens=tokens[0],
                output_tokens=tokens[1],
                total_tokens=tokens[2],
            )
            if tokens is not None
            else None
        ),
        estimated_cost_usd=cost,
    )


def start_event(user, organization, *, workflow, target_id):
    return start_ai_usage_event(
        organization=organization,
        actor=user,
        workflow=workflow,
        target_type=AIUsageEvent.ObjectType.VACANCY_REQUIREMENTS,
        target_id=target_id,
    )


def successful_event(user, organization, *, workflow, target_id, metadata_value):
    event = start_event(
        user,
        organization,
        workflow=workflow,
        target_id=target_id,
    )
    return complete_ai_usage_success(
        event=event,
        metadata=metadata_value,
        result_type=AIUsageEvent.ObjectType.VACANCY_REQUIREMENTS,
        result_id=target_id,
    )


def populate_usage(user, organization):
    successful_event(
        user,
        organization,
        workflow=AIUsageEvent.Workflow.VACANCY_REQUIREMENTS,
        target_id=1,
        metadata_value=metadata(
            duration_ms=100,
            retries=1,
            tokens=(10, 5, 15),
            cost=Decimal("0.001"),
        ),
    )
    successful_event(
        user,
        organization,
        workflow=AIUsageEvent.Workflow.CANDIDATE_PROFILE,
        target_id=2,
        metadata_value=metadata(
            request_id="request-2",
            duration_ms=300,
        ),
    )
    gateway_failure = start_event(
        user,
        organization,
        workflow=AIUsageEvent.Workflow.VACANCY_REQUIREMENTS,
        target_id=3,
    )
    complete_ai_usage_failure(
        event=gateway_failure,
        error=AIGatewayUnavailableError(),
    )
    application_failure = start_event(
        user,
        organization,
        workflow=AIUsageEvent.Workflow.MATCH_ASSESSMENT,
        target_id=4,
    )
    complete_ai_usage_failure(
        event=application_failure,
        error=ValidationError("private validation detail"),
        metadata=metadata(
            request_id="request-4",
            model="model-b",
            duration_ms=200,
            retries=2,
            tokens=(20, 10, 30),
            cost=Decimal("0.002"),
        ),
    )
    pending = start_event(
        user,
        organization,
        workflow=AIUsageEvent.Workflow.OUTREACH_DRAFT,
        target_id=5,
    )
    AIUsageEvent.objects.filter(pk=pending.pk).update(
        started_at=timezone.now() - timedelta(minutes=20)
    )
    return pending


def test_report_aggregates_available_metadata_without_inventing_missing_values():
    user, organization = make_workspace()
    populate_usage(user, organization)

    report = build_ai_usage_report(
        organization=organization,
        user=user,
        period="all",
    )

    assert report.workflow == ALL_WORKFLOWS
    assert report.metrics.attempts == 5
    assert report.metrics.succeeded == 2
    assert report.metrics.failed == 2
    assert report.metrics.pending == 1
    assert report.metrics.success_rate == Decimal("50.0")
    assert report.metrics.input_tokens == 30
    assert report.metrics.output_tokens == 15
    assert report.metrics.total_tokens == 45
    assert report.metrics.input_token_metadata_count == 2
    assert report.metrics.output_token_metadata_count == 2
    assert report.metrics.token_metadata_count == 2
    assert report.metrics.missing_token_metadata_count == 3
    assert report.metrics.cost_usd == Decimal("0.003000000")
    assert report.metrics.cost_metadata_count == 2
    assert report.metrics.average_duration_ms == Decimal("200")
    assert report.metrics.duration_metadata_count == 3
    assert report.metrics.retries_used == 3
    assert report.metrics.retried_attempts == 2
    assert report.metrics.retry_metadata_count == 3
    assert report.metrics.missing_retry_metadata_count == 2
    assert report.stale_pending_count == 1
    assert {row.label for row in report.workflow_rows} == {
        "Vacancy requirements",
        "Candidate profile",
        "Match assessment",
        "Outreach draft",
    }
    assert {row.label for row in report.model_rows} == {"model-a", "model-b"}
    assert {(row.stage, row.label, row.count) for row in report.failure_rows} == {
        ("Gateway", "AI service unavailable", 1),
        ("Application validation", "Application safety validation", 1),
    }


def test_report_period_and_workflow_filters_are_bounded_and_normalized():
    user, organization = make_workspace()
    old = successful_event(
        user,
        organization,
        workflow=AIUsageEvent.Workflow.VACANCY_REQUIREMENTS,
        target_id=1,
        metadata_value=metadata(),
    )
    AIUsageEvent.objects.filter(pk=old.pk).update(
        started_at=timezone.now() - timedelta(days=100)
    )
    successful_event(
        user,
        organization,
        workflow=AIUsageEvent.Workflow.CANDIDATE_PROFILE,
        target_id=2,
        metadata_value=metadata(request_id="request-2"),
    )

    filtered = build_ai_usage_report(
        organization=organization,
        user=user,
        period="30",
        workflow=AIUsageEvent.Workflow.CANDIDATE_PROFILE,
    )
    normalized = build_ai_usage_report(
        organization=organization,
        user=user,
        period="private-invalid-period",
        workflow="private-invalid-workflow",
    )

    assert filtered.metrics.attempts == 1
    assert filtered.workflow == AIUsageEvent.Workflow.CANDIDATE_PROFILE
    assert filtered.period == "30"
    assert normalized.period == "30"
    assert normalized.workflow == ALL_WORKFLOWS
    assert normalized.metrics.attempts == 1


def test_empty_report_and_cross_tenant_service_access():
    user, organization = make_workspace()
    outsider, _ = make_workspace("outsider")

    report = build_ai_usage_report(
        organization=organization,
        user=user,
        period="all",
    )

    assert report.metrics.attempts == 0
    assert report.metrics.success_rate is None
    assert report.metrics.average_duration_ms is None
    assert report.daily_rows == ()
    with pytest.raises(PermissionDenied):
        build_ai_usage_report(
            organization=organization,
            user=outsider,
            period="all",
        )


def test_usage_report_route_is_admin_only_tenant_scoped_and_content_free(client):
    user, organization = make_workspace()
    outsider, other = make_workspace("outsider")
    recruiter = User.objects.create_user(username="recruiter")
    OrganizationMembership.objects.create(
        user=recruiter,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )
    populate_usage(user, organization)
    route = reverse("audit:ai-usage-report", args=[organization.slug])
    client.force_login(user)

    response = client.get(route, {"period": "all"})
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context["report"].metrics.attempts == 5
    assert "AI usage" in content
    assert "45" in content
    assert "$0.003000" in content
    assert "AI service unavailable" in content
    assert "request-1" not in content
    assert "private validation detail" not in content
    assert "candidate_name" not in content

    client.force_login(recruiter)
    forbidden = client.get(route)
    assert forbidden.status_code == 403
    assert "45" not in forbidden.content.decode()

    client.force_login(outsider)
    hidden = client.get(route)
    assert hidden.status_code == 404
    assert organization.name not in hidden.content.decode()
    assert other != organization


def test_navigation_shows_organization_reports_only_to_admins(client):
    admin, organization = make_workspace()
    recruiter = User.objects.create_user(username="recruiter")
    OrganizationMembership.objects.create(
        user=recruiter,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )
    dashboard = reverse(
        "organizations:organization-dashboard",
        args=[organization.slug],
    )

    client.force_login(admin)
    response = client.get(dashboard)

    usage_route = reverse("audit:ai-usage-report", args=[organization.slug])
    privacy_route = reverse("audit:privacy-dashboard", args=[organization.slug])
    assert usage_route in response.content.decode()
    assert privacy_route in response.content.decode()

    client.force_login(recruiter)
    response = client.get(dashboard)

    assert usage_route not in response.content.decode()
    assert privacy_route not in response.content.decode()


def test_usage_report_service_rejects_recruiters():
    recruiter, organization = make_workspace(
        "recruiter",
        role=OrganizationMembership.Role.RECRUITER,
    )

    with pytest.raises(PermissionDenied):
        build_ai_usage_report(
            organization=organization,
            user=recruiter,
            period="all",
        )
