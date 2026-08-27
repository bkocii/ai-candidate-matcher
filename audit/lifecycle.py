from dataclasses import dataclass
from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from accounts.models import OrganizationMembership, User
from audit.models import (
    AIUsageEvent,
    AuditEvent,
    DataLifecycleEvent,
    OrganizationTombstone,
)
from candidates.models import CandidateDocument, CandidateIntakeItem
from matching.models import (
    CandidateSkill,
    HardConstraintRule,
    MatchRun,
    RequirementSkill,
)
from operations.models import BackgroundJob
from organizations.models import (
    Organization,
    OrganizationRetentionPolicy,
    RetentionException,
)
from organizations.permissions import (
    is_platform_owner,
    require_organization_admin,
    require_organization_lifecycle_manager,
)
from outreach.models import OutreachDraft


class DataLifecycleError(RuntimeError):
    """A lifecycle operation could not complete without violating safety rules."""


@dataclass(frozen=True)
class RetentionPlan:
    organization_id: int
    policy_version: int
    as_of: datetime
    temporary_intake_item_ids: tuple[int, ...]
    completed_job_ids: tuple[int, ...]
    obsolete_match_run_ids: tuple[int, ...]
    abandoned_outreach_entry_ids: tuple[int, ...]
    ai_usage_event_ids: tuple[int, ...]
    audit_event_ids: tuple[int, ...]
    lifecycle_event_ids: tuple[int, ...]
    estimated_private_bytes: int
    blocked_count: int
    legal_hold: bool

    @property
    def metadata_count(self) -> int:
        return (
            len(self.ai_usage_event_ids)
            + len(self.audit_event_ids)
            + len(self.lifecycle_event_ids)
        )

    @property
    def purgeable_count(self) -> int:
        return (
            len(self.temporary_intake_item_ids)
            + len(self.completed_job_ids)
            + len(self.obsolete_match_run_ids)
            + len(self.abandoned_outreach_entry_ids)
            + self.metadata_count
        )


@dataclass(frozen=True)
class RetentionResult:
    temporary_intake_items: int = 0
    completed_jobs: int = 0
    obsolete_match_runs: int = 0
    abandoned_outreach_chains: int = 0
    metadata_records: int = 0

    @property
    def total(self) -> int:
        return sum(
            (
                self.temporary_intake_items,
                self.completed_jobs,
                self.obsolete_match_runs,
                self.abandoned_outreach_chains,
                self.metadata_records,
            )
        )


def get_retention_policy(
    organization: Organization,
) -> OrganizationRetentionPolicy:
    policy, _ = OrganizationRetentionPolicy.objects.get_or_create(
        organization=organization
    )
    return policy


def update_retention_policy(
    *, organization: Organization, user: User, values: dict
) -> OrganizationRetentionPolicy:
    require_organization_admin(user, organization)
    with transaction.atomic():
        policy = (
            OrganizationRetentionPolicy.objects.select_for_update()
            .filter(organization=organization)
            .first()
        )
        if policy is None:
            policy = OrganizationRetentionPolicy(organization=organization)
        changed = False
        for field_name, value in values.items():
            if field_name not in {
                "temporary_intake_days",
                "completed_job_days",
                "uncommitted_workflow_days",
                "metadata_days",
                "organization_recovery_days",
                "legal_hold",
            }:
                continue
            if getattr(policy, field_name) != value:
                setattr(policy, field_name, value)
                changed = True
        if policy.pk and changed:
            policy.policy_version += 1
        policy.updated_by = user
        policy.full_clean()
        policy.save()
        return policy


def _active_exceptions(
    *, organization: Organization, as_of: datetime
) -> dict[str, set[int | None]]:
    rows = RetentionException.objects.filter(
        organization=organization,
        is_active=True,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=as_of.date()))
    result: dict[str, set[int | None]] = {}
    for scope, object_id in rows.values_list("scope", "object_id"):
        result.setdefault(scope, set()).add(object_id)
    return result


def _exclude_exception_ids(
    ids: list[int], *, scope: str, exceptions: dict[str, set[int | None]]
) -> tuple[tuple[int, ...], int]:
    held = exceptions.get(scope, set())
    if None in held:
        return (), len(ids)
    allowed = tuple(object_id for object_id in ids if object_id not in held)
    return allowed, len(ids) - len(allowed)


