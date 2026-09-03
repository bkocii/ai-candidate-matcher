# Project State

## Project

AI Candidate Matcher

Version: `0.1.0.dev0`

## Goal

Build an AI-assisted candidate rediscovery and shortlisting application for small recruitment agencies and employers, using an organization-controlled candidate pool and mandatory human review.

## Current milestone

Sprint 7 — Evaluation and showcase release — is in progress after the completed
`EVAL-001` synthetic baseline, `EVAL-002` ranking measurement, and `EVAL-003`
explanation review, and `DEMO-001` reproducible showcase.

Status: the user-approved corrective `INTAKE-001` task, `EVAL-001`, and
`EVAL-002`, `EVAL-003`, and `DEMO-001` are complete after `PROD-005`; `DEMO-002`
remains the next release-roadmap task. The user approved a pre-release
functionality pass before styling/positioning; `DEF-001` is complete and the
CV-first `CR-004` workflow, plain-language `CR-005` privacy/source pass, and
dependency-aware `CR-002` lifecycle controls and in-app `CR-003` client-company
management are complete. `CR-001` managed multi-organization provisioning and
membership administration is also complete. `DEMO-002` remains next.

## Decisions made

- The first product is recruiter-side candidate search, not job search for candidates.
- The MVP searches candidates supplied or controlled by the organization.
- The product does not scrape LinkedIn or arbitrary websites.
- The managed deployment supports several strictly isolated organizations and
  multiple recruiter accounts per organization.
- Platform ownership is separate from Django staff/superuser state and tenant
  membership; it never grants implicit recruitment-data access.
- Platform owners provision organizations and first administrators. Organization
  administrators manage recruiters, and shared accounts can switch active
  workspaces without one membership change affecting another.
- Agency deployments can associate vacancies with optional client companies.
- Deterministic filtering precedes AI assessment.
- Deterministic skill matching uses a small controlled alias policy, preserves
  original source wording/evidence, and never uses unrestricted substring
  matching.
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
- Bulk CV candidate creation uses reviewed local identity proposals and shared
  recruiter-supplied provenance. AI may create later evidence-based profile
  drafts, but it does not determine identity, lawful basis, consent, or contact
  permission and never creates candidates without an explicit selected action.
- Candidate creation is CV-first for one or several documents. Optional CSV data
  maps only by exact `cv_filename`; quick-add can include one validated CV; and
  one explicit batch action confirms only clean evidence-validated profile drafts
  after showing included/excluded rows. Every confirmed profile retains its own
  actor/time record, while candidate decisions and outreach remain separate.
- Recruiter-facing candidate source fields use practical wording and never
  default consent or contact permission to approval. Rediscovery outreach needs
  a recorded reason, Future roles allowed, and Given consent when consent is the
  selected reason.
- Organization lifecycle cleanup is dry-run first and removes complete,
  policy-expired dependency bundles only. Current workflows, recruiter decisions,
  and finally approved/copied/exported outreach remain protected; legal holds
  and tenant-scoped exceptions block scheduled deletion.

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
- Added an authenticated-HTML response boundary that marks tenant and platform
  pages private and non-cacheable, preventing protected content from being
  restored from browser history after logout without changing static-asset or
  other non-HTML caching.
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
  no file-delivery route at the `DATA-004` milestone; hardened private delivery
  was completed later in `PROD-001`.
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

### `DEF-001 — Canonical skill matching`

- Added a deliberately small, reviewable application-owned alias policy for
  unambiguous Python and Django developer/development wording.
- New candidate and vacancy skill links use canonical identities while retaining
  their original extracted or recruiter-entered labels and evidence.
- Hard filtering and shortlist scoring canonicalize both sides again at runtime,
  so existing confirmed records such as candidate `Python` versus vacancy
  `Python development` match without re-extraction or immutable-data rewriting.
- Existing duplicate aliases count at most once per canonical requirement;
  must-have remains authoritative over a duplicate nice-to-have entry.
- Unsafe near-matches such as `Java` and `JavaScript` remain distinct, and
  unknown terms receive no guessed substring or automatic AI match.
- Advanced the deterministic algorithm marker to v3 so earlier runs become
  inspectably stale and require explicit regeneration rather than silent edits.
- Added focused coverage for aliases, case/spacing/punctuation variation, new and
  saved-version behavior, source-label preservation, hard rules, shortlist
  scoring, and unsafe near-matches. No model or migration was required.

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

#### Corrective evidence-grounding and skill-completeness pass — 2026-08-15

- Preserved the strict exact-excerpt and fact-to-excerpt checks after live
  schema-valid responses paraphrased evidence or attached a skill to an excerpt
  that did not name it.
- Added exactly one application-owned correction request only for this grounding
  failure. It reuses the redacted source, supplies privacy-safe schema locations,
  excludes the failed provider output, and requires a complete replacement.
- The replacement must pass the unchanged deterministic validator. A second
  failure makes no third request, reports only bounded areas such as `skill item
  1`, and creates no profile or published skill.
- Recorded the failed first request and correction request as separate safe usage
  events. No toolkit source/API, database model, migration, confirmation rule, or
  matching behavior changed.
- Strengthened skill completeness so the structured request scans profile and
  experience narrative as well as a Skills heading. Distinct explicit facts such
  as `pytest` and `Automated testing` are requested separately; a tool does not
  imply an unnamed method, and every returned skill still requires exact source
  evidence before it can be confirmed and published.

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

### `PROD-001 — Private file delivery and upload hardening`

- Added an authenticated organization-scoped download for stored candidate CVs.
  The view resolves the organization, active candidate, and exact document
  relationship before a service repeats organization-object authorization.
