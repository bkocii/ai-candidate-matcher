# Project State

## Project

AI Candidate Matcher

Version: `0.1.0.dev0`

## Goal

Build an AI-assisted candidate rediscovery and shortlisting application for small recruitment agencies and employers, using an organization-controlled candidate pool and mandatory human review.

## Current milestone

Sprint 1 — Django foundation.

Status: In progress. `FOUND-001` is complete.

## Decisions made

- The first product is recruiter-side candidate search, not job search for candidates.
- The MVP searches candidates supplied or controlled by the organization.
- The product does not scrape LinkedIn or arbitrary websites.
- The MVP supports one organization per deployment and multiple recruiter accounts.
- Agency deployments can associate vacancies with optional client companies.
- Deterministic filtering precedes AI assessment.
- AI provides evidence-based decision support and never makes the final hiring decision.
- Outreach is editable and copy/export only in the MVP.
- The app is a separate repository from Python AI Toolkit.
- The app pins `python-ai-toolkit[django]==1.0.0` initially.
- Toolkit improvement candidates are recorded and reproduced before any toolkit change.

## Implemented

### `FOUND-001 — Django repository foundation`

- Created a Django project with `config` settings, URL, WSGI, and ASGI modules.
- Selected Django `5.2.17` LTS for extended support and stability.
- Pinned `python-ai-toolkit[django]==1.0.0` as a published dependency.
- Added `python-dotenv==1.2.2` as an explicit application dependency.
- Added exact development dependencies for pytest, pytest-django, and Ruff.
- Added `uv.lock` for reproducible dependency resolution.
- Added environment-based baseline settings and a safe `.env.example`.
- Disabled toolkit file logging in the baseline configuration.
- Added tests for Django settings, toolkit version, public Django integration entry
  points, configuration validation without network access, and import isolation.
- Verified the toolkit imports from `.venv` site-packages and no local `ai` package
  exists in the application repository.

## Verification

Verified on 2026-08-09 with Python 3.12.13:

- `python manage.py check`: passed.
- `pytest`: 5 passed.
- `ruff check .`: passed.
- `ruff format --check .`: passed.
- Dependency compatibility check: passed for 29 installed packages.
- Installed toolkit distribution: `python-ai-toolkit==1.0.0`.

## Not implemented

No domain applications, custom database models, recruiter UI, candidate data,
matching workflow, or AI business service has been implemented yet.

## Next task

`FOUND-002 — Add accounts, organizations, memberships, and roles.`
