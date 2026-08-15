# Project State

## Project

AI Candidate Matcher

Version: `0.1.0.dev0`

## Goal

Build an AI-assisted candidate rediscovery and shortlisting application for small recruitment agencies and employers, using an organization-controlled candidate pool and mandatory human review.

## Current milestone

Sprint 5 — Recruiter review and outreach — is complete.

Status: `REV-001`, `REV-002`, `OUT-001`, and `OUT-002` are complete; `PROD-001`
is the next approved task.

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
- Confirmed candidate profiles are reusable across vacancies and should be
  re-extracted only for a new or corrected CV/profile.
- Later recruiter UX must replace repetitive high-volume actions with
  exception-focused review and resumable background batches while keeping final
  approve/reject/revisit decisions individual and human-controlled.

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
- Completed the non-admin workflow with a recruiter-facing typed-rule editor on
  draft requirements. Required-skill choices are limited to saved must-have
  skills; valid operators and `unknown / keep for recruiter review` behavior are
  automatic; edit and confirmation-delete actions repeat tenant and draft-state
  checks in the service layer.
- Revalidate typed rules whenever a draft's normalized skills change and again
  before confirmation. A save that would orphan a required-skill rule rolls back
  atomically, while confirmed rules remain visible and immutable.

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
- Added a deterministic skill score from 0 to 100. Scoring algorithm v2 assigns
  two weight units to every must-have skill and one to every nice-to-have skill,
  then apportions exactly 100.00 points across all requirements. This keeps each
  individual must-have approximately twice as valuable as an individual
  nice-to-have regardless of the number of skills in either group.
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

### `AI-001 — Application AI gateway`

- Added an application-owned `AIGateway` protocol and toolkit-neutral structured
  result, token-usage, and safe request-metadata contracts.
- Added a `ToolkitAIGateway` adapter backed only by the published Python AI
  Toolkit v1.0.0 Django integration and structured `AIClient.ask()` contract.
- Constructed the toolkit client lazily so Django startup, checks, migrations,
  deterministic matching, and ordinary tests require neither an API key nor a
  provider request.
- Translated toolkit configuration, provider, JSON, schema-validation, and
  generic failures into bounded application exceptions without carrying raw
  provider messages into normal application error handling.
- Returned validated application-owned Pydantic data and safe operational
  metadata while deliberately excluding toolkit raw and original responses.
- Added a configured gateway factory and constructor injection seam so later
  business-service tests can substitute a fake without monkeypatching views or
  using a live provider.
- Added provider-aware environment mapping for model, API key, embedding model,
  and bounded retry configuration while keeping toolkit file logging disabled.
- Kept vacancy extraction, candidate extraction, match assessment, persistence,
  UI, and live smoke requests in their later explicit roadmap tasks.

### `AI-002 — Structured vacancy-requirements extraction`

- Added a recruiter-triggered, POST-only **Extract with AI** action for editable
  requirements drafts using the preserved source-description snapshot.
- Added an application-owned, extra-forbidding Pydantic extraction schema with
  bounded text and list fields, controlled work-mode and employment-type values,
  non-negative bounded experience, unique list items, and disjoint must-have and
  nice-to-have skill groups.
- Added an untrusted-source prompt that requires explicit source grounding,
  leaves missing facts empty, null, or `unknown`, separates mandatory from
  preferred skills, and excludes protected or sensitive characteristics.
- Applied validated suggestions only after repeating tenant, vacancy, and draft
  authorization. Successful extraction marks the draft AI-assisted, preserves
  its source snapshot, synchronizes normalized skill links, and never confirms
  the version.
- Kept AI hard-constraint suggestions as non-executable recruiter notes. Typed
  deterministic rules still require deliberate recruiter creation in the draft
  editor and retain fixed unknown-fact behavior.
- Prevented a response from overwriting a draft that changed during the provider
  request. Provider, schema, configuration, authorization, deleted-vacancy, and
  concurrent-edit failures leave the draft unchanged and expose only bounded
  recruiter-facing messages.
- Deferred request metadata and failure persistence to `AI-005`; the safe metadata
  was returned by the service but not stored by this task. No candidate data,
  candidate extraction, match assessment, or live ordinary test request was added.

### `AI-003 — Structured candidate-profile extraction`

- Added a recruiter-triggered, POST-only extraction action for successfully
  parsed CV documents and a separate tenant-safe profile review page.
- Added an application-owned, extra-forbidding Pydantic schema with bounded
  employment history, skills, location, work mode, languages, education,
  certifications, employment preferences, availability, and ambiguities.
- Removed the candidate name, contact values, generic emails, phone numbers,
  URLs, contact-labelled lines, and protected/sensitive prefixed lines before
  building the untrusted-CV prompt. The prompt requests no hiring recommendation.
