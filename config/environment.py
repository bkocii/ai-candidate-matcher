"""Small, strict helpers for environment-backed Django settings."""

import os
from collections.abc import Iterable

from django.core.exceptions import ImproperlyConfigured

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def env_bool(name: str, *, default: bool) -> bool:
    """Read a boolean without silently treating misspellings as false."""
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default

    value = raw_value.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ImproperlyConfigured(
        f"{name} must be one of: 1, 0, true, false, yes, no, on, off."
    )


def env_int(name: str, *, default: int, minimum: int = 0) -> int:
    """Read a bounded integer setting."""
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default

    try:
        value = int(raw_value)
    except ValueError as error:
        raise ImproperlyConfigured(f"{name} must be an integer.") from error
    if value < minimum:
        raise ImproperlyConfigured(f"{name} must be at least {minimum}.")
    return value


def env_list(name: str, *, default: Iterable[str] = ()) -> list[str]:
    """Read a comma-separated list, dropping empty items."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return list(default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def env_choice(name: str, *, default: str, choices: set[str]) -> str:
    """Read a normalized choice and reject unknown runtime modes."""
    value = os.getenv(name, default).strip().lower()
    if value not in choices:
        allowed = ", ".join(sorted(choices))
        raise ImproperlyConfigured(f"{name} must be one of: {allowed}.")
    return value


def secret_key(*, production: bool) -> str:
    """Return a development fallback, but require an explicit production key."""
    value = os.getenv("DJANGO_SECRET_KEY", "")
    if production and not value:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is required when DJANGO_ENVIRONMENT=production."
        )
    if production and value.startswith("django-insecure-"):
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must not use Django's insecure prefix in production."
        )
    return value or "django-insecure-development-only-change-before-deployment"
