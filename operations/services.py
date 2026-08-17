import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import User
from ai_gateway import AIGateway, AIGatewayError
from candidates.ai_extraction import extract_candidate_profile
from candidates.models import Candidate, CandidateDocument
from matching.ai_assessment import assess_shortlist_entry
from matching.models import MatchAssessment, MatchRun, ShortlistEntry
from matching.staleness import assess_match_run_staleness
from operations.models import BackgroundJob, BackgroundTask
from organizations.models import Organization
from organizations.permissions import (
    require_organization_access,
    require_organization_object_access,
)

TASK_LEASE = timedelta(hours=1)


@dataclass(frozen=True)
class QueueResult:
    job: BackgroundJob
    created: bool


def _idempotency_key(payload: object) -> str:
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _create_job(
    *,
    organization: Organization,
    user: User,
    workflow: str,
    scope_type: str,
    scope_id: int,
    key: str,
    targets: list[tuple[str, int]],
) -> QueueResult:
    with transaction.atomic():
        Organization.objects.select_for_update().get(pk=organization.pk)
        existing = BackgroundJob.objects.filter(idempotency_key=key).first()
        if existing is not None:
            require_organization_object_access(user, existing)
            return QueueResult(job=existing, created=False)
        job = BackgroundJob.objects.create(
            organization=organization,
            workflow=workflow,
            scope_type=scope_type,
            scope_id=scope_id,
            idempotency_key=key,
            total_count=len(targets),
            created_by=user,
        )
        BackgroundTask.objects.bulk_create(
            [
                BackgroundTask(
                    job=job,
                    target_type=target_type,
                    target_id=target_id,
                )
                for target_type, target_id in targets
            ]
        )
    return QueueResult(job=job, created=True)


def queue_candidate_profile_batch(
    *, organization: Organization, user: User
) -> QueueResult:
    """Queue only each active candidate's newest successful, unprofiled CV."""
    require_organization_access(user, organization)
    documents = (
        CandidateDocument.objects.for_organization(organization)
        .filter(
            candidate__status=Candidate.Status.ACTIVE,
            document_type=CandidateDocument.DocumentType.CV,
            extraction_status=CandidateDocument.ExtractionStatus.SUCCEEDED,
            deleted_at__isnull=True,
        )
        .prefetch_related("profile_versions")
        .order_by("candidate_id", "-created_at", "-id")
    )
    newest_by_candidate: dict[int, CandidateDocument] = {}
    for document in documents:
        newest_by_candidate.setdefault(document.candidate_id, document)
    eligible = [
        document
        for document in newest_by_candidate.values()
        if not document.profile_versions.all()
    ]
    target_ids = [document.pk for document in eligible]
    lookup_ids = target_ids or [
        document.pk for document in newest_by_candidate.values()
    ]
    existing = (
        BackgroundJob.objects.for_organization(organization)
        .filter(
            workflow=BackgroundJob.Workflow.CANDIDATE_PROFILE_BATCH,
            tasks__target_type=BackgroundTask.TargetType.CANDIDATE_DOCUMENT,
            tasks__target_id__in=lookup_ids,
        )
        .distinct()
        .first()
    )
    if existing is not None:
        return QueueResult(job=existing, created=False)
    if not eligible:
        raise ValidationError(
            "No active candidate has a new or corrected CV awaiting profile extraction."
        )
    targets = [
        (BackgroundTask.TargetType.CANDIDATE_DOCUMENT, document.pk)
        for document in sorted(eligible, key=lambda item: item.pk)
    ]
    key = _idempotency_key(
        {
            "schema": "candidate_profile_batch.v1",
            "organization_id": organization.pk,
            "documents": [
                {"id": document.pk, "sha256": document.sha256}
                for document in sorted(eligible, key=lambda item: item.pk)
            ],
        }
    )
    return _create_job(
        organization=organization,
        user=user,
        workflow=BackgroundJob.Workflow.CANDIDATE_PROFILE_BATCH,
        scope_type=BackgroundJob.ScopeType.ORGANIZATION,
        scope_id=organization.pk,
        key=key,
        targets=targets,
    )


def queue_candidate_profile_documents(
    *,
    organization: Organization,
    user: User,
    document_ids: list[int],
) -> QueueResult:
    """Queue an explicit validated CV set, such as newly accepted intake items."""
    require_organization_access(user, organization)
    requested_ids = sorted(set(document_ids))
    if not requested_ids:
        raise ValidationError("No candidate CVs were selected for profile extraction.")
    documents = list(
        CandidateDocument.objects.for_organization(organization)
        .filter(
            pk__in=requested_ids,
            candidate__status=Candidate.Status.ACTIVE,
            document_type=CandidateDocument.DocumentType.CV,
            extraction_status=CandidateDocument.ExtractionStatus.SUCCEEDED,
            deleted_at__isnull=True,
        )
        .order_by("id")
    )
    if [document.pk for document in documents] != requested_ids:
        raise ValidationError(
            "One or more selected CVs are unavailable for profile extraction."
        )
    key = _idempotency_key(
        {
            "schema": "candidate_profile_documents.v1",
            "organization_id": organization.pk,
            "documents": [
                {"id": document.pk, "sha256": document.sha256} for document in documents
            ],
        }
    )
    return _create_job(
        organization=organization,
        user=user,
        workflow=BackgroundJob.Workflow.CANDIDATE_PROFILE_BATCH,
        scope_type=BackgroundJob.ScopeType.ORGANIZATION,
        scope_id=organization.pk,
        key=key,
        targets=[
            (BackgroundTask.TargetType.CANDIDATE_DOCUMENT, document.pk)
            for document in documents
        ],
    )


