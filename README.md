# AI Candidate Matcher

AI-assisted candidate rediscovery and shortlisting for small recruitment agencies and employers.

The application searches a lawful, organization-controlled candidate pool. Recruiters create a vacancy, the system applies deterministic filters, AI produces evidence-based match assessments, and a human approves every shortlist and outreach draft.

This repository is intentionally separate from Python AI Toolkit. The application consumes the published package:

```text
python-ai-toolkit[django]==1.0.0
```

## Current status

Sprint 0 through Sprint 6, `EVAL-001` through `EVAL-003`, and `DEMO-001` are
complete. Evaluation and showcase work continues with `DEMO-002`.

The managed-SaaS workflow separates platform ownership from Django technical
administration and tenant membership. Platform owners provision organizations
and first administrators, manage administrator memberships, and use staged
organization suspension/recovery without receiving recruitment-content access.
Organization administrators manage recruiter memberships in the normal app.
Existing users can belong to several isolated workspaces and switch explicitly;
deactivating one membership leaves their account and other workspaces unchanged.
Public signup, invitation delivery, subscriptions, and billing are not included.

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
numbered correction versions. Organization administrators manage optional client
companies in the normal workspace; recruiters can edit a vacancy's title/client,
inactive clients cannot be newly assigned, and historical links remain intact.
Confirmed vacancies can then be opened, paused,
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
If a schema-valid response paraphrases or misaligns an evidence excerpt, the app
makes one bounded correction request against the same redacted source and still
requires the replacement to pass every exact grounding check before saving.
Extraction scans the complete CV for explicitly named job-relevant skills rather
than relying only on a Skills heading. Related facts such as `pytest` and
`Automated testing` remain separate when both are stated, and neither is inferred
from the other.
On a current deterministic shortlist, recruiters can request a separate,
versioned AI match assessment for any candidate with a confirmed profile. The
assessment evaluates every confirmed requirement, resolves model references back
to application-owned vacancy and candidate evidence, marks unsupported facts as
uncertain, derives a red/amber/green band from its separate AI score, and leaves
the deterministic rank and eligibility unchanged. It provides recruiter review
focus only; it cannot approve, reject, contact, or rank a candidate.
Every intentional AI request now creates a tenant-scoped usage event after its
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
inspectable. Recruiter edits append immutable versions rather than overwriting
history. Final approval binds one exact latest version with notes, contact-
permission attestation, actor, and timestamp. Only an exact approved current
version with explicit permitted contact can be copied or exported as plain text;
each action is recorded. No recipient is selected and nothing is sent.
Candidate CVs now have an authenticated, tenant-scoped, attachment-only download
that repeats authorization and verifies the stored size and SHA-256 before
delivery. Private responses are non-cacheable and expose neither the opaque
storage key nor extracted text. Upload validation additionally rejects filename
control characters, PDF scripts/launch actions/embedded files, DOCX symlinks,
duplicate entries, embedded active content, and unsafe external package
relationships. Organization-level serialization closes the duplicate-upload
race without preventing another organization from storing the same document.
Recruiters also have a tenant-scoped privacy and audit dashboard with retention
exceptions, staged deletion requests, minimized workflow histories, and deleted-
record integrity checks. Candidate deletion now freezes the record first; a
separate administrator action cancels the request or permanently purges it.
The schedulable retention command is a dry run by default and can only flag due
candidate records for review—it never auto-purges data. Immutable privacy events
record controlled IDs/actions/actors/timestamps without copying candidate,
prompt, decision-note, or outreach content.

Recruiters can queue each active candidate's newest successfully parsed,
unprofiled CV from **Candidates**, and can queue one assessment target for every
entry in a current shortlist. A separate durable database-backed worker claims
targets with expiring leases, isolates failures per candidate, reuses already
saved results after interruption, and exposes compact tenant-scoped job status
plus explicit exception retry. Profile jobs create drafts only; profile
confirmation, approve/reject/revisit decisions, and outreach remain separate
individual actions. Repeating the same batch request returns the existing job
instead of repeating routine AI work.

Recruiters also have a tenant-scoped **AI usage** report derived from the existing
minimized event ledger. Period and workflow filters expose aggregate attempts,
outcomes, token/cost/latency/retry coverage, workflow/model breakdowns, safe
failure categories, and bounded daily trends. Missing provider metadata is shown
as unavailable instead of being estimated, and the report contains no prompts,
responses, CV/contact data, recruiter notes, or outreach content.

Production now has a documented single-server reference topology: PostgreSQL,
Gunicorn behind Nginx, a separately supervised durable worker, a safe daily
retention-review timer, persistent private media, backups/restore drills, and
generic liveness/readiness endpoints. Production startup rejects missing
database/private-storage configuration, and `check_production` verifies Django
deployment settings, PostgreSQL/migrations, collected static assets, and a
private-media round trip without printing secrets or recruitment content.

