from dataclasses import fields
from decimal import Decimal

import pytest
from ai.schemas import AIResult, TokenUsage
from django.test import override_settings
from pydantic import BaseModel

from ai_gateway import (
    AIGateway,
    AIGatewayMetadata,
    AIGatewayResult,
    AIGatewayTokenUsage,
    AIGatewayUnavailableError,
    ToolkitAIGateway,
)
from ai_gateway.testing import FakeAIGateway


class ContractOutput(BaseModel):
    status: str


def contract_metadata() -> AIGatewayMetadata:
    return AIGatewayMetadata(
        request_id="contract-request-1",
        model="contract-model",
        duration_ms=10.5,
        retries_used=1,
        token_usage=AIGatewayTokenUsage(
            input_tokens=4,
            output_tokens=2,
            total_tokens=6,
        ),
        estimated_cost_usd=Decimal("0.000001"),
    )


def contract_toolkit_result() -> AIResult[ContractOutput]:
    return AIResult(
        data=ContractOutput(status="ok"),
        model="contract-model",
        raw_response='{"status":"ok"}',
        original_raw_response='{"status":"ok"}',
        duration_ms=10.5,
        retries_used=1,
        token_usage=TokenUsage(input_tokens=4, output_tokens=2, total_tokens=6),
        estimated_cost_usd=Decimal("0.000001"),
        request_id="contract-request-1",
    )


class ContractToolkitClient:
    def __init__(self) -> None:
        self.calls = []

    def ask(self, prompt, response_type):
        self.calls.append((prompt, response_type))
        return contract_toolkit_result()


@pytest.fixture(params=("fake", "toolkit"))
def contract_gateway(request):
    if request.param == "fake":
        gateway = FakeAIGateway(
            response=ContractOutput(status="ok"),
            metadata=contract_metadata(),
        )
        return gateway, gateway.calls
    client = ContractToolkitClient()
    return ToolkitAIGateway(client_factory=lambda: client), client.calls


@override_settings(
    AI_TOOLKIT={
        "input_cost_per_1m_tokens": "0.75",
        "output_cost_per_1m_tokens": "4.50",
    }
)
def test_fake_and_toolkit_gateways_share_success_contract(contract_gateway):
    gateway, calls = contract_gateway

    result = gateway.request_structured(
        prompt="  Return the synthetic contract result.  ",
        response_type=ContractOutput,
    )

    assert isinstance(gateway, AIGateway)
    assert isinstance(result, AIGatewayResult)
    assert result.data == ContractOutput(status="ok")
    assert result.metadata == contract_metadata()
    assert calls == [("Return the synthetic contract result.", ContractOutput)]
    assert [field.name for field in fields(result)] == ["data", "metadata"]
    assert not hasattr(result, "raw_response")


@pytest.mark.parametrize("prompt", ("", "   ", "\n\t"))
def test_fake_and_toolkit_gateways_share_blank_prompt_contract(
    contract_gateway,
    prompt,
):
    gateway, calls = contract_gateway

    with pytest.raises(ValueError, match="non-blank prompt"):
        gateway.request_structured(prompt=prompt, response_type=ContractOutput)

    assert calls == []


def test_fake_and_toolkit_gateways_share_response_type_contract(contract_gateway):
    gateway, calls = contract_gateway

    with pytest.raises(TypeError, match="Pydantic BaseModel"):
        gateway.request_structured(
            prompt="Synthetic contract",
            response_type=dict,  # type: ignore[arg-type]
        )

    assert calls == []


def test_fake_gateway_supports_dynamic_responses_and_records_normalized_calls():
    gateway = FakeAIGateway(
        responder=lambda prompt, response_type: response_type(status=prompt),
        metadata=contract_metadata(),
    )

    result = gateway.request_structured(
        prompt="  dynamic synthetic response  ",
        response_type=ContractOutput,
    )

    assert result.data.status == "dynamic synthetic response"
    assert gateway.calls[0].prompt == "dynamic synthetic response"
    assert gateway.calls[0].response_type is ContractOutput


def test_fake_gateway_raises_configured_failure_without_network_access():
    error = AIGatewayUnavailableError()
    gateway = FakeAIGateway(error=error)

    with pytest.raises(AIGatewayUnavailableError) as captured:
        gateway.request_structured(
            prompt="Synthetic failure",
            response_type=ContractOutput,
        )

    assert captured.value is error
    assert captured.value.code == "ai_service_unavailable"
    assert gateway.calls == [("Synthetic failure", ContractOutput)]


def test_fake_gateway_rejects_a_mismatched_test_response():
    class OtherOutput(BaseModel):
        value: str

    gateway = FakeAIGateway(response=OtherOutput(value="wrong schema"))

    with pytest.raises(TypeError, match="instance of the requested response type"):
        gateway.request_structured(
            prompt="Synthetic mismatch",
            response_type=ContractOutput,
        )
