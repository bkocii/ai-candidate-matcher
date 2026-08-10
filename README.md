# AI Candidate Matcher

AI-assisted candidate rediscovery and shortlisting for small recruitment agencies and employers.

The application searches a lawful, organization-controlled candidate pool. Recruiters create a vacancy, the system applies deterministic filters, AI produces evidence-based match assessments, and a human approves every shortlist and outreach draft.

This repository is intentionally separate from Python AI Toolkit. The application consumes the published package:

```text
python-ai-toolkit[django]==1.0.0
```

## Current status

Sprint 0, Sprint 1, and Sprint 2 are complete. Sprint 3 is next.

The repository now has a Django 5.2 LTS foundation, custom user model,
organizations, organization memberships, administrator/recruiter roles,
optional client companies, organization-scoped queryset and authorization
helpers, login and POST-only logout, responsive base templates, organization
selection, a minimal tenant-safe dashboard, strict environment parsing,
production-safe settings validation, reproducible dependency locking, a shared
local/CI quality command, and a four-version CI matrix. Organization-owned
candidate, provenance/consent, and private document models are also available.
Recruiters can list and manually create candidates, import a validated UTF-8 CSV
with per-row duplicate and error reporting, and upload PDF/DOCX CVs for bounded
safe text extraction. Organization-owned vacancies and immutable, versioned
recruiter-confirmed requirements snapshots are available. Recruiters can create
vacancies from pasted descriptions, select an optional client company, manually
edit structured requirements, explicitly confirm them, and create immutable
numbered correction versions. Confirmed vacancies can then be opened, paused,
closed, and reopened through recruiter-facing lifecycle controls. It uses the published
`python-ai-toolkit==1.0.0` distribution.

The next approved task is `MATCH-001 — Define normalized skills and explicit
hard-constraint rules`.

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
candidates, source/consent records, document metadata, vacancies, and versioned
vacancy requirements. A Django superuser does not bypass organization membership
on the normal dashboard. To test `/`, create an active organization membership
for that same user in Django admin.

After signing in to the normal application, open the organization workspace and
select **Candidates**. You can create a candidate manually or download the CSV
header template from **Import CSV**. Imports accept up to 2 MB and 2,000 rows;
`full_name` is required, while `email`, `phone`, `location`, `source_reference`,
and ISO `retention_until` are optional.

Open a candidate and select **Upload CV** to add a PDF or DOCX file up to 10 MB.
Password-protected, malformed, macro-enabled, textless/scanned, or resource-heavy
documents are rejected. The app shows safe metadata only; direct document
download is intentionally unavailable until the private-delivery task.

Open **Vacancies** to paste a job description. Every new vacancy receives an
editable requirements version 1. Recruiters enter list values one per line, save
the draft, and explicitly confirm it. Confirmed versions are read-only; **Create
correction draft** copies the current snapshot into the next numbered version.
After confirmation, use the vacancy detail page to open, pause, close, or reopen
the vacancy through the available validated lifecycle transitions.

For a complete browser walkthrough and safe synthetic CSV, PDF, DOCX, rejection,
and vacancy fixtures, follow `docs/manual_testing_guide.md`.

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