- Loads at most the existing 10 MB bound and verifies the saved byte length and
  SHA-256 before returning anything. Missing, changed, deleted, unsuccessful, or
  invalid-metadata documents receive only a bounded safe failure.
- Returns the validated original basename and content type as an attachment with
  private/no-store caching, no-sniff, sandbox, same-origin resource, no-referrer,
  and no-index headers. Neither opaque storage keys nor extracted CV text are
  included in the route, page, headers, or error messages.
- Hardened upload filenames against Unicode control/format spoofing. PDF parsing
  now rejects scripts, launch/external-file actions, submissions/import actions,
  rich media, and embedded files while retaining ordinary links.
- Hardened DOCX validation against case-insensitive duplicate entries, symlinks,
  backslash/drive-style paths, embedded/active objects, malformed relationships,
  and unsafe external package relationships. Ordinary hyperlink relationships
  remain supported.
- Serialized the final duplicate-hash check and save with organization and
  candidate row locks, and rechecked deleted-candidate state before persistence.
  Equal bytes remain allowed across separate organizations.
- Added focused service, parser, tenant-isolation, route, response-header,
  integrity, and recruiter-browser coverage. No AI/toolkit, audit-event,
  retention scheduler, background task, or observability behavior changed.

### `PROD-002 — Audit views, retention/deletion workflow, and minimization`

- Added immutable organization-owned privacy audit events with controlled
  actions/object types, numeric IDs, optional actor, schema version, and
  timestamp only. Candidate request/retention/cancel/purge, private CV download,
  and vacancy deletion are recorded without copied identity, contact, CV,
  prompt, response, note, or outreach content.
- Added a tenant-scoped **Privacy & audit** dashboard. It presents staged
  deletion requests, candidate/source/document retention exceptions, missing
  retention dates, deleted-tombstone minimization findings, privacy events, and
  compact summaries over existing AI/import/assessment/decision/outreach audit
  records.
- Replaced immediate candidate purge in the recruiter route with a staged
  request that freezes new upload, extraction, and matching work. A separate
  organization-administrator confirmation permanently purges the record; an
  administrator can instead cancel and restore its exact prior active/inactive
  status.
- Added a schedulable `process_retention` command. It reports only organization
  slug and aggregate due count, defaults to dry-run, and with `--apply` creates
  idempotent candidate deletion-review requests. It never purges data; source
  and document dates remain individually inspectable review signals.
- Tightened the minimized candidate tombstone by clearing request actor and
  prior-status metadata after purge while preserving request/purge attribution
  in the content-free ledger. Added checks for retained identity, provenance,
  documents, skills, or shortlist data after deletion.
- Kept AI/toolkit behavior, outreach separation, final individual candidate
  decisions, and the `PROD-003` background-processing boundary unchanged.

### `PROD-003 — Background processing, idempotency, resumability, and status`

- Added an application-owned `operations` app with durable organization-scoped
  background jobs and isolated per-target tasks. The database records only
  controlled workflow/target/result IDs, status, attempts, leases, counts, and
  allow-listed failure codes; it does not copy candidate, CV, prompt, response,
  decision-note, or outreach content.
- Added one recruiter action that queues each active candidate's newest
  successfully parsed, unprofiled CV. Existing drafts or confirmed profiles for
  that source are reused, while a newer corrected CV remains independently
  eligible. Completed extraction creates a draft and never silently confirms it.
- Added one whole-shortlist action that queues every entry only for a current
  deterministic run. Each task reuses an assessment already saved for the exact
  shortlist entry, current confirmed profile, and requirements snapshot; missing
  profiles and changed inputs remain visible exceptions.
- Added deterministic batch idempotency keys and organization-level creation
  serialization. Repeating the same eligible source set or match run returns the
  existing job and creates no duplicate task or routine AI call.
- Added a separate `run_background_worker` command with continuous, `--once`,
  `--burst`, and job-scoped modes. Expiring task leases make interrupted work
  reclaimable, and saved-result preflight makes post-save recovery idempotent.
- Isolated provider, authorization, validation, missing-target, and unexpected
  failures per task using content-free codes. Explicit retry requeues only failed
  or skipped targets and preserves successful work.
- Added **Jobs** list/detail status screens and result links resolved from current
  tenant-scoped records. Profile results remain individually inspectable and
  confirmable; assessments flow into the existing exception-focused review and
  individual decision workflow. No batch decision, confirmation, outreach, or
  send action was added.
- Kept toolkit integration unchanged: orchestration wraps the existing
  application services and their ordinary structured-request gateway calls.

### `PROD-004 — Token, cost, latency, retry, and failure reporting`

- Added a tenant-scoped **AI usage** report derived from the immutable,
  minimized `AIUsageEvent` ledger. No reporting copy or parallel usage store was
  introduced.
- Added 7-, 30-, and 90-day and all-time period filters plus workflow filters.
  The report aggregates attempts, completion outcomes, success rate, available
  input/output/total tokens, estimated cost, average latency, retries, and stale
  pending attempts.
- Added workflow and model breakdowns, allow-listed failure categories, and a
  bounded daily trend. Provider metadata coverage is shown explicitly; missing
  values remain unavailable rather than being treated as zero or estimated.
- Kept the report content-free: it exposes no request IDs, prompts, raw
  responses, source descriptions, CV or contact data, recruiter notes,
  decisions, or outreach content.
- Kept toolkit and schema boundaries unchanged. Existing safe success metadata,
  application timestamps, and failure codes were sufficient, so no toolkit
  change or database migration was needed.
- Corrected the shared quality gate to override all required HTTPS settings in
  its isolated deployment-check subprocess. A normal development `.env` can
  therefore retain secure-cookie values as false without contaminating the
  production configuration check.

