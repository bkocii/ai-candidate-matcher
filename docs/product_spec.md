# Product Specification

## Product statement

AI Candidate Matcher helps a small recruitment agency or employer rediscover suitable people inside a candidate pool it already lawfully controls.

The core promise is:

> Turn a vacancy and an existing candidate database into an explainable recruiter-reviewed shortlist and editable outreach drafts.

## Target users

### Primary

Small recruitment agencies with CVs stored in folders, spreadsheets, email exports, or a basic ATS.

### Secondary

Small and medium employers recruiting directly from their own historical applicant pool.

The managed SaaS supports several isolated organizations. Agency organizations
may associate vacancies with optional client companies. Platform owners provision
organizations and first administrators; they do not automatically enter tenant
workspaces or see recruitment content.

## Problem

Recruiters often accumulate many previous applicants but rely on filenames, memory, basic keyword searches, or manual CV review when a new vacancy arrives. Good candidates become difficult to rediscover, and repeated screening consumes time.

## MVP user journey

1. An administrator creates recruiter accounts and organization settings.
2. A recruiter imports candidates through CSV or a reviewed bulk intake of
   supported CV documents.
3. The recruiter pastes a vacancy description and confirms the extracted requirements.
4. Deterministic rules remove candidates who fail explicit hard constraints.
5. The application ranks the remaining candidates.
6. AI creates an evidence-based assessment for each shortlisted candidate.
7. The recruiter sees matching qualifications, gaps, uncertainties, and source evidence.
8. The recruiter approves, rejects, or marks a candidate for later review.
9. For an approved candidate, AI creates an editable outreach draft.
10. The recruiter copies or exports the final draft and sends it manually.

## MVP capabilities

- Secure recruiter login.
- Managed multi-organization hosting with strictly isolated tenant workspaces.
- Explicit platform-owner provisioning of organizations and first administrators
  without implicit candidate-data access.
- Organization-administrator recruiter management and multi-workspace switching.
- Optional client companies for agency use.
- Organization-administrator client-company settings with reversible
  deactivation; recruiters can assign active clients while creating or editing
  vacancies, and existing inactive-client relationships remain historical.
- Primary CV-first candidate creation for one or several documents, reviewed
  local identity proposals, shared provenance, exact CSV-to-CV mapping, and
  explicit selected-row creation.
- Lightweight manual quick-add with an optional CV in the same action.
- Explicit batch confirmation of only clean evidence-validated profile drafts,
  with included/excluded review and individual profile approval history.
- Plain-language candidate source/privacy controls with safe not-recorded
  defaults, shared bulk values, inspectable provenance, and explicit outreach
  permission enforcement.
- Audited recruiter correction of candidate/source records and immutable
  evidence-validated profile correction versions. Conflicting trusted candidate
  and CV-profile locations block individual and batch confirmation until resolved.
- Hardened PDF and DOCX CV upload, safe text extraction, and authorized private
  attachment delivery.
- Vacancy creation from pasted text.
- Recruiter confirmation of extracted vacancy requirements.
- Hard filters for explicit requirements.
- Candidate-to-vacancy shortlist.
- Structured AI match assessment with evidence, gaps, and uncertainty.
- Traffic-light display derived from a numeric score.
- Human review queue.
- Editable outreach subject and body.
- Copy/export only; no automatic sending.
- AI token, cost, latency, retry, and failure tracking when available.
- Audit history for imports, assessments, reviews, and draft approval.
- Tenant-scoped retention/deletion review, minimized privacy events, and
  deleted-record integrity checks.
- Organization-admin retention policies with dependency-aware previews, legal
  holds/exceptions, safe cleanup of abandoned operational bundles, and staged
  organization suspension, recovery, and content-free tombstoning.
- Django admin for operational management.
- Documented PostgreSQL/Gunicorn/Nginx deployment, separately supervised durable
  worker and retention timer, content-free health endpoints, production runtime
  checks, and paired database/private-media recovery guidance.

## Non-goals for the MVP

- Searching the open internet for candidates.
- LinkedIn or arbitrary website scraping.
- Buying or providing a proprietary candidate database.
- Automatic candidate rejection.
- Automatic email or platform messaging.
- Ranking based on age, gender, ethnicity, religion, disability, family status, photographs, or other protected/sensitive characteristics.
- Full ATS replacement.
- Multi-tenant SaaS billing and subscriptions.
- Public signup, self-service organization creation, or automatic email invitations.
- Mobile application or Windows executable.
- Automated legal compliance certification.

## Matching principles

- Explicit rules run before AI to reduce cost and make hard constraints understandable.
- Deterministic skill matching uses a small controlled alias vocabulary while
  retaining the original vacancy and candidate wording as inspectable evidence.
  Unrecognized terms remain distinct; unrestricted substring matching is not used.
- AI assessments are decision support, not employment decisions.
- Every substantive positive or negative conclusion must point to candidate or vacancy evidence.
- Missing information is reported as unknown, not treated as proof that a candidate lacks a skill.
- Recruiters can inspect and override every assessment.
- Review defaults to changed evidence and exceptions while keeping every latest
  assessment and its immutable version history individually inspectable.
- Approve, reject, and revisit are explicit individual recruiter actions with
  notes, actor, timestamp, and immutable correction history; they never trigger
  outreach automatically.
- Model prompts exclude protected characteristics and irrelevant personal data.
- A confirmed candidate profile is reusable across vacancies. High-volume intake
  and assessment should use resumable background batches and exception-focused
  review rather than forcing repetitive per-candidate setup, while employment
  decisions remain explicit individual recruiter actions.
