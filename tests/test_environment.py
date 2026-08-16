import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.environment import (
    env_bool,
    env_choice,
    env_int,
    env_list,
    env_required,
    secret_key,
)
from scripts.check import deployment_environment

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("value", ["1", "true", "YES", "on"])
def test_env_bool_accepts_explicit_true_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("EXAMPLE_BOOLEAN", value)

    assert env_bool("EXAMPLE_BOOLEAN", default=False) is True


@pytest.mark.parametrize("value", ["0", "false", "NO", "off"])
def test_env_bool_accepts_explicit_false_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("EXAMPLE_BOOLEAN", value)

    assert env_bool("EXAMPLE_BOOLEAN", default=True) is False


def test_env_bool_rejects_ambiguous_values(monkeypatch) -> None:
    monkeypatch.setenv("EXAMPLE_BOOLEAN", "tru")

    with pytest.raises(ImproperlyConfigured, match="EXAMPLE_BOOLEAN"):
        env_bool("EXAMPLE_BOOLEAN", default=False)


def test_environment_helpers_validate_and_normalize(monkeypatch) -> None:
    monkeypatch.setenv("EXAMPLE_INTEGER", "12")
    monkeypatch.setenv("EXAMPLE_LIST", "first, second, ,third")
    monkeypatch.setenv("EXAMPLE_CHOICE", "PRODUCTION")

    assert env_int("EXAMPLE_INTEGER", default=0) == 12
    assert env_list("EXAMPLE_LIST") == ["first", "second", "third"]
    assert (
        env_choice(
            "EXAMPLE_CHOICE",
            default="development",
            choices={"development", "production"},
        )
        == "production"
    )


def test_required_environment_value_rejects_blank(monkeypatch) -> None:
    monkeypatch.setenv("REQUIRED_VALUE", "  ")

    with pytest.raises(ImproperlyConfigured, match="REQUIRED_VALUE"):
        env_required("REQUIRED_VALUE")


def test_production_secret_key_must_be_explicit_and_safe(monkeypatch) -> None:
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
    with pytest.raises(ImproperlyConfigured, match="required"):
        secret_key(production=True)

    monkeypatch.setenv("DJANGO_SECRET_KEY", "django-insecure-placeholder")
    with pytest.raises(ImproperlyConfigured, match="insecure prefix"):
        secret_key(production=True)


def test_deployment_check_passes_with_explicit_secure_environment() -> None:
    environment = secure_production_environment()

    result = subprocess.run(
        [
            sys.executable,
            "manage.py",
            "check",
            "--deploy",
            "--fail-level",
            "WARNING",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_production_uses_postgresql_and_explicit_private_media() -> None:
    environment = secure_production_environment()
    environment["DJANGO_SETTINGS_MODULE"] = "config.settings"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from django.conf import settings; "
                "print(settings.DATABASES['default']['ENGINE']); "
                "print(settings.MEDIA_ROOT)"
            ),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "django.db.backends.postgresql" in result.stdout
    assert str(PROJECT_ROOT / ".test-private-media") in result.stdout


def test_quality_gate_overrides_development_https_settings(monkeypatch) -> None:
    monkeypatch.setenv("DJANGO_SECURE_SSL_REDIRECT", "false")
    monkeypatch.setenv("DJANGO_SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("DJANGO_CSRF_COOKIE_SECURE", "false")

    environment = deployment_environment()

    assert environment["DJANGO_ENVIRONMENT"] == "production"
    assert environment["DJANGO_SECURE_SSL_REDIRECT"] == "true"
    assert environment["DJANGO_SESSION_COOKIE_SECURE"] == "true"
    assert environment["DJANGO_CSRF_COOKIE_SECURE"] == "true"
    assert environment["POSTGRES_DB"] == "deployment_check"
    assert Path(environment["DJANGO_MEDIA_ROOT"]).is_absolute()


def secure_production_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "DJANGO_ENVIRONMENT": "production",
            "DJANGO_DEBUG": "false",
            "DJANGO_SECRET_KEY": "test-" + "a-secure-random-looking-value-" * 3,
            "DJANGO_ALLOWED_HOSTS": "example.com",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://example.com",
            "DJANGO_SECURE_SSL_REDIRECT": "true",
            "DJANGO_SESSION_COOKIE_SECURE": "true",
            "DJANGO_CSRF_COOKIE_SECURE": "true",
            "DJANGO_SECURE_HSTS_SECONDS": "31536000",
            "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS": "true",
            "DJANGO_SECURE_HSTS_PRELOAD": "true",
            "DJANGO_MEDIA_ROOT": str(PROJECT_ROOT / ".test-private-media"),
            "DJANGO_STATIC_ROOT": str(PROJECT_ROOT / ".test-staticfiles"),
            "POSTGRES_DB": "test_database",
            "POSTGRES_USER": "test_user",
            "POSTGRES_PASSWORD": "test-password-not-for-real-use",
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": "5432",
            "POSTGRES_SSLMODE": "prefer",
        }
    )
    return environment


@pytest.mark.parametrize(
    ("override", "expected_error"),
    [
        ({"DJANGO_SECRET_KEY": ""}, "DJANGO_SECRET_KEY is required"),
        ({"DJANGO_DEBUG": "true"}, "DJANGO_DEBUG must be false"),
        ({"DJANGO_ALLOWED_HOSTS": "*"}, "must contain explicit hosts"),
        ({"POSTGRES_DB": ""}, "POSTGRES_DB is required"),
        ({"POSTGRES_SSLMODE": "sometimes"}, "POSTGRES_SSLMODE must be one of"),
        ({"DJANGO_MEDIA_ROOT": "relative/media"}, "must be an absolute path"),
        (
            {"DJANGO_MEDIA_ROOT": str(PROJECT_ROOT / ".test-staticfiles")},
            "must be separate directories",
        ),
        (
            {"DJANGO_CSRF_TRUSTED_ORIGINS": "http://example.com"},
            "must use https://",
        ),
        ({"DJANGO_SESSION_COOKIE_SECURE": "false"}, "secure session/CSRF cookies"),
        ({"DJANGO_DEBUG": "sometimes"}, "must be one of"),
    ],
)
def test_production_startup_rejects_unsafe_configuration(
    override: dict[str, str],
    expected_error: str,
) -> None:
    environment = secure_production_environment()
    environment.update(override)

    result = subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert expected_error in result.stdout + result.stderr
