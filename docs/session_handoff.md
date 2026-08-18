# AI Candidate Matcher — Session Handoff

## Project

AI Candidate Matcher

Current version: `0.1.0.dev0`

## Goal

Continue developing an AI-assisted candidate rediscovery and shortlisting application for small recruitment agencies and employers.

The organization supplies or authorizes the candidate pool. The app does not scrape arbitrary websites. It filters candidates, creates evidence-based AI assessments, requires recruiter review, and generates editable outreach drafts that are copied or exported manually.

## Current status

Sprint 0 through Sprint 6, the user-approved corrective `INTAKE-001` task, and
`EVAL-001` and `EVAL-002` are complete. Sprint 7 is in progress; `EVAL-003` is the next
approved roadmap task.

`FOUND-001` through `FOUND-005` and `DATA-001` through `DATA-005` are complete. The project now has a Django
5.2.17 LTS foundation, a custom user model, organizations, memberships,
constrained administrator/recruiter roles, optional organization-owned client
companies, organization-scoped queryset and authorization helpers, login and
POST-only logout, responsive base templates, organization selection, and a
minimal organization dashboard. It also has strict environment parsing,
fail-closed production configuration, initial migrations, dependency locking,
pytest-django and Ruff configuration, import-isolation tests, one local/CI
quality command, and a Python 3.11–3.14 GitHub Actions matrix. It also has
organization-owned candidate, source/consent, and private candidate-document
models with tenant-scoped querysets, database constraints, retention/deletion
metadata, and Django admin support. Organization-owned vacancies now support an
optional same-organization client and versioned requirement snapshots with
source/schema provenance, structured requirement fields, confirmation metadata,
and immutable confirmed history. Recruiters now have organization-scoped candidate
lists, manual candidate/provenance entry, and validated CSV import with a template,
per-row created/duplicate/invalid reporting, and tenant-local stable-identity
checks. Recruiters can also upload PDF/DOCX CVs through a tenant-safe service that
validates content, applies bounded parsing and archive limits, extracts text,
stores private opaque-path files and hashes, and shows no raw text or storage path
in recruiter HTML. Recruiters can now list and create vacancies from pasted
descriptions, choose an optional organization-owned client, edit normalized
structured requirements, confirm meaningful versions through POST-only human
review, and create numbered correction drafts without changing confirmed
history. A detailed manual test guide and validated synthetic CSV/PDF/DOCX/job
fixtures are included. Vacancy and candidate-profile extraction are available
only through explicit draft actions described below.

A corrective `DATA-005` pass also makes completed CSV imports target the visible
report section and adds recruiter-facing, POST-only vacancy lifecycle controls.
Opening requires confirmed requirements; only draft-to-open, open-to-paused or
closed, paused-to-open or closed, and closed-to-open transitions are accepted.
The follow-up deletion pass added confirmation pages for candidates and
vacancies. `PROD-002` later replaced immediate candidate purge with the staged
request/administrator approval described below. Vacancy deletion still hides and
closes the record while preserving requirement history with deletion actor/time.

`MATCH-001` is also complete. It adds organization-owned normalized skills,
candidate skill evidence, versioned must-have/nice-to-have requirement links,
and typed hard-constraint rules with validated operator/payload combinations.
Unknown candidate facts are forced to remain eligible for recruiter review;
protected characteristics are not rule types. Existing requirements are
backfilled through a data migration, confirmed definitions are immutable, and
correction drafts copy the normalized links and typed rules. Filtering and rule
evaluation are implemented in `MATCH-002`.

`MATCH-002` evaluates only the current confirmed requirements against active
same-organization candidates. It returns inspectable pass/fail/unknown results
with recruiter source wording, expected and observed values, evidence, and an
explanation. Any explicit failure makes the candidate ineligible; missing or
partial evidence remains unknown and eligible for review. A recruiter opens the
vacancy and selects **Evaluate candidates** to see summary counts and paginated
per-candidate rule details. The evaluation does not inspect raw CV text, make an
AI request, or make a hiring decision.

`MATCH-003` is complete. After hard filtering, a recruiter can generate a
persistent, version-labelled shortlist containing at most 20 eligible candidates.
Explicit failures are excluded first. Scoring algorithm v2 gives every
must-have skill two weight units and every nice-to-have skill one, then
apportions exactly 100.00 points across the confirmed requirements. Each visible
score row shows the requirement, recorded candidate skill, evidence, and awarded
points. Missing skill evidence earns no points but is not treated as proof of absence. Runs retain
their requirements and algorithm versions, actor, counts, ranking, and score
breakdown. Generation is POST-only, tenant-scoped, and never makes an AI request
or hiring decision.

