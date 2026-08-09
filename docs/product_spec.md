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

The MVP runs for one organization. Agency deployments may associate vacancies with optional client companies.

## Problem

Recruiters often accumulate many previous applicants but rely on filenames, memory, basic keyword searches, or manual CV review when a new vacancy arrives. Good candidates become difficult to rediscover, and repeated screening consumes time.

## MVP user journey

1. An administrator creates recruiter accounts and organization settings.
2. A recruiter imports candidates through CSV and supported CV documents.
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
- One organization with multiple recruiter accounts.
- Optional client companies for agency use.
- Candidate creation and CSV import.
- PDF and DOCX CV upload, subject to implementation feasibility and safe text extraction.
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
- Django admin for operational management.

## Non-goals for the MVP

- Searching the open internet for candidates.
- LinkedIn or arbitrary website scraping.
- Buying or providing a proprietary candidate database.
- Automatic candidate rejection.
- Automatic email or platform messaging.
- Ranking based on age, gender, ethnicity, religion, disability, family status, photographs, or other protected/sensitive characteristics.
- Full ATS replacement.
- Multi-tenant SaaS billing and subscriptions.
- Mobile application or Windows executable.
- Automated legal compliance certification.

## Matching principles

- Explicit rules run before AI to reduce cost and make hard constraints understandable.
- AI assessments are decision support, not employment decisions.
- Every substantive positive or negative conclusion must point to candidate or vacancy evidence.
- Missing information is reported as unknown, not treated as proof that a candidate lacks a skill.
- Recruiters can inspect and override every assessment.
- Model prompts exclude protected characteristics and irrelevant personal data.

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

## Validation gate

Before positioning this as a SaaS, interview 3–5 agencies. Proceed toward a hosted product only if at least two want to test the workflow and at least one can provide anonymized sample data or a realistic schema.

