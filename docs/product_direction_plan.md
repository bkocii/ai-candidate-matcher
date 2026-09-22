# Product Direction Plan

Status: Approved direction; implementation scope must be reviewed and approved
one task at a time.

Recorded: 2026-09-21.

## Product identity

AI Candidate Matcher is an **AI shortlist engine and recruiter review
workspace**, not a full applicant-tracking system.

The product promise is:

> Give the application a vacancy and a set of lawfully held CVs. Receive an
> explainable ranked shortlist, then review the exceptions and make the final
> human decision.

The primary target is a small recruitment agency or internal recruitment team
that receives enough CVs for manual screening to be slow, but does not need a
large enterprise ATS implementation.

## Minimum-effort recruiter principle

The product must be designed for recruiters who want to spend as little time as
possible on administration and repetitive screening. AI and background work
should do the bulk of extraction, comparison, evidence linking, ranking, and
exception detection. The routine recruiter experience should be:

**Provide vacancy → upload CVs → receive ranked results → review exceptions →
confirm decisions**

Use sensible defaults, vacancy context, bulk actions, reuse of confirmed facts,
and automatic progress wherever they are safe. Do not require recruiters to
re-enter known information, approve every clean intermediate AI action, or move
through several screens to obtain a shortlist. Reliability remains the
constraint: evidence grounding, tenant isolation, explicit candidate reuse,
contact permission, currentness checks, and the final human decision must not be
removed merely to save a click.

## Intended client experience

The default delivery model is a hosted web application operated by the platform
owner:

1. The platform owner creates the organization and its first administrator.
2. The client receives the application URL and login details; the client does
   not need to buy a domain or operate a server.
3. The organization administrator can add recruiters and optional hiring
   clients.
4. A recruiter creates a vacancy, uploads the CVs received for that vacancy,
   reviews extraction exceptions, and receives a ranked shortlist.
5. The recruiter remains responsible for candidate reuse, decisions, and any
   outreach action.

Shared multi-tenant SaaS is the normal long-term model. A separately hosted
instance may later be offered to clients with stricter procurement or isolation
requirements. Self-hosting is not the default first-client path.

## Platform access and client terms

- Platform ownership is an operator capability, not tenant membership.
- A platform owner creates the organization and its first administrator, but a
  platform-owner account must not receive normal membership in a real client
  organization.
- Platform owners use a separate internal/demo organization and non-platform
  test account for ordinary product testing.
- Django superuser and infrastructure access remain exceptional technical
  capabilities for recovery, security, or client-requested support; they are
  not routine recruitment-data access.
- A later support-access workflow should be client-approved, purpose-recorded,
  time-limited, visible, revocable, and audited.
- Before real onboarding, the client must accept a service agreement and data-
  processing agreement covering authorized technical access, confidentiality,
  subprocessors including hosting and AI providers, incident handling,
  retention/deletion, export, and termination. Final legal text requires review
  by qualified counsel for the operating jurisdiction.

The application already separates platform pages from tenant content, but the
existing administrator-membership workflow can still link a platform-owner
account. `ACCESS-001` will close that narrow gap before any real client is
onboarded.

## Candidate retention direction

The existing retention policy, staged candidate deletion, legal holds,
exceptions, audit events, and dry-run lifecycle tools remain the foundation.
The client-readiness refinement must add a low-effort candidate-level default
suited to a reusable talent pool:

- Active recruitment prevents scheduled candidate expiry.
- An inactive reusable candidate defaults to review/deletion **24 months after
  the last meaningful activity**; an organization may choose a shorter 12-month
  period. Indefinite retention is not a normal option.
- Meaningful activity must represent a deliberate, lawful new purpose, such as
  an authorized new application/consideration, renewed candidate permission, or
  documented candidate contact. Viewing a profile, background processing, or an
  automatic AI run must not silently restart the clock.
- Organization administrators receive a warning 30 days before expiry. An
  extension requires a recorded valid reason or renewed permission rather than
  a convenience-only click.
- A valid deletion request is handled independently of the ordinary schedule,
  subject to documented legal-hold or legal-retention requirements.
- On customer termination, provide a 30-day export window, then delete live
  tenant data. Deployment documentation must define backup expiry and restoration
  handling so deleted data is not silently reintroduced; the target maximum
  backup rotation period is 30 days unless a reviewed legal requirement says
  otherwise.
- Initial irreversible processing should prefer complete deletion of personal
  candidate content over partial anonymization that could leave identity in CVs,
  evidence excerpts, notes, assessments, or outreach. A content-free deletion
  audit record may remain.