def build_retention_plan(
    *, organization: Organization, as_of: datetime | None = None
) -> RetentionPlan:
    as_of = as_of or timezone.now()
    if timezone.is_naive(as_of):
        as_of = timezone.make_aware(as_of)
    policy = get_retention_policy(organization)
    exceptions = _active_exceptions(organization=organization, as_of=as_of)
    blocked_count = 0

    intake_cutoff = as_of - timedelta(days=policy.temporary_intake_days)
    intake_rows = list(
        CandidateIntakeItem.objects.for_organization(organization)
        .filter(
            status=CandidateIntakeItem.Status.PENDING,
            created_at__lte=intake_cutoff,
        )
        .values_list("id", "size_bytes")
    )
    intake_ids, blocked = _exclude_exception_ids(
        [row[0] for row in intake_rows],
        scope=RetentionException.Scope.TEMPORARY_INTAKE,
        exceptions=exceptions,
    )
    blocked_count += blocked
    allowed_intake_ids = set(intake_ids)
    estimated_private_bytes = sum(
        size or 0 for object_id, size in intake_rows if object_id in allowed_intake_ids
    )

    job_cutoff = as_of - timedelta(days=policy.completed_job_days)
    job_candidates = list(
        BackgroundJob.objects.for_organization(organization)
        .filter(
            status__in=[
                BackgroundJob.Status.SUCCEEDED,
                BackgroundJob.Status.COMPLETED_WITH_ERRORS,
            ],
            completed_at__lte=job_cutoff,
        )
        .values_list("id", flat=True)
    )
    job_ids, blocked = _exclude_exception_ids(
        job_candidates,
        scope=RetentionException.Scope.COMPLETED_JOBS,
        exceptions=exceptions,
    )
    blocked_count += blocked

    workflow_cutoff = as_of - timedelta(days=policy.uncommitted_workflow_days)
    latest_run_ids = set(
        MatchRun.objects.for_organization(organization)
        .values("requirements__vacancy_id")
        .annotate(latest_id=Max("id"))
        .values_list("latest_id", flat=True)
    )
    match_candidates = list(
        MatchRun.objects.for_organization(organization)
        .filter(created_at__lte=workflow_cutoff)
        .exclude(id__in=latest_run_ids)
        .exclude(entries__review_decisions__isnull=False)
        .values_list("id", flat=True)
        .distinct()
    )
    match_run_ids, blocked = _exclude_exception_ids(
        match_candidates,
        scope=RetentionException.Scope.MATCH_RUNS,
        exceptions=exceptions,
    )
    blocked_count += blocked

    outreach_candidates: list[int] = []
    outreach_entry_ids_with_drafts = (
        OutreachDraft.objects.for_organization(organization)
        .values_list("shortlist_entry_id", flat=True)
        .distinct()
    )
    for entry_id in outreach_entry_ids_with_drafts:
        drafts = OutreachDraft.objects.filter(shortlist_entry_id=entry_id)
        latest_created_at = drafts.aggregate(latest=Max("created_at"))["latest"]
        if latest_created_at is None or latest_created_at > workflow_cutoff:
            continue
        if drafts.filter(
            Q(final_approval__isnull=False) | Q(manual_actions__isnull=False)
        ).exists():
            continue
        outreach_candidates.append(entry_id)
    outreach_entry_ids, blocked = _exclude_exception_ids(
        outreach_candidates,
        scope=RetentionException.Scope.OUTREACH,
        exceptions=exceptions,
    )
    blocked_count += blocked
    match_entry_ids = set(
        MatchRun.objects.filter(id__in=match_run_ids).values_list(
            "entries__id", flat=True
        )
    )
    outreach_entry_ids = tuple(
        object_id
        for object_id in outreach_entry_ids
        if object_id not in match_entry_ids
    )

    metadata_cutoff = as_of - timedelta(days=policy.metadata_days)
    usage_candidates = list(
        AIUsageEvent.objects.for_organization(organization)
        .exclude(status=AIUsageEvent.Status.PENDING)
        .filter(completed_at__lte=metadata_cutoff)
        .values_list("id", flat=True)
    )
    audit_candidates = list(
        AuditEvent.objects.for_organization(organization)
        .filter(occurred_at__lte=metadata_cutoff)
        .values_list("id", flat=True)
    )
    lifecycle_candidates = list(
        DataLifecycleEvent.objects.filter(
            organization_id_snapshot=organization.pk,
            occurred_at__lte=metadata_cutoff,
        ).values_list("id", flat=True)
    )
    metadata_held = exceptions.get(RetentionException.Scope.METADATA, set())
    if metadata_held:
        blocked_count += (
            len(usage_candidates) + len(audit_candidates) + len(lifecycle_candidates)
        )
        usage_ids: tuple[int, ...] = ()
        audit_ids: tuple[int, ...] = ()
        lifecycle_ids: tuple[int, ...] = ()
    else:
        usage_ids = tuple(usage_candidates)
        audit_ids = tuple(audit_candidates)
        lifecycle_ids = tuple(lifecycle_candidates)

    if policy.legal_hold:
        blocked_count += (
            len(intake_ids)
            + len(job_ids)
            + len(match_run_ids)
            + len(outreach_entry_ids)
            + len(usage_ids)
            + len(audit_ids)
            + len(lifecycle_ids)
        )
        intake_ids = ()
        job_ids = ()
        match_run_ids = ()
        outreach_entry_ids = ()
        usage_ids = ()
        audit_ids = ()
        lifecycle_ids = ()
        estimated_private_bytes = 0

    return RetentionPlan(
        organization_id=organization.pk,
        policy_version=policy.policy_version,
        as_of=as_of,
        temporary_intake_item_ids=intake_ids,
        completed_job_ids=job_ids,
        obsolete_match_run_ids=match_run_ids,
        abandoned_outreach_entry_ids=outreach_entry_ids,
        ai_usage_event_ids=usage_ids,
        audit_event_ids=audit_ids,
        lifecycle_event_ids=lifecycle_ids,
        estimated_private_bytes=estimated_private_bytes,
        blocked_count=blocked_count,
        legal_hold=policy.legal_hold,
    )