`MATCH-004` is complete. Each generated run records versioned SHA-256 signatures
for its confirmed vacancy inputs and active candidate matching facts. When a run
is viewed, an organization-authorized service compares those signatures with the
current requirements and candidate pool. New confirmed requirements, active
candidate additions/removals, candidate deletion, location changes, and
skill/experience/evidence changes clearly mark the historical run stale. Facts
unused by deterministic matching do not trigger false invalidation. Stale scores
remain immutable, regeneration creates a separate run, and pre-signature runs
are explicitly treated as stale.

Typed hard-constraint rules are managed in the normal recruiter application while
a requirements version is still a draft. The editor limits required-skill rules
to saved must-have skills, derives the operator and payload from the selected rule
type, fixes missing facts as `keep for recruiter review`, and uses a separate
delete-confirmation screen. Draft skill changes and confirmation both revalidate
all typed rules atomically. Confirmed rules are visible but immutable, and
corrections copy them into a new draft. The free-text hard-constraint field is
labelled as non-executable notes.

`AI-001` is complete. The plain `ai_gateway` package now owns a toolkit-neutral
protocol, validated result envelope, safe request metadata, bounded application
exceptions, configured factory, and a lazy `ToolkitAIGateway` backed by the
published v1.0.0 Django integration. Toolkit raw/original responses are never
returned through the application contract, underlying provider error text is
suppressed, file logging remains disabled, and no API key or request is required
for startup or ordinary tests. `AI-001` itself introduced no domain prompt or
provider-backed business workflow.

`AI-002` is complete. Recruiters can trigger structured extraction from an
editable requirements draft through the application gateway. The bounded
application-owned schema preserves unknowns, separates explicit must-have and
nice-to-have skills, excludes extra fields, and uses controlled vocabulary for
work mode and employment type. Successful output remains an AI-assisted draft,
synchronizes normalized skills, and never confirms requirements or creates typed
executable rules. Gateway failure and concurrent recruiter edits preserve the
existing draft. Candidate data is not involved; its safe usage metadata and
bounded failures are now recorded separately by `AI-005`.

`AI-003` is complete. Recruiters can trigger candidate-profile extraction from a
successfully parsed CV. The application removes contact and sensitive prefixed
content before the request, applies a bounded extra-forbidding schema, verifies
every returned evidence excerpt against the redacted source, normalizes only
presentation-level document punctuation during that comparison, and stores a new
numbered draft without changing deterministic matching. A separate recruiter
confirmation publishes grounded profile facts and normalized skills. Confirmed
profiles are immutable matching inputs, unknown or non-matching facts remain
eligible for review, and profile confirmation makes affected saved shortlists
stale. Manual candidate-skill assertions are preserved. Raw CV text, prompts,
provider output, contact data, and assessments are not stored or displayed by
this workflow; only the separate safe AI usage ledger retains operational
metadata.

A corrective `AI-003` pass on 2026-08-15 handles schema-valid responses that
paraphrase evidence or attach a fact to an excerpt that does not name it. The
app records that request as a safe application-validation failure and makes
exactly one correction request using the same redacted source plus privacy-safe
field locations, never the failed provider output. The replacement must pass the
unchanged exact grounding checks. A second failure names only bounded schema
areas, saves nothing, and makes no third request. Each request has its own safe
usage event; no migration or toolkit change is required.

The same corrective pass now requires a complete-CV skill scan instead of
favoring only a Skills heading. Explicit narrative competencies are requested
using source-supported wording, so the synthetic Arben profile may contain both
`pytest` and `Automated testing` when both are stated. Related tools, methods,
synonyms, or umbrella skills are never inferred from one another. Exact evidence
validation and separate recruiter confirmation remain unchanged.

`AI-004` is complete. Recruiters can explicitly assess one candidate on a
current deterministic shortlist when that candidate has a confirmed profile.
The bounded structured request uses opaque IDs for confirmed requirements and
candidate evidence, requires every requirement exactly once, requires supplied
evidence for a match or gap, and keeps unsupported facts uncertain. Accepted IDs
are resolved back to application-owned source wording before an immutable
numbered `MatchAssessment` is saved. The app derives the score band, rejects
decision/contact language, and rechecks profile and shortlist freshness after
the provider returns. Assessment versions appear beneath the unchanged
deterministic result with evidence-linked matches, gaps, uncertainties, and
recruiter review focus. Its safe usage metadata and bounded failures are now
recorded separately by `AI-005`; no approve/reject decision, outreach,
background batch, prompt, raw response, identity/contact data, or raw CV text
was added.

