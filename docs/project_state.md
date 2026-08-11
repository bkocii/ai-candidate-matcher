# Project State

## Project

AI Candidate Matcher

Version: `0.1.0.dev0`

## Goal

Build an AI-assisted candidate rediscovery and shortlisting application for small recruitment agencies and employers, using an organization-controlled candidate pool and mandatory human review.

## Current milestone

Sprint 4 — AI extraction and assessment.

Status: Not started. Sprint 3 is complete; `AI-001` is next.

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

### `DATA-001 — Candidate, source/consent, and document models`

- Added organization-owned candidates with minimal identity/contact fields,
  lifecycle state, retention date, deletion timestamps, creator, and audit times.
- Added candidate-source records for provenance, lawful-basis assertion, consent
  status, contact permission, notes, source reference, and retention metadata.
- Added private candidate-document metadata with an opaque UUID storage path,
  original filename, document/content type, size, SHA-256, retention/deletion
  fields, and uploader attribution.
- Added organization-aware querysets for candidates and candidate-related rows,
  with active membership required for user-visible reads.
- Registered all three models in Django admin and added schema constraints for
  controlled lifecycle, source, consent, permission, and document-type values.
- Kept upload validation, document text extraction, and storage-byte deletion out
  of this task for their explicit later roadmap items.

### `DATA-002 — Vacancy and versioned vacancy-requirements models`

- Added organization-owned vacancies with draft/open/paused/closed lifecycle,
  recruiter attribution, and optional same-organization client companies.
- Preserved direct-employer mode by allowing vacancies without a client company;
  deleting a client retains its vacancies and clears only that optional link.
- Added organization-scoped vacancy and requirements querysets with active
  membership filtering and reusable object-permission compatibility.
- Added numbered requirements snapshots containing the source job description,
  schema version, provenance method, skills, experience, location/work mode,
  languages, education, certifications, employment type, explicit hard
  constraints, and recruiter-visible ambiguities.
- Added draft and recruiter-confirmed requirements states, confirmation actor and
  timestamp integrity, unique positive version numbers, and choice constraints.
- Kept draft requirements editable while making confirmed snapshots immutable;
  corrections to confirmed requirements must create a new version.
- Added Django admin support and kept vacancy entry forms and AI extraction in
  their explicit later roadmap tasks.

### `DATA-003 — Manual candidate entry and CSV import`

- Added recruiter-facing, organization-scoped candidate lists and manual entry.
- Manual entry creates candidate identity and provenance/permission metadata in
  one transaction and reports stable-identifier duplicates without overwriting.
- Added a downloadable CSV template and documented the required/optional columns.
- Added UTF-8, comma-separated CSV parsing with 2 MB and 2,000-row limits,
  header/schema checks, field validation, and pre-write file-structure validation.
- Added per-row created, duplicate, and invalid results while allowing independent
  valid rows to succeed.
- Scoped duplicate detection to the organization using case-insensitive email,
  normalized phone digits, and exact source references; names are not treated as
  identity.
- Repeated membership authorization at both view and intake-service boundaries,
  and added candidate navigation plus an active-candidate dashboard count.

### `DATA-004 — Private CV upload and safe text extraction`

- Added organization-scoped candidate detail and CV upload screens for existing
  candidates, with authorization repeated at the view and document-service layers.
- Accepted only PDF and DOCX CV files up to 10 MB after filename, extension,
  declared content type, and binary/package signature validation.
- Added bounded PDF parsing with encrypted-file, page-count, extracted-text, and
  textless/scanned-document rejection.
- Added bounded DOCX parsing with package structure, entry count, individual and
  total expanded size, compression ratio, internal path, encryption, corruption,
  and macro-content checks before text extraction.
- Stored successful documents under opaque private paths with normalized content
  type, byte size, SHA-256, extracted text, extraction status/timestamp, retention
  date, and uploader attribution.
- Added organization-local duplicate-document reporting through SHA-256 without
  revealing or blocking identical files belonging to another organization.
- Kept stored bytes and extracted CV text out of recruiter-facing HTML and added
  no file-delivery route; hardened private delivery remains owned by `PROD-001`.
