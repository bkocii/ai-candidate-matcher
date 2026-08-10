# Architecture

## Boundary

The Django application owns users, organizations, clients, candidates, vacancies, files, permissions, matching workflow, reviews, outreach drafts, auditing, and persistence.

Python AI Toolkit owns provider-independent AI requests, structured response validation, retries, provider integration, and available request metadata.

The application must not depend directly on an OpenAI or other provider SDK outside a deliberately isolated adapter.

## Initial stack

- Python 3.11 or newer, constrained by dependency compatibility.
- Django web application.
- PostgreSQL as the production database.
- SQLite may be used only for early local development and fast unit tests.
- Server-rendered Django templates for the MVP.
- Python AI Toolkit v1.0.0 through its Django integration.
- Background task processing is introduced when batch parsing or assessment would otherwise block requests.
- Private file storage with a replaceable storage backend.

Exact dependency versions will be selected during `FOUND-001` and recorded in the lock or project configuration.

## Application modules

### accounts

Authentication, organization membership, and recruiter/admin roles.

### organizations

Organization settings and optional agency client companies.

### candidates

Candidate records, uploaded documents, consent/lawful-source metadata, structured profiles, and retention state.

### vacancies

Vacancy descriptions, extracted requirements, recruiter corrections, and lifecycle status.

### matching

Hard filters, shortlist construction, AI assessments, evidence, scores, and recruiter decisions.

### outreach

Editable drafts, approval state, and manual copy/export history.

### ai_gateway

Application-level interfaces around Python AI Toolkit. No views or models call the toolkit directly.

### audit

AI usage events, operational events, privacy-relevant access, and failures without raw sensitive content.

## Identity and organization policy

- `accounts.User` is the swappable Django user model. It keeps Django's standard
  username-based authentication during the foundation sprint.
- `organizations.Organization` is the ownership and data-isolation boundary.
- `accounts.OrganizationMembership` links a user to an organization as either an
  `admin` or `recruiter` and can be deactivated without deleting its history.
- An organization `admin` role does not grant Django `is_staff` or `is_superuser`
  status. Django administration access is managed separately.
- The schema allows a user to belong to more than one organization so isolation
  can be tested and the model does not require a destructive redesign later.
  The MVP deployment and user interface still operate for one organization.
- Organization-aware query helpers and object authorization are introduced in
  `FOUND-003`; views must use them rather than infer access from a role name.
- `organizations.ClientCompany` belongs to exactly one organization. Creating no
  client companies is the supported direct-employer mode; agency vacancies may
  reference one later, but that relationship will remain optional.
- Active user, organization, and membership state are all required for
  organization-scoped application access. Django staff or superuser status does
  not bypass this rule outside the separate Django admin surface.
- Organization-owned querysets expose `for_organization()` for an explicit
  tenant boundary and `visible_to()` for membership-filtered application reads.
- Authorization helpers provide ordinary-member, organization-administrator,
  and organization-owned-object checks. Service and view boundaries must still
  call the appropriate helper even after filtering a queryset.

## Foundation user interface

- The MVP uses server-rendered Django templates and a small project-owned CSS
  layer without a JavaScript framework.
- Authentication uses Django's built-in login and logout views. Logout is a
  CSRF-protected POST action rather than a state-changing link.
- The dashboard entry point redirects users with one active membership directly
  to that organization and asks users with several memberships to select one.
- Users without an active membership receive a safe access message that does
  not disclose organization names.
- Organization dashboard URLs resolve through `Organization.objects.visible_to()`;
  inaccessible or inactive organizations return `404` to avoid disclosing their
  existence.
- Navigation exposes Django administration only to Django staff. Organization
  administrator membership alone does not grant Django admin access.
- The dashboard displays only implemented organization data. Candidate navigation
  and active-candidate counts are available from `DATA-003`; vacancy, matching,
  and outreach navigation is added with the corresponding roadmap items.

## Core data model

- `Organization`
- `OrganizationMembership`
- `ClientCompany`
- `Candidate`
- `CandidateDocument`
- `CandidateProfile`
- `Vacancy`
- `VacancyRequirements`
- `MatchRun`
- `MatchAssessment`
- `ReviewDecision`
- `OutreachDraft`
- `AIUsageEvent`
- `AuditEvent`

### Candidate intake records

- `Candidate` belongs to exactly one organization and holds only the minimum
  identity/contact fields needed before structured profile extraction.
- Candidate lifecycle metadata distinguishes active, inactive, deletion-requested,
  and deleted records. Deletion states require their relevant audit timestamp.
