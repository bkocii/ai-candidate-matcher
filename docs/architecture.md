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

`ai_gateway` is a plain application boundary rather than a model-owning Django
app. Business services depend on its `AIGateway` protocol and application-owned
`AIGatewayResult`; they do not import toolkit clients, results, or exceptions.
The initial protocol exposes one validated structured-request primitive. The
vacancy, candidate, assessment, and outreach services added in later roadmap
tasks will own their domain schemas and prompts and receive this gateway through
an explicit dependency or the configured gateway factory.

`ToolkitAIGateway` uses only the published v1.0.0 Django integration to construct
`AIClient`, then calls its structured `ask()` method. Construction is lazy: a
missing API key cannot break startup, checks, migrations, deterministic matching,
or ordinary tests. One gateway instance reuses one client, while the application
factory does not keep global mutable state and can be replaced by a test factory.

The gateway result contains only validated Pydantic data plus request ID, model,
duration, retries, token counts, and estimated cost when the toolkit supplies
them. Raw and original model responses are not exposed. Toolkit configuration,
provider, parse, and schema failures become bounded application error classes;
underlying messages and exception chains are suppressed from normal application
error handling. `AIUsageEvent` persists the safe result metadata or a bounded
failure category without expanding the gateway contract.

Toolkit file logging is disabled in application settings. The application does
not log prompts, CV text, contact data, raw responses, or translated exception
details.

`FakeAIGateway` is the reusable provider-free business-service test double. It
implements the same runtime-checkable application protocol, shares prompt/type
input validation with `ToolkitAIGateway`, captures normalized calls, returns a
configured static or dynamic Pydantic response plus deterministic safe metadata,
or raises a configured bounded error. A mismatched fake response is a test
programming error rather than a simulated provider result.

### audit

Safe AI usage events and, in later production tasks, operational events and
privacy-relevant access. Audit storage contains no prompts, raw model responses,
source descriptions, CV text, candidate identity/contact data, provider exception
messages, or user-visible validation messages.

`AIUsageEvent` belongs directly to an organization and optionally retains the
actor. It uses controlled workflow/object-type values plus numeric target/result
IDs instead of domain foreign keys, allowing non-identifying operational history
to survive actor or candidate deletion without retaining copied candidate data.
Organization deletion is protected while usage history exists; actor deletion
sets the attribution to null.

An authorized business service creates a pending event only after its local
preconditions pass and immediately before configured gateway construction. A
successful event is finalized in the same transaction as the requirements
update, profile draft, or assessment and stores request ID, model, duration,
retries, optional token counts/cost, schema version, and completion time. Gateway
failures store only one allow-listed code and stage. When a response completes but
application evidence/concurrency validation rejects it, the event may retain the
safe response metadata with a generic application-validation code. Provider
failures expose no result metadata through toolkit v1.0.0, so those fields remain
blank rather than being inferred.

Completed usage events are immutable and database constraints keep status,
completion, result, and failure fields consistent. An unexpected process or
programming interruption may leave a pending event for later operational
diagnosis; the application does not hide unrelated programming exceptions.
Django admin exposes the ledger read-only. Recruiter-facing aggregation, cost/
latency reporting, retention policy, and operational recovery remain `PROD-002`
through `PROD-004`.

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
- `OutreachDraftApproval`
- `OutreachDraftAction`
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
  use an opaque UUID. No public media URL exists.
- PDF and DOCX CV uploads are validated and synchronously extracted before their
  metadata is committed. The service enforces a 10 MB file limit plus bounded
  page, archive-entry, expanded-byte, compression-ratio, and extracted-text limits.
- Successful extraction stores normalized content type, size, SHA-256, text,
  status, timestamp, retention date, and uploader. Failed validation or extraction
  stores neither a document row nor file bytes and returns a bounded public error.
- SHA-256 duplicate checks are organization-local and advisory. The same bytes in
  another organization neither disclose nor block that organization's upload.
  The final same-organization check and save are serialized with database row
  locks so concurrent uploads do not create an avoidable duplicate race.
- Recruiter HTML shows safe document metadata only and exposes neither storage
  paths nor extracted CV text. An authenticated tenant-scoped route downloads
  the original as an attachment only after the application repeats service-layer
  authorization and verifies its stored length and SHA-256. Responses are
  private/no-store, use the validated content type and safe original basename,
  and include browser hardening headers; failures never reveal the storage key.