The exact event calculation, migration, dependency preview, and deletion scope
must be agreed during `RET-001`; this direction does not authorize automatic
purge code by itself.

## Data ownership and separation

- The organization remains the tenant and authorization boundary.
- Recruiters belong to the organization, not directly to hiring clients.
- Hiring clients are internal organization-owned customer references.
- A vacancy belongs to the organization and may belong to one hiring client.
- A candidate profile belongs to the organization and is reusable; it is not
  duplicated merely because the candidate is considered for another vacancy.
- Candidate consideration for a vacancy is a separate relationship carrying
  the vacancy-specific source/application context, assessment, status,
  shortlist decision, notes, and history.
- Every intake must preserve its original vacancy, hiring client where present,
  batch, source, and later reuse history.

The detailed implementation task must inspect the current models before choosing
whether to extend an existing shortlist/intake relationship or introduce a new
candidate-vacancy record. This document approves the product behavior, not an
unreviewed schema.

## Vacancy-centric core workflow

The intended routine journey is:

**Hiring client → vacancy → upload CVs → extract profiles → evaluate and rank →
review exceptions → shortlist**

The vacancy page should normally show **Candidates for this vacancy**, not the
entire organization candidate pool. A secondary **Add from candidate pool**
action should allow deliberate reuse of existing candidates.

CVs uploaded from a vacancy must automatically retain that vacancy and intake
batch as their original application context. Confirmed profiles remain reusable
organization-level records.

## Candidate discovery and reuse

Candidates must not be permanently assigned to one role. Search and suggestions
should instead use supported structured facts such as likely roles, skills,
seniority, and experience areas.

When another vacancy is similar, the system may show **Potential existing
matches** from earlier batches or the wider organization pool. Reuse across
vacancies or hiring clients must always be an explicit recruiter action:

**AI suggests → recruiter reviews → recruiter adds candidate to the vacancy**

The system must not silently move, submit, shortlist, or contact a candidate for
another hiring client. Original provenance and permission/consent state remain
visible and enforceable.

## Matching and review direction

- Preserve deterministic hard constraints and evidence-backed AI assessments.
- Continue improving controlled semantic equivalence where benchmarks expose
  genuine misses; do not replace inspectable matching with unrestricted fuzzy
  or substring matching.
- Make the ranked shortlist the central output for each vacancy.
- Show concise reasons, evidence, missing requirements, and uncertainty beside
  the ranking.
- Default recruiter attention to ambiguous, unsupported, changed, or borderline
  cases while keeping all candidates inspectable.
- Never auto-reject candidates or convert an AI recommendation into a hiring
  decision.

## Outreach direction

The routine experience should feel like:

**Shortlist → create or edit outreach → open in email app/copy/export**

The interface may combine routine confirmations and remove redundant screens,
but it must preserve currentness checks, exact-recipient visibility, contact
permission, consent/lawful-source rules, an exact reviewed draft, and an audited
human action. Integrated email sending remains outside the current MVP unless
approved separately.

## AI credential strategy

AI credentials belong to an organization configuration, never to individual
recruiters.

The intended resolution order is:

1. Use an enabled organization-owned provider/API-key configuration when one is
   present.
2. Otherwise use the existing platform environment configuration.

Platform-managed AI remains the simplest client experience. Optional
organization-level bring-your-own-key (BYOK) reduces platform variable-cost risk
and supports stricter client procurement needs. The first implementation must
add only this override and fallback; it must not add billing, per-user keys,
provider marketplaces, or complex quotas.

Secrets must be encrypted or held by an appropriate secret manager, restricted
to organization administrators, and never displayed in full after saving.

## Implementation sequence

Each item requires a detailed design and acceptance-criteria review before code
changes begin.

### Phase A — Stable baseline

- `DIR-001` Record the focused product direction and close the completed manual-
  review pass. **Complete — 2026-09-21.**
- `DIR-002` Record the minimum-effort AI experience, operator-access boundary,
  client agreement requirement, and long-gap candidate-retention direction.
  **Complete — 2026-09-21; documentation only.**
- The user runs the complete local quality command against this baseline.

### Phase B — Vacancy-centric candidate workflow

- `FLOW-001` Bind normal CV intake to a vacancy and preserve original
  application/batch provenance while keeping one reusable organization candidate.
