"""Application-owned boundary around Python AI Toolkit."""

from ai_gateway.contracts import (
    AIGateway,
    AIGatewayConfigurationError,
    AIGatewayError,
    AIGatewayInvalidResponseError,
    AIGatewayMetadata,
    AIGatewayResult,
    AIGatewayTokenUsage,
    AIGatewayUnavailableError,
)
from ai_gateway.factory import get_ai_gateway
from ai_gateway.toolkit import ToolkitAIGateway

__all__ = [
    "AIGateway",
    "AIGatewayConfigurationError",
    "AIGatewayError",
    "AIGatewayInvalidResponseError",
    "AIGatewayMetadata",
    "AIGatewayResult",
    "AIGatewayTokenUsage",
    "AIGatewayUnavailableError",
    "ToolkitAIGateway",
    "get_ai_gateway",
]