- Upload validation rejects Unicode control/format filename spoofing, executable
  or embedded PDF features, duplicate or symlink DOCX entries, embedded active
  Word content, and unsafe external package relationships while retaining normal
  PDF and DOCX hyperlinks. Existing size, page, expansion, compression, XML,
  encryption, signature, and extracted-text limits remain enforced.
- Organization-row and candidate-row locks serialize the final same-organization
  hash check and save, closing the duplicate-upload race while keeping equal
  document bytes isolated and permitted across organizations.
- Textless/scanned PDFs are rejected rather than silently stored as usable CV
  text. OCR is a separately approved future capability.
- Retention/deletion services must remove underlying stored bytes; deleting a
  Django database row alone does not guarantee storage deletion.
- Recruiter-confirmed candidate deletion removes candidate contact fields,
  provenance rows, document database rows, stored document bytes, and extracted
  text. Document deletion cascades its candidate-profile versions and any
  AI-published skill evidence. It retains only the candidate primary key,
  organization ownership,
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

### Candidate profile extraction and confirmation

- `CandidateProfile` is a numbered, organization-scoped snapshot tied to one
  successfully extracted CV and its SHA-256/text SHA-256 source identity. It
  records bounded structured employment, skill, location, work-mode, language,
  education, certification, employment-type, and availability facts; exact
  source evidence; explicit ambiguities; and whether sensitive prefixed content
  was removed before the request.
- Extraction is a recruiter-triggered POST action. The service repeats tenant,
  candidate, document, lifecycle, document-type, extraction-status, and source-
  size checks. It redacts the candidate name, email addresses, phone numbers,
  URLs, contact-labelled lines, and protected/sensitive prefixed lines before
  constructing an untrusted-document prompt.
- The application-owned schema forbids extra fields, bounds all values, requires
  evidence for every returned fact, and requires either grounded facts or an
  explicit ambiguity. A second application check normalizes whitespace and
  verifies that every evidence excerpt occurs in the redacted source.
- The prompt requires a whole-source skill scan, including profile summaries and
  employment narrative rather than only headings named Skills or Technologies.
  It requests every distinctly and explicitly named job-relevant technology,
  tool, method, or competency using source-supported wording. Related explicit
  facts remain separate, while synonyms, umbrella skills, and tool-to-method
  implications are not inferred.
- If a schema-valid response fails only this application-owned grounding check,
  the service records that request as an application-validation failure and makes
  exactly one correction request against the same redacted source. The correction
  prompt contains privacy-safe field locations but not the failed output, requires
  a complete replacement with contiguous verbatim excerpts, and cannot relax the
  deterministic validator. The corrected request has its own safe usage event.
- A corrected response is saved only if every excerpt and fact-to-excerpt link
  passes. A second grounding failure names only bounded schema areas, makes no
  further request, and saves no profile or candidate skill.
- Successful extraction creates only a new draft version. It stores validated
  structured output but never stores prompts, raw provider responses, or contact
  values. Provider, schema, authorization, stale-source, deletion, and size
  failures create no profile and expose only bounded recruiter-facing errors.
- Confirmation is a separate POST action. A confirmed snapshot is immutable and
  becomes the candidate's current matching profile; a newer draft never replaces
  it, and an older draft cannot supersede a newer confirmed version.
- Confirmation publishes profile skills as inspectable `CandidateSkill` rows
  linked to both the source document and source profile. Recruiter/manual skill
  assertions are preserved; confirming a replacement profile removes only the
  earlier AI-published assertions from the same source document.
- Deterministic filtering consumes only confirmed profile facts and evidence.
  Explicit matching facts can pass a rule, while absent or non-matching profile
  facts remain unknown and eligible for recruiter review. A confirmed profile
  changes the candidate matching signature and makes affected historical runs
  stale; a draft profile does neither.

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
- Requirement list fields validate as lists of non-blank strings. Their original
  wording remains part of the immutable snapshot while matching-owned normalized
  skill links and typed constraint rules provide deterministic identities.
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
  snapshot remain application input. AI-assisted extraction uses only that
  preserved snapshot through the application gateway.
- A recruiter can trigger AI extraction only for an editable requirements draft.
  The business service repeats organization authorization and rejects confirmed
  versions, deleted vacancies, blank sources, and sources over 30,000 characters
  before constructing a gateway request.
- The application-owned `vacancy_requirements_extraction.v1` Pydantic schema
  forbids extra output, bounds every field, accepts only controlled work-mode and
  employment-type values, and rejects duplicate or cross-group skill entries.
  Missing facts stay empty, null, or `unknown`; they are not inferred.