def _record_lifecycle_event(
    *,
    organization_id: int,
    actor: User | None,
    action: str,
    object_type: str,
    object_id: int,
    policy_version: int,
) -> None:
    DataLifecycleEvent.objects.create(
        organization_id_snapshot=organization_id,
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=object_id,
        policy_version=policy_version,
    )


@transaction.atomic
def apply_retention_plan(
    *, organization: Organization, actor: User | None, as_of: datetime | None = None
) -> RetentionResult:
    if actor is not None:
        require_organization_admin(actor, organization)
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    plan = build_retention_plan(organization=organization, as_of=as_of)
    if plan.legal_hold:
        raise DataLifecycleError("A legal hold blocks automated lifecycle cleanup.")

    intake_count = 0
    for item in CandidateIntakeItem.objects.select_for_update().filter(
        id__in=plan.temporary_intake_item_ids
    ):
        stored_name = item.file.name
        try:
            if stored_name:
                item.file.storage.delete(stored_name)
                if item.file.storage.exists(stored_name):
                    raise DataLifecycleError(
                        "A temporary intake file still exists after deletion."
                    )
        except Exception as error:
            raise DataLifecycleError(
                "A temporary intake file could not be removed; cleanup stopped."
            ) from error
        item.status = CandidateIntakeItem.Status.SKIPPED
        item.original_filename = ""
        item.file = ""
        item.content_type = ""
        item.size_bytes = None
        item.sha256 = ""
        item.extracted_text = ""
        item.proposed_full_name = ""
        item.proposed_email = ""
        item.proposed_phone = ""
        item.proposed_location = ""
        item.proposed_source_reference = ""
        item.review_flags = []
        item.processed_by = actor
        item.processed_at = timezone.now()
        item.full_clean()
        item.save()
        intake_count += 1
        _record_lifecycle_event(
            organization_id=organization.pk,
            actor=actor,
            action=DataLifecycleEvent.Action.TEMPORARY_INTAKE_PURGED,
            object_type=DataLifecycleEvent.ObjectType.INTAKE_ITEM,
            object_id=item.pk,
            policy_version=plan.policy_version,
        )

    for job_id in plan.completed_job_ids:
        BackgroundJob.objects.filter(pk=job_id).delete()
        _record_lifecycle_event(
            organization_id=organization.pk,
            actor=actor,
            action=DataLifecycleEvent.Action.COMPLETED_JOB_PURGED,
            object_type=DataLifecycleEvent.ObjectType.BACKGROUND_JOB,
            object_id=job_id,
            policy_version=plan.policy_version,
        )

    for run_id in plan.obsolete_match_run_ids:
        MatchRun.objects.filter(pk=run_id).delete()
        _record_lifecycle_event(
            organization_id=organization.pk,
            actor=actor,
            action=DataLifecycleEvent.Action.MATCH_RUN_PURGED,
            object_type=DataLifecycleEvent.ObjectType.MATCH_RUN,
            object_id=run_id,
            policy_version=plan.policy_version,
        )

    for entry_id in plan.abandoned_outreach_entry_ids:
        OutreachDraft.objects.filter(shortlist_entry_id=entry_id).delete()
        _record_lifecycle_event(
            organization_id=organization.pk,
            actor=actor,
            action=DataLifecycleEvent.Action.OUTREACH_CHAIN_PURGED,
            object_type=DataLifecycleEvent.ObjectType.SHORTLIST_ENTRY,
            object_id=entry_id,
            policy_version=plan.policy_version,
        )

    usage_count = len(plan.ai_usage_event_ids)
    audit_count = len(plan.audit_event_ids)
    lifecycle_count = len(plan.lifecycle_event_ids)
    if usage_count:
        AIUsageEvent.objects.filter(id__in=plan.ai_usage_event_ids).delete()
    if audit_count:
        AuditEvent.objects.filter(id__in=plan.audit_event_ids)._raw_delete(
            using=AuditEvent.objects.db
        )
    if lifecycle_count:
        DataLifecycleEvent.objects.filter(id__in=plan.lifecycle_event_ids)._raw_delete(
            using=DataLifecycleEvent.objects.db
        )
    if usage_count or audit_count or lifecycle_count:
        _record_lifecycle_event(
            organization_id=organization.pk,
            actor=actor,
            action=DataLifecycleEvent.Action.METADATA_PURGED,
            object_type=DataLifecycleEvent.ObjectType.METADATA_GROUP,
            object_id=organization.pk,
            policy_version=plan.policy_version,
        )

    return RetentionResult(
        temporary_intake_items=intake_count,
        completed_jobs=len(plan.completed_job_ids),
        obsolete_match_runs=len(plan.obsolete_match_run_ids),
        abandoned_outreach_chains=len(plan.abandoned_outreach_entry_ids),
        metadata_records=usage_count + audit_count + lifecycle_count,
    )