- Required exact source evidence for every returned fact and independently
  verified each excerpt against the redacted source before saving anything.
  Presentation-only Unicode quote, dash, bullet, and line-wrap differences are
  normalized without accepting paraphrases or changing meaningful skill
  punctuation. Missing facts remain unknown and unsupported output is rejected.
- Added immutable, numbered `CandidateProfile` snapshots tied to one source
  document and its document/text hashes. Successful extraction creates only a
  draft; provider, schema, authorization, deletion, oversized-input, and source-
  change failures create no profile and expose bounded messages.
- Added a separate recruiter confirmation action. Only the latest confirmed
  profile is matching input, older drafts cannot supersede it, and confirmed
  snapshots cannot be changed in place.
- Published confirmed profile skills as inspectable candidate-skill evidence
  linked to the source profile and document while preserving recruiter/manual
  assertions and replacing only earlier AI-published assertions for that source.
- Extended deterministic rule evaluation to grounded confirmed profile facts.
  Non-matching or absent facts remain unknown and eligible for review rather than
  becoming inferred failures.
- Added confirmed profile content to privacy-preserving candidate input
  signatures. Draft extraction leaves historical shortlists current; confirmation
  makes affected runs stale without rewriting them.
- Extended candidate deletion so the source-document cascade removes profile
  versions and their AI-published skills. Raw CV text, prompts, contact values,
  provider output, match assessments, and AI request metadata are not displayed
  or persisted by this task.

### `AI-004 — Structured evidence-based match assessments`

- Added a recruiter-triggered, POST-only assessment action to each candidate on
  a current deterministic shortlist. One explicit request assesses one candidate,
  isolating failures and avoiding a blocking 20-candidate batch before background
  processing is introduced.
- Required the shortlist's exact current confirmed requirements version, an
  active same-organization candidate, a current confirmed candidate profile, and
  a non-stale match run before any provider request.
- Built a bounded minimized context from confirmed requirement wording,
  application-owned candidate evidence, source/schema versions, and the saved
  deterministic outcome. Candidate identity, contact details, raw CV text,
  vacancy identity, prompts, and raw provider output are not persisted or shown.
- Added an extra-forbidding structured schema containing an independent 0–100 AI
  score, a complete per-requirement outcome, opaque candidate-evidence references,
  an evidence-based summary, and recruiter review focus. Every confirmed
  requirement must appear exactly once; matches and gaps require supplied
  evidence, while absent support must remain uncertain.
- Resolved opaque model references back to application-owned vacancy and candidate
  evidence before persistence, so provider output cannot invent or rewrite the
  displayed source evidence. Unknown IDs, incomplete requirement coverage,
  decision language, and oversized context save nothing.
- Added immutable numbered `MatchAssessment` snapshots linked to the exact
  `ShortlistEntry`, `VacancyRequirements`, and `CandidateProfile` versions. The
  application derives red/amber/green from the AI score; neither value changes
  deterministic eligibility, rank, score, or historical shortlist content.
- Rechecked the candidate profile and shortlist inputs under database locks after
  the provider returns. Concurrent confirmation or matching-input changes discard
  the completed output instead of attaching it to stale evidence.
- Added tenant-safe shortlist display of all assessment versions, evidence-linked
  matches, gaps, uncertainties, and recruiter review focus. No approve/reject,
  hiring recommendation, ranking change, contact action, review queue, or
  outreach workflow was introduced.
- Deferred safe request metadata and failure persistence to `AI-005`. Ordinary
  tests use injected fake gateways and make no live request.

### `AI-005 — Safe AI usage and failure persistence`

- Added the `audit` Django app and a tenant-scoped `AIUsageEvent` ledger for
  vacancy extraction, candidate-profile extraction, and match assessment.
- Created one pending event only after workflow authorization and source/input
  preconditions pass, but before configured gateway construction and the provider
  request. Invalid local actions that never attempt AI create no misleading usage.
- Persisted successful request ID, model, duration, retries, optional input/output/
  total tokens, optional estimated USD cost, actor, organization, workflow,
  generic target/result type and numeric IDs, schema version, and timestamps.
- Finalized successful usage in the same database transaction as the resulting
  requirements update, candidate-profile draft, or match assessment so the two
  records cannot disagree after an ordinary transactional failure.
- Recorded gateway failures using only allow-listed configuration, unavailable,
  invalid-response, or generic request codes. Application rejection after a
  completed response uses one bounded application-validation code and retains
  only the response's safe operational metadata. Provider messages, validation
  messages, exception text, prompts, raw responses, source text, CV text, names,
  and contact values have no ledger fields.
