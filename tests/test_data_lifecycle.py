from datetime import timedelta
from io import StringIO

import pytest
from django.core.files.base import ContentFile
from django.core.management import CommandError, call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import OrganizationMembership, User
from audit.lifecycle import (
    DataLifecycleError,
    apply_retention_plan,
    build_retention_plan,
    cancel_organization_deletion,
    get_retention_policy,
    purge_organization,
    request_organization_deletion,
)
from audit.models import AuditEvent, DataLifecycleEvent, OrganizationTombstone
from audit.services import record_audit_event
from candidates.models import CandidateIntakeBatch, CandidateIntakeItem
from matching.models import MatchRun, ReviewDecision
from operations.models import BackgroundJob, BackgroundTask
from organizations.forms import RetentionExceptionForm
from organizations.models import (
    Organization,
    RetentionException,
)
from outreach.generation import generate_outreach_draft
from outreach.models import OutreachDraft, OutreachDraftApproval
from tests.test_match_ai_assessment import make_workspace
from tests.test_outreach_drafts import (
    ConfiguredOutreachGateway,
    approved_workspace,
)

pytestmark = pytest.mark.django_db


def make_admin(*, slug: str = "lifecycle") -> tuple[User, Organization]:
    user = User.objects.create_user(username=f"{slug}-admin")
    organization = Organization.objects.create(name=slug.title(), slug=slug)
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.ADMIN,
    )
    return user, organization


def age(model, object_id: int, field: str, *, days: int) -> None:
    model.objects.filter(pk=object_id).update(
        **{field: timezone.now() - timedelta(days=days)}
    )


def test_policy_defaults_dashboard_and_admin_boundary(client) -> None:
    admin, organization = make_admin()
    recruiter = User.objects.create_user(username="recruiter")
    OrganizationMembership.objects.create(
        user=recruiter,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )

    policy = get_retention_policy(organization)

    assert policy.temporary_intake_days == 7
    assert policy.completed_job_days == 90
    assert policy.uncommitted_workflow_days == 180
    assert policy.metadata_days == 365
    assert policy.organization_recovery_days == 30
    route = reverse("organizations:retention-dashboard", args=[organization.slug])
    client.force_login(recruiter)
    assert client.get(route).status_code == 403
    client.force_login(admin)
    response = client.get(route)
    assert response.status_code == 200
    assert response.context["plan"].purgeable_count == 0
    content = response.content.decode()
    assert "Current workflows and decision-bearing history remain protected" in content
    assert 'class="empty-preview"' in content
    assert "Nothing eligible for deletion" in content
    assert 'class="retention-form-grid"' in content
    assert "Delete the items shown above" not in content
    assert 'name="apply-confirmation"' not in content
    assert reverse("audit:privacy-dashboard", args=[organization.slug]) in content


def test_retention_exception_target_is_selected_from_current_organization() -> None:
    admin, organization = make_admin(slug="exception-target")
    _, other = make_admin(slug="other-exception-target")
    own_job = BackgroundJob.objects.create(
        organization=organization,
        workflow=BackgroundJob.Workflow.CANDIDATE_PROFILE_BATCH,
        scope_type=BackgroundJob.ScopeType.ORGANIZATION,
        scope_id=organization.pk,
        idempotency_key="c" * 64,
        status=BackgroundJob.Status.SUCCEEDED,
        completed_at=timezone.now(),
    )
    foreign_job = BackgroundJob.objects.create(
        organization=other,
        workflow=BackgroundJob.Workflow.CANDIDATE_PROFILE_BATCH,
        scope_type=BackgroundJob.ScopeType.ORGANIZATION,
        scope_id=other.pk,
        idempotency_key="d" * 64,
        status=BackgroundJob.Status.SUCCEEDED,
        completed_at=timezone.now(),
    )
    own_target = f"{RetentionException.Scope.COMPLETED_JOBS}:{own_job.pk}"
    foreign_target = f"{RetentionException.Scope.COMPLETED_JOBS}:{foreign_job.pk}"

    form = RetentionExceptionForm(
        data={"target": own_target, "reason": "Preserve for support review"},
        organization=organization,
    )
    forged = RetentionExceptionForm(
        data={"target": foreign_target, "reason": "Forged foreign target"},
        organization=organization,
    )

    assert form.is_valid(), form.errors
    exception = form.save(user=admin)
    assert exception.organization == organization
    assert exception.scope == RetentionException.Scope.COMPLETED_JOBS
    assert exception.object_id == own_job.pk
    assert not forged.is_valid()
    rendered_choices = str(forged["target"])
    assert own_target in rendered_choices
    assert foreign_target not in rendered_choices