`AI-005` is complete. The new `audit.AIUsageEvent` ledger creates one pending
tenant-scoped record after domain preconditions pass and before each configured
AI attempt. Successful vacancy extraction, profile extraction, and assessment
finalize safe request/model/duration/retry/token/cost metadata plus generic
target/result IDs in the same transaction as their domain result. Gateway
failures persist only an allow-listed code and stage; completed output rejected by
application validation may retain safe metadata with one generic validation code.
Completed events are immutable and read-only in Django admin. There are no fields
for prompts, raw responses, provider/validation messages, source text, CV text,
candidate identity, or contact data. Failure metadata not exposed by toolkit
v1.0.0 is left blank rather than inferred. `PROD-004` now reports aggregates over
this ledger while keeping those unavailable fields explicit.

`AI-006` is complete. `ai_gateway.testing.FakeAIGateway` is now the reusable
provider-free test double for all application AI business workflows. It shares
non-blank prompt and Pydantic response-type validation with `ToolkitAIGateway`,
captures normalized calls, supports static/dynamic schema-valid output and
bounded errors, and rejects mismatched test output. Shared contract tests exercise
both adapters and preserve the application-owned result/metadata boundary without
raw responses. A tiny synthetic live structured smoke test lives under
`live_tests`, outside ordinary pytest `testpaths`; it requires
`RUN_LIVE_AI_SMOKE=1`, may incur one provider charge, uses no recruitment or
database data, and is documented separately. No toolkit issue was reproduced.

`REV-001` is complete. Recruiters can open an organization-scoped review queue
that consolidates immutable history to the latest assessment per shortlist
entry. Changed shortlist/profile inputs, evidence-backed gaps, uncertainties,
confirmed-profile ambiguities, and deterministic unknown-fact flags appear
before routine assessments; routine items remain available through **All** and
are never silently approved. A dedicated detail screen shows application-owned
vacancy/candidate evidence, separate AI and deterministic scores, profile
ambiguities, currentness warnings, recruiter review focus, and all immutable
assessment versions. The workflow reuses confirmed profiles and creates no new
model or migration. It adds no decision, background batch, or outreach action.

`REV-002` is complete. Recruiters can record an individual approve, reject, or
revisit decision only from the exact latest assessment while its confirmed
profile and shortlist inputs remain current. Every immutable numbered decision
requires recruiter notes and records a protected human actor and timestamp.
Corrections append history rather than editing it. The queue defaults to pending
decisions and shows current decision counts/status under its other scopes; a
decision tied to an older assessment is not carried onto a newer assessment.
Cross-organization and stale actions are blocked, candidate deletion removes the
candidate-specific decision history, and Django admin is read-only. Decisions do
not change any score/evidence and create no outreach automatically.

`OUT-001` is complete. Recruiters can separately generate an immutable numbered
outreach draft only from the exact latest explicit approval while the linked
assessment, confirmed profile, and privacy-preserving shortlist inputs remain
current. Each generated draft records its source decision, human actor,
timestamp, bounded subject, and plain-text body. The service locks and rechecks
approval/currentness after the provider returns and creates no partial draft on
bounded failure. The minimized request uses a candidate-name placeholder plus
organization-approved vacancy and positive match facts; it excludes candidate
identity/contact data, raw CV text, recruiter notes, gaps, uncertainties, scores,
and protected characteristics. The application substitutes the real name only
after structured safety validation. At the `OUT-001` milestone, recruiters could
inspect version history but could not edit, approve, copy, export, or send a
draft. Safe outreach AI usage metadata is recorded without prompts or model
responses, cross-organization routes are hidden, candidate deletion removes
draft history, and Django admin is read-only.

