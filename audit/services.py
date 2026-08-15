from decimal import Decimal, InvalidOperation
from math import isfinite

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from ai_gateway import AIGatewayError, AIGatewayMetadata
from audit.models import AIUsageEvent, AuditEvent
from organizations.models import Organization
from organizations.permissions import require_organization_access

APPLICATION_VALIDATION_FAILURE = "ai_application_validation"
KNOWN_GATEWAY_FAILURE_CODES = {
    "ai_configuration_error",
    "ai_invalid_response",
    "ai_request_failed",
    "ai_service_unavailable",
}


def record_audit_event(
    *,
    organization: Organization,
    actor: User | None,
    action: str,
    object_type: str,
    object_id: int,
    system: bool = False,
) -> AuditEvent:
    """Record one minimized event without copying domain text or identity."""
    if actor is not None:
        require_organization_access(actor, organization)
    elif not system:
        raise ValidationError("Actorless audit events must be system-generated.")
    return AuditEvent.objects.create(
        organization=organization,
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=object_id,
    )


def start_ai_usage_event(
    *,
    organization: Organization,
    actor: User,
    workflow: str,
    target_type: str,
    target_id: int,
) -> AIUsageEvent:
    """Record one attempt only after domain preconditions have passed."""
    require_organization_access(actor, organization)
    return AIUsageEvent.objects.create(
        organization=organization,
        actor=actor,
        workflow=workflow,
        target_type=target_type,
        target_id=target_id,
    )


def _bounded_text(value: object, *, maximum: int = 255) -> str:
    return str(value).strip()[:maximum]


def _nonnegative_integer(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _nonnegative_decimal(value: object, *, places: int) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, float) and not isfinite(value):
        return None
    try:
        converted = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not converted.is_finite() or converted < 0:
        return None
    try:
        return converted.quantize(Decimal(1).scaleb(-places))
    except InvalidOperation:
        return None


def _apply_metadata(event: AIUsageEvent, metadata: AIGatewayMetadata | None) -> None:
    if metadata is None:
        return
    event.provider_request_id = _bounded_text(metadata.request_id)
    event.model = _bounded_text(metadata.model)
    event.duration_ms = _nonnegative_decimal(metadata.duration_ms, places=3)
    event.retries_used = _nonnegative_integer(metadata.retries_used) or 0
    event.estimated_cost_usd = _nonnegative_decimal(
        metadata.estimated_cost_usd,
        places=9,
    )
    if metadata.token_usage is not None:
        event.input_tokens = _nonnegative_integer(metadata.token_usage.input_tokens)
        event.output_tokens = _nonnegative_integer(metadata.token_usage.output_tokens)
        event.total_tokens = _nonnegative_integer(metadata.token_usage.total_tokens)


@transaction.atomic
def complete_ai_usage_success(
    *,
    event: AIUsageEvent,
    metadata: AIGatewayMetadata,
    result_type: str,
    result_id: int,
) -> AIUsageEvent:
    event = AIUsageEvent.objects.select_for_update().get(pk=event.pk)
    if event.status != AIUsageEvent.Status.PENDING:
        raise ValidationError("This AI usage event is already complete.")
    event.status = AIUsageEvent.Status.SUCCEEDED
    event.result_type = result_type
    event.result_id = result_id
    event.completed_at = timezone.now()
    _apply_metadata(event, metadata)
    event.save()
    return event


@transaction.atomic
def complete_ai_usage_failure(
    *,
    event: AIUsageEvent,
    error: AIGatewayError | ValidationError,
    metadata: AIGatewayMetadata | None = None,
) -> AIUsageEvent:
    event = AIUsageEvent.objects.select_for_update().get(pk=event.pk)
    if event.status != AIUsageEvent.Status.PENDING:
        raise ValidationError("This AI usage event is already complete.")
    event.status = AIUsageEvent.Status.FAILED
    event.completed_at = timezone.now()
    _apply_metadata(event, metadata)
    if isinstance(error, AIGatewayError):
        event.failure_stage = AIUsageEvent.FailureStage.GATEWAY
        event.failure_code = (
            error.code
            if error.code in KNOWN_GATEWAY_FAILURE_CODES
            else "ai_request_failed"
        )
    else:
        event.failure_stage = AIUsageEvent.FailureStage.APPLICATION
        event.failure_code = APPLICATION_VALIDATION_FAILURE
    event.save()
    return event
