"""Python AI Toolkit v1.0.0 adapter for the application gateway contract."""

from collections.abc import Callable
from typing import Protocol, TypeVar, cast

from ai.exceptions import (
    AIConfigurationError,
    AIError,
    AIJSONParseError,
    AIProviderError,
    AISchemaValidationError,
)
from ai.integrations.django import get_ai_client
from ai.schemas import AIResult
from django.conf import settings
from pydantic import BaseModel

from ai_gateway.contracts import (
    AIGatewayConfigurationError,
    AIGatewayError,
    AIGatewayInvalidResponseError,
    AIGatewayMetadata,
    AIGatewayResult,
    AIGatewayTokenUsage,
    AIGatewayUnavailableError,
    validate_structured_request,
)

StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)


def _explicit_cost_rates_are_configured() -> bool:
    """Trust toolkit cost estimates only when both operator rates are explicit."""
    toolkit_settings = getattr(settings, "AI_TOOLKIT", {})
    input_rate = toolkit_settings.get("input_cost_per_1m_tokens")
    output_rate = toolkit_settings.get("output_cost_per_1m_tokens")
    return bool(input_rate and output_rate)


class StructuredToolkitClient(Protocol):
    """Small part of AIClient used by this adapter."""

    def ask(
        self,
        prompt: str,
        response_type: type[StructuredOutput],
    ) -> AIResult[StructuredOutput]: ...


class ToolkitAIGateway:
    """Translate toolkit results and failures into application-owned types."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], StructuredToolkitClient] = get_ai_client,
    ) -> None:
        self._client_factory = client_factory
        self._client: StructuredToolkitClient | None = None

    def request_structured(
        self,
        *,
        prompt: str,
        response_type: type[StructuredOutput],
    ) -> AIGatewayResult[StructuredOutput]:
        normalized_prompt = validate_structured_request(
            prompt=prompt,
            response_type=response_type,
        )

        try:
            result = self._get_client().ask(normalized_prompt, response_type)
        except AIConfigurationError:
            raise AIGatewayConfigurationError() from None
        except AIProviderError:
            raise AIGatewayUnavailableError() from None
        except (AIJSONParseError, AISchemaValidationError):
            raise AIGatewayInvalidResponseError() from None
        except AIError:
            raise AIGatewayError() from None

        return self._translate_result(result)

    def _get_client(self) -> StructuredToolkitClient:
        if self._client is None:
            try:
                self._client = self._client_factory()
            except AIConfigurationError:
                raise AIGatewayConfigurationError() from None
            except AIError:
                raise AIGatewayError() from None

        return self._client

    @staticmethod
    def _translate_result(
        result: AIResult[StructuredOutput],
    ) -> AIGatewayResult[StructuredOutput]:
        token_usage = None
        if result.token_usage is not None:
            token_usage = AIGatewayTokenUsage(
                input_tokens=result.token_usage.input_tokens,
                output_tokens=result.token_usage.output_tokens,
                total_tokens=result.token_usage.total_tokens,
            )

        return AIGatewayResult(
            data=cast(StructuredOutput, result.data),
            metadata=AIGatewayMetadata(
                request_id=result.request_id,
                model=result.model,
                duration_ms=result.duration_ms,
                retries_used=result.retries_used,
                token_usage=token_usage,
                estimated_cost_usd=(
                    result.estimated_cost_usd
                    if _explicit_cost_rates_are_configured()
                    else None
                ),
            ),
        )
