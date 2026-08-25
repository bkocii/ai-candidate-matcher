# Pre-release Change Review

This file records product changes discussed after `DEMO-001`. Items remain
outside the roadmap until their status is **Approved for implementation**.

Status values: **Approved direction**, **Approved for implementation**,
**Proposed**, **Deferred**, and **Rejected**.

## CR-001 — Managed multi-organization SaaS

Status: **Approved direction — 2026-08-23**

For our app, the agreed middle ground is:

- Platform owners create organizations and their first administrator.
- Organization administrators create and manage their recruiters.
- Users belonging to multiple organizations can switch workspaces.
- Candidate data remains strictly separated by organization.
- Client companies remain internal customers within an organization.
- Django admin remains technical-only.
- There is no public signup or billing yet.

This is a managed multi-organization SaaS. The existing organization and
membership architecture already supports much of the isolation model; the
missing part is a safe in-application management interface.

Important boundaries:

- A platform owner manages organization lifecycle and administrators but does
  not automatically gain access to candidate content inside every organization.
- Organization administrators can manage only memberships in their own
  organization.
- Django superusers remain technical operator accounts, not customer accounts.
- Organization creation, membership changes, suspension, and deletion must be
  audited without copying private candidate content.

## CR-002 — Dependency-aware data lifecycle and storage control

Status: **Approved for implementation — 2026-08-23**

Problem: immutable profiles, shortlist runs, assessments, decisions, outreach
versions, usage events, background jobs, and private documents can accumulate.
Deleting rows individually could break evidence and approval history.

Recommended solution: add an organization-level retention policy and delete
complete dependency bundles only when they are no longer operationally or
legally required.

### Retention groups

1. **Temporary intake data**
   - Automatically remove abandoned pending intake files and extracted text
     after a short configurable period; suggested default: 7 days.
2. **Operational job history**
   - Remove completed background jobs/tasks after a configurable period;
     suggested default: 90 days. Keep only minimized aggregate counts if useful.
3. **Uncommitted workflow history**
   - Purge an obsolete shortlist bundle only when it is not current, is older
     than the policy limit, and has no recruiter decision or outreach record;
     suggested default: 180 days.
   - Purge a complete abandoned outreach version chain only when no version was
     finally approved, copied, or exported and the chain is older than the
     policy limit. Do not delete one parent version from the middle of a chain.
4. **Decision-bearing recruitment history**
   - Assessments, decisions, approved outreach, and action history remain linked
     and inspectable while their candidate/workspace retention period is active.
   - Candidate purge already removes private CVs, profiles, shortlist entries,
     assessments, decisions, and outreach through the dependency chain, while
     retaining only a minimized candidate tombstone and audit event.
5. **Usage and audit metadata**
   - Keep only the already minimized metadata for a configurable period;
     suggested default: 12 months unless contractual/legal needs require longer.
   - Never preserve prompts, responses, CV text, decision notes, or outreach
     bodies merely for reporting after their owning workflow is purged.
6. **Organization deletion**
   - Platform owner or organization administrator requests deletion; access is
     suspended immediately and a suggested 30-day recovery window begins.
   - A scheduled service then deletes the complete organization dependency tree
     and private files, retaining only a content-free organization tombstone.
   - Encrypted backups expire through their normal documented rotation; they are
     not treated as a live searchable archive.

### Safety and administration

- Current candidate/workflow records are never removed only because they are
  old; the applicable organization retention policy and dependency checks must
  authorize deletion.
- Legal hold or explicit retention exceptions block scheduled deletion.
- Organization administrators receive a retention dashboard with counts,
  estimated affected records, dry-run preview, exceptions, and explicit
  confirmation. It must not expose data from another organization.
- The scheduled cleanup process uses application services, transactions, and
  private-file verification; it does not require customer Django-superuser
  access.
- Every purge records a minimized audit event with organization/object IDs,
  actor or system marker, policy version, and timestamp.

### Suggested implementation order

1. Add read-only storage/retention counts and a dependency-aware dry-run report.
2. Add organization retention settings and administrator controls.
3. Add scheduled cleanup for temporary data, completed jobs, and safe obsolete
   workflow bundles.
4. Add staged whole-organization suspension, recovery, and purge.

## CR-003 — In-app client-company management

Status: **Approved for implementation — 2026-08-23**

- Client companies remain optional organization-owned records used by agencies
  to identify the hiring customer for a vacancy. They are not tenants, candidate
  owners, or login accounts.
- Organization creation does not require a client company; direct employers can
  leave the relationship empty.
- Organization administrators manage client companies under **Organization
  settings → Client companies**.
- Recruiters select an active client company while creating or editing a vacancy.
  The vacancy form provides administrators a convenient add-client shortcut.
- Deactivation prevents selection for new vacancies but preserves historical
  vacancy relationships.

## CR-004 — Unified candidate intake and batch profile confirmation

Status: **Complete — 2026-08-24**

Candidate creation should be CV-first and exception-focused. Manual entry and
CSV migration remain available, but recruiters should not repeatedly type data
that can be safely proposed from a CV or attach every CV in a separate later
step.

### Intake flows

- Make **Create candidates from CVs** the primary candidate-creation action.
- A single-CV upload proposes identity fields in an editable review screen and
  creates the candidate, source record, and CV together after confirmation.
- Multi-CV upload reuses shared source and compliance information, detects
  likely duplicates, and presents invalid, ambiguous, or conflicting records
  as exceptions.
- CSV intake can accept corresponding CV files in the same workflow. Matching
  must use an explicit `cv_filename` or stable external identifier. The system
  must never guess using a fuzzy name match; missing, duplicate, and conflicting
  mappings remain unresolved for recruiter review.
