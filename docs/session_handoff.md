# AI Candidate Matcher — Session Handoff

## Project

AI Candidate Matcher

Current version: `0.1.0.dev0`

## Goal

Continue developing an AI-assisted candidate rediscovery and shortlisting application for small recruitment agencies and employers.

The organization supplies or authorizes the candidate pool. The app does not scrape arbitrary websites. It filters candidates, creates evidence-based AI assessments, requires recruiter review, and generates editable outreach drafts that are copied or exported manually.

## Current status

Sprint 0 through Sprint 5 are complete. `REV-001`, `REV-002`, `OUT-001`, and
`OUT-002` are complete; `PROD-001` is the next approved roadmap task.

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
The follow-up deletion pass adds confirmation pages for candidates and vacancies.
Candidate deletion purges contact/provenance/document content and stored CV bytes,
leaving a minimal tombstone. Vacancy deletion hides and closes the record while
preserving requirement history with deletion actor/timestamp metadata.

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
v1.0.0 is left blank rather than inferred. Recruiter-facing usage reporting
remains `PROD-004`.

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

## Recruiter-efficiency requirement for later tasks

Do not treat the current per-candidate generation actions as the final high-volume UX.
Confirmed profiles are reusable across vacancies and should be re-extracted only
for new or corrected source/profile data. `REV-001` now provides a compact queue
emphasizing gaps, ambiguities, changed facts, and evidence exceptions.
`PROD-003` should add resumable background batch profile extraction and one
whole-shortlist assessment action with per-candidate failure isolation. Selected
profile drafts may be confirmed efficiently only while evidence remains
inspectable; no silent auto-confirmation is allowed. Final approve/reject/revisit
decisions are individual recruiter actions with notes, actor, and timestamp, and
outreach generation and final draft approval remain separate actions.

The next roadmap item is:

`PROD-001 — Add private file-delivery controls and upload hardening.`

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

Final corrective evidence-grounding and skill-completeness verification completed
on 2026-08-15:

- Focused candidate-profile and safe-usage regression set: `35 passed`.
- Complete `python scripts/check.py` quality gate: `395 passed`.
- Django system/deploy checks, migration drift, Ruff lint/format (`142` files),
  and dependency compatibility (`32` packages) all passed.
- This corrective pass adds no migration; the migration plan is empty and
  `outreach.0002_outreach_workflow` remains the latest project migration.
- Migration checks and the complete gate were repeated successfully from a clean
  extraction of the restricted final deliverable ZIP.

## Immediate next action

Implement only `PROD-001`: add private file-delivery controls and upload
hardening. Keep outreach sending unavailable and do not pull later retention,
background processing, or observability work forward.