- Added `pypdf==6.1.1` and `python-docx==1.2.0` as application dependencies. The
  toolkit loader hypothesis was evaluated as app-owned rather than a toolkit gap.

### `DATA-005 — Vacancy-description entry and recruiter-editable requirements`

- Added organization-scoped vacancy list, creation, detail, requirements-edit,
  confirmation, and correction-version routes.
- Added direct-employer vacancy entry and optional selection from active client
  companies belonging to the current organization.
- Created a first manual requirements draft atomically with every pasted vacancy
  description and redirected the recruiter directly into review.
- Added recruiter-friendly one-item-per-line fields for skills, languages,
  education, certifications, hard constraints, and ambiguities, with whitespace
  and case-insensitive duplicate normalization.
- Repeated organization membership checks at service boundaries for vacancy
  creation, requirements editing, confirmation, and correction-version creation.
- Made confirmation POST-only, required meaningful structured content, and
  recorded the confirming recruiter and timestamp.
- Preserved immutable confirmed history by copying the current confirmed snapshot
  into the next numbered draft rather than editing it in place.
- Added vacancy navigation, dashboard open-vacancy counts, synthetic manual test
  fixtures, and a detailed end-to-end testing guide.
- Corrected the completed intake workflow so successful CSV submissions bring
  the in-page report into view and recruiters can manage vacancy lifecycle through
  tenant-safe, POST-only, validated status transitions.
- Added confirmation-based deletion controls. Vacancy deletion closes and hides
  the vacancy while preserving its immutable requirements history and deletion
  actor/timestamp. Candidate deletion removes contact data, provenance rows,
  document metadata, stored CV bytes, and extracted text while retaining only a
  minimal organization-owned deletion tombstone.

### `MATCH-001 — Normalized skills and explicit hard-constraint rules`

- Added an organization-owned skill vocabulary with conservative Unicode,
  whitespace, and case normalization. Meaningful punctuation is preserved, so
  identifiers such as `C`, `C#`, and `C++` remain distinct.
- Added normalized requirement-skill links that retain must-have/nice-to-have
  importance, recruiter source wording, and ordering for each requirements
  version. Confirmation materializes the links, and a data migration backfills
  existing versions without rewriting their original JSON fields.
- Added candidate skill assertions with source wording, optional years of
  experience, inspectable evidence, and an optional source-document reference.
- Added typed hard-constraint rules for required skill, minimum experience,
  location, work mode, language, education, certification, and employment type.
- Constrained every rule to its valid operator and payload shape. Missing
  candidate facts always remain `unknown / keep for recruiter review`; they
  cannot be configured as an automatic failure.
- Kept protected and sensitive characteristics outside the rule-type vocabulary.
  Existing free-text hard-constraint notes are not silently interpreted as
  executable rules.
- Made confirmed requirement skill links and hard-constraint rules immutable.
  Correction drafts copy both normalized skills and typed rules into a new
  numbered version.
- Added organization-scoped querysets, service-layer authorization, Django admin
  support, database constraints, and candidate-deletion cleanup for skill evidence.

### `MATCH-002 — Inspectable deterministic candidate filtering`

- Added a deterministic evaluation service that accepts only confirmed
  requirements and active same-organization candidates after repeating tenant
  authorization at the service boundary.
- Added explicit per-rule `pass`, `fail`, and `unknown` results containing the
  rule source wording, expected value, observed candidate fact, available
  evidence, and a recruiter-readable explanation.
- Aggregated candidate outcomes as passed when all rules pass, failed when any
  rule fails, and review when no rule fails but at least one fact is unknown.
  Unknown candidates remain eligible and are never silently rejected.
- Evaluated normalized skill evidence, evidence-backed minimum experience, and
  explicit candidate location without searching raw CV text. Partial or missing
  facts remain unknown; unsupported profile fields are not inferred.
- Added a recruiter-facing, version-labelled candidate filtering report with
  summary counts, paginated candidate results, tenant-safe candidate links, and
  no contact details or private CV text.