### `PROD-005 — Deployment documentation and production checks`

- Replaced production SQLite with fail-closed explicit PostgreSQL configuration,
  connection health checks, configurable SSL mode, and locked Psycopg support.
  Development and ordinary tests continue to use SQLite.
- Added an explicit production private-media root, separate static root,
  restrictive uploaded-file permissions, and production validation that rejects
  missing, relative, equal, or nested private/static paths.
- Added locked Gunicorn support plus version-controlled reference Nginx and
  systemd units for web, continuous durable worker, release preparation, and the
  safe daily retention-review timer. Private media is never exposed by Nginx.
- Added content-free liveness and database-readiness endpoints. Database failure
  returns only a generic unavailable response and no credentials, paths,
  exception details, or recruitment content.
- Added `check_production`, which verifies Django deployment checks, PostgreSQL
  connectivity, fully applied migrations, collected project CSS, and a private-
  storage save/read/delete round trip with controlled operator output.
- Extended the shared quality gate to collect production static assets under its
  isolated deployment environment before the warning-strict deployment check.
- Added a complete deployment runbook covering prerequisites, secret handling,
  release installation, migrations/static/readiness, worker initialization,
  HTTPS, monitoring, retention scheduling, paired database/private-media
  backups, isolated restore drills, upgrades, rollback, and acceptance checks.
- Corrected local setup guidance so `.env.example` is copied only when `.env`
  does not already exist. No AI workflow, toolkit contract, recruiter decision,
  or outreach boundary changed.

### `INTAKE-001 — Reviewed bulk CV candidate intake`

- Added organization-scoped intake batches that record shared source,
  lawful-basis, consent, contact-permission, notes, and candidate/source/document
  retention defaults once before any candidate is created.
- Added multi-file PDF/DOCX intake with at most ten files and 10 MB combined per
  request and fifty items per batch. Every file independently reuses the existing
  hardened CV validator, so rejected files store no row or private bytes while
  valid files remain reviewable.
- Added conservative local name/email/phone/header-location proposals and clear
  missing, multiple, and filename-derived review flags. Identity/contact data is
  not sent to AI, and every proposed field remains recruiter-editable.
- Added compact selected-row creation. Each accepted row revalidates and
  integrity-checks its staged CV, repeats organization-local stable-identifier
  duplicate checks, and transactionally creates the active candidate,
  `DOCUMENT_UPLOAD` provenance, and private extracted CV.
- Exact-file duplicates are rejected before staging; possible identity duplicates
  cannot silently create a second candidate. Cross-organization candidates,
  documents, batches, and routes remain isolated.
- Created and discarded items clear their temporary file, extracted text,
  identity/contact proposals, hash, and file metadata. Discarding a batch clears
  every remaining pending item without changing already-created candidates.
- An explicit checked action queues only newly accepted CVs through the existing
  durable candidate-profile workflow. Repeating the same CV set reuses the job;
  the worker still creates drafts only, and profile confirmation, final candidate
  decisions, and outreach remain separate human actions.
- Added `candidates.0006_candidateintakebatch_candidateintakeitem_and_more` plus
  focused service, form, route, tenant, private-storage, duplicate, minimization,
  and background-job tests. No AI gateway, toolkit dependency, prompt, or
  operations schema changed.

### `CR-004 — Unified candidate intake and batch profile confirmation`

- Made **Create candidates from CVs** the primary creation action and reused the
  hardened reviewed intake for either one CV or several CVs.
- Added a bounded UTF-8 mapping CSV to the intake screen. It requires exact
  `cv_filename` plus `full_name`, accepts optional contact/location/source-
  reference values, and reports missing, repeated, conflicting, or invalid rows
  without fuzzy name matching or candidate creation.
- Converted manual creation into **Quick add**: full name remains the only
  required identity field, safe provenance/permission defaults remain explicit,
  and one optional PDF/DOCX CV is validated and committed in the same action. A
  failed CV rolls back the candidate and source.
- Linked each processed intake item to its exact accepted private document after
  clearing staging bytes, extracted text, identity proposals, filenames, and
  hashes. Historical items without a provable link remain safe exclusions.
- Added an intake profile-confirmation review with included/excluded counts and
  individual profile links. Only evidence-validated drafts without ambiguity,
  sensitive-content, changed-source, lifecycle, missing-link, or newer-confirmed
  exceptions are eligible.
- **Confirm all eligible profiles** is an explicit recruiter POST action that
  reuses the existing per-profile confirmation transaction. Each profile records
  its own actor/timestamp and publishes grounded matching facts; exception drafts
  remain unchanged and no assessment, candidate decision, outreach draft, or
  send action is created.
- Added `candidates.0007_intake_accepted_document` plus focused mapping,
  quick-add, batch-confirmation, rollback, safety-boundary, and tenant tests. No
  AI gateway, prompt, toolkit dependency, operations schema, matching model, or
  outreach behavior changed.

### `CR-005 — Practical candidate privacy and source fields`

- Preserved the existing controlled database values while translating normal
  recruiter forms and review pages to **Reason for storing data**, **Consent**,
  **Allowed contact**, and **Delete or review on**.
- Relabelled contact states as **Not confirmed**, **Future roles allowed**,
  **Application only**, and **Do not contact**. Consent defaults to **Not
  recorded**, never **Given**, across quick-add, CSV import, and reviewed CV
  intake.
- Added the approved source-name and source-reference explanations and retained
  shared bulk privacy/source values plus record-specific exact references.
- Added an inspectable candidate source/privacy table without exposing another
  organization or introducing mutable source administration early.
