"""Resolve the configured application AI gateway without global caching."""

from collections.abc import Callable
from typing import cast

from django.conf import settings
from django.utils.module_loading import import_string

from ai_gateway.contracts import AIGateway, AIGatewayConfigurationError


def get_ai_gateway() -> AIGateway:
    """Build the configured gateway, allowing safe per-test substitution."""

    factory_path = getattr(settings, "AI_GATEWAY_FACTORY", "")
    if not isinstance(factory_path, str) or not factory_path.strip():
        raise AIGatewayConfigurationError()

    try:
        factory = import_string(factory_path)
    except (AttributeError, ImportError):
        raise AIGatewayConfigurationError() from None

    if not isinstance(factory, Callable):
        raise AIGatewayConfigurationError()

    try:
        gateway = factory()
    except AIGatewayConfigurationError:
        raise
    except Exception:
        raise AIGatewayConfigurationError() from None

    if not callable(getattr(gateway, "request_structured", None)):
        raise AIGatewayConfigurationError()

    return cast(AIGateway, gateway)
