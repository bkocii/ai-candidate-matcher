from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from organizations.models import Organization


class AIUsageEventQuerySet(models.QuerySet):
    def for_organization(self, organization: Organization):
        return self.filter(organization=organization)

    def visible_to(self, user: object):
        if not (
            getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
        ):
            return self.none()
        return self.filter(
            organization__is_active=True,
            organization__memberships__user=user,
            organization__memberships__is_active=True,
        ).distinct()


class AIUsageEvent(models.Model):
    """Safe operational record for one intentional application AI attempt."""

    class Workflow(models.TextChoices):
        VACANCY_REQUIREMENTS = "vacancy_requirements", "Vacancy requirements"
        CANDIDATE_PROFILE = "candidate_profile", "Candidate profile"
        MATCH_ASSESSMENT = "match_assessment", "Match assessment"

    class ObjectType(models.TextChoices):
        VACANCY_REQUIREMENTS = "vacancy_requirements", "Vacancy requirements"
        CANDIDATE_DOCUMENT = "candidate_document", "Candidate document"
        CANDIDATE_PROFILE = "candidate_profile", "Candidate profile"
        SHORTLIST_ENTRY = "shortlist_entry", "Shortlist entry"
        MATCH_ASSESSMENT = "match_assessment", "Match assessment"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    class FailureStage(models.TextChoices):
        GATEWAY = "gateway", "Gateway"
        APPLICATION = "application", "Application validation"

    SCHEMA_VERSION = "ai_usage_event.v1"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="ai_usage_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_usage_events",
    )
    workflow = models.CharField(max_length=40, choices=Workflow.choices)
    target_type = models.CharField(max_length=40, choices=ObjectType.choices)
    target_id = models.PositiveBigIntegerField()
    result_type = models.CharField(
        max_length=40,
        choices=ObjectType.choices,
        blank=True,
    )
    result_id = models.PositiveBigIntegerField(null=True, blank=True)
    schema_version = models.CharField(max_length=50, default=SCHEMA_VERSION)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    provider_request_id = models.CharField(max_length=255, blank=True)
    model = models.CharField(max_length=255, blank=True)
    duration_ms = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    retries_used = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveBigIntegerField(null=True, blank=True)
    output_tokens = models.PositiveBigIntegerField(null=True, blank=True)
    total_tokens = models.PositiveBigIntegerField(null=True, blank=True)
    estimated_cost_usd = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    failure_stage = models.CharField(
        max_length=20,
        choices=FailureStage.choices,
        blank=True,
    )
    failure_code = models.CharField(max_length=64, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    objects = AIUsageEventQuerySet.as_manager()

    class Meta:
        ordering = ("-started_at", "-id")
        indexes = [
            models.Index(
                fields=("organization", "workflow", "started_at"),
                name="ai_usage_org_flow_started_idx",
            ),
            models.Index(
                fields=("target_type", "target_id"),
                name="ai_usage_target_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(status="pending", completed_at__isnull=True)
                    | models.Q(
                        status__in=["succeeded", "failed"],
                        completed_at__isnull=False,
                    )
                ),
                name="ai_usage_completion_matches_status",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="failed")
                    & ~models.Q(failure_stage="")
                    & ~models.Q(failure_code="")
                    | ~models.Q(status="failed")
                    & models.Q(failure_stage="", failure_code="")
                ),
                name="ai_usage_failure_fields_match_status",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="succeeded")
                    & ~models.Q(provider_request_id="")
                    & ~models.Q(model="")
                    & ~models.Q(result_type="")
                    & models.Q(result_id__isnull=False)
                    | ~models.Q(status="succeeded")
                ),
                name="ai_usage_success_has_result_metadata",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(result_type="", result_id__isnull=True)
                    | ~models.Q(result_type="") & models.Q(result_id__isnull=False)
                ),
                name="ai_usage_result_reference_complete",
            ),
        ]

    def _completed_record_changed(self) -> bool:
        if not self.pk:
            return False
        persisted = type(self).objects.get(pk=self.pk)
        if persisted.status == self.Status.PENDING:
            return False
        fields = (
            "organization_id",
            "actor_id",
            "workflow",
            "target_type",
            "target_id",
            "result_type",
            "result_id",
            "schema_version",
            "status",
            "provider_request_id",
            "model",
            "duration_ms",
            "retries_used",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "estimated_cost_usd",
            "failure_stage",
            "failure_code",
            "completed_at",
        )
        return any(
            getattr(self, field_name) != getattr(persisted, field_name)
            for field_name in fields
        )

    def clean(self) -> None:
        super().clean()
        is_pending = self.status == self.Status.PENDING
        is_succeeded = self.status == self.Status.SUCCEEDED
        is_failed = self.status == self.Status.FAILED
        if is_pending != (self.completed_at is None):
            raise ValidationError(
                {"completed_at": "Only pending usage events omit completion time."}
            )
        if (is_failed and not (self.failure_stage and self.failure_code)) or (
            not is_failed and (self.failure_stage or self.failure_code)
        ):
            raise ValidationError(
                {"failure_code": "Failure details must match failed status."}
            )
        has_result_type = bool(self.result_type)
        has_result_id = self.result_id is not None
        if has_result_type != has_result_id:
            raise ValidationError(
                {"result_type": "Result type and ID must be recorded together."}
            )
        if not is_succeeded and has_result_type:
            raise ValidationError(
                {"result_type": "Only successful usage events reference a result."}
            )
        if is_succeeded and not (
            self.provider_request_id and self.model and has_result_type
        ):
            raise ValidationError(
                "Successful AI usage requires safe request and result metadata."
            )

    def save(self, *args, **kwargs) -> None:
        if self._completed_record_changed():
            raise ValidationError("Completed AI usage events are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.get_workflow_display()} — {self.get_status_display()}"