- `CandidateSource` belongs to a candidate and records source type/name/reference,
  obtained date, stated lawful basis, consent status, contact permission, notes,
  retention date, and the user who recorded it. These fields document the
  organization's assertion; they do not certify legal compliance.
- `CandidateDocument` belongs to a candidate and records document type, original
  filename, opaque storage key, content type, byte size, SHA-256 hash, retention
  date, uploader, and deletion timestamp.
- Candidate, source, and document querysets all require explicit organization
  scoping or an active user/membership path. Related objects expose their owning
  organization for the shared object-permission helpers.
- Stored document paths retain only the extension from the supplied filename and
  use an opaque UUID. No public media URL or delivery route exists.
- PDF and DOCX CV uploads are validated and synchronously extracted before their
  metadata is committed. The service enforces a 10 MB file limit plus bounded
  page, archive-entry, expanded-byte, compression-ratio, and extracted-text limits.
- Successful extraction stores normalized content type, size, SHA-256, text,
  status, timestamp, retention date, and uploader. Failed validation or extraction
  stores neither a document row nor file bytes and returns a bounded public error.
- SHA-256 duplicate checks are organization-local and advisory. The same bytes in
  another organization neither disclose nor block that organization's upload;
  concurrency hardening remains part of the production workflow.
- Recruiter HTML shows safe document metadata only. It exposes neither storage
  paths nor extracted CV text, and no application route serves document bytes.
  Hardened private delivery remains in `PROD-001`.
- Textless/scanned PDFs are rejected rather than silently stored as usable CV
  text. OCR is a separately approved future capability.
- Retention/deletion services must remove underlying stored bytes; deleting a
  Django database row alone does not guarantee storage deletion.
- Recruiter-confirmed candidate deletion removes candidate contact fields,
  provenance rows, document database rows, stored document bytes, and extracted
  text. It retains only the candidate primary key, organization ownership,
  creator attribution, a non-identifying placeholder name, and deletion
  timestamps as a minimal tombstone. Deleted candidates are excluded from
  recruiter lists, detail routes, and uploads.

### Candidate intake workflow

- Recruiter-facing candidate routes resolve the organization through active
  membership and return `404` for inaccessible organizations. Intake services
  repeat the membership check so non-view callers cannot cross the tenant boundary.
- Manual entry creates the candidate and its source/provenance row in one database
  transaction. Consent, lawful-basis, and contact-permission values default to
  explicit unknown/not-recorded states rather than inferred permission.
- CSV import accepts UTF-8 comma-separated data with a required `full_name` column
  and optional `email`, `phone`, `location`, `source_reference`, and
  `retention_until` columns. A project-provided header template and on-page format
  guidance let a recruiter prepare the file without developer help.
- File-level structure, encoding, size, and row limits are checked before any row
  is created. Valid rows can still be created when other data rows fail field
  validation, and the authorized recruiter receives an in-memory per-row report.
- A completed import targets the report section on the returned page so the
  browser brings the created/duplicate/invalid summary into view without a
  client-side application or persistent import record.
- Duplicate detection is limited to the current organization. It uses
  case-insensitive email, normalized phone digits, and exact stable source
  references. Names alone are never treated as identity, existing rows are never
  overwritten or merged, and deleted/inactive records still prevent accidental
  silent recreation when a stable identity matches.
- Duplicate reporting is an intake safety aid rather than a universal identity
  guarantee. Concurrency hardening and durable import/audit events remain part of
  the later production workflow.

### Vacancy intake records

- `Vacancy` belongs to exactly one organization and may reference an optional
  client company for agency use. The model rejects client companies owned by a
  different organization; direct-employer vacancies leave the field empty.
- A client-company deletion does not delete a vacancy. It clears the optional
  relationship so the vacancy and its requirement history remain available.
- Vacancy lifecycle state is limited to draft, open, paused, or closed. Vacancy
  description text remains application-owned input and is not sent to an AI
  provider by the model layer.
- `VacancyRequirements` rows are numbered snapshots unique within a vacancy.
  Each records its schema version, creation method, source-description snapshot,
  structured requirements, recruiter-visible ambiguities, author, and creation
  time so later matching results can identify the exact input version.
- Requirements are editable while draft. Confirmation requires a recruiter actor
  and timestamp; a confirmed snapshot is immutable and corrections create a new
  version. The latest confirmed version is the vacancy's current requirements;
  a newer unconfirmed draft does not silently replace it.
- Requirement list fields validate as lists of non-blank strings. Normalized
  skill entities and executable hard-constraint rules remain owned by Sprint 3.
