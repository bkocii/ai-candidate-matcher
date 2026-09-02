from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import OrganizationMembership, User
from audit.models import AIUsageEvent, AuditEvent
from audit.reporting import build_audit_history, build_retention_and_minimization_report
from audit.services import record_audit_event
from candidates.models import Candidate, CandidateSource
from candidates.services import (
    cancel_candidate_deletion,
    delete_candidate,
    request_candidate_deletion,
)
from organizations.models import Organization

pytestmark = pytest.mark.django_db


def add_member(
    user: User,
    organization: Organization,
    *,
    role: str = OrganizationMembership.Role.RECRUITER,
) -> None:
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=role,
    )


def test_audit_events_are_minimized_immutable_and_tenant_scoped() -> None:
    user = User.objects.create_user(username="recruiter")
    outsider = User.objects.create_user(username="outsider")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    other = Organization.objects.create(name="Other", slug="other")
    add_member(user, organization)
    add_member(outsider, other)

    event = record_audit_event(
        organization=organization,
        actor=user,
        action=AuditEvent.Action.CANDIDATE_DELETION_REQUESTED,
        object_type=AuditEvent.ObjectType.CANDIDATE,
        object_id=42,
    )

    assert set(field.name for field in AuditEvent._meta.fields) == {
        "id",
        "organization",
        "actor",
        "action",
        "object_type",
        "object_id",
        "schema_version",
        "occurred_at",
    }
    assert list(AuditEvent.objects.visible_to(user)) == [event]
    assert not AuditEvent.objects.visible_to(outsider).exists()
    event.object_id = 99
    with pytest.raises(ValidationError, match="immutable"):
        event.save()
    with pytest.raises(ValidationError, match="immutable"):
        AuditEvent.objects.filter(pk=event.pk).update(object_id=99)
    with pytest.raises(ValidationError, match="immutable"):
        AuditEvent.objects.filter(pk=event.pk).delete()


def test_deletion_request_can_only_be_cancelled_by_an_admin() -> None:
    recruiter = User.objects.create_user(username="recruiter")
    admin = User.objects.create_user(username="admin")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(recruiter, organization)
    add_member(admin, organization, role=OrganizationMembership.Role.ADMIN)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Candidate",
        status=Candidate.Status.INACTIVE,
    )

    request_candidate_deletion(candidate=candidate, user=recruiter)
    candidate.refresh_from_db()
    assert candidate.status == Candidate.Status.DELETION_REQUESTED
    assert candidate.status_before_deletion_request == Candidate.Status.INACTIVE
    with pytest.raises(PermissionDenied):
        cancel_candidate_deletion(candidate=candidate, user=recruiter)

    cancel_candidate_deletion(candidate=candidate, user=admin)
    candidate.refresh_from_db()
    assert candidate.status == Candidate.Status.INACTIVE
    assert candidate.status_before_deletion_request == ""
    assert candidate.deletion_requested_at is None
    assert candidate.deletion_requested_by is None
    assert list(
        AuditEvent.objects.filter(object_id=candidate.pk).values_list(
            "action", flat=True
        )
    ) == [
        AuditEvent.Action.CANDIDATE_DELETION_CANCELLED,
        AuditEvent.Action.CANDIDATE_DELETION_REQUESTED,
    ]


def test_candidate_purge_refuses_to_skip_staged_review() -> None:
    user = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Candidate",
    )

    with pytest.raises(ValidationError, match="Request candidate deletion"):
        delete_candidate(candidate=candidate, user=user)

    candidate.refresh_from_db()
    assert candidate.status == Candidate.Status.ACTIVE
    assert not AuditEvent.objects.exists()


def test_retention_command_is_dry_run_by_default_and_apply_is_idempotent() -> None:
    user = User.objects.create_user(username="owner")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    due = Candidate.objects.create(
        organization=organization,
        full_name="Private Candidate Name",
        email="private@example.test",
        retention_until=date(2026, 8, 15),
    )
    Candidate.objects.create(
        organization=organization,
        full_name="Future Candidate",
        retention_until=date(2026, 8, 16),
    )

    dry_run = StringIO()
    call_command(
        "process_retention",
        as_of="2026-08-15",
        stdout=dry_run,
    )
    due.refresh_from_db()
    assert due.status == Candidate.Status.ACTIVE
    assert "northstar: 1 candidate(s) due" in dry_run.getvalue()
    assert "Private Candidate Name" not in dry_run.getvalue()
    assert "private@example.test" not in dry_run.getvalue()

    applied = StringIO()
    call_command(
        "process_retention",
        as_of="2026-08-15",
        apply=True,
        stdout=applied,
    )
    due.refresh_from_db()
    assert due.status == Candidate.Status.DELETION_REQUESTED
    assert due.deletion_requested_by is None
    assert AuditEvent.objects.get().action == (
        AuditEvent.Action.CANDIDATE_RETENTION_FLAGGED
    )

    repeated = StringIO()
    call_command(
        "process_retention",
        as_of="2026-08-15",
        apply=True,
        stdout=repeated,
    )
    assert "northstar: 0 candidate(s) due" in repeated.getvalue()
    assert AuditEvent.objects.count() == 1


