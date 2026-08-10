# Project State

## Project

AI Candidate Matcher

Version: `0.1.0.dev0`

## Goal

Build an AI-assisted candidate rediscovery and shortlisting application for small recruitment agencies and employers, using an organization-controlled candidate pool and mandatory human review.

## Current milestone

Sprint 2 — Candidate and vacancy intake.

Status: Ready to start. Sprint 1 is complete; no Sprint 2 task is implemented.

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

### `FOUND-002 — Accounts, organizations, memberships, and roles`

- Added a custom `accounts.User` model before domain migrations are established.
- Added `organizations.Organization` as the future data-isolation boundary.
- Added unique user/organization memberships with active state and database-
  constrained `admin` and `recruiter` roles.
- Kept organization roles separate from Django staff and superuser privileges.
- Registered users, organizations, and memberships in Django admin.
- Added initial migrations and model tests for roles, inactive membership,
  multi-organization membership, uniqueness, and invalid-role rejection.

### `FOUND-003 — Optional client companies and organization-scoped permissions`

- Added organization-owned client companies with optional website metadata,
  active state, and per-organization slug uniqueness.
- Added explicit organization and organization-owned queryset scoping through
  `visible_to()` and `for_organization()`.
- Added reusable checks for active organization membership, organization-admin
  capability, and organization-owned object access.
- Required active user, organization, and membership state for application
  access; Django staff and superuser flags do not implicitly bypass tenant scope.
- Registered client companies in Django admin and added cross-organization,
  inactive-state, role, object-access, and database-constraint tests.

### `FOUND-004 — Base templates, navigation, and minimal dashboard`

- Added responsive project-owned base, authentication, organization-selection,
  no-access, and dashboard templates with a small static CSS layer.
- Added Django login and POST-only logout routes with safe redirect settings.
- Added a membership-aware dashboard entry point that redirects a single active
  organization or presents an explicit selection when several are available.
- Added an organization dashboard showing the active-client count and current
  membership role without introducing future candidate or vacancy features.
- Resolved organization dashboard access through `visible_to()` so inactive or
  cross-organization targets return `404` without disclosing tenant details.
- Kept Django admin navigation limited to Django staff, independently of the
  organization administrator role.

### `FOUND-005 — CI quality and secure environment configuration`

- Added strict environment parsing that rejects invalid boolean, integer, and
  runtime-mode values instead of silently weakening settings.
- Preserved a safe development-only secret fallback when `.env` contains a
  blank key, while requiring an explicit non-placeholder key in production.
- Made production fail closed for debug mode, missing or wildcard hosts,
  non-HTTPS trusted origins, disabled HTTPS redirect, and insecure cookies.
- Added explicit HSTS and trusted-proxy settings with safe operational guidance.
- Added one cross-platform `scripts/check.py` quality gate for Django checks,
  deployment checks, migration drift, tests, Ruff, and dependency compatibility.
- Added GitHub Actions CI on pull requests and `main` pushes for Python 3.11,
  3.12, 3.13, and 3.14 using locked dependencies and read-only repository access.

## Verification

Verified on 2026-08-10 with Python 3.12.13:

- Normal and warning-strict production Django checks: passed.
- Migration drift check: passed.
- `pytest`: 51 passed.
- Ruff lint and formatting: passed.
- Dependency compatibility check: passed for 29 installed packages.
- Installed toolkit distribution: `python-ai-toolkit==1.0.0`.

## Not implemented

No recruiter UI, candidate data, vacancy data, matching workflow, outreach
workflow, or AI business service has been implemented yet.

## Next task

`DATA-001 — Add candidate, source/consent metadata, and candidate-document models.`