def _has_inactive_admin_membership(user: User, organization: Organization) -> bool:
    return is_platform_owner(user) or (
        bool(user.is_authenticated and user.is_active)
        and OrganizationMembership.objects.filter(
            user=user,
            organization=organization,
            role=OrganizationMembership.Role.ADMIN,
            is_active=True,
        ).exists()
    )


@transaction.atomic
def request_organization_deletion(
    *, organization: Organization, user: User
) -> Organization:
    require_organization_lifecycle_manager(user, organization)
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    if organization.deletion_requested_at is not None:
        raise ValidationError("Organization deletion is already scheduled.")
    policy = get_retention_policy(organization)
    now = timezone.now()
    organization.is_active = False
    organization.deletion_requested_at = now
    organization.deletion_requested_by = user
    organization.purge_after = now + timedelta(days=policy.organization_recovery_days)
    organization.full_clean()
    organization.save()
    _record_lifecycle_event(
        organization_id=organization.pk,
        actor=user,
        action=DataLifecycleEvent.Action.ORGANIZATION_DELETION_REQUESTED,
        object_type=DataLifecycleEvent.ObjectType.ORGANIZATION,
        object_id=organization.pk,
        policy_version=policy.policy_version,
    )
    return organization


@transaction.atomic
def cancel_organization_deletion(
    *, organization: Organization, user: User
) -> Organization:
    if not _has_inactive_admin_membership(user, organization):
        raise PermissionDenied("Organization administrator access is required.")
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    if organization.deletion_requested_at is None:
        raise ValidationError("Organization deletion is not scheduled.")
    if organization.purge_after and organization.purge_after <= timezone.now():
        raise ValidationError("The recovery window has ended.")
    policy = get_retention_policy(organization)
    organization.is_active = True
    organization.deletion_requested_at = None
    organization.deletion_requested_by = None
    organization.purge_after = None
    organization.full_clean()
    organization.save()
    _record_lifecycle_event(
        organization_id=organization.pk,
        actor=user,
        action=DataLifecycleEvent.Action.ORGANIZATION_DELETION_CANCELLED,
        object_type=DataLifecycleEvent.ObjectType.ORGANIZATION,
        object_id=organization.pk,
        policy_version=policy.policy_version,
    )
    return organization


