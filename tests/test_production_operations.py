from io import StringIO
from unittest.mock import patch

import pytest
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from django.test import override_settings
from django.urls import reverse

from operations.production import (
    ProductionReadinessError,
    _check_private_storage,
    _check_static_assets,
    run_production_readiness_checks,
)


@pytest.mark.django_db
def test_health_endpoints_are_content_free(client) -> None:
    live_response = client.get(reverse("health-live"))
    ready_response = client.get(reverse("health-ready"))

    assert live_response.status_code == 200
    assert live_response.json() == {"status": "ok"}
    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ok"}
    assert live_response["Cache-Control"] == "no-store"
    assert ready_response["Cache-Control"] == "no-store"


def test_readiness_failure_exposes_no_database_detail(client) -> None:
    with patch("config.views.connection.cursor", side_effect=DatabaseError("private")):
        response = client.get(reverse("health-ready"))

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert b"private" not in response.content


def test_production_command_rejects_development_mode() -> None:
    with pytest.raises(CommandError, match="must be production"):
        call_command("check_production")


@override_settings(ENVIRONMENT="production")
def test_production_command_reports_only_check_names() -> None:
    output = StringIO()
    with patch(
        "operations.management.commands.check_production."
        "run_production_readiness_checks",
        return_value=("database", "storage"),
    ):
        call_command("check_production", stdout=output)

    text = output.getvalue()
    assert "OK: database." in text
    assert "OK: storage." in text
    assert "Production readiness checks passed." in text


@override_settings(ENVIRONMENT="production")
def test_production_readiness_runs_every_boundary_check() -> None:
    with (
        patch("operations.production._check_django_deployment_settings") as django,
        patch("operations.production._check_database") as database,
        patch("operations.production._check_static_assets") as static,
        patch("operations.production._check_private_storage") as storage,
    ):
        completed = run_production_readiness_checks()

    django.assert_called_once_with()
    database.assert_called_once_with()
    static.assert_called_once_with()
    storage.assert_called_once_with()
    assert len(completed) == 4


def test_static_check_requires_collected_project_asset(tmp_path) -> None:
    with override_settings(STATIC_ROOT=tmp_path):
        with pytest.raises(ProductionReadinessError, match="collectstatic"):
            _check_static_assets()

        asset = tmp_path / "css" / "app.css"
        asset.parent.mkdir(parents=True)
        asset.write_text("body {}", encoding="utf-8")
        _check_static_assets()


def test_private_storage_check_round_trips_and_cleans_up(tmp_path) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        _check_private_storage()

    assert not any(tmp_path.rglob("*.tmp"))
    assert default_storage is not None