def test_privacy_dashboard_is_tenant_scoped_and_omits_source_content(client) -> None:
    recruiter = User.objects.create_user(username="recruiter")
    admin = User.objects.create_user(username="admin")
    outsider = User.objects.create_user(username="outsider")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    hidden = Organization.objects.create(name="Hidden", slug="hidden")
    add_member(recruiter, organization)
    add_member(admin, organization, role=OrganizationMembership.Role.ADMIN)
    add_member(outsider, hidden)
    pending = Candidate.objects.create(
        organization=organization,
        full_name="Pending Candidate",
        retention_until=date(2026, 8, 15),
    )
    request_candidate_deletion(candidate=pending, user=recruiter)
    due = Candidate.objects.create(
        organization=organization,
        full_name="Due Candidate",
        retention_until=date(2026, 8, 15),
    )
    missing = Candidate.objects.create(
        organization=organization,
        full_name="Missing Date Candidate",
    )
    CandidateSource.objects.create(
        candidate=due,
        source_type=CandidateSource.SourceType.MANUAL_ENTRY,
        source_name="SECRET SOURCE CONTENT",
        source_reference="SECRET-REFERENCE",
        permission_notes="SECRET NOTES",
        retention_until=date(2026, 8, 15),
    )
    bad_tombstone = Candidate.objects.create(
        organization=organization,
        full_name="Identity left behind",
        email="retained@example.test",
        status=Candidate.Status.DELETED,
        deletion_requested_at=timezone.now(),
        deleted_at=timezone.now(),
    )

    report = build_retention_and_minimization_report(
        organization=organization,
        user=admin,
        as_of=date(2026, 8, 15),
    )
    assert report.pending_deletions == (pending,)
    assert report.overdue_candidates == (due,)
    assert report.overdue_sources[0].candidate == due
    assert report.candidates_missing_retention == (missing,)
    assert report.candidates_without_retention == 1
    assert report.needs_attention_count == 5
    assert report.minimization_issues[0].object_id == bad_tombstone.pk

    route = reverse("audit:privacy-dashboard", args=[organization.slug])
    client.force_login(recruiter)
    assert client.get(route).status_code == 403

    client.force_login(admin)
    response = client.get(route)
    content = response.content.decode()
    assert response.status_code == 200
    assert "Pending Candidate" in content
    assert "Due Candidate" in content
    assert "Needs attention (5)" in content
    assert "Missing Date Candidate" in content
    assert 'class="privacy-status-strip"' in content
    assert "Activity log" in content
    assert "Workflow audit summaries" not in content
    assert "CSV-created source records" not in content
    assert "Candidate records due (0)" not in content
    assert "Source records due (0)" not in content
    assert "Documents due (0)" not in content
    assert "SECRET SOURCE CONTENT" not in content
    assert "SECRET-REFERENCE" not in content
    assert "SECRET NOTES" not in content
    assert "retained@example.test" not in content
    assert "Review purge" in content

    client.force_login(outsider)
    hidden_response = client.get(route)
    assert hidden_response.status_code == 404
    assert "Pending Candidate" not in hidden_response.content.decode()


def test_workflow_activity_is_plain_sorted_bounded_and_filterable() -> None:
    user = User.objects.create_user(username="admin")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization, role=OrganizationMembership.Role.ADMIN)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Private Candidate",
    )
    source = CandidateSource.objects.create(
        candidate=candidate,
        source_type=CandidateSource.SourceType.CSV_IMPORT,
        source_name="PRIVATE SOURCE",
        recorded_by=user,
    )
    attempt = AIUsageEvent.objects.create(
        organization=organization,
        actor=user,
        workflow=AIUsageEvent.Workflow.CANDIDATE_PROFILE,
        target_type=AIUsageEvent.ObjectType.CANDIDATE_DOCUMENT,
        target_id=1,
    )
    CandidateSource.objects.filter(pk=source.pk).update(
        created_at=timezone.now() - timedelta(minutes=5)
    )

    history = build_audit_history(
        organization=organization,
        user=user,
        limit=1,
    )
    intake_only = build_audit_history(
        organization=organization,
        user=user,
        category="intake",
    )
    normalized = build_audit_history(
        organization=organization,
        user=user,
        category="invalid",
    )

    assert len(history.workflow_entries) == 1
    assert history.workflow_entries[0].reference == f"AI attempt #{attempt.pk}"
    assert intake_only.workflow_entries[0].activity == "Candidate added from CSV"
    assert intake_only.workflow_entries[0].reference == f"Candidate #{candidate.pk}"
    assert "PRIVATE SOURCE" not in repr(intake_only.workflow_entries)
    assert normalized.selected_category == "all"