- The source text is explicitly treated as untrusted data in the prompt. Output
  instructions exclude protected and sensitive criteria and produce only a
  generic recruiter/legal-review ambiguity when such source content is detected.
- A successful response updates the same requirements draft, marks its creation
  method AI-assisted, resynchronizes normalized skills, and remains subject to
  ordinary recruiter editing and explicit confirmation. It does not alter the
  preserved source snapshot or create a confirmed matching input.
- AI-suggested hard constraints are stored only in the existing non-executable
  notes list. A recruiter must deliberately create typed rules through the normal
  editor before deterministic filtering can use them.
- The service snapshots the draft and typed-rule state before the request and
  rechecks it under a database lock before applying the response. A concurrent
  edit therefore prevents stale AI output from overwriting newer recruiter work.
- Safe request metadata and bounded failure categories are persisted separately
  as `AIUsageEvent` records. Ordinary tests substitute a fake gateway and make no
  provider request.

Structured AI outputs are stored with a schema version and the relevant source
versions so their evidence boundary remains inspectable when inputs later change.

### Deterministic matching definitions

- `matching.Skill` is an organization-owned canonical identity. Its key uses
  Unicode NFKC, collapsed whitespace, and case folding while preserving
  punctuation. This removes formatting duplicates without claiming that
  organization-specific synonyms such as `Postgres` and `PostgreSQL` are equal.
- `RequirementSkill` links a skill to one vacancy-requirements version as either
  must-have or nice-to-have, retaining the recruiter/source label and list order.
  The same canonical skill cannot appear twice in one version; must-have wins if
  duplicate raw values occur across both legacy list fields.
- Saving through the recruiter requirements service synchronizes normalized
  skill links. Confirmation rechecks them, and the initial matching migration
  backfills existing versions without changing original recruiter input.
- `CandidateSkill` records a candidate skill assertion with its source label,
  optional years, evidence, and optional source document. Evidence remains
  inspectable application data and is removed when the candidate is deleted.
- `HardConstraintRule` belongs to exactly one requirements snapshot. Supported
  types are required skill, minimum years of experience, location, work mode,
  language, education, certification, and employment type. Each type has one
  explicit operator and one validated payload shape; arbitrary free-text notes
  are not silently promoted into executable rules.
- A required-skill rule must reference a normalized must-have skill in the same
  requirements version. Work-mode and employment-type rules use the existing
  controlled vocabularies. Numeric thresholds cannot be negative.
- Missing candidate information has one enforced result: keep the candidate for
  recruiter review as unknown. No rule type represents a protected or sensitive
  personal characteristic, and rules do not make hiring decisions.
- All matching-definition querysets support explicit organization scoping and
  active-membership visibility. Creation services repeat authorization checks,
  and cross-organization candidate, document, skill, and requirement links fail
  model validation.
- Normalized links and typed rules are editable only while their requirements
  version is a draft. They become immutable with confirmation and are copied,
  rather than changed, when a recruiter creates a correction version.
- The normal draft requirements screen lists typed rules and links to guided add
  and edit forms plus a separate delete-confirmation screen. Rule type determines
  the operator and payload shape; the UI never exposes configurable operators or
  an alternative missing-fact outcome. Required-skill choices come only from the
  draft's saved normalized must-have skills.
- Draft saves resynchronize normalized skills and then revalidate every typed
  rule in the same transaction. Confirmation repeats that validation, so removing
  a skill referenced by an executable rule cannot create a silently inconsistent
  confirmed snapshot. Confirmed rules are visible on the vacancy detail page but
  have no mutation actions.
- Deterministic evaluation uses only the current confirmed requirements version
  and active candidates owned by the same authorized organization. Draft,
  deleted-vacancy, inactive-candidate, and cross-organization inputs are rejected.
- Every typed rule produces an inspectable result containing its recruiter source
  wording, expected value, observed candidate fact, available evidence,
  explanation, and `pass`, `fail`, or `unknown` outcome. Any failure makes the
  candidate ineligible at this stage; no failures plus an unknown keeps the
  candidate for review; all passes produce a passed result.
- A recorded normalized candidate skill proves a required-skill pass. Absence of
  a skill assertion stays unknown. Recorded skill-years can prove that a minimum
  duration is met, but lower partial evidence cannot prove total experience is
  insufficient. An explicit candidate location is compared using the rule's
  conservative normalized equality and can pass or fail.
- Work mode, language, education, certification, and employment type remain
  unknown until a structured candidate profile supplies those facts. Evaluation
  never keyword-searches raw CV text or infers facts from missing records.