- Made completed events immutable, protected organization ownership, preserved
  non-identifying event history when an actor is deleted, added database status/
  result/failure consistency constraints, and exposed read-only Django admin
  inspection without adding recruiter-facing cost/failure reporting early.
- Added service, integration, tenant, privacy, immutability, deletion, and
  database-constraint tests. The existing AI workflow fake gateways remain fully
  provider-free; broader contract and opt-in live smoke coverage remains `AI-006`.

### `AI-006 — Fake gateway, contracts, and opt-in live smoke test`

- Added a reusable provider-free `FakeAIGateway` with deterministic safe
  metadata, static or dynamic structured responses, configured bounded failures,
  normalized call capture, and response-type mismatch detection.
- Replaced the separate vacancy, candidate-profile, and match-assessment request
  doubles with the shared fake while preserving each domain suite's specialized
  outputs and concurrency simulations.
- Centralized non-blank prompt and Pydantic response-type validation so the fake
  and `ToolkitAIGateway` enforce the same application input contract.
- Made `AIGateway` runtime-checkable and added shared contract tests that exercise
  fake and toolkit-backed adapters for normalized requests, validated result/
  metadata envelopes, absent raw-response exposure, and pre-call validation.
- Preserved adapter-specific coverage for lazy toolkit client construction,
  safe result translation, optional metadata, bounded exception translation,
  configured factory substitution, and non-toolkit programming failures.
- Added `live_tests/test_ai_gateway_live.py` outside ordinary pytest `testpaths`.
  It requires `RUN_LIVE_AI_SMOKE=1`, sends one tiny synthetic structured prompt,
  verifies safe metadata, uses no domain/database/private data, and remains
  potentially billable and deliberately manual.
- Documented the PowerShell live command and confirmed the test skips without
  the explicit switch. CI and `scripts/check.py` cannot collect the live test
  under the configured ordinary `tests` path.
- No toolkit defect or reusable API gap was reproduced against the published
  v1.0.0 integration.

### `REV-001 — Recruiter review queue and assessment detail`

- Added an organization-scoped review queue that consolidates immutable history
  to the latest assessment for each shortlist entry and exposes explicit scopes
  for items needing focus, changed inputs, and all assessments.
- Ordered changed shortlist/profile inputs and evidence exceptions before routine
  results. Each compact item shows gap, uncertainty, confirmed-profile ambiguity,
  and deterministic unknown-fact counts without silently approving routine work.
- Added a tenant-safe assessment detail screen with application-owned vacancy and
  candidate evidence, separate AI and deterministic scores, confirmed-profile
  ambiguities, currentness warnings, recruiter review focus, and links to every
  immutable assessment version for the shortlist entry.
- Reused existing confirmed candidate profiles and privacy-preserving shortlist
  signatures. The workflow stores no repeated profile approval, review decision,
  contact data, raw CV text, prompt, raw response, or protected characteristic.
- Added normal workspace navigation and an assessment-detail link from the
  shortlist while preserving the existing shortlist assessment display.
- Kept approve/reject/revisit decisions in `REV-002`, batch/background processing
  in `PROD-003`, and outreach in `OUT-001`/`OUT-002`. No model or migration was
  required because review state is derived from existing immutable records.

### `REV-002 — Individual recruiter decisions`

- Added immutable numbered `ReviewDecision` events tied to one shortlist entry
  and the exact latest assessment reviewed. Choices are limited to approve,
  reject, or revisit, and every record requires bounded recruiter notes, a
  protected human actor, and timestamp.
- Added an organization-authorized transactional service that serializes
  decision versions and refuses decisions for inactive candidates, older
  assessment versions, changed confirmed profiles, stale shortlist inputs, or
  deleted vacancies.
- Added a POST-only decision form to the evidence detail screen. Corrections
  append a new decision version while preserving earlier choice, notes,
  assessment, actor, and time.
- Updated the review queue to default to pending individual decisions while
  retaining exception, changed-input, and all scopes. It shows current decision
  counts and status badges and never carries a decision from an older assessment
  onto a newer version.
- Added read-only Django admin inspection, tenant-isolation and immutability
  safeguards, candidate-deletion cleanup, focused automated coverage, and a full
  manual browser test workflow.
- Decisions do not change deterministic or AI results and create no outreach
  draft, approval, copy/export, send, or contact action. Those remain `OUT-001`
  and `OUT-002`.

### `OUT-001 — Approved-only outreach draft generation`

- Added an organization-scoped `outreach` app with immutable numbered
  `OutreachDraft` snapshots tied to the exact approved `ReviewDecision`, shortlist
  entry, schema version, generating human actor, and timestamp.
- Added a POST-only generation service and route that accept only the latest
  explicit approval while the exact latest assessment, active candidate,
  confirmed profile, and shortlist inputs remain current. The service locks and
  repeats those checks after the provider returns.
