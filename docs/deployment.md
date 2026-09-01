# Production Deployment

This is the supported single-server reference deployment for the MVP. It keeps
the existing architecture: PostgreSQL, Gunicorn behind an HTTPS reverse proxy,
one separately supervised durable worker, server-rendered Django, and persistent
private filesystem storage. Adapt hostnames, paths, service users, worker counts,
TLS tooling, and backup destinations to the actual operator environment.

This guide does not make the product production-ready by itself. The roadmap
release gate still requires Sprint 7 evaluation and a privacy/security review.

## 1. Required components

- A supported Python version from 3.11 through 3.14 and `uv`.
- PostgreSQL with a dedicated database and least-privilege application user.
- Nginx or an equivalent trusted HTTPS reverse proxy.
- A persistent directory for private candidate documents. It must not be beneath
  a public web root and must be backed up with the database.
- An external secret file or secret manager. Never commit production values.
- One web service, one continuously running background-worker service, and the
  daily retention-review timer.

Gunicorn and the Psycopg PostgreSQL driver are locked application dependencies.
SQLite remains supported only for development and tests.

## 2. Host and database preparation

The examples assume these paths and identities:

```text
Application user: ai-candidate-matcher
Application root: /srv/ai-candidate-matcher/current
Private media:    /srv/ai-candidate-matcher/private-media
Environment file: /etc/ai-candidate-matcher.env
Database:         ai_candidate_matcher
```

Create the operating-system account and directories with permissions that allow
only the application account to read private media and secrets. Create a
PostgreSQL role/database using the platform's approved administration process.
The application role needs ordinary schema and data privileges for migrations;
it should not be a PostgreSQL superuser.

For a same-host PostgreSQL connection, loopback plus `POSTGRES_SSLMODE=prefer`
can be appropriate when host access is already restricted. For a remote database,
use TLS and normally `require` or `verify-full` with the provider's certificate
guidance.

## 3. Install a release

Place a clean release under `/srv/ai-candidate-matcher/current`, then run as the
application user:

```bash
cd /srv/ai-candidate-matcher/current
uv sync --locked
```

Do not copy a developer `.env`, SQLite database, uploaded media directory, cache,
or virtual environment into the release. Releases must be reproducible from
`pyproject.toml` and `uv.lock`.

## 4. Configure secrets and production settings

Copy `deploy/production.env.example` to `/etc/ai-candidate-matcher.env`, replace
every placeholder, set ownership to the application account, and set mode 0600.
The file is read by systemd and must remain outside the repository.

Production startup requires:

- an explicit non-placeholder Django secret;
- debug disabled, explicit hosts, HTTPS redirect, and secure cookies;
- HTTPS CSRF trusted origins;
- PostgreSQL database, user, password, host, port, and SSL mode;
- an absolute persistent private-media path distinct from static assets;
- the AI provider key only when live AI workflows will be used.

The production example explicitly configures the `gpt-5.4-mini` token rates
verified from OpenAI on 2026-09-01: `AI_INPUT_COST_PER_1M_TOKENS=0.75` and
`AI_OUTPUT_COST_PER_1M_TOKENS=4.50`. These values are USD per one million
tokens. Review and update both values together whenever the configured model or
provider pricing changes. If they are intentionally omitted, the application
records cost as unavailable rather than trusting a zero-price placeholder.

Set `DJANGO_TRUST_X_FORWARDED_PROTO=True` only when the trusted proxy overwrites
the header as the provided Nginx example does. Enable HSTS only after HTTPS is
stable. Treat subdomain coverage and browser preload as separate deliberate
decisions because they are difficult to reverse.

## 5. Prepare database and static assets

Install the provided deployment oneshot unit, reload systemd, and run:

```bash
sudo systemctl daemon-reload
sudo systemctl start ai-candidate-matcher-deploy.service
sudo systemctl --no-pager --full status ai-candidate-matcher-deploy.service
```

The unit reads the same protected environment file as the runtime services and
runs the migration plan, migrations, static collection, and readiness command in
order. `check_production` fails unless all Django deployment checks pass,
PostgreSQL answers a query, no migration is pending, the project CSS was
collected, and private storage can save, read, and delete a temporary object. It
prints only controlled check names and never secrets, database URLs, storage
paths, candidate data, prompts, or provider responses.

## 6. Start the web, worker, and retention services