- Recruiters open a vacancy's **Evaluate candidates** page to inspect summary
  counts and per-candidate rule tables. Results are computed on request for the
  identified confirmed version and are not a ranking or hiring decision.
- A shortlist generation request repeats tenant authorization and accepts only
  the vacancy's current confirmed requirements. It runs the hard-filter stage
  first and excludes every candidate with an explicit failure. Passed and
  needs-review candidates remain eligible for scoring.
- Relevance scoring uses only normalized requirement-skill links and recorded
  candidate-skill assertions. Algorithm v2 gives each must-have skill two weight
  units and each nice-to-have skill one, then uses deterministic largest-remainder
  apportionment to distribute exactly 100.00 points. Cent-level rounding is
  stable by requirement order. Missing skill evidence earns zero points but is
  never converted into a hard-filter failure.
- Ranking sorts by score descending, uses passed-before-review only as an equal-
  score tie-break, and finally uses the stable candidate record ID. Candidate
  names, contact data, raw CV text, and protected characteristics do not affect
  the order.
- `MatchRun` persists the confirmed requirements version, scoring algorithm
  version, recruiter actor, generation time, fixed limit of 20, and evaluated and
  eligible counts. Each `ShortlistEntry` persists rank, score, hard-filter
  outcome, group match counts, and a JSON score breakdown containing only the
  relevant skill wording, evidence, match state, and points.
- Candidate deletion removes that candidate's shortlist entries and their
  evidence snapshots. The non-identifying run-level version, algorithm, limit,
  and aggregate counts remain, including the number originally shortlisted.
- Recruiters generate a run through a POST-only action and can inspect the latest
  or earlier version-labelled report. Generating again creates history rather
  than overwriting a previous run. Explicit failures never enter the shortlist,
  regardless of their possible skill score.
- Every generated run stores a versioned SHA-256 signature of its immutable
  requirements inputs and another signature of the active candidate pool facts
  used by filtering, scoring, and evidence display. The signatures retain no raw
  candidate payload and cannot be used as replacement profile data.
- Staleness is evaluated against current authorized inputs when a run is viewed.
  A newer confirmed requirements version, a matching-definition change, an active
  candidate addition/removal, or a change to candidate location, skill,
  experience, evidence, or evidence-document reference marks the historical run
  stale. Contact, source, retention, and other facts unused by deterministic
  matching do not create false invalidation.
- Runs created before versioned input signatures are explicitly stale rather
  than assumed current. Stale history remains inspectable and is never silently
  recomputed; recruiter-triggered regeneration creates a separate current run.
  AI assessment and recruiter decisions remain later, separate stages.
- A run whose scoring algorithm version differs from the current application
  policy is also stale. Its saved ranking and breakdown remain immutable, while
  regeneration creates a new run under the current algorithm.

### Evidence-based AI match assessment

- `MatchAssessment` is an immutable numbered snapshot for one `ShortlistEntry`.
  It also references the exact confirmed `VacancyRequirements` and confirmed
  `CandidateProfile` used, stores schema version `match_assessment.v1`, and is
  removed with the candidate's shortlist entry/profile when candidate data is
  deleted.
- Assessment is an explicit POST-only action for one shortlisted candidate. The
  service repeats tenant authorization and accepts only an active candidate, the
  vacancy's current confirmed requirements, the candidate's current confirmed
  profile, and a non-stale deterministic match run. This one-request-per-entry
  boundary isolates failures and allows a recruiter to continue with other
  candidates without requiring synchronous batch orchestration.
- The request context is capped at 80,000 serialized characters and contains
  source/schema versions, confirmed requirement wording and evidence, confirmed
  candidate facts with exact evidence, and the saved deterministic score/filter
  outcome. It excludes candidate identity/contact data, raw CV text, vacancy
  identity, and protected or sensitive characteristics.
- Every requirement and candidate evidence item receives an application-owned
  opaque ID. The structured response must assess each requirement exactly once as
  `match`, `gap`, or `uncertain`; matches and gaps must cite supplied candidate
  evidence, while missing support must be uncertain. The application rejects
  unknown IDs or incomplete coverage and resolves accepted IDs back to its own
  stored wording, preventing the provider from rewriting source evidence.
- The AI score is a separate 0–100 decision-support value. The application, not
  the provider, derives red below 50, amber from 50 through 74, and green from 75.
  Neither the score nor the band changes hard-filter eligibility, deterministic
  score, rank, or shortlist membership.
