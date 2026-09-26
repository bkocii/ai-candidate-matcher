# Roadmap

Roadmap items are implemented in order unless a documented architectural reason requires a change.

## Sprint 0 — Product and architecture definition

Status: Complete.

- `PLAN-001` Define target user, product promise, MVP, and non-goals.
- `PLAN-002` Define application/toolkit ownership boundaries.
- `PLAN-003` Define privacy and human-review rules.
- `PLAN-004` Define the toolkit feedback process.
- `PLAN-005` Prepare Codex instructions and session handoff.

## Sprint 1 — Django foundation

Status: Complete.

- `FOUND-001` Bootstrap the Django repository, dependency management, settings, and test tooling. **Complete — 2026-08-09.**
- `FOUND-002` Add accounts, organizations, memberships, and roles. **Complete — 2026-08-09.**
- `FOUND-003` Add optional client companies and organization-scoped permissions. **Complete — 2026-08-09.**
- `FOUND-004` Establish base templates, navigation, and a minimal dashboard. **Complete — 2026-08-10.**
- `FOUND-005` Add CI-quality commands and security-conscious environment configuration. **Complete — 2026-08-10.**
- `CR-003` Add in-application organization-administrator client-company
  management plus active-client selection on vacancy creation/editing while
  preserving historical relationships. **Complete — 2026-08-25 as an approved
  pre-release workflow correction.**
- `CR-001` Add managed multi-organization provisioning, explicit platform-owner
  administration, organization-admin recruiter management, workspace switching,
  and content-free tenant-management auditing without granting platform owners
  tenant content access. **Complete — 2026-08-27 as an approved pre-release
  SaaS workflow correction.**

Sprint acceptance: two organizations in tests cannot access each other's
objects; platform owners can provision tenants and administrators without
receiving recruitment-data access; organization administrators can manage
recruiters and optional agency clients without Django admin; inactive memberships
and clients cannot be newly used while historical records remain intact; project
checks pass; and the published toolkit package is installed without importing
local toolkit code.

## Sprint 2 — Candidate and vacancy intake

- `DATA-001` Add candidate, source/consent metadata, and candidate-document models. **Complete — 2026-08-10.**
- `DATA-002` Add vacancy and versioned vacancy-requirements models. **Complete — 2026-08-10.**
- `DATA-003` Add manual candidate entry and CSV import with validation and duplicate reporting. **Complete — 2026-08-10.**
- `DATA-004` Add private CV upload and safe PDF/DOCX text extraction. **Complete — 2026-08-10.**
- `DATA-005` Add vacancy-description entry and recruiter-editable requirements. **Complete — 2026-08-10; corrective workflow and deletion passes complete.**
- `INTAKE-001` Add reviewed bulk CV candidate intake with shared provenance,
  local identity proposals, isolated file validation, explicit selected creation,
  temporary-data minimization, and targeted background profile queuing.
  **Complete — 2026-08-17 as a user-approved corrective intake task before
  `EVAL-001`.**
- `CR-004` Unify CV-first candidate creation, exact CSV-to-CV mapping, optional
  CV quick-add, and explicit batch confirmation of only clean eligible profile
  drafts. **Complete — 2026-08-24 as a user-approved pre-release workflow
  correction.**
- `CR-005` Replace legalistic candidate privacy/source wording with practical
  recruiter labels and safe defaults, expose inspectable source records, and
  enforce reason/consent/allowed-contact checks at final outreach approval.
  **Complete — 2026-08-25 as a user-approved pre-release workflow correction.**
- `CR-006` Add audited candidate/source correction, evidence-validated profile
  correction versions, deterministic trusted-data conflict detection, and
  conflict-safe individual/batch confirmation. **Implemented — 2026-08-29;
  browser retest pending as a user-approved manual-testing correction.**

Status: Complete.

Sprint acceptance: a recruiter can import an anonymized candidate set through
CSV or reviewed CV-first intake, attach a CV during quick-add, confirm clean
profile drafts efficiently while inspecting exceptions, and create a vacancy
without developer help. Candidate source/privacy fields use plain language and
incomplete or restricted permissions cannot authorize outreach.

## Sprint 3 — Deterministic search and shortlist

