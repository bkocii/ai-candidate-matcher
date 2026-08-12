"""Toolkit-neutral contracts exposed to application business services."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)


@dataclass(frozen=True)
class AIGatewayTokenUsage:
    """Provider-independent token counts available for a completed request."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class AIGatewayMetadata:
    """Safe operational metadata, with no prompt or response content."""

    request_id: str
    model: str
    duration_ms: float | None
    retries_used: int
    token_usage: AIGatewayTokenUsage | None
    estimated_cost_usd: Decimal | None


@dataclass(frozen=True)
class AIGatewayResult(Generic[StructuredOutput]):
    """Validated application output plus safe request metadata."""

    data: StructuredOutput
    metadata: AIGatewayMetadata


class AIGateway(Protocol):
    """Interface business services use for validated structured requests."""

    def request_structured(
        self,
        *,
        prompt: str,
        response_type: type[StructuredOutput],
    ) -> AIGatewayResult[StructuredOutput]: ...


class AIGatewayError(RuntimeError):
    """Base class for bounded application-facing AI failures."""

    code = "ai_request_failed"
    public_message = "The AI request could not be completed. Please try again."

    def __init__(self) -> None:
        super().__init__(self.public_message)


class AIGatewayConfigurationError(AIGatewayError):
    """AI configuration is unavailable or invalid."""

    code = "ai_configuration_error"
    public_message = "The AI service is not configured. Contact an administrator."


class AIGatewayUnavailableError(AIGatewayError):
    """The configured provider could not complete the request."""

    code = "ai_service_unavailable"
    public_message = "The AI service is temporarily unavailable. Please try again."


class AIGatewayInvalidResponseError(AIGatewayError):
    """The provider response could not satisfy the required schema."""

    code = "ai_invalid_response"
    public_message = "The AI response could not be validated. No result has been saved."