- Summaries, explanations, and review focus are bounded and rejected if they
  recommend hiring, rejecting, approving, contacting, or outreach. The result
  can identify what a recruiter should verify; it cannot record a decision.
- After the provider returns, the service locks and rechecks the entry, active
  candidate, current profile, and run freshness. A concurrent profile
  confirmation or matching-input change discards the output without persistence.
- The shortlist displays all immutable assessment versions with evidence-linked
  matches, gaps, uncertainties, and recruiter review focus. A dedicated review
  detail route exposes the same application-owned evidence plus assessment
  version history without changing the snapshot.
- Validated assessment output is persisted separately from its safe
  `AIUsageEvent`. Background/idempotent bulk processing remains `PROD-003`.

### Recruiter assessment review

- The review queue is a derived view over existing immutable assessments; it
  creates no review decision or duplicate assessment state. It selects only the
  latest assessment version for each surviving shortlist entry while keeping
  older versions reachable from the assessment detail screen.
- The queue repeats tenant authorization, excludes soft-deleted vacancies from
  the normal workspace, and resolves assessments only through organization-
  scoped querysets. Cross-organization queue and detail URLs return `404`.
- Changed shortlist inputs or a superseded confirmed profile are shown first,
  followed by evidence-backed gaps, uncertainties, confirmed-profile
  ambiguities, and deterministic unknown-fact review flags. Routine assessments
  remain available through the explicit **All** scope instead of being deleted
  or silently treated as approved.
- Queue currentness is calculated from the existing privacy-preserving shortlist
  signatures and current confirmed profile relationship. No raw CV text,
  candidate contact details, prompt, raw provider response, or protected
  characteristic is introduced into the review surface.
- The detail screen shows the immutable AI score separately from the
  deterministic score, all vacancy and candidate evidence resolved by the
  application, profile ambiguities, changed-input warnings, recruiter review
  focus, and links to every assessment version for the same shortlist entry.
- `REV-001` records no approve, reject, revisit, or outreach action. Individual
  decisions are introduced separately by `REV-002`; background whole-shortlist
  assessment generation remains `PROD-003`.

### Human recruiter decisions

- `ReviewDecision` is an immutable numbered event for one `ShortlistEntry` and
  the exact `MatchAssessment` reviewed. It stores only approve, reject, or
  revisit, mandatory bounded recruiter notes, the recruiter actor, and timestamp.
- Decision creation repeats tenant authorization and is POST-only. It accepts
  only the latest assessment version for an active candidate while the confirmed
  profile and privacy-preserving shortlist input signatures remain current.
  Historical or stale assessments remain inspectable but cannot receive a new
  current decision.
- A recruiter may correct a decision only by appending another decision version;
  earlier choices, notes, actors, timestamps, and assessment links remain
  unchanged. The actor is protected from deletion while attributed history
  exists.
- The queue defaults to latest assessments with no decision for that exact
  assessment. It also exposes exception, changed-input, and all scopes, plus
  counts and badges for current approved, rejected, and revisit decisions. A
  decision on an older assessment is not silently applied to a newer version.
- Candidate deletion removes the candidate-specific shortlist, assessments, and
  review decisions together. Cross-organization queue, detail, and decision URLs
  return `404` without disclosing notes or actor identity.
- Decisions do not change deterministic eligibility, rank, score, assessment
  evidence, or traffic-light band. They create no outreach draft and perform no
  contact action; outreach remains a separately approved workflow.

### Approved outreach draft generation

- `OutreachDraft` is an immutable numbered generated snapshot for one
  `ShortlistEntry` and the exact `ReviewDecision` that authorized it. Every
  version records the generating human actor, timestamp, schema version, subject,
  and plain-text body. Candidate deletion removes its draft history with the
  candidate-specific shortlist and review history.
- Generation is a separate POST-only recruiter action. The service repeats
  tenant authorization and accepts only the exact latest decision when it is an
  explicit approval tied to the latest assessment while the active candidate,
  current confirmed profile, and privacy-preserving shortlist inputs remain
  current. Approval and currentness are locked and rechecked after the provider
  returns so a concurrent correction discards the output.
- The minimized structured request contains the organization name, vacancy title,
  and at most eight evidence-backed positive match facts. It excludes candidate
  name/contact data, raw CV text, recruiter decision notes, assessment summary,
  gaps, uncertainties, scores, protected characteristics, prompts, and raw model
  responses. The provider must use an application-owned candidate-name
  placeholder exactly once; the application substitutes the real name only after
  validating the bounded output.
