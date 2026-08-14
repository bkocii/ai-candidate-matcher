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

Sprint acceptance: two organizations in tests cannot access each other's objects, project checks pass, and the published toolkit package is installed without importing local toolkit code.

## Sprint 2 — Candidate and vacancy intake

- `DATA-001` Add candidate, source/consent metadata, and candidate-document models. **Complete — 2026-08-10.**
- `DATA-002` Add vacancy and versioned vacancy-requirements models. **Complete — 2026-08-10.**
- `DATA-003` Add manual candidate entry and CSV import with validation and duplicate reporting. **Complete — 2026-08-10.**
- `DATA-004` Add private CV upload and safe PDF/DOCX text extraction. **Complete — 2026-08-10.**
- `DATA-005` Add vacancy-description entry and recruiter-editable requirements. **Complete — 2026-08-10; corrective workflow and deletion passes complete.**

Status: Complete.

Sprint acceptance: a recruiter can import an anonymized candidate set and create a vacancy without developer help.

## Sprint 3 — Deterministic search and shortlist

- `MATCH-001` Define normalized skills and explicit hard-constraint rules. **Complete — 2026-08-10; corrective recruiter-facing typed-rule editor complete — 2026-08-12.**
- `MATCH-002` Implement inspectable deterministic candidate filtering. **Complete — 2026-08-11.**
- `MATCH-003` Implement relevance scoring and a bounded shortlist. **Complete — 2026-08-11; corrective per-skill 2:1 weighting pass complete.**
- `MATCH-004` Add stale-result invalidation when candidate or vacancy data changes. **Complete — 2026-08-11.**

Corrective workflow pass: recruiters can now create, edit, and confirmation-delete
typed hard-constraint rules in the normal draft requirements editor. Confirmed
versions remain immutable, and free-text hard-constraint notes remain explicitly
non-executable.

Status: Complete.

Sprint acceptance: the app produces a useful shortlist without any AI provider.

## Sprint 4 — AI extraction and assessment

- `AI-001` Add an application AI gateway backed by Python AI Toolkit v1.0.0. **Complete — 2026-08-11.**
- `AI-002` Extract and validate structured vacancy requirements. **Complete — 2026-08-12.**
- `AI-003` Extract and validate structured candidate profiles from CV text. **Complete — 2026-08-12.**
- `AI-004` Generate structured evidence-based match assessments. **Complete — 2026-08-12.**
- `AI-005` Store request metadata and safe failure information. **Complete — 2026-08-12.**
- `AI-006` Add fake-gateway, contract, and opt-in live smoke tests. **Complete — 2026-08-13.**

Status: Complete.

Sprint acceptance: AI output is schema-valid, evidence is traceable, missing data is marked unknown, and failure does not break the deterministic shortlist.

### Approved recruiter-efficiency requirement for later tasks

The safe per-candidate workflow is a foundation, not the intended high-volume
recruiter experience. Confirmed profiles must be reusable across vacancies and
should require re-extraction only for a new or corrected CV/profile. `REV-001`
should provide a compact queue emphasizing gaps, ambiguities, changed facts, and
evidence exceptions. `PROD-003` should add resumable background batch profile
extraction and whole-shortlist assessment generation with per-candidate failure
isolation. Selected profile drafts may be confirmed efficiently only after their
evidence remains inspectable; no profile is silently auto-confirmed. Final
approve/reject/revisit decisions remain individual human actions in `REV-002`,
and outreach remains separately approved.

## Sprint 5 — Recruiter review and outreach

- `REV-001` Add the review queue and assessment detail screen. **Complete — 2026-08-13.**
- `REV-002` Add approve, reject, and revisit decisions with recruiter notes. **Complete — 2026-08-13.**
- `OUT-001` Generate outreach drafts only for explicitly approved candidates.
- `OUT-002` Add editing, final approval, copy, and export.

Sprint acceptance: nothing is sent automatically, and every decision/draft has a human actor and timestamp.

Status: In progress. `OUT-001` is next.

## Sprint 6 — Production safeguards and observability

- `PROD-001` Add private file-delivery controls and upload hardening.
- `PROD-002` Add audit views, retention/deletion workflow, and data minimization checks.
- `PROD-003` Add background processing, idempotency, resumability, and operational status.
- `PROD-004` Add token, cost, latency, retry, and failure reporting.
- `PROD-005` Add deployment documentation and production checks.

## Sprint 7 — Evaluation and showcase release

- `EVAL-001` Create synthetic/anonymized candidates and vacancies with expected matches.
- `EVAL-002` Measure deterministic and AI-assisted ranking quality separately.
- `EVAL-003` Review explanations for evidence, unsupported claims, and protected-attribute leakage.
- `DEMO-001` Create a reproducible demo and screenshots.
- `DEMO-002` Prepare a client-facing README and Upwork Project Catalog positioning.

## Release gate

Do not call the product production-ready until Sprints 1–7 pass their acceptance criteria and a privacy/security review is complete.