- Added a bounded extra-forbidding subject/body output schema. The minimized
  request sends an application-owned candidate-name placeholder, organization
  name, vacancy title, and evidence-backed positive match facts only. Candidate
  name/email/phone, raw CV text, recruiter notes, scores, gaps, uncertainties,
  protected characteristics, and raw responses are excluded.
- Added application-side placeholder substitution plus rejection of missing or
  repeated placeholders, invented contact details/links, and hiring-decision or
  job-offer language.
- Added a recruiter-facing generated-draft detail and immutable version history,
  with its exact source decision, actor, timestamp, and an explicit generated-
  only/no-send warning. The assessment review page exposes generation only when
  currently eligible.
- Added safe outreach workflow/target/result categories to `AIUsageEvent`; domain
  persistence and successful usage finalization share a transaction, while
  bounded gateway/application failures create no partial draft.
- Added read-only Django admin, tenant-isolation, concurrency/currentness,
  privacy-minimization, immutability, candidate-deletion, route, and manual test
  coverage. Editing, final approval, copy, export, and sending remain `OUT-002`.

### `OUT-002 — Editing, exact final approval, copy, and export`

- Extended immutable `OutreachDraft` history with creation method and parent-
  version provenance. Recruiter edits append a numbered version with actor and
  timestamp; generated or prior versions are never overwritten, and approval is
  never carried to edited content.
- Added immutable one-to-one `OutreachDraftApproval` records for the exact latest
  subject/body. Approval requires bounded recruiter notes, an explicit contact-
  permission attestation, actor, and timestamp while the source approved decision,
  assessment, confirmed profile, and shortlist remain current.
- Required at least one explicitly permitted candidate source before final
  approval. Restricted or withdrawn contact permission and withdrawn consent
  block approval; permission and evidence checks repeat before every manual use.
- Added recruiter-facing edit and final-approval workflows. Historical versions
  remain inspectable, an approved draft can be edited only into a new unapproved
  version, and stale/superseded decisions or drafts expose clear blockers.
- Added manual browser clipboard copy and UTF-8 plain-text export for only the
  exact approved current draft. The server revalidates before returning copy text
  or export content; downloads use a private no-store response and non-identifying
  filename.
- Added immutable `OutreachDraftAction` copy/export history with exact draft,
  actor, and timestamp plus read-only Django admin inspection. Candidate deletion
  removes approval/action history with its private outreach and matching history.
- Added tenant isolation, method safety, model immutability, exact-version,
  permission-withdrawal, stale-decision, route, clipboard/export, deletion, and
  manual browser coverage. No recipient, email/ATS integration, provider send,
  automatic outreach, or new AI request was added.

## Verification

Final `OUT-002` verification completed on 2026-08-14:

- Focused outreach/review/audit regression set: `39 passed`.
- Complete `python scripts/check.py` quality gate: `390 passed`.
- Django system and deploy checks passed with no issues.
- Migration drift check reported no changes.
- Ruff lint passed and all `142` files were already formatted.
- Dependency check confirmed all `32` installed packages are compatible.
- New migration `outreach.0002_outreach_workflow` applied successfully.
- The complete gate and migration application were repeated successfully from a
  clean extraction of the restricted final deliverable ZIP.

## Not implemented

Outreach generation, immutable recruiter editing, exact final approval, manual
copy, and plain-text export are implemented. Automatic sending, recipient
selection, email/ATS/platform integrations, and permission-management UI are not
implemented; sending remains outside the MVP.
Recruiters can intentionally run structured vacancy extraction for an editable
requirements draft and candidate-profile extraction for a lawfully stored,
successfully parsed CV. Both create human-reviewable drafts; only explicit
candidate-profile confirmation publishes grounded matching facts. Candidate
records can also be manually created, imported, and given
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
For each candidate on a current shortlist with a confirmed profile, recruiters
can request and inspect immutable evidence-based AI assessment versions. These
are decision support only and cannot change the deterministic shortlist.
Safe AI usage events are available to operators through read-only Django admin;
recruiter-facing usage/cost/failure reports remain deferred to `PROD-004`.
The review queue now reuses confirmed profiles and provides compact exception-
focused assessment review and individual decision history. Remaining high-volume work uses `PROD-003` for resumable batch
profile extraction and whole-shortlist assessment generation. No profile will be
silently confirmed, and final employment decisions are individual recruiter
actions with notes, actor, and timestamp.

Recruiters can manage typed hard-constraint records from the normal requirements
editor while the version is a draft. The older free-text hard-constraint field is
clearly labelled as non-executable notes. Confirmed versions remain immutable;
rule corrections require a copied draft version.

## Next task

`PROD-001 — Add private file-delivery controls and upload hardening.`
