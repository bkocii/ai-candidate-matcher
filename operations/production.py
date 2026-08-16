"""Runtime production-readiness checks with content-free results."""

from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.checks import WARNING, run_checks
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import connections
from django.db.migrations.executor import MigrationExecutor


class ProductionReadinessError(RuntimeError):
    """A bounded production-readiness failure safe for operator output."""


def _check_django_deployment_settings() -> None:
    if settings.ENVIRONMENT != "production":
        raise ProductionReadinessError(
            "DJANGO_ENVIRONMENT must be production for this check."
        )
    messages = run_checks(include_deployment_checks=True)
    failures = sorted(
        {
            message.id or "deployment-check"
            for message in messages
            if message.level >= WARNING
        }
    )
    if failures:
        raise ProductionReadinessError(
            f"Django deployment checks failed: {', '.join(failures)}."
        )


def _check_database() -> None:
    connection = connections["default"]
    if connection.vendor != "postgresql":
        raise ProductionReadinessError("The production database must be PostgreSQL.")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        if executor.migration_plan(targets):
            raise ProductionReadinessError("Unapplied database migrations exist.")
    except ProductionReadinessError:
        raise
    except Exception as error:
        raise ProductionReadinessError(
            "The production database or migration state is unavailable."
        ) from error


def _check_static_assets() -> None:
    expected_asset = Path(settings.STATIC_ROOT) / "css" / "app.css"
    if not expected_asset.is_file():
        raise ProductionReadinessError(
            "Collected static assets are unavailable; run collectstatic."
        )


def _check_private_storage() -> None:
    object_name = f".production-check/{uuid4().hex}.tmp"
    saved_name = None
    try:
        saved_name = default_storage.save(object_name, ContentFile(b"storage-check"))
        if not default_storage.exists(saved_name):
            raise ProductionReadinessError("Private storage verification failed.")
        with default_storage.open(saved_name, "rb") as stored_file:
            if stored_file.read() != b"storage-check":
                raise ProductionReadinessError("Private storage verification failed.")
    except ProductionReadinessError:
        raise
    except Exception as error:
        raise ProductionReadinessError("Private storage is unavailable.") from error
    finally:
        if saved_name:
            try:
                default_storage.delete(saved_name)
            except Exception:
                pass

    try:
        if saved_name and default_storage.exists(saved_name):
            raise ProductionReadinessError("Private storage deletion failed.")
    except ProductionReadinessError:
        raise
    except Exception as error:
        raise ProductionReadinessError("Private storage is unavailable.") from error


def run_production_readiness_checks() -> tuple[str, ...]:
    """Run bounded deployment, database, static, and private-storage checks."""
    _check_django_deployment_settings()
    _check_database()
    _check_static_assets()
    _check_private_storage()
    return (
        "Django deployment settings",
        "PostgreSQL connection and migrations",
        "collected static assets",
        "private media read/write/delete",
    )
