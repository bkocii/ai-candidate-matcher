from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from audit.models import AIUsageEvent
from organizations.models import Organization
from organizations.permissions import require_organization_admin

ALL_WORKFLOWS = "all"
DEFAULT_REPORTING_PERIOD = "30"
REPORTING_PERIODS = (
    ("7", "Past 7 days"),
    ("30", "Past 30 days"),
    ("90", "Past 90 days"),
    ("all", "All recorded time"),
)
REPORTING_PERIOD_DAYS = {"7": 7, "30": 30, "90": 90, "all": None}
FAILURE_CODE_LABELS = {
    "ai_configuration_error": "AI configuration unavailable",
    "ai_invalid_response": "AI output could not be processed",
    "ai_request_failed": "AI request failed",
    "ai_service_unavailable": "AI service unavailable",
    "ai_application_validation": "AI output did not pass safety checks",
}
FAILURE_STAGE_LABELS = {
    AIUsageEvent.FailureStage.GATEWAY: "AI request",
    AIUsageEvent.FailureStage.APPLICATION: "After AI response",
}


def format_count(value: int) -> str:
    return f"{value:,}"


def format_cost_usd(value: Decimal) -> str:
    if value == 0:
        return "$0.00"
    if value < Decimal("0.01"):
        return "< $0.01"
    return f"${value:,.2f}"