Review and install the examples under `deploy/systemd/`. Then reload systemd and
enable the services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ai-candidate-matcher-web.service
sudo systemctl enable --now ai-candidate-matcher-worker.service
sudo systemctl enable --now ai-candidate-matcher-retention.timer
```

The worker is initialized as its own continuously supervised process:

```bash
.venv/bin/python manage.py run_background_worker --poll-interval 2
```

It must not run inside a Gunicorn web worker. Restarting it is safe: durable task
leases are reclaimable and exact saved results are reused. Profile drafts still
require explicit evidence review and confirmation, candidate decisions remain
individual, and outreach remains a separate approved action.

For the one-time managed-SaaS bootstrap, a technical Django administrator creates
one ordinary active user and explicitly enables **Platform owner**. Keep Django
staff/superuser privileges separate unless that person also performs technical
operations. The platform owner then signs in to the normal application to create
organizations and first administrators. Platform ownership alone does not grant
tenant membership or access to candidate, CV, vacancy, assessment, decision, or
outreach content. There is no public signup or billing workflow.

The daily timer runs three explicit services in order:

```bash
.venv/bin/python manage.py process_retention --apply
.venv/bin/python manage.py process_data_lifecycle --apply --confirm "PURGE ELIGIBLE DATA"
.venv/bin/python manage.py process_organization_deletions --apply --confirm "PURGE ORGANIZATIONS"
```

The first command only stages due candidates for individual administrator
review. The second applies the organization policy only to dependency-safe
temporary/job/uncommitted/metadata bundles. The third purges only suspended
organizations whose recovery window has ended. Legal holds and active exceptions
block the applicable scheduled deletion. All commands are dry-run by default;
the committed systemd unit supplies their explicit apply/confirmation options.

## 7. Configure HTTPS reverse proxy

Adapt `deploy/nginx/ai-candidate-matcher.conf`, install an approved TLS
certificate, validate the Nginx configuration, and reload Nginx. Keep the proxy's
upload limit above the application's 10 MB limit. Never add a `/media/` alias:
private CV bytes must pass through the authenticated, tenant-scoped, integrity-
checked Django download route.

## 8. Verify a deployment

Run the runtime check as the service account and inspect service state:

```bash
cd /srv/ai-candidate-matcher/current
.venv/bin/python manage.py check_production
systemctl --no-pager --full status ai-candidate-matcher-web.service
systemctl --no-pager --full status ai-candidate-matcher-worker.service
systemctl --no-pager --full status ai-candidate-matcher-retention.timer
curl --fail --silent https://matcher.example.com/health/live/
curl --fail --silent https://matcher.example.com/health/ready/
```

`/health/live/` proves the web process can serve Django. `/health/ready/` also
runs `SELECT 1`. Both return only a generic status and `Cache-Control: no-store`;
the readiness endpoint returns HTTP 503 without database details when unavailable.

Complete a synthetic recruiter smoke test: sign in, inspect one private CV,
queue a provider-free/reusable job where possible, inspect **Jobs**, **AI usage**,
and **Privacy & audit**, and confirm that no decision or outreach action occurs
automatically.

## 9. Monitoring and alerts

Monitor at minimum:

- web and background-worker service restarts or prolonged downtime;
- readiness failures and HTTP 5xx rates;
- PostgreSQL capacity, connections, slow queries, and backup age;
- private-media filesystem capacity, permissions, and backup age;
- failed/attention background targets and stale leases under **Jobs**;
- failure, latency, retry, token, and cost trends under **AI usage**;
- staged deletion and retention exceptions under **Privacy & audit**.

Application and proxy logs must not record request bodies, raw CV text,
candidate contact values, AI prompts/responses, recruiter notes, outreach content,
environment values, or provider exception details. Restrict log access and set a
documented retention period.

## 10. Backups and restore drills

Back up PostgreSQL and the private-media directory on the same documented
schedule. Encrypt backups, restrict access, store at least one copy outside the
application host, define retention, and monitor successful completion. The
environment/secret file belongs in the approved secret-management recovery
process, not in the source archive.

For a consistent recovery point, briefly stop web and worker writes or use an
infrastructure snapshot method that coordinates PostgreSQL and private media.
A database-only restore can leave document metadata without its corresponding
bytes; a media-only restore can leave unreferenced private files.

Practice restore into an isolated environment:

1. Restore PostgreSQL and private media from the same recovery point.
2. Install the exact application release and locked dependencies.
3. Run migrations, `collectstatic`, and `check_production`.
4. Verify synthetic private-file byte integrity and tenant isolation.
5. Record recovery time, recovery point, failures, and corrective actions.

Never test a destructive restore against the live database or live media path.

## 11. Upgrades and rollback

Before deploying a new release, take/verify a recoverable backup and run the
quality gate. Install locked dependencies, inspect `migrate --plan`, apply
migrations once, collect static assets, run `check_production`, then restart web
and worker services. Verify health endpoints and synthetic workflows afterward.

Rollback code only when its schema is compatible with the applied migrations.
Do not casually reverse data migrations. If schema or data is incompatible, use
the documented database-and-media recovery procedure and preserve audit evidence.

## 12. Production acceptance checklist

- Production starts only with explicit secure settings and PostgreSQL.
- `check --deploy --fail-level WARNING` and `check_production` both pass.
- Migrations are fully applied and collected static assets are available.
- Private media is persistent, non-public, writable only by the application, and
  included with the database in encrypted tested backups.
- Gunicorn, background worker, and retention timer are separately supervised.
- Nginx overwrites forwarded-protocol headers and serves no media directory.
- Liveness/readiness monitoring and capacity/backup alerts are configured.
- Logs and monitoring contain no private recruitment or AI request/response data.
- A restore drill and synthetic tenant/privacy smoke test are documented.
- Sprint 7 evaluation and the final privacy/security review remain outstanding.
