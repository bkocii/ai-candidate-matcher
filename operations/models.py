from django.conf import settings
from django.db import models

from organizations.models import Organization


def _user_can_query_operations(user: object) -> bool:
    return bool(
        getattr(user, "is_authenticated", False) and getattr(user, "is_active", False)
    )


class BackgroundJobQuerySet(models.QuerySet):
    def for_organization(self, organization: Organization):
        return self.filter(organization=organization)

    def visible_to(self, user: object):
        if not _user_can_query_operations(user):
            return self.none()
        return self.filter(
            organization__is_active=True,
            organization__memberships__user=user,
            organization__memberships__is_active=True,
        ).distinct()


class BackgroundJob(models.Model):
    """One durable, idempotent batch request owned by an organization."""

    class Workflow(models.TextChoices):
        CANDIDATE_PROFILE_BATCH = (
            "candidate_profile_batch",
            "Candidate profile extraction",
        )
        SHORTLIST_ASSESSMENT_BATCH = (
            "shortlist_assessment_batch",
            "Whole-shortlist assessment",
        )

    class ScopeType(models.TextChoices):
        ORGANIZATION = "organization", "Organization"
        MATCH_RUN = "match_run", "Match run"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        COMPLETED_WITH_ERRORS = "completed_with_errors", "Completed with exceptions"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="background_jobs",
    )
    workflow = models.CharField(max_length=40, choices=Workflow.choices)
    scope_type = models.CharField(max_length=20, choices=ScopeType.choices)
    scope_id = models.PositiveBigIntegerField()
    idempotency_key = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    total_count = models.PositiveIntegerField(default=0)
    succeeded_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    schema_version = models.CharField(max_length=50, default="background_job.v1")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_background_jobs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BackgroundJobQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("organization", "status"),
                name="background_job_org_status_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    workflow__in=[
                        "candidate_profile_batch",
                        "shortlist_assessment_batch",
                    ]
                ),
                name="background_job_valid_workflow",
            ),
            models.CheckConstraint(
                condition=models.Q(scope_type__in=["organization", "match_run"]),
                name="background_job_valid_scope",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "queued",
                        "running",
                        "succeeded",
                        "completed_with_errors",
                    ]
                ),
                name="background_job_valid_status",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_workflow_display()} job {self.pk or 'new'}"


class BackgroundTask(models.Model):
    """One isolated, resumable target inside a background job."""

    class TargetType(models.TextChoices):
        CANDIDATE_DOCUMENT = "candidate_document", "Candidate document"
        SHORTLIST_ENTRY = "shortlist_entry", "Shortlist entry"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        SKIPPED = "skipped", "Needs attention"
        FAILED = "failed", "Failed"

    class ResultType(models.TextChoices):
        CANDIDATE_PROFILE = "candidate_profile", "Candidate profile"
        MATCH_ASSESSMENT = "match_assessment", "Match assessment"

    class Outcome(models.TextChoices):
        CREATED = "created", "Created"
        REUSED = "reused", "Reused"

    job = models.ForeignKey(
        BackgroundJob,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    target_type = models.CharField(max_length=30, choices=TargetType.choices)
    target_id = models.PositiveBigIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    result_type = models.CharField(
        max_length=30,
        choices=ResultType.choices,
        blank=True,
    )
    result_id = models.PositiveBigIntegerField(null=True, blank=True)
    outcome = models.CharField(max_length=20, choices=Outcome.choices, blank=True)
    failure_code = models.CharField(max_length=50, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=("job", "target_type", "target_id"),
                name="unique_background_target_per_job",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    target_type__in=["candidate_document", "shortlist_entry"]
                ),
                name="background_task_valid_target",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["queued", "running", "succeeded", "skipped", "failed"]
                ),
                name="background_task_valid_status",
            ),
        ]
        indexes = [
            models.Index(
                fields=("status", "lease_expires_at", "id"),
                name="background_task_claim_idx",
            )
        ]

    @property
    def organization(self) -> Organization:
        return self.job.organization

    def __str__(self) -> str:
        return f"{self.get_target_type_display()} {self.target_id}"
