from decimal import Decimal

import pytest
from ai.exceptions import (
    AIConfigurationError,
    AIError,
    AIJSONParseError,
    AIProviderError,
    AISchemaValidationError,
)
from ai.schemas import AIResult, TokenUsage
from django.test import override_settings
from pydantic import BaseModel

from ai_gateway import (
    AIGatewayConfigurationError,
    AIGatewayError,
    AIGatewayInvalidResponseError,
    AIGatewayUnavailableError,
    ToolkitAIGateway,
    get_ai_gateway,
)


class ExampleOutput(BaseModel):
    summary: str


class RecordingClient:
    def __init__(
        self,
        *,
        result: AIResult[ExampleOutput] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or successful_toolkit_result()
        self.error = error
        self.calls: list[tuple[str, type[BaseModel]]] = []

    def ask(
        self,
        prompt: str,
        response_type: type[BaseModel],
    ) -> AIResult[ExampleOutput]:
        self.calls.append((prompt, response_type))
        if self.error is not None:
            raise self.error
        return self.result


class ConfiguredFakeGateway:
    def request_structured(self, *, prompt, response_type):
        return (prompt, response_type)


class InvalidGateway:
    pass


def exploding_gateway_factory():
    raise RuntimeError("internal factory detail")


def successful_toolkit_result() -> AIResult[ExampleOutput]:
    return AIResult(
        data=ExampleOutput(summary="Evidence-based result"),
        model="test-model",
        raw_response='{"summary":"Evidence-based result"}',
        original_raw_response='{"summary":"Evidence-based result"}',
        duration_ms=125.5,
        retries_used=1,
        token_usage=TokenUsage(
            input_tokens=20,
            output_tokens=8,
            total_tokens=28,
        ),
        estimated_cost_usd=Decimal("0.00042"),
        request_id="request-123",
    )


def test_toolkit_gateway_returns_application_owned_result_and_metadata() -> None:
    client = RecordingClient()
    gateway = ToolkitAIGateway(client_factory=lambda: client)

    result = gateway.request_structured(
        prompt="  Analyze only supplied evidence.  ",
        response_type=ExampleOutput,
    )

    assert result.data == ExampleOutput(summary="Evidence-based result")
    assert result.metadata.request_id == "request-123"
    assert result.metadata.model == "test-model"
    assert result.metadata.duration_ms == 125.5
    assert result.metadata.retries_used == 1
    assert result.metadata.estimated_cost_usd == Decimal("0.00042")
    assert result.metadata.token_usage is not None
    assert result.metadata.token_usage.input_tokens == 20
    assert result.metadata.token_usage.output_tokens == 8
    assert result.metadata.token_usage.total_tokens == 28
    assert client.calls == [("Analyze only supplied evidence.", ExampleOutput)]


def test_gateway_result_does_not_expose_toolkit_raw_response() -> None:
    raw_response = "PRIVATE-RAW-RESPONSE"
    client = RecordingClient(result=successful_toolkit_result())
    client.result.raw_response = raw_response
    gateway = ToolkitAIGateway(client_factory=lambda: client)

    result = gateway.request_structured(
        prompt="Private prompt",
        response_type=ExampleOutput,
    )

    assert not hasattr(result, "raw_response")
    assert raw_response not in repr(result)


def test_toolkit_client_is_built_lazily_and_reused_by_gateway_instance() -> None:
    client = RecordingClient()
    factory_calls = 0

    def build_client() -> RecordingClient:
        nonlocal factory_calls
        factory_calls += 1
        return client

    gateway = ToolkitAIGateway(client_factory=build_client)

    assert factory_calls == 0
    gateway.request_structured(prompt="First", response_type=ExampleOutput)
    gateway.request_structured(prompt="Second", response_type=ExampleOutput)

    assert factory_calls == 1
    assert len(client.calls) == 2


def test_gateway_supports_results_without_optional_metadata() -> None:
    toolkit_result = successful_toolkit_result()
    toolkit_result.duration_ms = None
    toolkit_result.token_usage = None
    toolkit_result.estimated_cost_usd = None
    gateway = ToolkitAIGateway(
        client_factory=lambda: RecordingClient(result=toolkit_result)
    )

    result = gateway.request_structured(
        prompt="Analyze",
        response_type=ExampleOutput,
    )

    assert result.metadata.duration_ms is None
    assert result.metadata.token_usage is None
    assert result.metadata.estimated_cost_usd is None


@pytest.mark.parametrize(
    ("toolkit_error", "gateway_error", "expected_code"),
    [
        (
            AIConfigurationError("secret configuration detail"),
            AIGatewayConfigurationError,
            "ai_configuration_error",
        ),
        (
            AIProviderError("secret provider detail"),
            AIGatewayUnavailableError,
            "ai_service_unavailable",
        ),
        (
            AIJSONParseError("private raw response"),
            AIGatewayInvalidResponseError,
            "ai_invalid_response",
        ),
        (
            AISchemaValidationError("private validation response"),
            AIGatewayInvalidResponseError,
            "ai_invalid_response",
        ),
        (
            AIError("unexpected toolkit detail"),
            AIGatewayError,
            "ai_request_failed",
        ),
    ],
)
def test_toolkit_failures_are_translated_to_bounded_application_errors(
    toolkit_error: AIError,
    gateway_error: type[AIGatewayError],
    expected_code: str,
) -> None:
    client = RecordingClient(error=toolkit_error)
    gateway = ToolkitAIGateway(client_factory=lambda: client)

    with pytest.raises(gateway_error) as captured:
        gateway.request_structured(
            prompt="Sensitive prompt",
            response_type=ExampleOutput,
        )

    assert captured.value.code == expected_code
    assert str(toolkit_error) not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__suppress_context__ is True


@pytest.mark.parametrize(
    ("factory_error", "gateway_error"),
    [
        (AIConfigurationError("missing secret key"), AIGatewayConfigurationError),
        (AIError("toolkit construction detail"), AIGatewayError),
    ],
)
def test_toolkit_client_construction_failures_are_translated(
    factory_error: AIError,
    gateway_error: type[AIGatewayError],
) -> None:
    def build_client():
        raise factory_error

    gateway = ToolkitAIGateway(client_factory=build_client)

    with pytest.raises(gateway_error) as captured:
        gateway.request_structured(prompt="Analyze", response_type=ExampleOutput)

    assert str(factory_error) not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__suppress_context__ is True


def test_non_toolkit_programming_failure_is_not_hidden() -> None:
    programming_error = RuntimeError("application programming error")
    gateway = ToolkitAIGateway(
        client_factory=lambda: RecordingClient(error=programming_error)
    )

    with pytest.raises(RuntimeError, match="application programming error"):
        gateway.request_structured(prompt="Analyze", response_type=ExampleOutput)


@pytest.mark.parametrize("prompt", ["", "   ", "\n\t"])
def test_blank_prompt_is_rejected_before_client_creation(prompt: str) -> None:
    factory_called = False

    def build_client():
        nonlocal factory_called
        factory_called = True
        return RecordingClient()

    gateway = ToolkitAIGateway(client_factory=build_client)

    with pytest.raises(ValueError, match="non-blank prompt"):
        gateway.request_structured(prompt=prompt, response_type=ExampleOutput)

    assert factory_called is False


def test_non_pydantic_response_type_is_rejected_before_client_creation() -> None:
    factory_called = False

    def build_client():
        nonlocal factory_called
        factory_called = True
        return RecordingClient()

    gateway = ToolkitAIGateway(client_factory=build_client)

    with pytest.raises(TypeError, match="Pydantic BaseModel"):
        gateway.request_structured(prompt="Analyze", response_type=dict)  # type: ignore[arg-type]

    assert factory_called is False


@override_settings(AI_GATEWAY_FACTORY="tests.test_ai_gateway.ConfiguredFakeGateway")
def test_gateway_factory_supports_configured_test_substitution() -> None:
    gateway = get_ai_gateway()

    assert isinstance(gateway, ConfiguredFakeGateway)


def test_default_gateway_factory_is_lazy_and_returns_toolkit_adapter() -> None:
    gateway = get_ai_gateway()

    assert isinstance(gateway, ToolkitAIGateway)


@pytest.mark.parametrize(
    "factory_path",
    [
        "",
        "tests.test_ai_gateway.DoesNotExist",
        "tests.test_ai_gateway.InvalidGateway",
        "tests.test_ai_gateway.exploding_gateway_factory",
    ],
)
def test_invalid_gateway_factory_configuration_is_bounded(factory_path: str) -> None:
    with override_settings(AI_GATEWAY_FACTORY=factory_path):
        with pytest.raises(AIGatewayConfigurationError) as captured:
            get_ai_gateway()

    assert "internal factory detail" not in str(captured.value)


@override_settings(
    AI_TOOLKIT={
        "provider": "openai",
        "api_key": "",
        "model": "test-model",
        "embedding_model": "text-embedding-3-small",
        "max_retries": 1,
        "file_logging_enabled": False,
    }
)
def test_default_gateway_defers_missing_api_key_until_first_request() -> None:
    gateway = ToolkitAIGateway()

    with pytest.raises(AIGatewayConfigurationError) as captured:
        gateway.request_structured(prompt="Analyze", response_type=ExampleOutput)

    assert "API key" not in str(captured.value)