def queue_shortlist_assessment_batch(*, run: MatchRun, user: User) -> QueueResult:
    """Queue one isolated assessment target for every entry in a current run."""
    require_organization_object_access(user, run)
    run = MatchRun.objects.select_related("requirements__vacancy").get(pk=run.pk)
    if run.vacancy.deleted_at is not None:
        raise ValidationError("Deleted vacancies cannot produce AI assessments.")
    if assess_match_run_staleness(run=run, user=user).is_stale:
        raise ValidationError(
            "This shortlist is stale. Generate a current shortlist before queuing "
            "assessments."
        )
    entry_ids = list(run.entries.order_by("rank", "id").values_list("id", flat=True))
    if not entry_ids:
        raise ValidationError("This shortlist has no candidates to assess.")
    key = _idempotency_key(
        {
            "schema": "shortlist_assessment_batch.v1",
            "organization_id": run.organization.pk,
            "match_run_id": run.pk,
            "entries": entry_ids,
        }
    )
    return _create_job(
        organization=run.organization,
        user=user,
        workflow=BackgroundJob.Workflow.SHORTLIST_ASSESSMENT_BATCH,
        scope_type=BackgroundJob.ScopeType.MATCH_RUN,
        scope_id=run.pk,
        key=key,
        targets=[(BackgroundTask.TargetType.SHORTLIST_ENTRY, pk) for pk in entry_ids],
    )


def _refresh_job(job_id: int) -> BackgroundJob:
    counts = dict(
        BackgroundTask.objects.filter(job_id=job_id)
        .values("status")
        .annotate(count=Count("id"))
        .values_list("status", "count")
    )
    unfinished = counts.get(BackgroundTask.Status.QUEUED, 0) + counts.get(
        BackgroundTask.Status.RUNNING, 0
    )
    now = timezone.now()
    values = {
        "total_count": sum(counts.values()),
        "succeeded_count": counts.get(BackgroundTask.Status.SUCCEEDED, 0),
        "skipped_count": counts.get(BackgroundTask.Status.SKIPPED, 0),
        "failed_count": counts.get(BackgroundTask.Status.FAILED, 0),
        "updated_at": now,
    }
    if unfinished:
        values["status"] = BackgroundJob.Status.RUNNING
        values["completed_at"] = None
    else:
        values["status"] = (
            BackgroundJob.Status.COMPLETED_WITH_ERRORS
            if values["skipped_count"] or values["failed_count"]
            else BackgroundJob.Status.SUCCEEDED
        )
        values["completed_at"] = now
    BackgroundJob.objects.filter(pk=job_id).update(**values)
    return BackgroundJob.objects.get(pk=job_id)


def _claim_task(*, job_id: int | None = None) -> BackgroundTask | None:
    now = timezone.now()
    with transaction.atomic():
        tasks = BackgroundTask.objects.select_related("job", "job__created_by").filter(
            Q(status=BackgroundTask.Status.QUEUED)
            | Q(
                status=BackgroundTask.Status.RUNNING,
                lease_expires_at__lt=now,
            )
        )
        if job_id is not None:
            tasks = tasks.filter(job_id=job_id)
        if connection.features.has_select_for_update_skip_locked:
            tasks = tasks.select_for_update(skip_locked=True)
        else:
            tasks = tasks.select_for_update()
        task = tasks.order_by("id").first()
        if task is None:
            return None
        task.status = BackgroundTask.Status.RUNNING
        task.attempt_count += 1
        task.started_at = now
        task.completed_at = None
        task.lease_expires_at = now + TASK_LEASE
        task.failure_code = ""
        task.save(
            update_fields=(
                "status",
                "attempt_count",
                "started_at",
                "completed_at",
                "lease_expires_at",
                "failure_code",
                "updated_at",
            )
        )
        BackgroundJob.objects.filter(pk=task.job_id).update(
            status=BackgroundJob.Status.RUNNING,
            started_at=models_case_started_at(now),
            completed_at=None,
            updated_at=now,
        )
        return task


def models_case_started_at(now):
    """Keep the first job start timestamp without a read-modify-write race."""
    from django.db.models.functions import Coalesce

    return Coalesce("started_at", now)


def _complete_task(
    task: BackgroundTask,
    *,
    status: str,
    result_type: str = "",
    result_id: int | None = None,
    outcome: str = "",
    failure_code: str = "",
) -> None:
    BackgroundTask.objects.filter(pk=task.pk).update(
        status=status,
        result_type=result_type,
        result_id=result_id,
        outcome=outcome,
        failure_code=failure_code,
        lease_expires_at=None,
        completed_at=timezone.now(),
        updated_at=timezone.now(),
    )
    _refresh_job(task.job_id)


