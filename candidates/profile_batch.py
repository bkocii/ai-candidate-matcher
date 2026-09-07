import hashlib
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import User
from candidates.ai_extraction import confirm_candidate_profile
from candidates.models import (
    Candidate,
    CandidateIntakeBatch,
    CandidateIntakeItem,
    CandidateProfile,
)
from candidates.profile_review import candidate_profile_conflicts
from operations.models import BackgroundJob, BackgroundTask
from organizations.permissions import require_organization_object_access

PROFILE_PROCESSING = "processing"
PROFILE_READY = "ready"
PROFILE_NEEDS_REVIEW = "needs_review"
PROFILE_CONFIRMED = "confirmed"


@dataclass(frozen=True)
class IntakeProfileReviewRow:
    item: CandidateIntakeItem
    profile: CandidateProfile | None
    status: str
    reason: str

    @property
    def eligible(self) -> bool:
        return self.status == PROFILE_READY

    @property
    def status_label(self) -> str:
        return {
            PROFILE_PROCESSING: "Processing",
            PROFILE_READY: "Ready to confirm",
            PROFILE_NEEDS_REVIEW: "Needs individual review",
            PROFILE_CONFIRMED: "Already confirmed",
        }[self.status]


@dataclass(frozen=True)
class IntakeProfileReview:
    rows: tuple[IntakeProfileReviewRow, ...]

    @property
    def eligible_rows(self) -> tuple[IntakeProfileReviewRow, ...]:
        return tuple(row for row in self.rows if row.eligible)

    @property
    def excluded_rows(self) -> tuple[IntakeProfileReviewRow, ...]:
        return self.needs_review_rows

    @property
    def processing_rows(self) -> tuple[IntakeProfileReviewRow, ...]:
        return tuple(row for row in self.rows if row.status == PROFILE_PROCESSING)

    @property
    def needs_review_rows(self) -> tuple[IntakeProfileReviewRow, ...]:
        return tuple(row for row in self.rows if row.status == PROFILE_NEEDS_REVIEW)

    @property
    def confirmed_rows(self) -> tuple[IntakeProfileReviewRow, ...]:
        return tuple(row for row in self.rows if row.status == PROFILE_CONFIRMED)


