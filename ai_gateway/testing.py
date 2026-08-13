"""Reusable provider-free gateway test double for application service tests."""

from collections.abc import Callable
from decimal import Decimal
from typing import NamedTuple, cast

from pydantic import BaseModel

from ai_gateway.contracts import (
    AIGatewayMetadata,
    AIGatewayResult,
    AIGatewayTokenUsage,
    StructuredOutput,
    validate_structured_request,
)

ResponseFactory = Callable[[str, type[BaseModel]], BaseModel]


class FakeAIGatewayCall(NamedTuple):
    """One normalized fake request, tuple-compatible with earlier test helpers."""

    prompt: str
    response_type: type[BaseModel]


def fake_gateway_metadata() -> AIGatewayMetadata:
    """Return deterministic safe metadata without provider or network access."""
    return AIGatewayMetadata(
        request_id="fake-request-1",
        model="fake-model",
        duration_ms=1.0,
        retries_used=0,
        token_usage=AIGatewayTokenUsage(
            input_tokens=1,
            output_tokens=1,
            total_tokens=2,
        ),
        estimated_cost_usd=Decimal("0"),
    )


class FakeAIGateway:
    """Return configured validated output or raise a configured bounded error."""

    def __init__(
        self,
        *,
        response: BaseModel | None = None,
        responder: ResponseFactory | None = None,
        error: Exception | None = None,
        metadata: AIGatewayMetadata | None = None,
    ) -> None:
        if response is not None and responder is not None:
            raise ValueError("Configure either a response or responder, not both.")
        self.response = response
        self.responder = responder
        self.error = error
        self.metadata = metadata or fake_gateway_metadata()
        self.calls: list[FakeAIGatewayCall] = []

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
        self.calls.append(
            FakeAIGatewayCall(
                prompt=normalized_prompt,
                response_type=response_type,
            )
        )
        if self.error is not None:
            raise self.error
        output = (
            self.responder(normalized_prompt, response_type)
            if self.responder is not None
            else self.response
        )
        if not isinstance(output, response_type):
            raise TypeError(
                "The fake response must be an instance of the requested response type."
            )
        return AIGatewayResult(
            data=cast(StructuredOutput, output),
            metadata=self.metadata,
        )
