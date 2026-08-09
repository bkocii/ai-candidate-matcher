# AI Candidate Matcher — Session Handoff

## Project

AI Candidate Matcher

Current version: `0.1.0.dev0`

## Goal

Continue developing an AI-assisted candidate rediscovery and shortlisting application for small recruitment agencies and employers.

The organization supplies or authorizes the candidate pool. The app does not scrape arbitrary websites. It filters candidates, creates evidence-based AI assessments, requires recruiter review, and generates editable outreach drafts that are copied or exported manually.

## Current status

Sprint 0 is complete. Sprint 1 is in progress.

`FOUND-001` and `FOUND-002` are complete. The project now has a Django 5.2.17
LTS foundation, a custom user model, organizations, memberships, constrained
administrator/recruiter roles, initial migrations, dependency locking,
pytest-django and Ruff configuration, and import-isolation tests.

The next roadmap item is:

`FOUND-003 — Add optional client companies and organization-scoped permissions.`

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

Verified on 2026-08-09 with Python 3.12.13:

- Django system check passed.
- 13 pytest tests passed.
- Ruff lint and format checks passed.
- All 29 installed packages passed dependency compatibility checks.
- `python-ai-toolkit==1.0.0` imports from `.venv` site-packages.
- The application repository contains no local `ai` toolkit source package.

## Immediate next action

Design the optional client-company ownership model and organization-scoped query
and authorization policy for `FOUND-003`, then implement only that roadmap item.
