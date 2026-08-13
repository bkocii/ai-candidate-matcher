"""Explicitly opted-in live contract smoke test using synthetic data only."""

import os
from typing import Literal

import pytest
from django.conf import settings
from pydantic import BaseModel, ConfigDict

from ai_gateway import ToolkitAIGateway

pytestmark = pytest.mark.live_ai
LIVE_AI_SMOKE_ENABLED = os.getenv("RUN_LIVE_AI_SMOKE") == "1"


class LiveSmokeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]


@pytest.mark.skipif(
    not LIVE_AI_SMOKE_ENABLED,
    reason="Set RUN_LIVE_AI_SMOKE=1 to authorize one live structured AI request.",
)
def test_live_structured_gateway_contract_with_synthetic_input():
    """Make one tiny request without candidate, vacancy, CV, or database data."""
    assert settings.AI_TOOLKIT["file_logging_enabled"] is False
    gateway = ToolkitAIGateway()

    result = gateway.request_structured(
        prompt=(
            "This is a synthetic connectivity test. Return the structured field "
            "status with the exact value ok. Do not add any other fields."
        ),
        response_type=LiveSmokeOutput,
    )

    assert result.data == LiveSmokeOutput(status="ok")
    assert result.metadata.request_id
    assert result.metadata.model
    assert result.metadata.retries_used >= 0
    assert not hasattr(result, "raw_response")