`EVAL-002` is complete. A provider-free management command measures frozen
deterministic and complete-current AI-assisted rankings separately at cutoff 5
using nDCG, precision, expected-top overlap, and explicit AI coverage. The
systems are never blended, partial AI coverage is unavailable, stale inputs are
refused, and reports copy no private recruitment content. `EVAL-003` adds a
second provider-free, read-only command that verifies stored evidence snapshots
and requirement coverage, flags explicit protected-attribute language and
high-confidence unsupported claims, and reports incomplete assessment coverage
as unavailable. New assessment output with explicit protected/sensitive
attribute language is rejected before persistence. Neither evaluation changes
scores, assessments, decisions, or outreach. `DEMO-001` adds a provider-free
synthetic setup command, a safety-bound walkthrough, and real reference
screenshots of the shortlist, review, assessment, and blocked outreach workflow.
The next approved task is `DEMO-002 — Prepare a client-facing README and Upwork
Project Catalog positioning`.

## Reproducible demo

After creating an active user, build an isolated showcase without an AI key:

```powershell
uv run python manage.py prepare_demo --username admin --organization-slug synthetic-demo-001
uv run python manage.py runserver
```

The command refuses to overwrite an existing organization and prints the exact
dashboard, shortlist, review, assessment, and draft routes. It creates only
synthetic EVAL-001 records, stops before final outreach approval, and keeps
Allowed contact set to **Application only**. See [`docs/demo.md`](docs/demo.md) for the
five-minute walkthrough and verified screenshots.

## Local setup

Python 3.11 through 3.14 and [uv](https://docs.astral.sh/uv/) are supported.

```powershell
uv sync --extra dev --locked
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
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

Run the durable worker in a second PowerShell window. `--burst` processes all
currently queued targets and exits; omit it for a continuous worker:

```powershell
uv run python manage.py run_background_worker --burst
```

Open `http://127.0.0.1:8000/admin/` and create one ordinary user with **Platform
owner** enabled. This is the technical bootstrap step; a Django superuser alone
is not a platform owner and never bypasses tenant membership. Sign in as the
platform owner at `/`, select **Platform → Create organization**, and create the
tenant plus its first administrator. Sign in as that administrator to manage
recruiters under **Organization settings → Team members** and optional clients
under **Organization settings → Client companies**. New managed users can replace
their temporary password through **Change password** in normal navigation.

After signing in to the normal application, open the organization workspace and
select **Candidates**. You can create a candidate manually or download the CSV
header template from **Import CSV**. Imports accept up to 2 MB and 2,000 rows;
`full_name` is required, while `email`, `phone`, `location`, `source_reference`,
and ISO `retention_until` are optional.

Open a candidate and select **Upload CV** to add a PDF or DOCX file up to 10 MB.
Password-protected, malformed, active-content, embedded-payload, macro-enabled,
textless/scanned, or resource-heavy documents are rejected. An authorized
organization member can select **Download original**. Delivery is attachment-
only, private/no-store, tenant-scoped, and blocked if stored bytes no longer
match their saved size and SHA-256. No public media URL or opaque storage path is
exposed.
After a CV extracts successfully, select **Extract profile** to run the optional
AI workflow. Review its exact source excerpts and explicit ambiguities on the
versioned draft page. Only **Confirm profile** publishes the profile's grounded
skills and facts to deterministic matching; extraction alone does not change a
shortlist or matching input. Extracted CV text, contact details, prompts, and raw
provider output are never shown on the review page.

Open **Vacancies** to paste a job description. Every new vacancy receives an
editable requirements version 1. Recruiters can select an active optional client
or leave the vacancy in direct-employer mode. **Edit vacancy** changes only the
display title/client and does not rewrite the original description or requirements
source snapshots. Recruiters enter list values one per line, save
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
inspectable and actor-attributed. The latest current version can be edited into a
new immutable version, then separately approved after explicit contact-permission
checks. Only that exact approved version exposes manual copy and `.txt` export;
both actions are actor-attributed, and sending remains unavailable.

## Production deployment

The supported reference deployment is PostgreSQL plus Gunicorn behind an HTTPS
reverse proxy, with a separate continuously supervised background worker and
persistent private media storage. Follow [docs/deployment.md](docs/deployment.md)
and adapt the version-controlled examples under `deploy/`.

Production fails closed without explicit security, PostgreSQL, and private-media
settings. `check_production` verifies Django deployment checks, PostgreSQL
connectivity and migration state, collected static assets, and private-media
read/write/delete access before a service restart.

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
- `docs/deployment.md`