- Tightened final outreach approval and every later copy/export recheck. Every
  source needs a recorded reason, only Future roles allowed permits rediscovery
  outreach, and consent selected as the reason requires Consent = Given.
- Left candidate/source/document delete-review dates explicit rather than
  inventing a universal default. CR-002 separately supplies organization policy
  limits for abandoned intake, jobs, uncommitted workflow history, minimized
  metadata, and staged organization deletion.
- Added focused form, safe-default, display, tenant, and outreach eligibility
  tests. No model field, migration, AI gateway, prompt, toolkit, matching,
  decision, or send boundary changed.

### `CR-006 — Candidate correction and conflict-safe confirmation`

- Added tenant-scoped **Edit details** and source/privacy correction routes.
  Candidate edits repeat email/phone duplicate checks; source edits repeat stable
  reference checks. Deletion-frozen records remain uneditable.
- Added minimized immutable audit actions for candidate, source, and corrected
  profile versions without copying private values or before/after content.
- Added recruiter correction that creates a new numbered profile draft against
  the unchanged CV, permits removal of questionable skills, and reruns the
  existing schema/evidence validators. Existing versions remain unchanged.
- Added deterministic candidate/profile location conflict detection. Direct
  confirmation fails and intake batch review excludes the draft until resolved.
- Replaced the source/privacy table with responsive cards, exposed phone, added
  edit actions, clarified draft wording, labelled evidence, and omitted fully
  empty qualification panels.
- Adds `audit.0006_remove_auditevent_audit_event_has_valid_action_and_more`; no
  candidate, matching, AI/toolkit, decision, or outreach schema changes.
- Focused correction/intake/profile/privacy/outreach/staleness coverage:
  `77 passed`; expanded candidate/audit/lifecycle regressions: `151 passed`.
- Complete quality gate: `542 passed`; deployment/static checks, migration drift,
  Ruff across `223` files, formatting, and dependency compatibility all passed.

### `EVAL-001 — Synthetic candidates, vacancies, and expected matches`

- Added the strict version-controlled `eval-001.synthetic-multirole.v1`
  manifest with 20 obviously synthetic candidates, 3 synthetic vacancies,
  exact expected deterministic top-five ranks/scores, and a complete 0–3
  relevance judgment for every candidate/vacancy pair.
- Added a safe management command that installs the fixtures under one new
  isolated organization owned by an existing active user. It refuses to replace
  any existing organization or recruitment data.
- Generated one private DOCX CV per candidate from the manifest and passed every
  document through the existing hardened upload service. Each synthetic profile
  is schema-validated, exactly grounded in that generated document, individually
  confirmed, and publishes its normal inspectable skill evidence.
- Created each vacancy through the existing draft/edit/confirm/open services and
  generated one ordinary deterministic shortlist. A frozen rank or score
  mismatch rolls back the database operation and removes generated private
  files.
- Kept synthetic contact fields empty and every source contact permission
  restricted. Installation makes no provider request, AI usage event,
  assessment, recruiter decision, outreach draft, copy/export, or send action.
- Added focused manifest, command, private-file cleanup, evidence-grounding,
  frozen-ranking, and no-side-effect coverage. No model, migration, matching
  algorithm, prompt, AI gateway, toolkit dependency, or production behavior
  changed.

### `EVAL-002 — Separate deterministic and AI-assisted ranking quality`

- Added a read-only measurement service and management command over the frozen
  EVAL-001 workspace. It resolves exact synthetic candidates/vacancies, requires
  a complete current candidate pool and non-stale deterministic runs, and never
  changes the manifest or recruitment records.
- Measures each vacancy and the macro average at cutoff 5 using graded nDCG,
  grade-2-or-3 precision, and expected-top-set overlap. The frozen deterministic
  baseline is nDCG `1.0000`, precision `0.9333`, and overlap `1.0000`.
- Measures AI-assisted ordering only from each shortlist entry's latest current
  assessment score. Deterministic rank is only a reproducible equal-score
  tie-break; deterministic and AI scores are never blended.
- Reports incomplete or profile-stale AI assessment coverage as unavailable.
  A strict command option can fail the gate after reporting; it never fills the
  missing coverage or makes a provider request.
- Keeps output content-minimized to dataset identity, organization slug, vacancy
  codes, metrics, and coverage counts. No candidate identity/contact, CV,
  evidence, prompt/response, decision, or outreach content is copied.
- Added provider-free tests for frozen metrics, complete and partial AI coverage,
  degraded independent AI ordering, stale-run refusal, safe JSON, no usage-event
  side effect, and the strict coverage gate. No model, migration, prompt, AI
  gateway, toolkit dependency, or production behavior changed.

### `EVAL-003 — Explanation evidence and protected-attribute review`

- Added a read-only explanation-review service and management command over the
  exact installed EVAL-001 workspace and each entry's latest assessment tied to
  its current confirmed profile and requirements.
- Reconstructs application-owned requirement and candidate-evidence references,
  verifies exact stored snapshots and complete requirement coverage, and flags
  invalid or missing evidence links without trusting stored provider text.
- Flags explicit protected/sensitive attribute terminology, unsupported measured
  or quoted claims, and match citations with no direct lexical support. The last
  remains a human-review signal; the evaluator never turns it into a candidate
  decision.
- Reports partial current-assessment coverage as unavailable. Strict complete and
  clean gates fail only after the same content-minimized report is produced.
- Limits reports to frozen dataset identity, organization slug, synthetic
  vacancy/candidate codes, assessment version, safe issue location/code, and
  counts. It copies no source evidence, provider explanation, candidate identity,
  contact, CV, prompt/response, decision, or outreach content.