- Kept results computed on request and intentionally excluded ranking, shortlist
  bounds, persisted match runs, AI calls, and hiring decisions from this task.

### `MATCH-003 — Relevance scoring and bounded shortlist`

- Added persistent, organization-scoped match runs tied to one immutable
  confirmed requirements version, algorithm version, recruiter actor, generation
  time, shortlist limit, and evaluated/eligible population counts.
- Excluded every explicit hard-constraint failure before relevance scoring while
  preserving passed and needs-review candidates as eligible.
- Added a deterministic skill score from 0 to 100. When both groups exist,
  must-have skills contribute 70 points and nice-to-have skills contribute 30;
  a single available group contributes all 100 points, and skills within each
  group are equally weighted.
- Treated missing candidate skill evidence as zero relevance points rather than
  proof of failure. Every skill row preserves requirement wording, recorded
  candidate wording, evidence, match state, and awarded/possible points.
- Ranked by score descending, then passed before needs-review only for equal
  scores, then stable candidate record ID. Names and protected characteristics
  do not influence the order.
- Bounded each persisted shortlist to 20 entries while recording the full
  evaluated and eligible counts and reporting how many eligible candidates fell
  outside the bound.
- Added POST-only generation, a recruiter-facing score explanation and shortlist
  report, latest-shortlist links, tenant isolation, database constraints, admin
  inspection, and version-labelled historical runs.
- Extended candidate deletion to remove persisted shortlist entries and skill
  evidence snapshots while retaining only non-identifying run-level counts.
- Kept AI requests, hiring decisions, candidate approval/rejection, and stale-run
  invalidation outside this task.

### `MATCH-004 — Stale-result invalidation`

- Added versioned SHA-256 signatures for the confirmed vacancy matching inputs
  and active candidate-pool facts used by deterministic filtering, scoring, and
  displayed evidence.
- Added an organization-authorized staleness service that compares saved input
  signatures with current inputs without exposing or duplicating candidate data.
- Marked runs stale after a newer confirmed requirements version, matching-input
  mutation, active candidate addition/removal, candidate deletion, location
  change, or skill/experience/evidence change.
- Kept unrelated contact, source, retention, and vacancy-lifecycle changes out of
  invalidation because they cannot affect the deterministic result.
- Added a clear current/stale result banner, reason-specific warnings, stale
  labels on latest-shortlist links, and recruiter-triggered regeneration that
  creates a new run while preserving old history.
- Treated pre-signature match runs as explicitly stale instead of incorrectly
  assuming they are current, and repeated tenant authorization in the staleness
  service.
- Kept all AI requests, assessment persistence, review decisions, and outreach
  outside this task.

## Verification

Verified on 2026-08-11 with Python 3.12.13:

- Normal and warning-strict production Django checks: passed.
- Migration drift check: passed.
- `pytest`: 239 passed.
- Ruff lint and formatting: passed.
- Dependency compatibility check: passed for 32 installed packages.
- Installed toolkit distribution: `python-ai-toolkit==1.0.0`.

## Not implemented

No outreach workflow or AI business service has been implemented yet. Candidate
records can be manually created, imported, and given
validated PDF/DOCX CVs through the organization workspace. Recruiters can create
vacancies, manually structure and confirm their requirements, and preserve
corrections as immutable numbered history. Scanned-image CVs are not supported,
and stored document bytes have no delivery route before `PROD-001`. Recruiters
can manage vacancy status through the normal organization workspace after a
requirements version is confirmed. Recruiters can also delete vacancies and
candidates through explicit confirmation pages; scheduled retention enforcement,
administrative deletion reports, and comprehensive audit views remain in
`PROD-002`. Recruiters can inspect deterministic rule outcomes for active
candidates using the current confirmed requirements, then generate a persistent
version-labelled shortlist of up to 20 eligible candidates. Relevant candidate
or confirmed-requirements changes clearly mark earlier runs stale while retaining
their immutable historical scores and explanations.

## Next task

`AI-001 — Add an application AI gateway backed by Python AI Toolkit v1.0.0.`
