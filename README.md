# AI Candidate Matcher

AI-assisted candidate rediscovery and shortlisting for small recruitment agencies and employers.

The application searches a lawful, organization-controlled candidate pool. Recruiters create a vacancy, the system applies deterministic filters, AI produces evidence-based match assessments, and a human approves every shortlist and outreach draft.

This repository is intentionally separate from Python AI Toolkit. The application consumes the published package:

```text
python-ai-toolkit[django]==1.0.0
```

## Current status

Sprint 0 and Sprint 1 are complete. Sprint 2 is in progress.

The repository now has a Django 5.2 LTS foundation, custom user model,
organizations, organization memberships, administrator/recruiter roles,
optional client companies, organization-scoped queryset and authorization
helpers, login and POST-only logout, responsive base templates, organization
selection, a minimal tenant-safe dashboard, strict environment parsing,
production-safe settings validation, reproducible dependency locking, a shared
local/CI quality command, and a four-version CI matrix. Organization-owned
candidate, provenance/consent, and private document metadata models are also
available through Django admin. It uses the published
`python-ai-toolkit==1.0.0` distribution.

The next approved task is `DATA-002 — Add vacancy and versioned
vacancy-requirements models`.

## Local setup

Python 3.11 through 3.14 and [uv](https://docs.astral.sh/uv/) are supported.

```powershell
uv sync --extra dev
Copy-Item .env.example .env
uv run python manage.py migrate
uv run python scripts/check.py
```

An OpenAI API key is not needed for Django startup or the ordinary test suite.
Add it to `.env` only when a later opt-in AI request is intentionally run:

```env
OPENAI_API_KEY=
```

## Local admin test

Create a Django superuser and start the development server:

```powershell
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Open `http://127.0.0.1:8000/admin/` to create organizations, memberships,
candidates, source/consent records, and document metadata. A Django superuser
does not bypass organization membership on the normal dashboard. To test `/`,
create an active organization membership for that same user in Django admin.

## Production configuration

Set `DJANGO_ENVIRONMENT=production` to disable development defaults. Production
startup then requires an explicit secret key and allowed hosts, rejects debug
mode and wildcard hosts, requires HTTPS redirect plus secure cookies, and
accepts only HTTPS CSRF trusted origins.

Use `.env.example` as the complete variable reference. Enable
`DJANGO_TRUST_X_FORWARDED_PROTO` only when a trusted reverse proxy overwrites
that header. HSTS remains explicit because enabling it before HTTPS is stable
can make a deployment unreachable.

## Quality gate

The single local and CI command is:

```powershell
uv run python scripts/check.py
```

It runs Django checks, the production deployment check, migration-drift check,
tests, Ruff lint/format checks, and dependency compatibility verification.

## Source of truth

- `docs/product_spec.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/project_state.md`
- `docs/toolkit_integration.md`
- `docs/toolkit_feedback.md`
- `docs/future_backlog.md`
- `docs/session_handoff.md`