- Reuses the explicit protected/sensitive detector at the match-assessment write
  boundary so new unsafe provider output is rejected before persistence. No
  ranking, assessment score, recruiter decision, or outreach behavior is added.
- Added provider-free clean/partial coverage, unsupported-claim, protected-term,
  snapshot-integrity, citation-mismatch, minimized-command, strict-gate, and
  runtime no-save coverage. No model, migration, AI request, toolkit dependency,
  or background-job schema changed.

### `DEMO-001 — Reproducible synthetic demo and screenshots`

- Added `prepare_demo`, which installs the frozen EVAL-001 fixture into a new
  isolated organization and refuses to overwrite an existing slug.
- Uses the normal assessment, individual-decision, and outreach-generation
  services with schema-validated deterministic fake-gateway responses. It makes
  no provider or network request and is explicitly not an AI-quality measure.
- Creates 20 current assessments for the V01 Django shortlist, one each approve,
  revisit, and reject decision, and one inspectable outreach draft tied to the
  approved decision.
- Preserves all safety boundaries: profiles are already evidence-confirmed,
  missing requirement evidence remains uncertain, decisions are individual, and
  outreach remains a separate unapproved action. Restricted synthetic contact
  permission visibly blocks final approval, copy, and export; nothing is sent.
- Added a five-minute walkthrough and four 1440 × 1080 reference screenshots
  generated from the authenticated Django templates and repository CSS.
- Added provider-free command, state, minimized-output, overwrite-refusal,
  explanation-cleanliness, and tenant-scoped page coverage. No model, migration,
  scoring algorithm, prompt, toolkit dependency, or production topology changed.

### `CR-002 — Dependency-aware data lifecycle and storage control`

- Added one versioned retention policy per organization with 7-day temporary
  intake, 90-day completed job, 180-day uncommitted workflow, 365-day minimized
  metadata, and 30-day organization recovery defaults.
- Added organization-admin policy controls, legal hold, whole-group or object-ID
  exceptions, content-minimized dry-run counts, temporary private-byte estimate,
  and exact confirmation before applying cleanup.
- Added dependency-safe services that minimize expired pending intake payloads,
  remove completed job/task history, delete only non-current old match runs with
  no decisions/outreach, and delete only complete old outreach chains with no
  final approval/copy/export. Candidate expiry remains the existing separate
  staged individual-review workflow.
- Added minimized immutable lifecycle events with organization/object IDs,
  actor/system attribution, policy version, and time. They copy no candidate,
  CV, prompt, decision-note, or outreach content.
- Added staged organization deletion: immediate access suspension, policy-based
  recovery deadline, a dedicated administrator recovery route, private-file
  removal verification, complete tenant dependency purge, and a content-free
  organization tombstone.
- Added dry-run-first scheduled commands for dependency cleanup and expired
  organization purge, then integrated both after candidate retention staging in
  the daily systemd retention service.

### `CR-003 — In-app client-company management`

- Added administrator-only **Organization settings → Client companies** pages
  for organization-scoped list, create, edit, deactivate, and reactivate actions.
- Generated stable per-organization slugs internally so normal administrators do
  not manage routing identifiers; client companies remain optional hiring-
  customer references and create no tenant, candidate ownership, membership, or
  login account.
- Added vacancy detail editing for title and optional client assignment without
  rewriting the original description or any immutable requirements source
  snapshot.
- Limited new vacancy assignments to active same-organization clients at both
  form and transactional service boundaries. A vacancy may retain only its exact
  current inactive client, preserving historical relationships after
  deactivation.
- Added a same-origin administrator shortcut from vacancy create/edit forms that
  safely returns with the newly created active client selected. Recruiters can
  use existing active clients but cannot administer them.
- Preserved direct-employer vacancies and existing deletion semantics. No model,
  AI/toolkit, matching, decision, outreach, or migration change was required.

### `CR-001 — Managed multi-organization SaaS`

- Added explicit `User.is_platform_owner` capability independent of Django staff,
  superuser, and organization membership state.
- Added a separate platform organization list/detail workflow that atomically
  creates an organization and first administrator, adds or links further
  administrators, and never renders tenant recruitment content.
- Allowed platform owners to use the existing staged suspension/recovery lifecycle
  without making them organization members or bypassing candidate authorization.
- Added organization-administrator **Team members** screens to create/link,
  deactivate, and reactivate recruiter memberships only. The shared user account
  and any other organization memberships remain unchanged.
- Required a temporary password only for new managed accounts. Adding an existing
  username preserves its password and global active state.
- Added a normal authenticated password-change page so a managed user can replace
  the temporary password without technical administration.
- Added explicit workspace switching for users with several active memberships,
  plus last-active-administrator protection.
- Added immutable content-free tenant-management events containing only numeric
  organization/user snapshots, controlled role/action, actor, schema version,
  and timestamp.
- Added `accounts.0002_user_is_platform_owner` and
  `audit.0005_tenantmanagementevent`. No candidate, vacancy, matching, outreach,
  operations, or AI/toolkit schema changed.

## Verification

`PROD-005` verification completed on 2026-08-15:

- Focused environment, health, deployment-command, artifact, and foundation set:
  `42 passed`.
- Complete `python scripts/check.py` quality gate: `441 passed`.
- Django system and deploy checks passed with no issues.
- Production static collection completed successfully.
- `PROD-005` adds no migration. All existing migrations applied successfully
  from an empty database, the resulting plan is empty, and drift is zero.
- Ruff lint passed and all `172` files were formatted.
- Dependency check confirmed all `35` installed packages are compatible.
- A clean extraction of the restricted final ZIP installed from the lockfile,
  applied all migrations from an empty database, reported an empty follow-up
  plan, copied the development `.env.example` to `.env`, and passed the same
  complete `441`-test quality gate.

