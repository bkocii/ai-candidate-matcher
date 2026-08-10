"""Run the same complete quality gate locally and in continuous integration."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, environment: dict[str, str] | None = None) -> None:
    print(f"\n> {' '.join(command)}", flush=True)
    subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
    )


def deployment_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "DJANGO_ENVIRONMENT": "production",
            "DJANGO_DEBUG": "false",
            "DJANGO_SECRET_KEY": (
                "ci-deployment-check-only-7bf2f088aeb84cb8a9c44b29bba3e706-"
                "not-for-real-use"
            ),
            "DJANGO_ALLOWED_HOSTS": "example.com",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://example.com",
            "DJANGO_SECURE_HSTS_SECONDS": "31536000",
            "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS": "true",
            "DJANGO_SECURE_HSTS_PRELOAD": "true",
        }
    )
    return environment


def main() -> int:
    python = sys.executable
    uv = shutil.which("uv")
    if uv is None:
        print("uv is required to run the dependency compatibility check.")
        return 2

    commands: list[tuple[list[str], dict[str, str] | None]] = [
        ([python, "manage.py", "check"], None),
        (
            [python, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
            deployment_environment(),
        ),
        ([python, "manage.py", "makemigrations", "--check", "--dry-run"], None),
        ([python, "-m", "pytest"], None),
        ([python, "-m", "ruff", "check", "."], None),
        ([python, "-m", "ruff", "format", "--check", "."], None),
        ([uv, "pip", "check", "--python", python], None),
    ]

    try:
        for command, environment in commands:
            run(command, environment=environment)
    except subprocess.CalledProcessError as error:
        return error.returncode

    print("\nQuality gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