- Manual creation becomes a lightweight quick-add flow requiring only the
  minimum identity/contact information. A CV can be included in the same action
  or added later.
- Candidate provenance, lawful basis, consent, and contact permission remain
  recruiter-supplied or explicitly selected; AI must not infer them.

### Batch profile confirmation

- After evidence validation, recruiters may select **Confirm all eligible
  profiles** without opening every clean profile individually.
- Batch-eligible profiles must have no unsupported evidence, validation error,
  duplicate conflict, unresolved identity field, or other review exception.
- Exception profiles are excluded from the batch action and require individual
  review. The review screen must clearly show included and excluded counts and
  allow any profile to be opened before confirmation.
- The batch action creates an individual confirmed profile/version and approval
  record for every included candidate, recording the actor, timestamp, and
  validated draft version. Every result remains individually inspectable and
  reusable after confirmation.
- Batch confirmation is an explicit recruiter action, not automatic AI
  approval. It confirms extracted candidate information only; final candidate
  decisions remain individually inspectable and approved, and outreach remains
  a separate approved action.

### Later intake options

- Vacancy-specific application forms or email inboxes may create candidate
  intake records automatically, while retaining the same duplicate, provenance,
  consent, evidence, and review controls.

Implementation note: **Create candidates from CVs** is now the primary candidate
action and reuses the reviewed intake batch for one or several CVs. The same
screen accepts exact `cv_filename` CSV mappings without fuzzy name matching.
Quick-add accepts an optional CV in the same transaction. Each accepted intake
item retains a safe exact link to its accepted private CV after temporary data is
cleared. The intake profile-review page derives included/excluded rows from that
link and confirms only grounded drafts with no ambiguities, sensitive-content
flag, stale source, or candidate-state exception. Existing profile confirmation
actor/time fields remain the individual approval record; candidate decisions and
outreach are unchanged and separate.

## CR-005 — Practical candidate privacy and source fields

Status: **Complete — 2026-08-25**

Recruiter-facing candidate intake should use plain language and safe practical
defaults while retaining the underlying privacy, provenance, and outreach
controls. Where possible, these are presentation and workflow changes rather
than unnecessary internal field renames or schema redesign.

### Recruiter-facing wording

- **Reason for storing data** replaces the displayed label **Lawful basis**.
  Helper text explains that this is the permitted reason for processing the
  candidate record, with clear organization-approved choices.
- **Consent** replaces **Consent status**. Its default is **Not recorded**;
  consent must never default to **Given**.
- **Allowed contact** replaces **Contact permission**, using understandable
  choices such as **Application only**, **Future roles allowed**, **Do not
  contact**, and **Not confirmed**.
- **Delete or review on** replaces **Retention until**. The date is calculated
  automatically from the organization's retention policy when possible, while
  authorized users can review documented exceptions.
- **Source name** is displayed with the helper text: **Where this candidate
  record came from.**
- **Source reference** is displayed with the helper text: **Optional stable ID
  or reference from the original source.**

### Practical workflow rules

- Direct applications, recruiter sourcing, referrals, imports, and other
  organization-approved intake methods expose only the relevant reason and
  contact choices.
- Bulk workflows can apply shared source and privacy values once, while source
  references remain record-specific where supplied.
- Source references support traceability and deterministic duplicate/import
  matching but are optional and must not be used as a fuzzy identity guess.
- Consent and allowed contact remain separate concepts. Outreach cannot be
  approved when the reason for storing data is missing or allowed contact does
  not permit it. When consent is the selected processing reason, valid recorded
  consent is also required.
- The interface provides concise explanations and validation messages so normal
  recruiters can complete intake without interpreting legal terminology.

Implementation note: the stable database values remain unchanged while all
recruiter intake, candidate-source review, and outreach surfaces translate them
into the approved plain language. **Future roles allowed** is the only state that
permits rediscovery outreach; **Application only**, **Do not contact**, and **Not
confirmed** remain safe blockers. Final approval also requires a recorded reason
for every source and, when that reason is consent, consent recorded as **Given**.
Dates remain blank when no organization retention policy exists; CR-002 will
supply policy-derived dates instead of CR-005 inventing a universal default.

## DEF-001 — Canonical skill matching

Status: **Complete — 2026-08-24**

Problem: deterministic shortlist generation can reject a valid match when the
confirmed candidate profile and vacancy express the same skill differently,
for example candidate skill **Python** versus vacancy skill **Python
development**. A later AI assessment may understand the relationship, but it
must not be required to repair an incorrect deterministic shortlist result.

### Required correction

- Canonicalize skill terms produced by both candidate-profile and vacancy
  extraction, while preserving the original source wording and evidence.
- Apply the same canonicalization again when comparing saved profile and
  vacancy versions so existing confirmed records benefit without mandatory
  re-extraction.
- Use controlled, reviewable aliases for safe equivalences such as **Python
  development**, **Python programming**, and role wording that clearly denotes
  the canonical skill **Python**.
- Do not use unrestricted substring matching; terms such as **Java** and
  **JavaScript** must remain distinct.
- Use canonical skills consistently for must-have checks, deterministic scores,
  and shortlist inclusion, while displaying the original evidence to the
  recruiter.
- Terms that remain unresolved after deterministic normalization may receive an
  explainable AI semantic-match suggestion. AI must not silently create an
  alias, mutate confirmed data, or override a hard constraint.
- Add focused tests for equivalent phrases, case and punctuation variation,
  unsafe near-matches, saved-version matching, and unresolved-term behavior.

Implementation note: the first controlled policy covers explicit Python and
Django developer/development wording. Unknown terms remain separate. No AI
fallback was required for this deterministic correction; unresolved semantic
suggestions remain optional future work and cannot override a hard constraint.