def test_cleanup_expires_intake_and_jobs_but_honors_exception(
    tmp_path, settings
) -> None:
    settings.MEDIA_ROOT = tmp_path
    admin, organization = make_admin(slug="cleanup")
    policy = get_retention_policy(organization)
    batch = CandidateIntakeBatch.objects.create(
        organization=organization,
        source_name="Synthetic test intake",
        created_by=admin,
    )
    item = CandidateIntakeItem.objects.create(
        batch=batch,
        original_filename="fixture.txt",
        file=ContentFile(b"Synthetic CV", name="fixture.txt"),
        content_type="text/plain",
        size_bytes=12,
        sha256="a" * 64,
        extracted_text="Synthetic CV",
        uploaded_by=admin,
    )
    age(CandidateIntakeItem, item.pk, "created_at", days=8)
    old_job = BackgroundJob.objects.create(
        organization=organization,
        workflow=BackgroundJob.Workflow.CANDIDATE_PROFILE_BATCH,
        scope_type=BackgroundJob.ScopeType.ORGANIZATION,
        scope_id=organization.pk,
        idempotency_key="a" * 64,
        status=BackgroundJob.Status.SUCCEEDED,
        completed_at=timezone.now(),
    )
    held_job = BackgroundJob.objects.create(
        organization=organization,
        workflow=BackgroundJob.Workflow.CANDIDATE_PROFILE_BATCH,
        scope_type=BackgroundJob.ScopeType.ORGANIZATION,
        scope_id=organization.pk,
        idempotency_key="b" * 64,
        status=BackgroundJob.Status.SUCCEEDED,
        completed_at=timezone.now(),
    )
    BackgroundTask.objects.create(
        job=old_job,
        target_type=BackgroundTask.TargetType.CANDIDATE_DOCUMENT,
        target_id=1,
    )
    for job in (old_job, held_job):
        age(BackgroundJob, job.pk, "completed_at", days=91)
    RetentionException.objects.create(
        organization=organization,
        scope=RetentionException.Scope.COMPLETED_JOBS,
        object_id=held_job.pk,
        reason="Synthetic fixture hold",
        created_by=admin,
    )

    plan = build_retention_plan(organization=organization)
    assert plan.temporary_intake_item_ids == (item.pk,)
    assert plan.completed_job_ids == (old_job.pk,)
    assert plan.blocked_count == 1
    assert plan.estimated_private_bytes == 12

    result = apply_retention_plan(organization=organization, actor=admin)
    item.refresh_from_db()
    assert result.temporary_intake_items == 1
    assert result.completed_jobs == 1
    assert item.status == CandidateIntakeItem.Status.SKIPPED
    assert item.file.name == ""
    assert item.extracted_text == ""
    assert not BackgroundJob.objects.filter(pk=old_job.pk).exists()
    assert BackgroundJob.objects.filter(pk=held_job.pk).exists()
    assert (
        DataLifecycleEvent.objects.filter(
            organization_id_snapshot=organization.pk
        ).count()
        == 2
    )
    assert policy.policy_version == 1


def test_legal_hold_blocks_all_scheduled_cleanup() -> None:
    _, organization = make_admin(slug="held")
    policy = get_retention_policy(organization)
    policy.legal_hold = True
    policy.save(update_fields=("legal_hold",))

    plan = build_retention_plan(organization=organization)

    assert plan.legal_hold is True
    assert plan.purgeable_count == 0
    with pytest.raises(DataLifecycleError, match="legal hold"):
        apply_retention_plan(organization=organization, actor=None)


def test_old_shortlist_without_decisions_is_removed_but_latest_is_kept() -> None:
    user, organization, _, _, _, _, old_run, _ = make_workspace(
        username="shortlist-retention"
    )
    latest = MatchRun.objects.create(
        requirements=old_run.requirements,
        algorithm_version="retention-test.v1",
        shortlist_limit=10,
        evaluated_count=0,
        eligible_count=0,
        shortlisted_count=0,
        created_by=user,
    )
    age(MatchRun, old_run.pk, "created_at", days=181)

    plan = build_retention_plan(organization=organization)

    assert plan.obsolete_match_run_ids == (old_run.pk,)
    apply_retention_plan(organization=organization, actor=None)
    assert not MatchRun.objects.filter(pk=old_run.pk).exists()
    assert MatchRun.objects.filter(pk=latest.pk).exists()


def test_decision_history_survives_while_abandoned_outreach_chain_expires() -> None:
    values = approved_workspace(username="outreach-retention")
    user, organization, _, _, _, _, old_run, entry, _, decision = values
    draft = generate_outreach_draft(
        decision=decision,
        user=user,
        gateway=ConfiguredOutreachGateway(),
    ).draft
    MatchRun.objects.create(
        requirements=old_run.requirements,
        algorithm_version="newer-run.v1",
        shortlist_limit=10,
        evaluated_count=0,
        eligible_count=0,
        shortlisted_count=0,
        created_by=user,
    )
    age(MatchRun, old_run.pk, "created_at", days=181)
    age(OutreachDraft, draft.pk, "created_at", days=181)

    plan = build_retention_plan(organization=organization)

    assert old_run.pk not in plan.obsolete_match_run_ids
    assert plan.abandoned_outreach_entry_ids == (entry.pk,)
    apply_retention_plan(organization=organization, actor=None)
    assert MatchRun.objects.filter(pk=old_run.pk).exists()
    assert ReviewDecision.objects.filter(pk=decision.pk).exists()
    assert not OutreachDraft.objects.filter(pk=draft.pk).exists()