def _source_text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def review_intake_profiles(
    *, batch: CandidateIntakeBatch, user: User
) -> IntakeProfileReview:
    require_organization_object_access(user, batch)
    items = tuple(
        CandidateIntakeItem.objects.for_organization(batch.organization)
        .filter(batch=batch, status=CandidateIntakeItem.Status.CREATED)
        .select_related("candidate", "accepted_document")
        .prefetch_related("accepted_document__profile_versions")
        .order_by("id")
    )
    document_ids = [
        item.accepted_document_id for item in items if item.accepted_document_id
    ]
    latest_task_by_document: dict[int, BackgroundTask] = {}
    for task in (
        BackgroundTask.objects.filter(
            job__organization=batch.organization,
            job__workflow=BackgroundJob.Workflow.CANDIDATE_PROFILE_BATCH,
            target_type=BackgroundTask.TargetType.CANDIDATE_DOCUMENT,
            target_id__in=document_ids,
        )
        .select_related("job")
        .order_by("id")
    ):
        latest_task_by_document[task.target_id] = task

    rows: list[IntakeProfileReviewRow] = []
    for item in items:
        candidate = item.candidate
        document = item.accepted_document
        if candidate is None or document is None:
            rows.append(
                IntakeProfileReviewRow(
                    item=item,
                    profile=None,
                    status=PROFILE_NEEDS_REVIEW,
                    reason="No exact accepted CV is linked to this intake record.",
                )
            )
            continue
        profiles = list(document.profile_versions.all())
        latest = max(profiles, key=lambda profile: profile.version, default=None)
        if latest is None:
            task = latest_task_by_document.get(document.pk)
            if task and task.status in {
                BackgroundTask.Status.QUEUED,
                BackgroundTask.Status.RUNNING,
            }:
                reason = (
                    "Profile creation is queued and waiting for the background worker."
                    if task.status == BackgroundTask.Status.QUEUED
                    else "The background worker is creating this profile draft."
                )
                status = PROFILE_PROCESSING
            elif task and task.status in {
                BackgroundTask.Status.SKIPPED,
                BackgroundTask.Status.FAILED,
            }:
                reason = (
                    "Profile creation needs attention. Review the background job "
                    "before trying again."
                )
                status = PROFILE_NEEDS_REVIEW
            else:
                reason = (
                    "No profile draft exists yet. Queue profile creation for this CV."
                )
                status = PROFILE_NEEDS_REVIEW
            rows.append(
                IntakeProfileReviewRow(
                    item=item,
                    profile=None,
                    status=status,
                    reason=reason,
                )
            )
            continue
        if latest.status == CandidateProfile.Status.CONFIRMED:
            rows.append(
                IntakeProfileReviewRow(
                    item=item,
                    profile=latest,
                    status=PROFILE_CONFIRMED,
                    reason="This exact profile is already confirmed.",
                )
            )
            continue
        if candidate.status != Candidate.Status.ACTIVE:
            rows.append(
                IntakeProfileReviewRow(
                    item=item,
                    profile=latest,
                    status=PROFILE_NEEDS_REVIEW,
                    reason="The candidate is not active.",
                )
            )
            continue
        if latest.ambiguities:
            rows.append(
                IntakeProfileReviewRow(
                    item=item,
                    profile=latest,
                    status=PROFILE_NEEDS_REVIEW,
                    reason=(
                        "The profile contains ambiguities requiring individual review."
                    ),
                )
            )
            continue
        if latest.excluded_sensitive_content_detected:
            rows.append(
                IntakeProfileReviewRow(
                    item=item,
                    profile=latest,
                    status=PROFILE_NEEDS_REVIEW,
                    reason=(
                        "Sensitive-prefixed source content was removed; review this "
                        "profile individually."
                    ),
                )
            )
            continue
        conflicts = candidate_profile_conflicts(candidate=candidate, profile=latest)
        if conflicts:
            rows.append(
                IntakeProfileReviewRow(
                    item=item,
                    profile=latest,
                    status=PROFILE_NEEDS_REVIEW,
                    reason=" ".join(conflict.message for conflict in conflicts),
                )
            )
            continue
        if (
            document.deleted_at is not None
            or document.sha256 != latest.source_document_sha256
            or _source_text_sha256(document.extracted_text) != latest.source_text_sha256
        ):
            rows.append(
                IntakeProfileReviewRow(
                    item=item,
                    profile=latest,
                    status=PROFILE_NEEDS_REVIEW,
                    reason="The source CV changed after extraction.",
                )
            )
            continue
        newer_confirmed = candidate.profile_versions.filter(
            status=CandidateProfile.Status.CONFIRMED,
            version__gt=latest.version,
        ).exists()
        if newer_confirmed:
            rows.append(
                IntakeProfileReviewRow(
                    item=item,
                    profile=latest,
                    status=PROFILE_CONFIRMED,
                    reason="A newer candidate profile is already confirmed.",
                )
            )
            continue
        rows.append(
            IntakeProfileReviewRow(
                item=item,
                profile=latest,
                status=PROFILE_READY,
                reason="Evidence validated with no recorded review exception.",
            )
        )
    return IntakeProfileReview(rows=tuple(rows))


@transaction.atomic
def confirm_all_eligible_intake_profiles(
    *, batch: CandidateIntakeBatch, user: User
) -> tuple[CandidateProfile, ...]:
    require_organization_object_access(user, batch)
    CandidateIntakeBatch.objects.select_for_update().get(pk=batch.pk)
    review = review_intake_profiles(batch=batch, user=user)
    eligible = review.eligible_rows
    if not eligible:
        raise ValidationError("No profile drafts are ready for confirmation.")

    confirmed: list[CandidateProfile] = []
    for row in eligible:
        confirmed.append(confirm_candidate_profile(profile=row.profile, user=user))
    return tuple(confirmed)