`OUT-002` is complete. Recruiter edits append immutable numbered draft versions
with parent-version provenance, actor, and timestamp rather than changing
generated or historical text. Separate final approval binds one exact latest
subject/body and records required notes, contact-permission attestation, actor,
and timestamp. Approval and manual use require the source recruiter decision,
latest assessment, confirmed profile, shortlist inputs, and draft version to
remain current. At least one candidate source must explicitly permit contact;
restricted/withdrawn contact or withdrawn consent blocks the workflow. Only the
exact approved current draft exposes clipboard copy or a no-store plain-text
export, and each action records the exact draft, actor, and timestamp. The server
rechecks permission/currentness before returning content. No recipient is chosen,
no provider or AI request is made by these human steps, and nothing is sent.

`PROD-001` is complete. Recruiters can download an original candidate CV only
through an authenticated tenant-scoped attachment route. The application repeats
service authorization, loads no more than the existing upload bound, and verifies
the stored length and SHA-256 before delivery. Private/no-store, no-sniff,
sandbox, same-origin resource, no-referrer, and no-index headers protect the
response; opaque storage paths and extracted text remain hidden. Uploads now
reject filename control/format spoofing, PDF scripts/launch actions/embedded
files, and DOCX duplicate entries, symlinks, active embedded objects, malformed
relationships, and unsafe external package relationships. The final
same-organization duplicate check is serialized before save. No AI, toolkit,
audit view/event, retention scheduler, background task, or observability scope
was added.

`PROD-002` is complete. Recruiters have a tenant-scoped **Privacy & audit**
dashboard with candidate/source/document retention exceptions, missing-date
counts, a staged candidate deletion queue, deleted-tombstone minimization checks,
immutable privacy events, and compact histories over existing AI usage, CSV
source, assessment, decision, outreach-approval, and copy/export records. These
views omit contact fields, CV/source text, prompts, raw responses, decision and
approval notes, and outreach content.

Candidate deletion now requires two explicit stages. An organization member
requests deletion, freezing the candidate from new uploads, extraction, and
matching while preserving data for review. An organization administrator then
either cancels and restores the exact prior active/inactive status or approves a
second irreversible purge. Purge removes private bytes and all candidate-owned
provenance/profile/matching/decision/outreach data, clears temporary request
metadata, and retains only the minimized candidate tombstone plus content-free
request/purge events.

The schedulable `process_retention` command reports only organization slug and
aggregate due count, is dry-run by default, and with `--apply` idempotently stages
candidate-level expiry for the same review queue. It never auto-purges; source
and document expiry remain individually inspectable signals. Private CV download
and vacancy deletion also create controlled audit events. `PROD-002` adds
`audit.0003_auditevent` and
`candidates.0005_candidate_deletion_requested_by_and_more`. It adds no AI or
toolkit change, background queue, cost/latency aggregation, recipient, or send
action.

`PROD-003` is complete. The new application-owned `operations` app stores
durable tenant-scoped `BackgroundJob` and `BackgroundTask` records with
controlled target/result IDs, deterministic idempotency keys, aggregate status,
attempt counts, expiring leases, and content-free failure codes. It adds
`operations.0001_initial`.

From **Candidates**, a recruiter can queue each active candidate's newest
successful CV only when that source has no draft or confirmed profile. From a
current shortlist, one action queues every entry. Repeating the same source set
or match run returns the existing job. The separate
`run_background_worker` command supports continuous, `--once`, `--burst`, and
job-scoped processing. It reclaims expired leases, checks for an already saved
exact-source profile or exact-input assessment before calling AI, and isolates
each target's provider, authorization, validation, missing-record, or unexpected
failure. Explicit retry requeues only exceptions.

The tenant-scoped **Jobs** pages expose compact status and resolve candidate and
result links from current domain records without copying private content into the
queue. Profile results remain drafts requiring evidence inspection and
individual confirmation. Assessment results enter the existing review flow;
approve/reject/revisit and outreach remain separate individual actions.

`PROD-004` is complete. The tenant-scoped **AI usage** page derives aggregate
attempt, outcome, token, cost, latency, retry, model, workflow, safe-failure, and
daily trend reporting from existing minimized `AIUsageEvent` records. Filters
support 7, 30, and 90 days or all time and individual workflows. Metadata
coverage is explicit, and absent provider metadata remains unavailable rather
than being estimated. The report contains no request IDs or private recruitment
content. No toolkit or database migration change was needed.

The shared quality gate also supplies every required HTTPS value to its isolated
production-check subprocess. This prevents a normal development `.env` with
secure cookies disabled from overriding the deployment check.