def test_recent_or_finally_approved_outreach_chain_is_never_eligible() -> None:
    values = approved_workspace(username="protected-outreach")
    user, organization, _, _, _, _, _, entry, _, decision = values
    first = generate_outreach_draft(
        decision=decision,
        user=user,
        gateway=ConfiguredOutreachGateway(),
    ).draft
    second = generate_outreach_draft(
        decision=decision,
        user=user,
        gateway=ConfiguredOutreachGateway(),
    ).draft
    age(OutreachDraft, first.pk, "created_at", days=181)

    assert (
        entry.pk
        not in build_retention_plan(
            organization=organization
        ).abandoned_outreach_entry_ids
    )

    age(OutreachDraft, second.pk, "created_at", days=181)
    OutreachDraftApproval.objects.create(
        draft=second,
        notes="Synthetic exact-version approval.",
        contact_permission_confirmed=True,
        approved_by=user,
    )

    assert (
        entry.pk
        not in build_retention_plan(
            organization=organization
        ).abandoned_outreach_entry_ids
    )


def test_organization_suspension_recovery_and_complete_purge() -> None:
    values = make_workspace(username="organization-purge")
    user, organization, candidate, _, _, _, run, _ = values
    membership = OrganizationMembership.objects.get(
        user=user, organization=organization
    )
    membership.role = OrganizationMembership.Role.ADMIN
    membership.save(update_fields=("role",))
    record_audit_event(
        organization=organization,
        actor=user,
        action=AuditEvent.Action.CANDIDATE_DELETION_REQUESTED,
        object_type=AuditEvent.ObjectType.CANDIDATE,
        object_id=candidate.pk,
    )

    request_organization_deletion(organization=organization, user=user)
    organization.refresh_from_db()
    assert organization.is_active is False
    assert not Organization.objects.visible_to(user).exists()

    cancel_organization_deletion(organization=organization, user=user)
    organization.refresh_from_db()
    assert organization.is_active is True

    request_organization_deletion(organization=organization, user=user)
    Organization.objects.filter(pk=organization.pk).update(
        purge_after=timezone.now() - timedelta(minutes=1)
    )
    organization.refresh_from_db()
    organization_id = organization.pk
    purge_organization(organization=organization)

    assert not Organization.objects.filter(pk=organization_id).exists()
    assert not MatchRun.objects.filter(pk=run.pk).exists()
    assert (
        OrganizationTombstone.objects.get(
            organization_id_snapshot=organization_id
        ).policy_version
        == 1
    )
    assert DataLifecycleEvent.objects.filter(
        organization_id_snapshot=organization_id,
        action=DataLifecycleEvent.Action.ORGANIZATION_PURGED,
    ).exists()


def test_organization_suspension_page_names_target_deadline_and_exact_phrase(
    client,
) -> None:
    admin, organization = make_admin(slug="suspension-review")
    policy = get_retention_policy(organization)
    policy.legal_hold = True
    policy.save(update_fields=("legal_hold",))
    RetentionException.objects.create(
        organization=organization,
        scope=RetentionException.Scope.ORGANIZATION,
        reason="Synthetic organization hold",
        created_by=admin,
    )
    route = reverse(
        "organizations:organization-delete-request", args=[organization.slug]
    )
    phrase = f"SUSPEND {organization.name.upper()}"
    client.force_login(admin)

    response = client.get(route)
    content = response.content.decode()

    assert response.status_code == 200
    assert f"Suspend {organization.name} and schedule deletion" in content
    assert phrase in content
    assert "Recovery for 30 days" in content
    assert "Projected purge deadline" in content
    assert "Permanent purge is currently blocked" in content
    assert 'class="danger-confirmation"' in content

    invalid = client.post(route, {"confirmation": "DELETE ORGANIZATION"})
    organization.refresh_from_db()
    assert invalid.status_code == 200
    assert organization.is_active is True
    assert "Enter the exact confirmation phrase" in invalid.content.decode()

    confirmed = client.post(route, {"confirmation": phrase})
    organization.refresh_from_db()
    assert confirmed.status_code == 302
    assert organization.is_active is False
    assert organization.purge_after is not None


def test_lifecycle_command_is_dry_run_and_apply_needs_confirmation() -> None:
    _, organization = make_admin(slug="command")
    output = StringIO()

    call_command(
        "process_data_lifecycle",
        organization=organization.slug,
        stdout=output,
    )

    assert "eligible=0" in output.getvalue()
    assert "dry run" in output.getvalue()
    with pytest.raises(CommandError, match="requires --confirm"):
        call_command(
            "process_data_lifecycle",
            organization=organization.slug,
            apply=True,
        )