def _process_profile_task(task: BackgroundTask, gateway: AIGateway | None) -> None:
    document = (
        CandidateDocument.objects.select_related("candidate")
        .filter(pk=task.target_id)
        .first()
    )
    if document is None:
        _complete_task(
            task,
            status=BackgroundTask.Status.SKIPPED,
            failure_code="target_unavailable",
        )
        return
    existing = document.profile_versions.order_by("-version", "-id").first()
    if existing is not None:
        _complete_task(
            task,
            status=BackgroundTask.Status.SUCCEEDED,
            result_type=BackgroundTask.ResultType.CANDIDATE_PROFILE,
            result_id=existing.pk,
            outcome=BackgroundTask.Outcome.REUSED,
        )
        return
    result = extract_candidate_profile(
        document=document,
        user=task.job.created_by,
        gateway=gateway,
    )
    _complete_task(
        task,
        status=BackgroundTask.Status.SUCCEEDED,
        result_type=BackgroundTask.ResultType.CANDIDATE_PROFILE,
        result_id=result.profile.pk,
        outcome=BackgroundTask.Outcome.CREATED,
    )


def _process_assessment_task(task: BackgroundTask, gateway: AIGateway | None) -> None:
    entry = (
        ShortlistEntry.objects.select_related(
            "candidate", "match_run__requirements__vacancy"
        )
        .filter(pk=task.target_id)
        .first()
    )
    if entry is None:
        _complete_task(
            task,
            status=BackgroundTask.Status.SKIPPED,
            failure_code="target_unavailable",
        )
        return
    profile = entry.candidate.current_profile
    if profile is None:
        _complete_task(
            task,
            status=BackgroundTask.Status.SKIPPED,
            failure_code="confirmed_profile_required",
        )
        return
    existing = MatchAssessment.objects.filter(
        shortlist_entry=entry,
        requirements=entry.match_run.requirements,
        candidate_profile=profile,
    ).first()
    if existing is not None:
        _complete_task(
            task,
            status=BackgroundTask.Status.SUCCEEDED,
            result_type=BackgroundTask.ResultType.MATCH_ASSESSMENT,
            result_id=existing.pk,
            outcome=BackgroundTask.Outcome.REUSED,
        )
        return
    result = assess_shortlist_entry(
        entry=entry,
        user=task.job.created_by,
        gateway=gateway,
    )
    _complete_task(
        task,
        status=BackgroundTask.Status.SUCCEEDED,
        result_type=BackgroundTask.ResultType.MATCH_ASSESSMENT,
        result_id=result.assessment.pk,
        outcome=BackgroundTask.Outcome.CREATED,
    )


def process_next_background_task(
    *, job_id: int | None = None, gateway: AIGateway | None = None
) -> BackgroundTask | None:
    """Claim and process one target; target failures never stop the batch."""
    task = _claim_task(job_id=job_id)
    if task is None:
        return None
    if task.job.created_by is None:
        _complete_task(
            task,
            status=BackgroundTask.Status.FAILED,
            failure_code="authorization_failed",
        )
        return BackgroundTask.objects.get(pk=task.pk)
    try:
        if task.target_type == BackgroundTask.TargetType.CANDIDATE_DOCUMENT:
            _process_profile_task(task, gateway)
        else:
            _process_assessment_task(task, gateway)
    except AIGatewayError as error:
        _complete_task(
            task,
            status=BackgroundTask.Status.FAILED,
            failure_code=error.code,
        )
    except PermissionDenied:
        _complete_task(
            task,
            status=BackgroundTask.Status.FAILED,
            failure_code="authorization_failed",
        )
    except ValidationError:
        _complete_task(
            task,
            status=BackgroundTask.Status.SKIPPED,
            failure_code="application_validation",
        )
    except Exception:
        # The durable worker boundary must isolate a target without persisting
        # exception text, provider payloads, or candidate content.
        _complete_task(
            task,
            status=BackgroundTask.Status.FAILED,
            failure_code="unexpected_processing_error",
        )
    return BackgroundTask.objects.get(pk=task.pk)


def retry_background_job(*, job: BackgroundJob, user: User) -> int:
    """Explicitly requeue exceptions; successful work remains reusable."""
    require_organization_object_access(user, job)
    with transaction.atomic():
        job = BackgroundJob.objects.select_for_update().get(pk=job.pk)
        count = job.tasks.filter(
            status__in=[BackgroundTask.Status.SKIPPED, BackgroundTask.Status.FAILED]
        ).update(
            status=BackgroundTask.Status.QUEUED,
            failure_code="",
            lease_expires_at=None,
            completed_at=None,
            updated_at=timezone.now(),
        )
        if count:
            BackgroundJob.objects.filter(pk=job.pk).update(
                status=BackgroundJob.Status.QUEUED,
                skipped_count=0,
                failed_count=0,
                completed_at=None,
                updated_at=timezone.now(),
            )
    return count