`INTAKE-001` verification completed on 2026-08-17:

- Focused bulk-intake, candidate-intake, private-document, background-job, and
  synthetic-fixture set: `77 passed`.
- Complete `python scripts/check.py` quality gate: `451 passed`.
- Django system and warning-strict deployment checks passed; production static
  collection passed; migration drift is zero; Ruff lint passed and all `176`
  files are formatted; all `35` installed packages are compatible.
- `INTAKE-001` adds
  `candidates.0006_candidateintakebatch_candidateintakeitem_and_more`. It
  applies successfully after the existing migrations; the follow-up migration
  plan is empty and model-to-migration drift is zero. No `operations`, AI,
  toolkit, or other app migration was added.

`EVAL-001` verification completed on 2026-08-17:

- Focused evaluation-dataset, deterministic-shortlist, staleness,
  candidate-profile, and private-document set: `95 passed`.
- Complete `python scripts/check.py` quality gate: `455 passed`.
- Django system and warning-strict deployment checks passed; production static
  collection passed; migration drift is zero; Ruff lint passed and all `184`
  files are formatted; all `35` installed packages are compatible.
- EVAL-001 adds no migration. All existing candidate and matching migrations are
  applied, the follow-up migration plan is empty, and model-to-migration drift is
  zero.

`EVAL-002` verification completed on 2026-08-17:

- Focused evaluation-measurement, dataset, deterministic-shortlist, staleness,
  and AI-assessment set: `60 passed`.
- Complete `python scripts/check.py` quality gate: `461 passed`.
- Django system and warning-strict deployment checks passed; production static
  collection passed; migration drift is zero; Ruff lint passed and all `187`
  files are formatted; all `35` installed packages are compatible.
- EVAL-002 adds no migration. Every existing migration is applied, the follow-up
  migration plan is empty, and model-to-migration drift is zero.

`EVAL-003` verification completed on 2026-08-18:

- Focused explanation-review, ranking-measurement, dataset, deterministic-
  shortlist, staleness, and AI-assessment set: `65 passed`.
- Complete `python scripts/check.py` quality gate: `466 passed`.
- Django system and warning-strict deployment checks passed; production static
  collection passed; migration drift is zero; Ruff lint passed and all `191`
  files are formatted; installed dependency compatibility passed.
- EVAL-003 adds no migration. Every existing migration applies successfully from
  an empty database, the follow-up migration plan is empty, and model-to-
  migration drift is zero.

`DEMO-001` verification completed on 2026-08-20:

- Focused demo, dataset, explanation-review, recruiter-review, and outreach-
  workflow set: `30 passed`.
- Complete `python scripts/check.py` quality gate: `470 passed`.
- Django system and warning-strict deployment checks passed; production static
  collection passed; migration drift is zero; Ruff lint passed and all `195`
  files are formatted; installed dependency compatibility passed.
- DEMO-001 adds no migration. Every existing migration applies successfully,
  the follow-up migration plan is empty, and model-to-migration drift is zero.

`DEF-001` verification completed on 2026-08-24:

- Focused canonical-skill, matching-model, hard-filter, shortlist, staleness,
  vacancy-extraction, profile-extraction, and evaluation-dataset set: `138 passed`.
- Complete `python scripts/check.py` quality gate: `481 passed`.
- Django system and warning-strict deployment checks passed; production static
  collection passed; migration drift is zero; Ruff lint passed and all `199`
  files are formatted; installed dependency compatibility passed.
- DEF-001 adds no migration. Every existing migration is applied, the follow-up
  migration plan is empty, and model-to-migration drift is zero.

`CR-004` verification completed on 2026-08-24:

- Focused unified-intake, bulk-intake, manual/CSV intake, private-document,
  profile-extraction, background-job, filtering, shortlist, staleness, review,
  decision, outreach, and retention set: `190 passed`.
- Complete `python scripts/check.py` quality gate: `488 passed`.
- Django system and warning-strict deployment checks passed; production static
  collection passed; migration drift is zero; Ruff lint passed and all `203`
  files are formatted; installed dependency compatibility passed.
- CR-004 adds `candidates.0007_intake_accepted_document`. It applied successfully
  after every existing migration, the follow-up migration plan is empty, and
  model-to-migration drift is zero. No AI, toolkit, operations, matching, or
  outreach migration was added.
- The exact restricted final ZIP was extracted into an empty directory, installed
  from `uv.lock`, migrated from an empty database through `candidates.0007`,
  reported an empty follow-up plan and zero drift, and passed the same complete
  `488`-test quality gate.

`CR-005` verification completed on 2026-08-25:

- Focused privacy/source forms, manual/CSV intake, reviewed bulk intake,
  CV-first confirmation, outreach approval, and retention set: `64 passed`.
- Complete `python scripts/check.py` quality gate: `495 passed`.
- Django system and warning-strict deployment checks passed; production static
  collection passed; migration drift is zero; Ruff lint passed and all `205`
  files are formatted; all `35` clean-environment packages are compatible.
- CR-005 adds no migration. The current migration plan is empty and model-to-
  migration drift is zero. Stable stored source values are translated only at
  recruiter-facing form, display, and outreach-policy boundaries.
- The restricted ZIP was extracted into an empty directory, installed from
  `uv.lock`, migrated from an empty database through `candidates.0007`, reported
  an empty follow-up plan and zero drift, and passed the same complete
  `495`-test quality gate.

`CR-002` verification completed on 2026-08-25:

- Focused lifecycle, audit/retention, organization access/dashboard, background
  job, shortlist, and outreach regression set: `72 passed`.