`PROD-005` is complete. Production now requires explicit PostgreSQL and an
absolute persistent private-media root separate from static assets. Gunicorn,
Psycopg, generic health endpoints, `check_production`, and reference Nginx and
systemd artifacts cover web serving, the separate continuous worker, release
preparation, and safe retention scheduling. The deployment runbook documents
secrets, TLS/proxy trust, migrations/static, monitoring, paired database/media
backups, isolated restore drills, upgrades, rollback, and acceptance checks.
The quality gate also collects static assets under its isolated production
configuration. Local setup now guards `.env` from accidental overwrite. No AI,
toolkit, recruiter-decision, or outreach behavior changed.

`INTAKE-001` is complete. Recruiters can create a tenant-scoped bulk intake with
shared source, lawful-basis, consent, contact-permission, notes, and retention
defaults, then upload several PDF/DOCX CVs for isolated validation. The app
proposes name, email, phone, and header location locally, marks missing/multiple/
filename-derived values for compact review, and sends no identity/contact data to
AI. Exact-file duplicates are rejected before staging, stable-identifier
duplicates block creation, and only explicitly selected edited rows create an
active candidate, `DOCUMENT_UPLOAD` source, and private CV transactionally.

Processed or discarded intake items clear their temporary file, extracted text,
identity/contact proposals, hash, and file metadata. A checked action queues only
the newly accepted CVs through the existing durable profile-extraction job; the
worker still creates evidence-validated drafts only. Profile confirmation, final
candidate decisions, outreach approval, and sending boundaries are unchanged.
`INTAKE-001` adds
`candidates.0006_candidateintakebatch_candidateintakeitem_and_more`; it changes
no AI gateway, toolkit dependency, prompt, or operations schema.

`EVAL-001` is complete. The strict version-controlled
`eval-001.synthetic-multirole.v1` manifest contains 20 obviously synthetic
candidates, 3 synthetic vacancies, exact deterministic top-five ranks/scores,
and a complete 0–3 relevance judgment for every candidate/vacancy pair. A safe
management command installs it only into a new isolated organization for an
existing active user and refuses to overwrite existing data.

The installer generates private DOCX CVs from the manifest, validates them
through the normal hardened document service, creates schema-valid profiles with
evidence exactly present in each generated document, and confirms those profiles
without a provider call. It creates, edits, confirms, and opens each vacancy
through existing services, generates its deterministic shortlist, and verifies
the frozen expected ranks and scores. Any mismatch rolls back database changes
and removes generated files. Synthetic contacts are empty and contact permission
is restricted. No usage event, assessment, decision, outreach, model, migration,
algorithm, prompt, gateway, toolkit, or production behavior was added or changed.

`EVAL-002` is complete. Its read-only service and management command bind the
frozen manifest to the exact isolated workspace, reject incomplete fixture sets
or stale deterministic runs, and measure each vacancy plus macro quality at
cutoff 5. Metrics are graded nDCG, grade-2-or-3 precision, and expected-top-set
overlap. The unchanged deterministic baseline is `1.0000`, `0.9333`, and
`1.0000` respectively.

AI-assisted ordering is independently derived from each entry's latest current
assessment score; deterministic rank is used only to break equal AI scores.
There is no blended score. A vacancy has AI quality only with 20/20 current
assessments, the macro requires 60/60, and partial or profile-stale coverage is
reported unavailable. The command makes no provider request and its text/JSON
reports contain only dataset identity, organization slug, vacancy codes,
metrics, and counts. It stores no report, usage event, decision, or outreach
action and adds no model or migration.

## Recruiter-efficiency requirement

Do not treat the current per-candidate generation actions as the final high-volume UX.
Confirmed profiles are reusable across vacancies and should be re-extracted only
for new or corrected source/profile data. `REV-001` now provides a compact queue
emphasizing gaps, ambiguities, changed facts, and evidence exceptions.
`PROD-003` adds resumable background batch profile extraction and one
whole-shortlist assessment action with per-candidate failure isolation. Existing
profiles and exact-input assessments are reused, interrupted leases are
reclaimable, and safe job status plus explicit exception retry are available.
Profile drafts still require individually inspectable evidence and explicit
confirmation. Final approve/reject/revisit decisions remain individual recruiter
actions with notes, actor, and timestamp, and outreach remains separate.

The next roadmap item is:

`EVAL-003 — Review explanations for evidence, unsupported claims, and
protected-attribute leakage.`

## Required instructions

