# AI Candidate Matcher — Session Handoff

## Project

AI Candidate Matcher

Current version: `0.1.0.dev0`

## Goal

Continue developing an AI-assisted candidate rediscovery and shortlisting application for small recruitment agencies and employers.

The organization supplies or authorizes the candidate pool. The app does not scrape arbitrary websites. It filters candidates, creates evidence-based AI assessments, requires recruiter review, and generates editable outreach drafts that are copied or exported manually.

## Current status

Sprint 0 through Sprint 3 are complete. Sprint 4 is next.

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
fixtures are included. No AI extraction workflow exists yet.

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
Explicit failures are excluded first. Recorded must-have skills contribute 70%
and nice-to-have skills 30% when both groups exist; each visible score row shows
the requirement, recorded candidate skill, evidence, and awarded points. Missing
skill evidence earns no points but is not treated as proof of absence. Runs retain
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

The next roadmap item is:

`AI-001 — Add an application AI gateway backed by Python AI Toolkit v1.0.0.`

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

Verified on 2026-08-11 with Python 3.12.13:

- Django system check passed.
- 239 pytest tests passed.
- Ruff lint and format checks passed.
- All 32 installed packages passed dependency compatibility checks.
- `python-ai-toolkit==1.0.0` imports from `.venv` site-packages.
- The application repository contains no local `ai` toolkit source package.
- The normal and warning-strict production Django checks passed.
- No migration drift was detected.

## Immediate next action

Implement only `AI-001`: add an application-owned AI gateway backed by the
published Python AI Toolkit v1.0.0, preserving the existing privacy boundary and
using fake/test substitution without starting vacancy or candidate extraction.