- `VAC-001` Simplify vacancy creation into one AI-first path: choose an optional
  hiring client, enter a title, provide the description by paste or validated
  PDF/DOCX/TXT upload, create and analyze, review a compact requirements draft,
  then confirm/open and continue directly to vacancy-scoped CV upload. Preserve
  manual draft fallback, immutable source/history, and explicit confirmation.
- `FLOW-002` Make vacancy views default to candidates associated with that
  vacancy and provide a separate organization-pool entry point.
- `FLOW-003` Add deliberate **Add from candidate pool** and cross-vacancy reuse
  with permission and provenance checks.

### Phase C — Shortlist and recruiter experience

- `MATCH-005` Add supported role/seniority discovery and improve measured
  semantic matching without weakening deterministic evidence rules.
- `MATCH-006` Make a concise ranked, evidence-backed shortlist the vacancy's
  central result.
- `REV-003` Extend exception-focused review across intake, matching, and ranking
  while retaining individual human decisions.
- `OUT-003` Simplify the outreach interface without removing permission,
  currentness, exact-draft, or human-action safeguards.

### Phase D — Client readiness

- `ACCESS-001` Prevent platform-owner accounts from receiving normal membership
  in real client organizations; retain separate internal/demo use through a
  non-platform test account and exceptional documented technical access.
- `RET-001` Extend the existing candidate retention workflow with a configurable
  24-month inactive-talent-pool default, 12-month shorter option, meaningful-
  activity calculation, 30-day warning, and reviewed deletion/offboarding rules.
- `AI-007` Add optional organization-level BYOK with platform configuration as
  the backward-compatible fallback.
- `PRIV-001` Re-audit tenant isolation, private CV authorization, candidate
  deletion/retention, provenance, AI-provider disclosure, and audit coverage for
  the new relationships.
- `LEGAL-001` Prepare service/data-processing agreement inputs, subprocessor and
  operator-access disclosures, and a client onboarding acceptance record for
  qualified legal review.
- `DEPLOY-001` Document hosted-SaaS onboarding plus the optional dedicated-
  instance path for stricter clients.

## Deferred or excluded scope

- `DEMO-002` is deferred until the revised core workflow reaches an agreed
  positioning checkpoint, so client-facing material describes the product being
  built rather than the superseded workflow.
- Public signup, subscription billing, full ATS lifecycle management, interview
  scheduling, payroll/HR features, per-recruiter AI keys, and automatic outreach
  sending remain outside this plan.

## Next activity

Discuss `FLOW-001` in detail. Before implementation, confirm:

- the exact candidate-to-vacancy behavior;
- duplicate handling when the same person appears in more than one intake;
- the minimum provenance fields;
- how existing candidates and historical shortlists are migrated or preserved;
- authorization, privacy, and deletion behavior;
- focused tests and manual browser checks.

No `FLOW-001` code is approved merely by this planning document.

`VAC-001` is approved in direction but follows `FLOW-001` because its final
**Confirm and upload CVs** action requires the vacancy-scoped intake destination.
Before implementation, confirm the compact review layout and exact upload
validation/error behavior against the existing vacancy and document services.

### `VAC-001` approved behavior

- The create page contains optional hiring client, required title, pasted job
  description, and one vacancy-document upload control.
- Exactly one description source is required: pasted text or one PDF, DOCX, or
  UTF-8 TXT file. Supplying neither or both returns a clear form error.
- Upload validation is bounded and content-aware. Reuse/generalize the hardened
  PDF/DOCX safety and extraction logic; add bounded UTF-8 text handling. Reject
  oversized, encrypted, unsafe, corrupt, empty, scanned/no-text, mismatched, or
  unsupported input with recruiter-safe messages.
- Preserve extracted source text and safe upload provenance. The raw vacancy file
  does not need to be retained in the first version.
- The primary action is **Create and analyze vacancy**. It creates the draft and
  runs AI requirement extraction without a separate recruiter action.
- AI failure preserves a usable manual draft and offers safe retry/manual editing;
  it must not discard the vacancy or create duplicate drafts.
- The review page leads with AI ambiguities and essential matching requirements.
  Less common fields and custom eligibility-rule controls remain available under
  a clearly labelled advanced section.
- The routine final action is **Confirm and upload CVs**. It confirms the exact
  reviewed requirements, opens a draft vacancy atomically, and redirects to the
  `FLOW-001` vacancy intake page. It does not evaluate candidates automatically.
- **Save draft without AI** and manual correction remain secondary fallbacks.
- Existing tenant authorization, immutable confirmed versions, correction
  drafts, deterministic eligibility boundaries, safe AI usage events, and
  provider-free tests remain intact.