- Complete `python scripts/check.py` quality gate: `503 passed`.
- Django system and warning-strict deployment checks passed; production static
  collection passed; migration drift is zero; Ruff lint passed and all `212`
  files are formatted; installed dependency compatibility passed.
- CR-002 adds
  `organizations.0003_organizationretentionpolicy_retentionexception_and_more`
  and `audit.0004_organizationtombstone_datalifecycleevent`. Both apply after
  every existing migration; the follow-up plan is empty and model-to-migration
  drift is zero.

`CR-003` verification completed on 2026-08-25:

- Focused client-company management, organization access/dashboard, vacancy
  model/intake, and shortlist-staleness regression set: `95 passed`.
- Complete `python scripts/check.py` quality gate: `517 passed`.
- Django system and warning-strict deployment checks passed; production static
  collection passed; migration drift is zero; Ruff lint passed and all `214`
  files are formatted; installed dependency compatibility passed.
- CR-003 adds no migration. The current migration plan is empty and model-to-
  migration drift is zero.
- The restricted ZIP installed from `uv.lock` in an empty extraction, applied
  every existing migration from an empty database, reported an empty follow-up
  plan and zero drift, and passed the same complete `517`-test quality gate.

`CR-001` verification completed on 2026-08-27:

- Focused managed-SaaS, identity, organization-permission/dashboard, client,
  lifecycle, intake, vacancy, and audit regression set: `140 passed`.
- Complete `python scripts/check.py` quality gate: `534 passed`.
- Django system and warning-strict deployment checks passed; production static
  collection passed; migration drift is zero; Ruff lint passed and all `218`
  files are formatted; installed dependency compatibility passed.
- Adds `accounts.0002_user_is_platform_owner` and
  `audit.0005_tenantmanagementevent`; both are additive and retain the previous
  tenant foreign-key boundaries. Both apply successfully, and the follow-up
  migration plan is empty.

`MT-041-S01` verification completed on 2026-08-30:

- Focused authenticated-cache, logout, health, private-document, and outreach
  response set: `66 passed`.
- Complete `python scripts/check.py` quality gate: `545 passed`.
- Django system and warning-strict deployment checks passed; production static
  collection passed; migration drift is zero; Ruff lint passed and all `224`
  files are formatted; installed dependency compatibility passed.
- The correction adds no model or migration. Automated response tests confirm
  authenticated HTML is private/no-store and anonymous or non-HTML caching is
  unchanged. Cross-browser history restoration remains a manual retest.

`MT-025-F01` verification completed on 2026-09-01:

- The environment examples now configure the official `gpt-5.4-mini` API rates
  verified on 2026-09-01: `$0.75` input and `$4.50` output per one million
  tokens. Both values map into the published toolkit's Django configuration.
- The application forwards calculated cost metadata only when both explicit
  rates are configured. Missing rates are unavailable instead of inheriting the
  toolkit v1.0.0 placeholder zero-price table; historical events are unchanged.
- Focused configuration, gateway, ledger, usage-report, environment, and
  deployment coverage: `86 passed`.
- Complete `python scripts/check.py` quality gate: `547 passed`; Django system
  and deployment checks, static collection, zero migration drift, Ruff over
  `224` files, and dependency compatibility all passed.
- This correction adds no model or migration.

`MT-025-U01`, `MT-025-V01`, and `MT-025-C01` were implemented on 2026-09-01:

- The administrator report now prioritizes four primary metrics and one compact
  operational strip; model, failure, and metadata coverage remain collapsed
  under technical details by default.
- Tokens, sub-cent/zero costs, and latency have readable display formats while
  stored and aggregated values remain unchanged.
- Failure categories use administrator-facing wording and continue to exclude
  provider messages and private application-validation detail.
- Focused usage/ledger/retention coverage: `19 passed`. Complete quality gate:
  `548 passed`; system/deployment checks, static collection, zero migration
  drift, Ruff, formatting, and dependency compatibility passed.
- Browser layout retesting remains pending. No model or migration was added.

`MT-026-U01` and `MT-026-V01` were implemented on 2026-09-02. The privacy and
retention dashboard now leads with one organization-scoped **Needs attention**
list, links missing-date records to their candidate detail, reduces four totals
to a compact status strip, and omits empty due-date panels. Browser retesting
remains pending. Focused privacy/AI-report coverage passed `11` tests; the full
quality gate passed `548` tests and all checks. No model or migration was added.

`MT-026-U02` and `MT-026-C01` were implemented on 2026-09-02. Six workflow
history cards are replaced by one newest-first, type-filtered, 25-row paginated
activity table. Activity names and results use plain language; internal IDs are
secondary references, and private workflow content remains excluded. Browser
retesting remains pending. Focused audit coverage passed `6` tests; the complete
quality gate passed `549` tests and all checks. No model or migration was added.

The follow-up activity-filter styling correction gives the three controlled
filters a dedicated responsive row instead of squeezing them beside the section
description. The stale navigation regression expectation was also corrected:
AI usage and privacy/audit remain organization-administrator-only in navigation,
views, and reporting services; recruiters receive `403`. Focused report,
dashboard, and permission coverage passed `35` tests; all `549` project tests,
Ruff, formatting, and migration checks passed.

`MT-027-U01` was implemented on 2026-09-02. Retention exceptions use one
organization-scoped **What should be protected?** selector with whole-group and
eligible record choices instead of separate scope and raw object-ID fields.
Forged, mistyped, cross-scope, and cross-tenant targets fail form validation;
the persisted model and cleanup matching semantics are unchanged. Focused
lifecycle coverage passed `9` tests; all `550` project tests, lint, formatting,
and migration checks passed.