- `MATCH-001` Define normalized skills and explicit hard-constraint rules. **Complete — 2026-08-10; corrective recruiter-facing typed-rule editor complete — 2026-08-12.**
- `MATCH-002` Implement inspectable deterministic candidate filtering. **Complete — 2026-08-11.**
- `MATCH-003` Implement relevance scoring and a bounded shortlist. **Complete — 2026-08-11; corrective per-skill 2:1 weighting pass complete.**
- `MATCH-004` Add stale-result invalidation when candidate or vacancy data changes. **Complete — 2026-08-11.**
- `DEF-001` Correct deterministic canonical skill matching while preserving
  source wording and evidence. **Complete — 2026-08-24 as a user-approved
  correctness task before the remaining pre-release functionality pass.**

Corrective workflow pass: recruiters can now create, edit, and confirmation-delete
typed hard-constraint rules in the normal draft requirements editor. Confirmed
versions remain immutable, and free-text hard-constraint notes remain explicitly
non-executable.

Corrective canonical-matching pass: controlled aliases such as `Python
development` resolve to the canonical `Python` identity for filtering and
scoring. Existing saved versions are canonicalized again at comparison time,
unsafe near-matches such as `Java`/`JavaScript` remain distinct, and historical
v2 runs become stale rather than being rewritten.

Status: Complete.

Sprint acceptance: the app produces a useful shortlist without any AI provider.

## Sprint 4 — AI extraction and assessment

- `AI-001` Add an application AI gateway backed by Python AI Toolkit v1.0.0. **Complete — 2026-08-11.**
- `AI-002` Extract and validate structured vacancy requirements. **Complete — 2026-08-12.**
- `AI-003` Extract and validate structured candidate profiles from CV text.
  **Complete — 2026-08-12; corrective bounded evidence-repair pass complete —
  2026-08-15; explicit narrative-skill completeness pass complete — 2026-08-15.**
- `AI-004` Generate structured evidence-based match assessments. **Complete — 2026-08-12.**
- `AI-005` Store request metadata and safe failure information. **Complete — 2026-08-12.**
- `AI-006` Add fake-gateway, contract, and opt-in live smoke tests. **Complete — 2026-08-13.**

Status: Complete.

Sprint acceptance: AI output is schema-valid, evidence is traceable, missing data is marked unknown, and failure does not break the deterministic shortlist.

### Approved recruiter-efficiency requirement for later tasks

The safe per-candidate workflow is a foundation, not the intended high-volume
recruiter experience. Confirmed profiles must be reusable across vacancies and
should require re-extraction only for a new or corrected CV/profile. `REV-001`
provides a compact queue emphasizing gaps, ambiguities, changed facts, and
evidence exceptions. `PROD-003` adds resumable background batch profile
extraction and whole-shortlist assessment generation with per-candidate failure
isolation. Selected profile drafts may be confirmed efficiently only after their
evidence remains inspectable; no profile is silently auto-confirmed. Final
approve/reject/revisit decisions remain individual human actions in `REV-002`,
and outreach remains separately approved.

## Sprint 5 — Recruiter review and outreach

- `REV-001` Add the review queue and assessment detail screen. **Complete — 2026-08-13.**
- `REV-002` Add approve, reject, and revisit decisions with recruiter notes. **Complete — 2026-08-13.**
- `OUT-001` Generate outreach drafts only for explicitly approved candidates. **Complete — 2026-08-14.**
- `OUT-002` Add editing, final approval, copy, and export. **Complete — 2026-08-14.**

Sprint acceptance: nothing is sent automatically, and every decision/draft has a human actor and timestamp.

Status: Complete.

## Sprint 6 — Production safeguards and observability

- `PROD-001` Add private file-delivery controls and upload hardening. **Complete — 2026-08-15.**
- `PROD-002` Add audit views, retention/deletion workflow, and data minimization checks. **Complete — 2026-08-15.**
- `PROD-003` Add background processing, idempotency, resumability, and operational status. **Complete — 2026-08-15.**
- `PROD-004` Add token, cost, latency, retry, and failure reporting. **Complete — 2026-08-15.**
- `PROD-005` Add deployment documentation and production checks. **Complete — 2026-08-15.**
- `CR-002` Add organization retention policies, dependency-aware dry-run and
  cleanup, legal holds/exceptions, and staged organization recovery/purge.
  **Complete — 2026-08-25 as an approved pre-release lifecycle correction.**

Sprint acceptance: private files remain non-public, durable jobs are recoverable,
safe operational reporting is available, and the documented PostgreSQL web/
worker deployment passes static, security, migration, database, and private-
storage readiness checks without weakening human review.

Status: Complete.

## Sprint 7 — Evaluation and showcase release

Status: In progress.