- Vacancy and requirement querysets provide explicit organization scoping and
  active-membership visibility. Requirement rows expose their vacancy's
  organization for the shared object-permission helpers.
- Recruiter-facing vacancy routes let active organization members list vacancies,
  create a direct-employer or same-organization-client vacancy from pasted text,
  and immediately review the first manual requirements draft. Authorization is
  repeated at both view and service boundaries.
- Requirements list fields use recruiter-friendly one-item-per-line inputs that
  trim blanks and case-insensitive duplicates before persisting validated JSON
  lists. Unknown values remain explicitly blank or `unknown` rather than inferred.
- A recruiter can save a draft repeatedly and explicitly confirm it only after at
  least one meaningful structured requirement is recorded. Confirmation is a
  POST-only action that records the actor and timestamp.
- Confirmed requirements remain immutable. A correction action copies the current
  confirmed snapshot into the next numbered manual draft; if a draft already
  exists, the app reopens it instead of silently creating parallel drafts.
- Recruiters manage vacancy lifecycle from the vacancy detail page through
  POST-only transitions: draft to open, open to paused or closed, paused to open
  or closed, and closed to open. Opening always requires a confirmed requirements
  version. The service repeats tenant authorization, validates the transition,
  and serializes concurrent updates before changing the status.
- Recruiters can delete a vacancy through a separate confirmation page. This is
  a soft deletion: the vacancy is closed and excluded from recruiter lists and
  normal object routes, while its description, immutable requirements history,
  deletion actor, and deletion timestamp remain available for future match
  integrity and administrative audit. Service calls reject later lifecycle or
  requirements mutations on a deleted vacancy.
- The vacancy description and each requirement version's source-description
  snapshot remain application input. AI-assisted extraction remains behind the
  application gateway in `AI-002`.

Structured AI outputs should be stored with a schema version and the relevant source/document version so assessments can be reproduced or invalidated when input changes.

## Matching pipeline

1. Normalize and validate vacancy requirements.
2. Apply organization-visible candidates only.
3. Apply explicit hard filters.
4. Build a deterministic relevance score and bounded shortlist.
5. Send only necessary job and candidate evidence for structured AI assessment.
6. Validate the AI response.
7. Store assessment, metadata, schema version, and source versions.
8. Present results for recruiter review.

Embedding-based retrieval may be added after the deterministic baseline is measured. It is not required to prove the MVP.

## Privacy and security

- Authorization checks are organization-scoped at the query layer and view/service boundary.
- Candidate documents are private and never served by guessable public paths.
- Upload type, size, and content are validated.
- Logs do not contain raw CVs, contact details, prompts, or model responses.
- AI requests minimize personal data and exclude protected attributes.
- Candidate records include source, permission/consent notes, retention dates, and deletion status.
- Deleting a candidate invalidates or removes derived profiles and assessments according to the approved retention policy.
- Secrets come from environment variables or a secret manager and never from committed files.
- AI failures must not expose provider details or sensitive prompts to ordinary users.
- `DJANGO_ENVIRONMENT=production` disables development fallbacks and requires an
  explicit non-placeholder secret, explicit hosts, debug mode off, HTTPS
  redirects, and secure session and CSRF cookies.
- Production rejects wildcard hosts and non-HTTPS CSRF trusted origins.
- `X-Forwarded-Proto` is trusted only through an explicit setting for a known
  reverse proxy that overwrites the header.
- HSTS is explicit rather than silently enabled; deployment owners must confirm
  stable HTTPS before setting its duration, subdomain, or preload options.

## Reliability

- Imports are idempotent where a stable source identifier exists.
- File hashes help detect duplicate CVs.
- A vacancy or candidate profile edit invalidates stale assessments.
- AI calls use bounded retries.
- Batch operations can resume without duplicating completed assessments.
- The deterministic shortlist remains inspectable if AI is unavailable.

## Testing strategy

- Unit tests for parsing normalization, hard filters, scoring bands, and permissions.
- Service tests with a fake AI gateway; ordinary tests never make live provider calls.
- Contract tests against Python AI Toolkit structured outputs.
- Integration tests for import-to-review workflows.
- Security tests for cross-organization access and private documents.
- A separate opt-in smoke test may make a live low-cost API request.
- An anonymized/synthetic benchmark set measures ranking stability and explanation quality.
- `scripts/check.py` is the single local and CI quality gate. It includes normal
  and warning-strict deployment checks, migration-drift detection, tests, lint,
  formatting, and dependency compatibility.
- GitHub Actions runs the locked environment and shared quality gate on every
  pull request and push to `main` across Python 3.11 through 3.14.