1. Read `AGENTS.md` completely.
2. Read `docs/project_state.md`, `docs/roadmap.md`, `docs/product_spec.md`, `docs/architecture.md`, `docs/toolkit_integration.md`, and `docs/toolkit_feedback.md` before changing anything.
3. Inspect the repository; do not assume files or APIs exist.
4. Implement only the next approved roadmap task.
5. Do not redesign, skip ahead, or expand scope without a concrete reason and user approval.
6. Keep the application separate from Python AI Toolkit.
7. Initially install the published `python-ai-toolkit[django]==1.0.0` package.
8. Do not copy or edit toolkit source inside this repository.
9. Record suspected toolkit improvements in `docs/toolkit_feedback.md`; treat them as unverified until reproduced.
10. Keep recruitment decisions human-controlled and exclude protected characteristics from matching.

## Current verification

`PROD-005` verification completed on 2026-08-15:

- Focused environment, health, deployment-command, artifact, and foundation set:
  `42 passed`.
- Complete `python scripts/check.py` quality gate: `441 passed`.
- Django system/deploy checks passed; migration drift is zero; Ruff lint passed
  and all `172` files are formatted; production static collection passed; all
  `35` installed packages are compatible.
- `PROD-005` adds no migration. All existing migrations apply cleanly from an
  empty database, the follow-up migration plan is empty, and drift is zero.
- A clean extraction of the restricted final ZIP installed from the lockfile,
  applied all migrations from an empty database, reported an empty follow-up
  plan, copied the development `.env.example` to `.env`, and passed the same
  complete `441`-test quality gate.

`INTAKE-001` verification completed on 2026-08-17:

- Focused bulk-intake, candidate-intake, private-document, background-job, and
  synthetic-fixture set: `77 passed`.
- Complete `python scripts/check.py` quality gate: `451 passed`.
- Django system and warning-strict deployment checks passed; production static
  collection passed; migration drift is zero; Ruff lint passed and all `176`
  files are formatted; all `35` installed packages are compatible.
- `INTAKE-001` adds
  `candidates.0006_candidateintakebatch_candidateintakeitem_and_more`. It
  applies successfully after the existing migrations, the follow-up migration
  plan is empty, and model-to-migration drift is zero. No `operations`, AI,
  toolkit, or other app migration was added.

The focused command is:

```text
uv run pytest -q tests/test_candidate_bulk_intake.py tests/test_candidate_intake.py tests/test_candidate_documents.py tests/test_background_jobs.py tests/test_manual_testing_fixtures.py
```

`EVAL-001` verification completed on 2026-08-17:

- Focused evaluation-dataset, deterministic-shortlist, staleness,
  candidate-profile, and private-document set: `95 passed`.
- Complete `python scripts/check.py` quality gate: `455 passed`.
- Django system and warning-strict deployment checks passed; production static
  collection passed; migration drift is zero; Ruff lint passed and all `184`
  files are formatted; all `35` installed packages are compatible.
- EVAL-001 adds no migration. All existing candidate and matching migrations are
  applied, the follow-up migration plan is empty, and model-to-migration drift is
  zero.

The focused command is:

```text
uv run pytest -q tests/test_evaluation_dataset.py tests/test_matching_shortlist.py tests/test_matching_staleness.py tests/test_candidate_ai_extraction.py tests/test_candidate_documents.py
```

`EVAL-002` verification completed on 2026-08-17:

- Focused evaluation-measurement, dataset, deterministic-shortlist, staleness,
  and AI-assessment set: `60 passed`.
- Complete `python scripts/check.py` quality gate: `461 passed`.
- Django system and warning-strict deployment checks passed; production static
  collection passed; migration drift is zero; Ruff lint passed and all `187`
  files are formatted; all `35` installed packages are compatible.
- EVAL-002 adds no migration. Every existing migration is applied, the follow-up
  migration plan is empty, and model-to-migration drift is zero.

The focused command is:

```text
uv run pytest -q tests/test_evaluation_measurement.py tests/test_evaluation_dataset.py tests/test_matching_shortlist.py tests/test_matching_staleness.py tests/test_match_ai_assessment.py
```

## Immediate next action

Implement only `EVAL-003`: review match-assessment explanations against the
frozen synthetic evidence for supported claims and protected-attribute leakage.
Preserve the frozen dataset, separate ranking measurements, reviewed bulk
intake, production/deployment, minimized usage reporting, durable jobs, staged
deletion, and separate individually approved candidate-decision and outreach
actions.
