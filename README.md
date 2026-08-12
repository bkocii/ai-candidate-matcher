# AI Candidate Matcher

AI-assisted candidate rediscovery and shortlisting for small recruitment agencies and employers.

The application searches a lawful, organization-controlled candidate pool. Recruiters create a vacancy, the system applies deterministic filters, AI produces evidence-based match assessments, and a human approves every shortlist and outreach draft.

This repository is intentionally separate from Python AI Toolkit. The application consumes the published package:

```text
python-ai-toolkit[django]==1.0.0
```

## Current status

Sprint 0 through Sprint 3 are complete. Sprint 4 is in progress, with `AI-001`
through `AI-004` complete.

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
closed, and reopened through recruiter-facing lifecycle controls. The matching
foundation now includes an organization-owned normalized skill vocabulary,
candidate skill evidence, version-specific must-have/nice-to-have skill links,
and typed hard-constraint rules. Unknown candidate facts are fixed as `keep for
recruiter review`, and protected characteristics are not supported rule types.
Recruiters can evaluate the active organization candidate pool against a
vacancy's current confirmed rules and inspect pass, fail, or unknown results,
expected values, candidate facts, evidence, and explanations. Unknown facts
remain eligible for review. Recruiters can generate a persistent shortlist of
up to 20 eligible candidates ranked by an inspectable deterministic skill score.
Each must-have skill has twice the weight of each nice-to-have skill, with the
combined weights normalized to exactly 100 points; every recorded match, missing
fact, evidence item, and point contribution is visible. Each match run also stores privacy-preserving signatures of the
confirmed vacancy inputs and active candidate matching facts. A historical run
is clearly labelled stale when either input set changes; regeneration creates a
new run without rewriting the saved ranking. The app uses the published
`python-ai-toolkit==1.0.0` distribution through an application-owned, lazy AI
gateway. The gateway returns validated data plus safe metadata, excludes raw
responses, translates provider/toolkit failures into bounded application errors,
and supports fake substitution. Recruiters can now intentionally extract bounded,
structured vacancy-requirement suggestions from a preserved source description.
The suggestions remain an editable draft, never create executable rules, and
still require explicit recruiter confirmation. Recruiters can also intentionally
extract a versioned candidate-profile draft from a successfully parsed CV. The
application removes contact and sensitive prefixed lines before the request,
requires source-verifiable evidence, keeps missing facts explicitly unknown, and
publishes matching facts and skills only after a separate recruiter confirmation.
On a current deterministic shortlist, recruiters can request a separate,
versioned AI match assessment for any candidate with a confirmed profile. The
assessment evaluates every confirmed requirement, resolves model references back
to application-owned vacancy and candidate evidence, marks unsupported facts as
uncertain, derives a red/amber/green band from its separate AI score, and leaves
the deterministic rank and eligibility unchanged. It provides recruiter review
focus only; it cannot approve, reject, contact, or rank a candidate.

The next approved task is `AI-005 — Store request metadata and safe failure
information`.

## Local setup

Python 3.11 through 3.14 and [uv](https://docs.astral.sh/uv/) are supported.

```powershell
uv sync --extra dev
Copy-Item .env.example .env
uv run python manage.py migrate
uv run python scripts/check.py
```

An OpenAI API key is not needed for Django startup, deterministic matching, or
the ordinary test suite. Add it to `.env` only when a later opt-in AI request is
intentionally run:

```env
OPENAI_API_KEY=
```

The default AI model is configured through `AI_MODEL`, or `OPENAI_MODEL` for the
default provider. See `.env.example` for the provider, model, embedding, retry,
and generic key fallbacks. Toolkit file logging is disabled by the application.

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
After a CV extracts successfully, select **Extract profile** to run the optional
AI workflow. Review its exact source excerpts and explicit ambiguities on the
versioned draft page. Only **Confirm profile** publishes the profile's grounded
skills and facts to deterministic matching; extraction alone does not change a
shortlist or matching input. Extracted CV text, contact details, prompts, and raw
provider output are never shown on the review page.

Open **Vacancies** to paste a job description. Every new vacancy receives an
editable requirements version 1. Recruiters enter list values one per line, save
the draft, add executable typed hard-constraint rules in the same editor, and
explicitly confirm it. Operators and missing-fact behavior are fixed by rule type;
recruiters cannot turn unknown evidence into automatic rejection. Confirmed
versions are read-only; **Create correction draft** copies the current snapshot
and its typed rules into the next numbered version.
On an editable requirements version, **Extract with AI** sends only the preserved
vacancy source description and replaces the draft's structured suggestions after
schema validation. Review every field, then add any executable typed rules
deliberately before confirmation. A missing or invalid AI configuration produces
a bounded error and leaves the current draft unchanged.
After confirmation, use the vacancy detail page to open, pause, close, or reopen
the vacancy through the available validated lifecycle transitions. Candidate and
vacancy detail pages also provide confirmation-based deletion. Candidate deletion
purges current private candidate content and stored CV files; vacancy deletion
hides the vacancy while retaining its immutable requirements history.

For a complete browser walkthrough and safe synthetic CSV, PDF, DOCX, rejection,
and vacancy fixtures, follow `docs/manual_testing_guide.md`.

Normalized skills and candidate-skill evidence can still be inspected in Django
admin. Typed vacancy rules are created, edited, and deleted from the normal draft
requirements screen, and confirmed rules remain visible on the vacancy page.
After confirming a requirements version, open the vacancy and select
**Evaluate candidates** for recruiter-facing deterministic results. This stage
does not call an AI provider. From that report, select **Generate shortlist** to
persist and inspect a version-labelled ranking of up to 20 eligible candidates.
The shortlist page labels the result current or stale. A stale warning explains
whether confirmed vacancy requirements, active candidate matching inputs, or a
legacy untracked snapshot requires regeneration; saved history is never silently
recomputed. On a current shortlist, candidates with confirmed profiles expose
**Generate AI assessment**. Each explicit request handles one candidate, creates
an immutable numbered assessment, and shows evidence-linked matches, gaps,
uncertainties, score band, and recruiter review focus beneath the unchanged
deterministic result. Regeneration creates another assessment version.

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
