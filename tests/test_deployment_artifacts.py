from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_documented_local_env_copy_does_not_overwrite_existing_file() -> None:
    safe_command = "if (-not (Test-Path .env)) { Copy-Item .env.example .env }"

    assert safe_command in read_project_file("README.md")
    assert safe_command in read_project_file("docs/manual_testing_guide.md")


def test_reference_services_keep_web_worker_and_retention_separate() -> None:
    web = read_project_file("deploy/systemd/ai-candidate-matcher-web.service")
    worker = read_project_file("deploy/systemd/ai-candidate-matcher-worker.service")
    retention = read_project_file(
        "deploy/systemd/ai-candidate-matcher-retention.service"
    )
    timer = read_project_file("deploy/systemd/ai-candidate-matcher-retention.timer")

    assert "gunicorn config.wsgi:application" in web
    assert "run_background_worker" not in web
    assert "run_background_worker --poll-interval 2" in worker
    assert "process_retention --apply" in retention
    assert "OnCalendar=daily" in timer


def test_deployment_unit_runs_migrations_static_and_runtime_check_in_order() -> None:
    service = read_project_file("deploy/systemd/ai-candidate-matcher-deploy.service")

    migration = service.index("manage.py migrate --noinput")
    static = service.index("manage.py collectstatic --noinput --clear")
    readiness = service.index("manage.py check_production")
    assert migration < static < readiness


def test_nginx_serves_static_but_never_private_media() -> None:
    nginx = read_project_file("deploy/nginx/ai-candidate-matcher.conf")

    assert "location /static/" in nginx
    assert "proxy_set_header X-Forwarded-Proto https;" in nginx
    assert "\n    location /media/" not in nginx


def test_production_env_example_has_placeholders_not_real_secrets() -> None:
    environment = read_project_file("deploy/production.env.example")

    assert "DJANGO_ENVIRONMENT=production" in environment
    assert "POSTGRES_PASSWORD=replace-with-a-database-password" in environment
    assert "OPENAI_API_KEY=replace-with-the-provider-key" in environment
    assert "DJANGO_MEDIA_ROOT=/srv/ai-candidate-matcher/private-media" in environment