def format_duration_ms(value: Decimal) -> str:
    if value < Decimal("1000"):
        return f"{value.quantize(Decimal('1'), rounding=ROUND_HALF_UP):,} ms"
    seconds = (value / Decimal("1000")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{seconds:,} s"


@dataclass(frozen=True)
class UsageMetrics:
    attempts: int
    succeeded: int
    failed: int
    pending: int
    completed: int
    success_rate: Decimal | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_token_metadata_count: int
    output_token_metadata_count: int
    token_metadata_count: int
    cost_usd: Decimal
    cost_metadata_count: int
    average_duration_ms: Decimal | None
    duration_metadata_count: int
    retries_used: int
    retried_attempts: int
    retry_metadata_count: int
    model_metadata_count: int

    @property
    def missing_token_metadata_count(self) -> int:
        return self.attempts - self.token_metadata_count

    @property
    def missing_input_token_metadata_count(self) -> int:
        return self.attempts - self.input_token_metadata_count

    @property
    def missing_output_token_metadata_count(self) -> int:
        return self.attempts - self.output_token_metadata_count

    @property
    def missing_cost_metadata_count(self) -> int:
        return self.attempts - self.cost_metadata_count

    @property
    def missing_duration_metadata_count(self) -> int:
        return self.attempts - self.duration_metadata_count

    @property
    def missing_retry_metadata_count(self) -> int:
        return self.attempts - self.retry_metadata_count

    @property
    def missing_model_metadata_count(self) -> int:
        return self.attempts - self.model_metadata_count

    @property
    def input_tokens_display(self) -> str:
        return format_count(self.input_tokens)

    @property
    def output_tokens_display(self) -> str:
        return format_count(self.output_tokens)

    @property
    def total_tokens_display(self) -> str:
        return format_count(self.total_tokens)

    @property
    def cost_display(self) -> str:
        return format_cost_usd(self.cost_usd)

    @property
    def average_duration_display(self) -> str:
        if self.average_duration_ms is None:
            return "—"
        return format_duration_ms(self.average_duration_ms)


@dataclass(frozen=True)
class UsageBreakdownRow:
    key: str
    label: str
    metrics: UsageMetrics


@dataclass(frozen=True)
class FailureBreakdownRow:
    stage: str
    label: str
    count: int


@dataclass(frozen=True)
class DailyUsageRow:
    day: object
    attempts: int
    succeeded: int
    failed: int
    total_tokens: int
    token_metadata_count: int
    cost_usd: Decimal
    cost_metadata_count: int

    @property
    def total_tokens_display(self) -> str:
        return format_count(self.total_tokens)

    @property
    def cost_display(self) -> str:
        return format_cost_usd(self.cost_usd)


@dataclass(frozen=True)
class AIUsageReport:
    period: str
    period_label: str
    workflow: str
    workflow_label: str
    metrics: UsageMetrics
    stale_pending_count: int
    workflow_rows: tuple[UsageBreakdownRow, ...]
    model_rows: tuple[UsageBreakdownRow, ...]
    failure_rows: tuple[FailureBreakdownRow, ...]
    daily_rows: tuple[DailyUsageRow, ...]


def normalize_reporting_period(value: str | None) -> str:
    return value if value in REPORTING_PERIOD_DAYS else DEFAULT_REPORTING_PERIOD


def normalize_reporting_workflow(value: str | None) -> str:
    valid = {choice for choice, _ in AIUsageEvent.Workflow.choices}
    return value if value in valid else ALL_WORKFLOWS


def _rate(numerator: int, denominator: int) -> Decimal | None:
    if denominator == 0:
        return None
    return (Decimal(numerator) * Decimal("100") / Decimal(denominator)).quantize(
        Decimal("0.1"),
        rounding=ROUND_HALF_UP,
    )


def _int(value) -> int:
    return int(value or 0)


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def _metrics(queryset) -> UsageMetrics:
    values = queryset.aggregate(
        attempts=Count("id"),
        succeeded=Count("id", filter=Q(status=AIUsageEvent.Status.SUCCEEDED)),
        failed=Count("id", filter=Q(status=AIUsageEvent.Status.FAILED)),
        pending=Count("id", filter=Q(status=AIUsageEvent.Status.PENDING)),
        input_token_sum=Sum("input_tokens"),
        output_token_sum=Sum("output_tokens"),
        total_token_sum=Sum("total_tokens"),
        input_token_metadata_count=Count("id", filter=Q(input_tokens__isnull=False)),
        output_token_metadata_count=Count("id", filter=Q(output_tokens__isnull=False)),
        token_metadata_count=Count("id", filter=Q(total_tokens__isnull=False)),
        cost_sum=Sum("estimated_cost_usd"),
        cost_metadata_count=Count("id", filter=Q(estimated_cost_usd__isnull=False)),
        duration_average=Avg("duration_ms"),
        duration_metadata_count=Count("id", filter=Q(duration_ms__isnull=False)),
        retry_sum=Sum("retries_used", filter=~Q(provider_request_id="")),
        retried_attempts=Count(
            "id",
            filter=~Q(provider_request_id="") & Q(retries_used__gt=0),
        ),
        retry_metadata_count=Count("id", filter=~Q(provider_request_id="")),
        model_metadata_count=Count("id", filter=~Q(model="")),
    )
    succeeded = _int(values["succeeded"])
    failed = _int(values["failed"])
    completed = succeeded + failed
    average_duration = values["duration_average"]
    return UsageMetrics(
        attempts=_int(values["attempts"]),
        succeeded=succeeded,
        failed=failed,
        pending=_int(values["pending"]),
        completed=completed,
        success_rate=_rate(succeeded, completed),
        input_tokens=_int(values["input_token_sum"]),
        output_tokens=_int(values["output_token_sum"]),
        total_tokens=_int(values["total_token_sum"]),
        input_token_metadata_count=_int(values["input_token_metadata_count"]),
        output_token_metadata_count=_int(values["output_token_metadata_count"]),
        token_metadata_count=_int(values["token_metadata_count"]),
        cost_usd=_decimal(values["cost_sum"]),
        cost_metadata_count=_int(values["cost_metadata_count"]),
        average_duration_ms=(
            _decimal(average_duration) if average_duration is not None else None
        ),
        duration_metadata_count=_int(values["duration_metadata_count"]),
        retries_used=_int(values["retry_sum"]),
        retried_attempts=_int(values["retried_attempts"]),
        retry_metadata_count=_int(values["retry_metadata_count"]),
        model_metadata_count=_int(values["model_metadata_count"]),
    )


def _breakdown_rows(queryset, *, field: str, labels: dict[str, str]):
    keys = sorted(
        {
            key
            for key in queryset.order_by().values_list(field, flat=True).distinct()
            if key
        },
        key=lambda key: labels.get(key, key).casefold(),
    )
    return tuple(
        UsageBreakdownRow(
            key=key,
            label=labels.get(key, key),
            metrics=_metrics(queryset.filter(**{field: key})),
        )
        for key in keys
    )


def build_ai_usage_report(
    *,
    organization: Organization,
    user,
    period: str | None = None,
    workflow: str | None = None,
    now=None,
) -> AIUsageReport:
    """Aggregate only minimized operational metadata for one organization."""
    require_organization_admin(user, organization)
    selected_period = normalize_reporting_period(period)
    selected_workflow = normalize_reporting_workflow(workflow)
    current_time = now or timezone.now()
    queryset = AIUsageEvent.objects.for_organization(organization)
    period_days = REPORTING_PERIOD_DAYS[selected_period]
    if period_days is not None:
        queryset = queryset.filter(
            started_at__gte=current_time - timedelta(days=period_days)
        )
    if selected_workflow != ALL_WORKFLOWS:
        queryset = queryset.filter(workflow=selected_workflow)

    workflow_labels = dict(AIUsageEvent.Workflow.choices)
    failure_rows = tuple(
        FailureBreakdownRow(
            stage=FAILURE_STAGE_LABELS.get(item["failure_stage"], "Recorded failure"),
            label=FAILURE_CODE_LABELS.get(
                item["failure_code"], "Other recorded failure"
            ),
            count=item["count"],
        )
        for item in queryset.filter(status=AIUsageEvent.Status.FAILED)
        .order_by("failure_stage", "failure_code")
        .values("failure_stage", "failure_code")
        .annotate(count=Count("id"))
    )
    daily_values = list(
        queryset.annotate(day=TruncDate("started_at"))
        .values("day")
        .annotate(
            attempts=Count("id"),
            succeeded=Count("id", filter=Q(status=AIUsageEvent.Status.SUCCEEDED)),
            failed=Count("id", filter=Q(status=AIUsageEvent.Status.FAILED)),
            total_token_sum=Sum("total_tokens"),
            token_metadata_count=Count("id", filter=Q(total_tokens__isnull=False)),
            cost_sum=Sum("estimated_cost_usd"),
            cost_metadata_count=Count("id", filter=Q(estimated_cost_usd__isnull=False)),
        )
        .order_by("day")
    )[-90:]
    return AIUsageReport(
        period=selected_period,
        period_label=dict(REPORTING_PERIODS)[selected_period],
        workflow=selected_workflow,
        workflow_label=(
            workflow_labels[selected_workflow]
            if selected_workflow != ALL_WORKFLOWS
            else "All workflows"
        ),
        metrics=_metrics(queryset),
        stale_pending_count=queryset.filter(
            status=AIUsageEvent.Status.PENDING,
            started_at__lt=current_time - timedelta(minutes=15),
        ).count(),
        workflow_rows=_breakdown_rows(
            queryset,
            field="workflow",
            labels=workflow_labels,
        ),
        model_rows=_breakdown_rows(
            queryset.filter(~Q(model="")),
            field="model",
            labels={},
        ),
        failure_rows=failure_rows,
        daily_rows=tuple(
            DailyUsageRow(
                day=item["day"],
                attempts=item["attempts"],
                succeeded=item["succeeded"],
                failed=item["failed"],
                total_tokens=_int(item["total_token_sum"]),
                token_metadata_count=_int(item["token_metadata_count"]),
                cost_usd=_decimal(item["cost_sum"]),
                cost_metadata_count=_int(item["cost_metadata_count"]),
            )
            for item in daily_values
        ),
    )