- `EVAL-001` Create synthetic/anonymized candidates and vacancies with expected
  matches. **Complete — 2026-08-17.**
- `EVAL-002` Measure deterministic and AI-assisted ranking quality separately.
  **Complete — 2026-08-17.**
- `EVAL-003` Review explanations for evidence, unsupported claims, and protected-attribute leakage.
  **Complete — 2026-08-18.**
- `DEMO-001` Create a reproducible demo and screenshots. **Complete — 2026-08-20.**
- `DIR-001` Record the focused product direction after the completed manual-
  review pass. **Complete — 2026-09-21.**
- `DIR-002` Record the minimum-effort AI experience, restricted platform-owner
  membership boundary, client agreement requirement, and long-gap candidate-
  retention direction. **Complete — 2026-09-21; documentation only.**
- `DEMO-002` Prepare a client-facing README and Upwork Project Catalog
  positioning. **Deferred until the revised core workflow reaches an approved
  positioning checkpoint.**

## Approved product-direction sequence

Status: Direction approved; each implementation task requires detailed scope
and acceptance-criteria approval before code changes begin.

The canonical plan is `docs/product_direction_plan.md`. `FLOW-001` behavior,
acceptance criteria, and implementation were completed on 2026-09-22. `VAC-001`
was completed on 2026-09-23. `FLOW-002` was completed on 2026-09-24, and
`FLOW-003` and `MATCH-005` were completed on 2026-09-25. `MATCH-006` was
completed on 2026-09-26.

### Vacancy-centric candidate workflow

- `FLOW-001` Bind routine CV intake to a vacancy while preserving reusable
  organization candidates and original application/batch provenance. Remove
  the visible shared-details step from routine vacancy intake, derive
  application-only contact/source/retention context safely, and keep future-role
  permission separate. **Complete — 2026-09-22.**
- `VAC-001` Replace the multi-screen routine vacancy setup with an AI-first flow
  accepting pasted text or one validated PDF/DOCX/TXT vacancy document, compact
  recruiter review, explicit confirm/open, and direct handoff to vacancy CV
  intake. Keep manual fallback and immutable requirement history. **Complete —
  2026-09-23.**
- `FLOW-002` Default vacancy views to their associated candidates and separate
  access to the wider organization candidate pool. **Complete — 2026-09-24.**
- `FLOW-003` Add deliberate cross-vacancy reuse through **Add from candidate
  pool**, with provenance and permission checks. **Complete — 2026-09-25.**

### Shortlist and recruiter experience

- `MATCH-005` Add supported role/seniority discovery and measured semantic-
  matching improvements. **Complete — 2026-09-25.** The first measured stage
  uses evidence-grounded controlled values only as equal-score tie-breakers;
  numeric skill scoring and hard eligibility are unchanged.
- `MATCH-006` Make the ranked evidence-backed shortlist the central vacancy
  result. **Complete — 2026-09-26.** Confirming vacancy-scoped candidate
  profiles refreshes the deterministic shortlist once, and vacancy detail shows
  the ranked result, one bulk AI-assessment action, exceptions, and history.
- `REV-003` Extend exception-focused review across the core workflow. **Complete
  — 2026-09-26.** Reviews default to actionable profile, matching, ranking, and
  AI exceptions; individual decisions advance to the next candidate.
- `OUT-003` Simplify outreach presentation while retaining currentness,
  permission, exact-draft, and explicit human-action safeguards. Approved scope
  includes optional approved, revisit/status-update, and rejection emails while
  keeping internal decision notes out of candidate-facing content.

### Client readiness

- `ACCESS-001` Prevent platform-owner accounts from receiving normal membership
  in real client organizations while preserving separate internal/demo use
  through a non-platform test account and documented exceptional support.
- `RET-001` Refine the existing candidate lifecycle around a configurable
  24-month inactive-candidate default, optional shorter 12-month policy,
  meaningful activity, expiry warning, deletion requests, and offboarding.
- `AI-007` Add optional organization-level BYOK with platform configuration as
  the backward-compatible fallback.
- `PRIV-001` Re-audit privacy, tenant isolation, provenance, deletion, and AI-
  provider disclosure for the revised workflow.
- `LEGAL-001` Prepare client service/data-processing agreement inputs and an
  onboarding acceptance record for qualified legal review.
- `DEPLOY-001` Document hosted-SaaS onboarding and an optional dedicated-
  instance path.

## Release gate

Do not call the product production-ready until Sprints 1–7 pass their acceptance criteria and a privacy/security review is complete.