- The output schema allows only a bounded subject and plain-text body, forbids
  extra fields, invented contact details/links, job-offer or hiring-decision
  language, and a missing or repeated name placeholder. Safe AI usage metadata is
  finalized transactionally with the draft; bounded failures create no partial
  draft.
- Recruiters can inspect generated version history and its exact source approval.
  `OUT-001` adds no editing, final draft approval, copy/export, email/platform
  integration, or sending. Those human-controlled actions remain `OUT-002`, and
  sending remains outside the MVP.

### Outreach editing, final approval, copy, and export

- Generated and recruiter-edited outreach content uses one immutable
  `OutreachDraft` version sequence per shortlist entry. Editing is a deliberate
  recruiter action that copies the latest current draft into a new version with
  its creation method, parent version, actor, and timestamp. It never mutates the
  source version or carries final approval forward.
- `OutreachDraftApproval` is an immutable one-to-one human approval of one exact
  draft version. It requires bounded notes, an explicit contact-permission
  attestation, the approving recruiter, and timestamp. Only the latest draft can
  be approved, and its source recruiter approval, latest assessment, confirmed
  profile, and shortlist inputs must still be current.
- Final approval additionally requires at least one candidate-source record with
  explicit permitted contact. A restricted or withdrawn contact record, or any
  withdrawn consent record, blocks approval. The same permission/currentness
  checks run again before every copy or export, so a later decision correction,
  new draft, changed evidence, or permission withdrawal disables manual use while
  preserving history.
- `OutreachDraftAction` records each approved-draft copy or plain-text export with
  the exact draft, action type, human actor, and timestamp. The copy endpoint
  revalidates and records the action before returning the exact text to the
  browser clipboard workflow. Export is POST-only, returns a private no-store
  UTF-8 `.txt` attachment with a non-identifying filename, and records the action
  before returning content.
- Copy/export never selects or stores a recipient and never opens or calls an
  email, ATS, or messaging provider. No send action or outbound integration
  exists. Candidate deletion removes draft, final-approval, and manual-action
  history with the candidate-specific shortlist; operator inspection remains
  read-only in Django admin.

## Matching pipeline

1. Normalize and validate vacancy requirements.
2. Apply organization-visible candidates only.
3. Apply explicit hard filters.
4. Build a deterministic relevance score and bounded shortlist.
5. Send only necessary job and candidate evidence for structured AI assessment.
6. Validate the AI response.
7. Store the validated assessment, schema version, and source versions; finalize
   the separate safe usage event in the same transaction.
8. Present results for recruiter review.

Embedding-based retrieval may be added after the deterministic baseline is measured. It is not required to prove the MVP.

## Privacy and security

- Authorization checks are organization-scoped at the query layer and view/service boundary.
- Candidate documents are private and never served by guessable public paths.
- Upload type, size, package structure, active content, and resource use are
  validated before persistence. Private delivery repeats authorization and
  verifies byte integrity before returning a non-cacheable attachment.
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
- Relevant vacancy or candidate matching-input changes invalidate deterministic
  shortlist freshness without overwriting historical results.
- AI calls use bounded retries.
- Per-candidate assessment requests isolate failures; durable resumable batch
  processing and idempotency are introduced in `PROD-003`.
- The deterministic shortlist remains inspectable if AI is unavailable.
- Confirmed profiles are reusable across vacancies. The eventual high-volume
  path uses exception-focused review plus background batch profile extraction and
  whole-shortlist assessment generation, while confirmation and final employment
  decisions remain explicit human actions.

## Testing strategy

- Unit tests for parsing normalization, hard filters, scoring bands, and permissions.
- Service tests use the shared fake AI gateway; ordinary tests never make live
  provider calls.
- Shared contract tests exercise both the fake and toolkit-backed adapters for
  normalized input validation and the application-owned result/metadata envelope.
- Integration tests for import-to-review workflows.
- Security tests for cross-organization access and private documents.
- A separate synthetic smoke test lives outside ordinary pytest `testpaths`,
  requires `RUN_LIVE_AI_SMOKE=1`, and may make one low-cost billable API request.
- An anonymized/synthetic benchmark set measures ranking stability and explanation quality.
- `scripts/check.py` is the single local and CI quality gate. It includes normal
  and warning-strict deployment checks, migration-drift detection, tests, lint,
  formatting, and dependency compatibility.
- GitHub Actions runs the locked environment and shared quality gate on every
  pull request and push to `main` across Python 3.11 through 3.14.