The page-level `MT-027-V01`, `MT-027-U02`, `MT-027-U03`, `MT-027-C01`, and
`MT-027-U04` correction was completed with `MT-027-U01`: retention policy and
exception controls use explicit responsive field components; an empty plan is
one compact safe state; purge controls appear only for a non-empty eligible
plan; operational labels are plain; and navigation returns to Privacy & audit.

The screen-level `MT-028` correction was completed on 2026-09-03. Organization
suspension now names the tenant and slug, requires `SUSPEND <ORGANIZATION NAME>`,
shows immediate access loss, recovery duration, and projected deadline, and
explains active legal-hold/organization-exception effects. The actual deadline
continues to be recalculated inside the transactional suspension service. A
responsive danger card replaces the generic unstyled form.

## Not implemented

Outreach generation, immutable recruiter editing, exact final approval, manual
copy, and plain-text export are implemented. Automatic sending, recipient
selection, email/ATS/platform integrations, and permission-management UI are not
implemented; source/privacy assertions are inspectable and correctable in the
tenant workspace.
Sending remains outside the MVP.
Recruiters can intentionally run structured vacancy extraction for an editable
requirements draft and candidate-profile extraction for a lawfully stored,
successfully parsed CV. Both create human-reviewable drafts; only explicit
candidate-profile confirmation publishes grounded matching facts. Candidate
records can also be manually created, imported, and given
validated PDF/DOCX CVs through the organization workspace. Recruiters can create
vacancies, manually structure and confirm their requirements, and preserve
corrections as immutable numbered history. Scanned-image CVs are not supported.
Stored document bytes are available only through the integrity-checked,
authenticated private attachment route completed in `PROD-001`. Recruiters
can manage vacancy status through the normal organization workspace after a
requirements version is confirmed. Recruiters can also delete vacancies and
use staged candidate deletion, administrative purge/cancellation, retention
review, and minimized tenant-scoped audit views completed in `PROD-002`.
Recruiters can inspect deterministic rule outcomes for active
candidates using the current confirmed requirements, then generate a persistent
version-labelled shortlist of up to 20 eligible candidates. Relevant candidate
or confirmed-requirements changes clearly mark earlier runs stale while retaining
their immutable historical scores and explanations.
For each candidate on a current shortlist with a confirmed profile, recruiters
can request and inspect immutable evidence-based AI assessment versions. These
are decision support only and cannot change the deterministic shortlist.
Safe AI usage events are available to operators through read-only Django admin,
as compact content-free summaries on the privacy dashboard, and as aggregate
tenant-scoped token/cost/latency/retry/failure reporting under **AI usage**.
The review queue now reuses confirmed profiles and provides compact exception-
focused assessment review and individual decision history. Resumable batch
profile extraction and whole-shortlist assessment generation are implemented in
`PROD-003`. No profile is silently confirmed, and final employment decisions
remain individual recruiter actions with notes, actor, and timestamp.

Recruiters can manage typed hard-constraint records from the normal requirements
editor while the version is a draft. The older free-text hard-constraint field is
clearly labelled as non-executable notes. Confirmed versions remain immutable;
rule corrections require a copied draft version.

## Next task

`DEMO-002 — Prepare a client-facing README and Upwork Project Catalog
positioning` is the next release-roadmap task after the completed pre-release
functionality pass through `CR-001`.

The MT-029 platform organization list now surfaces active tenants without an
administrator, distinguishes active from total memberships, and supports
search, health/status filtering, and 25-row pagination. A compact summary makes
tenant exceptions visible without opening each organization. Browser testing
passed on 2026-09-03.

MT-030 administrator access changes now use a dedicated identity-and-impact
confirmation page. It displays the tenant, account email, remaining active
administrator count, and separate platform-owner membership semantics. The last
active administrator is blocked before submission and by the service boundary.
Browser retesting remains pending; no migration was added.

MT-030 browser testing passed on 2026-09-03. MT-031 now separates existing- and
new-administrator workflows. Existing accounts require exact lookup and visible
identity confirmation before access is granted; new-account fields are isolated
with correct autocomplete attributes and cannot silently reuse an existing
username. Expiring invitation/password setup remains a separate open security
task. No migration was added.

The interim temporary-credential safeguard is implemented. Every newly created
managed account is marked **must change password** and is blocked from
application pages until a successful private password change. Existing linked
accounts are unaffected. Migration `accounts.0003_user_must_change_password`
adds the state; expiring email invitations remain future work.

MT-032 organization provisioning now separates numbered organization and first-
administrator sections, reuses explicit existing/new account modes, previews an
editable stable workspace URL, and rejects duplicate slugs before any account or
tenant is created. Success guidance identifies the administrator's next safe
steps. Browser testing passed on 2026-09-03; no additional migration was added.

MT-033 now uses organization-neutral **Hiring clients** language and presents
team, hiring-client, and retention cards in one balanced desktop row that stacks
responsively. The broader organization timezone/locale profile remains a
separate proposed feature.

MT-034 recruiter access changes now use a tenant-scoped identity confirmation
page for both removal and restoration. Team rows and confirmation details show
email when available, label membership state as **Organization access**, and use
**Access removed** rather than implying a disabled global account. Cross-tenant
membership IDs remain hidden by 404. Browser retesting remains pending.

MT-034 browser testing passed on 2026-09-03. MT-035 now reuses the explicit
existing/new managed-account pattern for recruiters. Exact existing-account
lookup shows identity before the grant, while new accounts use isolated fields,
reject existing usernames, and remain subject to the mandatory first password
change. Expiring email invitations remain future work.