def organizations_available_for_recovery(user: User):
    if not (user.is_authenticated and user.is_active):
        return Organization.objects.none()
    return Organization.objects.filter(
        is_active=False,
        deletion_requested_at__isnull=False,
        memberships__user=user,
        memberships__role=OrganizationMembership.Role.ADMIN,
        memberships__is_active=True,
    ).distinct()


@transaction.atomic
def purge_organization(
    *, organization: Organization, as_of: datetime | None = None
) -> int:
    """Delete a suspended tenant graph after recovery while retaining no content."""
    as_of = as_of or timezone.now()
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    policy = get_retention_policy(organization)
    if organization.is_active or organization.deletion_requested_at is None:
        raise DataLifecycleError("Organization deletion has not been requested.")
    if organization.purge_after is None or organization.purge_after > as_of:
        raise DataLifecycleError("The organization recovery window is still open.")
    if policy.legal_hold:
        raise DataLifecycleError("A legal hold blocks organization deletion.")
    exceptions = _active_exceptions(organization=organization, as_of=as_of)
    if exceptions.get(RetentionException.Scope.ORGANIZATION):
        raise DataLifecycleError("A retention exception blocks organization deletion.")

    organization_id = organization.pk
    deletion_requested_at = organization.deletion_requested_at
    file_fields = [
        *CandidateDocument.objects.for_organization(organization).select_related(
            "candidate"
        ),
        *CandidateIntakeItem.objects.for_organization(organization),
    ]
    try:
        for record in file_fields:
            stored_name = record.file.name
            if stored_name:
                record.file.storage.delete(stored_name)
                if record.file.storage.exists(stored_name):
                    raise DataLifecycleError(
                        "A private file still exists after deletion."
                    )
    except Exception as error:
        raise DataLifecycleError(
            "Private files could not be verified as removed; "
            "organization purge stopped."
        ) from error

    MatchRun.objects.for_organization(organization).delete()
    CandidateSkill.objects.for_organization(organization).delete()
    RequirementSkill.objects.for_organization(organization)._raw_delete(
        using=RequirementSkill.objects.db
    )
    HardConstraintRule.objects.for_organization(organization)._raw_delete(
        using=HardConstraintRule.objects.db
    )
    AIUsageEvent.objects.for_organization(organization).delete()
    AuditEvent.objects.for_organization(organization)._raw_delete(
        using=AuditEvent.objects.db
    )
    DataLifecycleEvent.objects.filter(
        organization_id_snapshot=organization_id
    )._raw_delete(using=DataLifecycleEvent.objects.db)
    OrganizationTombstone.objects.create(
        organization_id_snapshot=organization_id,
        policy_version=policy.policy_version,
        deletion_requested_at=deletion_requested_at,
    )
    organization.delete()
    _record_lifecycle_event(
        organization_id=organization_id,
        actor=None,
        action=DataLifecycleEvent.Action.ORGANIZATION_PURGED,
        object_type=DataLifecycleEvent.ObjectType.ORGANIZATION,
        object_id=organization_id,
        policy_version=policy.policy_version,
    )
    return organization_id
