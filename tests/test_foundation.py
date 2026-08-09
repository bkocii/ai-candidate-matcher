from importlib.metadata import version
from pathlib import Path

import ai
from ai.integrations.django import get_ai_client, get_django_ai_config
from django.conf import settings
from django.test import override_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_django_settings_load() -> None:
    assert settings.ROOT_URLCONF == "config.urls"
    assert settings.DEFAULT_AUTO_FIELD == "django.db.models.BigAutoField"


def test_published_toolkit_version_is_installed() -> None:
    assert version("python-ai-toolkit") == "1.0.0"


def test_toolkit_import_does_not_resolve_to_local_source() -> None:
    toolkit_path = Path(ai.__file__).resolve()

    assert "site-packages" in toolkit_path.parts
    assert not (PROJECT_ROOT / "ai").exists()


def test_django_integration_entry_points_are_available() -> None:
    assert callable(get_django_ai_config)
    assert callable(get_ai_client)


@override_settings(
    AI_TOOLKIT={
        "provider": "openai",
        "api_key": "test-key-not-used-for-network-calls",
        "model": "gpt-5.4-mini",
        "file_logging_enabled": False,
    }
)
def test_toolkit_django_configuration_validates_without_network() -> None:
    config = get_django_ai_config()

    assert config.provider == "openai"
    assert config.model == "gpt-5.4-mini"
    assert config.file_logging_enabled is False