- Bulk CV intake proposes candidate identity locally, keeps uncertain fields and
  possible duplicates visible, and never asks AI to determine identity, lawful
  basis, consent, or contact permission. Only explicitly selected reviewed rows
  create candidates; accepted CVs may then enter the existing background AI
  profile-draft workflow.
- Candidate intake displays **Reason for storing data**, **Consent**, **Allowed
  contact**, and **Delete or review on** while preserving controlled internal
  values. Consent never defaults to Given. Rediscovery outreach requires Future
  roles allowed, a recorded reason for every source, and Given consent whenever
  consent is the selected reason.
- CSV-assisted CV intake joins rows only by an exact `cv_filename` supplied by
  the recruiter. Missing, repeated, and conflicting mappings remain unresolved;
  candidate names are never used as a fuzzy join key.
- A batch confirmation action may confirm only saved drafts whose evidence
  already passed deterministic grounding and which have no ambiguity,
  sensitive-content, changed-source, identity/duplicate, or lifecycle exception.
  Every confirmed version records its own human actor and timestamp and remains
  individually inspectable. This is profile confirmation only, never a final
  candidate decision or outreach approval.
- Repeating the same batch must reuse the existing operational job and saved
  per-candidate results. Interrupted targets must be reclaimable, one candidate's
  failure must not block the rest, and safe status must expose exceptions without
  copying CV, prompt, response, contact, or decision content.
- Retention expiry is a review signal, not an automatic purge. Candidate deletion
  first freezes the record, and permanent erasure requires a separate,
  individually inspectable administrator action.
- Audit views expose only the minimum identifiers and operational metadata needed
  for accountability; they do not duplicate CV, contact, prompt, response,
  recruiter-note, or outreach content.
- AI usage reporting is organization-administrator-only, tenant-scoped, and
  aggregate. It distinguishes unavailable provider metadata from zero, never
  estimates missing token/cost/latency/retry values, and does not expose
  per-request or private recruitment content.
- Full organization privacy/audit reporting is administrator-only. Recruiters
  retain the task-specific processing state and candidate context required by
  their ordinary workflows, but cannot inspect organization-wide retention,
  actor-history, model, cost, or failure reports.
- Client companies are optional organization-owned hiring-customer references,
  not tenants, candidate owners, memberships, or login accounts. Direct
  employers need none. Only active same-organization clients can be newly
  assigned to a vacancy; deactivation does not erase an existing relationship.
- Platform ownership, Django staff status, and Django superuser status do not
  grant organization content access. Every tenant workspace still requires an
  explicit active membership.
- Disabling a membership removes only that organization's access. A shared user
  account and its memberships in other organizations remain active.

## Core structured outputs

### Vacancy requirements

- Title and summary.
- Must-have skills.
- Nice-to-have skills.
- Minimum experience where explicitly stated.
- Location and remote expectations.
- Languages.
- Education or certification requirements.
- Employment type.
- Explicit hard constraints.
- Ambiguities requiring recruiter confirmation.

### Candidate profile

- Skills and evidence.
- Employment history.
- Relevant experience summary.
- Location and work-mode preference when supplied.
- Languages.
- Education and certifications.
- Availability when supplied.
- Missing or ambiguous information.

### Match assessment

- Score from 0 to 100.
- Traffic-light band.
- Matching requirements with evidence.
- Gaps.
- Uncertainties.
- Concise recommendation for recruiter review.
- Model and request metadata.

## MVP success test

Using an anonymized or synthetic set of at least 20 candidates and 3 vacancies, a recruiter must be able to:

1. Import candidates without developer assistance.
2. Create and confirm a vacancy.
3. Generate a shortlist.
4. Understand why each candidate was ranked.
5. Correct a mistaken requirement or assessment.
6. Approve a candidate and produce an editable outreach draft.
7. Complete the workflow without any message being sent automatically.

`EVAL-001` supplies the reproducible baseline for this test: 20 entirely
synthetic candidates with private generated CVs and grounded confirmed profiles,
3 synthetic vacancies, frozen deterministic top-five results, and a complete
0–3 relevance judgment matrix. The dataset is isolated from real recruitment
records, permits no contact, and makes no AI request merely by being installed.

`EVAL-002` measures deterministic and AI-assisted ordering separately at cutoff
5 using graded nDCG, relevant-result precision, expected-top overlap, and honest
assessment coverage. It never blends deterministic and AI scores. Incomplete or
stale AI coverage is unavailable rather than treated as zero or a partial
quality result, and running the measurement makes no provider request or hiring
decision.

`EVAL-003` reviews current stored AI assessment explanations separately from
ranking quality. It requires exact application-owned requirement/evidence
snapshots and complete requirement coverage, flags explicit protected or
sensitive attribute terminology and high-confidence unsupported measured or
quoted claims, and highlights match citations that require human inspection.
Incomplete assessment coverage is unavailable, never a passing result. The
review makes no AI request, changes no assessment or score, and cannot approve,
reject, rank, contact, or generate outreach for a candidate.

`DEMO-001` turns the same frozen synthetic baseline into a reproducible product
walkthrough without a provider key. It demonstrates confirmed-profile reuse,
inspectable deterministic ranking, compact exception-focused review, individual
human decisions, and a separate outreach draft. The synthetic source remains
contact-restricted, so final outreach approval and manual use are visibly blocked
and nothing can be sent. Deterministic fixture responses demonstrate workflow
state only and are not presented as live-model quality evidence.

## Validation gate

Before positioning this as a SaaS, interview 3–5 agencies. Proceed toward a hosted product only if at least two want to test the workflow and at least one can provide anonymized sample data or a realistic schema.
