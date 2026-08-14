# AI Candidate Matcher

AI-assisted candidate rediscovery and shortlisting for small recruitment agencies and employers.

The application searches a lawful, organization-controlled candidate pool. Recruiters create a vacancy, the system applies deterministic filters, AI produces evidence-based match assessments, and a human approves every shortlist and outreach draft.

This repository is intentionally separate from Python AI Toolkit. The application consumes the published package:

```text
python-ai-toolkit[django]==1.0.0
```

## Current status

Sprint 0 through Sprint 4 are complete. Sprint 5 is in progress: `REV-001`,
`REV-002`, and `OUT-001` are complete, and `OUT-002` is next.

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
Every intentional AI attempt now creates a tenant-scoped usage event after its
domain preconditions pass. Successful events retain only safe request ID, model,
duration, retry, token, cost, workflow/target/result IDs, actor, and timestamps;
failed events retain an allow-listed gateway or application-validation category.
Prompts, source descriptions, CV text, candidate identity/contact data, raw
responses, provider exception messages, and user-visible validation text are not
stored in the ledger. The operational records are read-only in Django admin.
The three AI workflows now share a provider-free fake gateway and an explicit
application contract tested against both the fake and published-toolkit adapter.
A separately invoked synthetic live smoke test is outside the ordinary test path
and cannot run without an explicit environment switch.
Recruiters now have an organization-scoped assessment review queue that shows
only the latest assessment per shortlist entry, places changed inputs, gaps,
uncertainties, profile ambiguities, and deterministic unknowns first, and keeps
routine assessments available under **All**. Each assessment has a dedicated
evidence-linked detail screen with immutable version history. The review surface
keeps decision state separate from assessment evidence and never triggers outreach.
Recruiters can now record an individual approve, reject, or revisit decision
from the exact latest assessment reviewed. Every immutable decision version
requires notes and records the human actor and timestamp; stale or older evidence
cannot receive a current decision. Decisions never change scores or generate
outreach automatically. From the exact latest explicit approval, a recruiter can
now separately generate immutable numbered outreach drafts while the assessment,
confirmed profile, and shortlist inputs remain current. The AI request uses a
candidate-name placeholder and confirmed positive match evidence, excluding
identity/contact data, raw CV text, recruiter notes, gaps, and uncertainties.
Every draft records its source approval, actor, and timestamp and remains
inspectable without any edit, final-approval, copy, export, or send action.

The next approved task is `OUT-002 — Add editing, final approval, copy, and
export`.

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
The optional potentially billable synthetic smoke test is documented in
`live_tests/README.md`; it is not collected by `scripts/check.py`.

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
Open **Reviews** from the organization navigation to inspect the exception-first
queue. **Decision pending** is the compact default; **Needs focus** shows evidence
exceptions, **Changed inputs** isolates stale evidence boundaries, and **All**
keeps routine or already-decided latest assessments individually inspectable. The
detail screen shows evidence, profile ambiguities, currentness, and all immutable
versions before any individual decision is recorded.
From a current latest assessment, the recruiter can record an individual
**Approve**, **Reject**, or **Revisit later** decision with mandatory notes.
Corrections append history rather than editing it, and the pending queue updates
without creating outreach automatically or contacting the candidate. When the
latest decision is an approval and all evidence is current, the same review page
offers a separate **Generate outreach draft** POST action. Generated versions are
inspectable and actor-attributed, but editing, final approval, copy, export, and
sending are intentionally unavailable until `OUT-002`.

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
