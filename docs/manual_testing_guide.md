# Manual Testing Guide

This guide verifies the application from the Django foundation through
`DATA-005`. Use only the synthetic files in `manual_testing/fixtures` or other
invented data. Do not upload real candidate records or CVs to a development
machine merely for testing.

## 1. Prepare the local project

Open PowerShell in the project root (the directory containing `manage.py`):

```powershell
uv sync --extra dev
Copy-Item .env.example .env -ErrorAction SilentlyContinue
uv run python manage.py migrate
uv run python scripts/check.py
```

Expected result:

- The shared quality gate finishes successfully.
- Django reports no migration drift.
- The ordinary test suite makes no live AI request.
- No OpenAI API key is required.

If `.env` already exists, do not overwrite it. A blank
`DJANGO_SECRET_KEY=` is accepted only in development and uses the local
development fallback. Production configuration still requires a real secret.

## 2. Create the first test administrator

```powershell
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Open `http://127.0.0.1:8000/admin/` and sign in.

Create these records in order:

1. **Organization**
   - Name: `Northstar Recruitment Test`
   - Slug: `northstar-test`
   - Active: checked
2. **Organization membership**
   - User: the superuser you just created
   - Organization: `Northstar Recruitment Test`
   - Role: `Administrator`
   - Active: checked
3. **Client company**
   - Organization: `Northstar Recruitment Test`
   - Name: `Acme Test Industries`
   - Slug: `acme-test-industries`
   - Active: checked

Why the membership is necessary: Django superuser status grants access to the
separate `/admin/` surface, but it deliberately does not bypass normal
organization isolation.

## 3. Test authentication and the organization dashboard

1. Open `http://127.0.0.1:8000/`.
2. If prompted, sign in with the superuser.
3. Confirm that the single active organization opens automatically.
4. Confirm that the navigation contains **Dashboard**, **Candidates**,
   **Vacancies**, **Django admin**, and **Sign out**.
5. Confirm the dashboard initially shows zero active candidates and zero open
   vacancies.
6. Select **Sign out** and confirm you return to the login page.

Expected security behavior:

- Logout is a POST action protected by CSRF, not a state-changing link.
- A signed-in user without any active membership receives a safe access page.
- An inactive user, organization, or membership cannot enter the workspace.

## 4. Test manual candidate entry

Open **Candidates** and select **Add candidate**. Enter:

- Full name: `Arben Testi`
- Email: `arben.testi@example.test`
- Phone: `+383 44 111 222`
- Location: `Prishtina`
- Source name: `Synthetic manual test`
- Source reference: `MAN-001`
- Lawful basis: `Not recorded`
- Consent status: `Unknown`
- Contact permission: `Unknown`
- Permission notes: `Synthetic test record; no real person.`

Expected result:

- The candidate is created and appears in the organization candidate list.
- The provenance record is created in the same operation.
- Unknown permission/consent remains explicitly unknown.

Repeat the entry using the same email or the same source reference.

Expected result: the app reports a possible duplicate and creates no second
candidate. A matching name by itself is not treated as a duplicate.

## 5. Test candidate CSV import

Open **Candidates** > **Import CSV**. The page also offers the exact header-only
template used by the application.

### Valid import

Upload `manual_testing/fixtures/candidate-import-valid.csv` and set:

- Source name: `Synthetic valid CSV test`
- Lawful basis: `Not recorded`
- Consent status: `Unknown`
- Contact permission: `Unknown`

Expected report: `3 created`, `0 duplicates`, `0 invalid`.

After submission, the browser should move directly to the import report below
the form. Keyboard focus can be moved to the report container, and the complete
row table remains horizontally scrollable on narrow screens.

### Mixed-result import

Then upload `manual_testing/fixtures/candidate-import-mixed.csv` with source name
`Synthetic mixed CSV test`.

Expected report, assuming the valid file was imported first:

- 6 processed rows
- 2 created
- 2 duplicates
- 2 invalid

The valid rows must still be created even though other rows fail. Existing
records must not be overwritten.

### Phone duplicate normalization

Create or import a synthetic candidate with phone `+383 44 123 456`, then try
another row in the same organization with `+383-44-123-456`.

Expected result: the second row is reported as a phone duplicate. Formatting
characters are ignored. A local number such as `044 123 456` is not yet assumed
to be the same as `+383 44 123 456`; country-aware normalization requires a
future organization-country setting.

## 6. Test private CV upload and extraction

Open `Arben Testi`, select **Upload CV**, and upload
`synthetic-arben-testi-cv.pdf`.

Expected result:

- The upload succeeds.
- The candidate page shows filename, type, size, extraction status, and time.
- No extracted CV text, private storage path, or download link is displayed.

Open another synthetic candidate and upload `synthetic-amina-berisha-cv.docx`.
Expected result: the DOCX is accepted and extraction succeeds.

Now test rejection cases:

1. Upload `rejected-textless-cv.pdf`.
   - Expected: rejected because no readable text was found; scanned-image PDFs
     are not supported yet.
2. Upload `rejected-invalid-signature.pdf`.
   - Expected: rejected because its content is not a valid PDF.
3. Upload `synthetic-arben-testi-cv.pdf` to another candidate in the same
   organization.
   - Expected: reported as the exact document already stored for `Arben Testi`.

Failed uploads must create neither a document database row nor stored file
bytes. Use a retention date if you also want to verify that optional metadata.

### Candidate deletion

Create a disposable synthetic candidate, add a provenance record, and upload one
of the synthetic CVs. Open the candidate and select **Delete candidate**.

Expected result:

- A separate confirmation page explains that deletion cannot be undone.
- Cancel returns to the unchanged candidate.
- Confirming deletion returns to the candidate list.
- The candidate no longer appears and its former detail URL returns `404`.
- Contact fields, provenance records, document rows, stored CV bytes, and
  extracted text are removed.
- Django admin retains only a non-identifying candidate tombstone and deletion
  timestamps for minimal audit integrity.

## 7. Test vacancy creation and requirements version 1

Open **Vacancies** and select **Add vacancy**. Use:

- Title: `Senior Django Developer`
- Client company: `Acme Test Industries`
- Description: paste `manual_testing/fixtures/vacancy-description.txt`

Expected result:

- The vacancy is created as `Draft`.
- Requirements version 1 is created as an editable manual draft.
- You are redirected directly to the requirements editor.
- The original pasted description is available in the collapsed source panel.

Enter the values from
`manual_testing/fixtures/vacancy-requirements-reference.md`. List fields accept
one item per line. Save the draft.

Expected result:

- The vacancy detail page shows a recruiter-review warning.
- The draft is not described as current matching input.
- Version 1 remains editable until confirmed.

## 8. Test confirmation and immutable corrections

On the vacancy detail page, select **Confirm version 1**.

Expected result:

- Version 1 becomes `Confirmed` with the acting recruiter and timestamp.
- It becomes the current confirmed requirements.
- It is read-only; the app does not offer in-place editing.

Select **Create correction draft**.

Expected result:

- Version 2 is created as a draft.
- Its values are copied from version 1.
- Version 1 remains unchanged in history.

Edit version 2, change minimum experience from `4.0` to `5.0`, add the
ambiguity `Clarify whether occasional travel is required`, save, and confirm.

Expected result:

- Version 2 becomes the current confirmed requirements.
- Both version 1 and version 2 remain in the history.
- Creating a correction again produces version 3; it never overwrites a
  confirmed snapshot.

Also create a second vacancy with no client company. Expected result: it is
accepted as a direct-employer vacancy.

## 9. Test blank confirmation protection

Create another vacancy, do not enter any structured requirements, return to its
detail page, and select **Confirm version 1**.

Expected result: confirmation is refused with a message asking for at least one
structured requirement. The version remains a draft.

## 10. Test vacancy lifecycle and dashboard count

New vacancies remain `Draft`; confirming requirements alone does not make the
dashboard's **Open vacancies** count increase.

1. Before confirming requirements, confirm that **Change to Open** is unavailable
   and the page explains that a confirmed version is required.
2. After confirming requirements, select **Change to Open**.
3. Return to the dashboard and confirm **Open vacancies** increases by one.
4. Return to the vacancy and select **Change to Paused**. Confirm the dashboard
   count decreases.
5. Change the vacancy from `Paused` back to `Open`, then from `Open` to `Closed`.
6. Confirm a closed vacancy can be reopened when it still has confirmed
   requirements.

Only these transitions are available:

- `Draft → Open`
- `Open → Paused` or `Closed`
- `Paused → Open` or `Closed`
- `Closed → Open`

All changes are POST-only and organization-scoped. Requirement confirmation and
vacancy lifecycle remain separate recruiter decisions.

### Vacancy deletion

Create a disposable vacancy and at least one requirements version. Open the
vacancy and select **Delete vacancy**.

Expected result:

- A separate confirmation page explains that requirements history is preserved.
- Cancel returns to the unchanged vacancy.
- Confirming deletion returns to the vacancy list.
- The vacancy disappears from the list and its former detail URL returns `404`.
- If it was open, the dashboard's open-vacancy count decreases.
- Django admin still contains the closed vacancy, its requirements history, and
  the deletion actor/timestamp.

## 11. Inspect skills, typed rules, and deterministic filtering

Use only synthetic evidence. Django admin is still needed to create the typed
candidate-skill and hard-constraint records; the evaluation report itself is in
the normal recruiter application.

1. Create or open an unconfirmed vacancy requirements draft in the normal app.
2. Enter `Python` and `Django` as must-have skills and `PostgreSQL` as a
   nice-to-have skill, then select **Save draft**.
3. Open Django admin and inspect **Matching → Requirement skills**.

Expected result: the version has three ordered links. `Python` and `Django` are
must-have; `PostgreSQL` is nice-to-have. **Matching → Skills** contains one
organization-owned canonical record for each name. Changing case or surrounding
spaces in the draft does not create another skill, while `C`, `C#`, and `C++`
remain different skills.

To record synthetic candidate evidence, open **Matching → Candidate skills** and
add:

- Candidate: a synthetic candidate in the same organization
- Skill: the organization’s `Python` skill
- Source label: `Python`
- Evidence: `Built a synthetic Django API project.`
- Years experience: `3.0`

Cross-organization candidate, document, and skill combinations must be rejected.

To inspect a typed rule while the requirements version is still a draft, open
**Matching → Hard constraint rules** and add:

- Requirements: the draft version above
- Rule type: `Required skill`
- Operator: `Has skill`
- Source text: `Python is explicitly required.`
- Skill: the same organization’s `Python` skill
- Position: `1`
- Expected value and numeric value: blank

You may add a location rule at position `2` using rule type `Location`, operator
`Equals`, source text `Candidate must be based in Prishtina`, and expected value
`Prishtina`. The unknown outcome is read-only and remains **Keep for recruiter
review**.

Confirm the requirements in the normal app, then try to edit either normalized
skill links or typed rules in admin. Expected result: confirmed definitions are
immutable. Create a correction draft and inspect admin again; the normalized
links and typed rules are copied to the new version instead of changing history.

Free-text values previously entered in the vacancy’s **Hard constraints** box
remain recruiter notes. They are not silently converted into executable rules.

Before confirming, create three active synthetic candidates in the same
organization:

- `Synthetic Pass`: location `Prishtina`, with the recorded `Python` skill.
- `Synthetic Review`: blank location and no recorded `Python` skill.
- `Synthetic Fail`: location `Peja`, with or without the `Python` skill.

Confirm the requirements, return to the vacancy detail page, and select
**Evaluate candidates**.

Expected result:

- The page identifies confirmed requirements version 1.
- `Synthetic Pass` passes both rules.
- `Synthetic Review` has unknown results and remains in **Needs review**. A
  missing skill or location is never treated as proof of failure.
- `Synthetic Fail` fails the explicit location equality rule.
- Every rule row shows the recruiter source wording, expected value, candidate
  fact, evidence when present, and explanation.
- Summary counts distinguish passed, needs-review, failed, and total evaluated.
- Inactive, deletion-requested, and deleted candidates are not evaluated.
- Candidate email, phone, raw extracted CV text, and private storage paths are
  not displayed on the report.

A minimum-experience rule can pass when a recorded candidate skill contains at
least that many years. A lower skill-specific value remains unknown because it
does not prove the candidate's total experience is lower. Work mode, language,
education, certification, and employment-type rules also remain unknown until a
later structured candidate profile records those facts.

## 12. Test deterministic scoring and bounded shortlist

Continue with the confirmed vacancy and synthetic candidates from the previous
section. In Django admin, add the following normalized requirement skills before
confirmation if they are not already present:

- Must-have: `Python`, `Django`
- Nice-to-have: `PostgreSQL`, `Redis`

Record different candidate-skill combinations with synthetic evidence. Return to
**Evaluate candidates** and select **Generate shortlist**.

Expected result:

- The generated run identifies the exact confirmed requirements version,
  generation time, algorithm version, evaluated count, eligible count, shortlist
  count, and fixed limit of 20.
- A candidate matching one of two must-have skills and one of two nice-to-have
  skills receives `50.00`: 35 must-have points plus 15 nice-to-have points.
- A missing skill is shown as **Not recorded**, receives zero points, and is not
  described as proof that the candidate lacks the skill.
- Explicit hard-filter failures do not appear in the shortlist, even if they have
  many recorded skills.
- Scores sort descending. At an equal score, a candidate who passed all hard
  filters appears before a candidate who still needs review. The final tie-break
  uses stable record ID rather than candidate name.
- Every row shows requirement wording, importance, recorded candidate wording,
  evidence, and awarded/possible points.
- Candidate contact fields, raw CV text, and storage paths are absent.
- Generating again creates a new run; it does not overwrite the earlier report.

To test the bound, create more than 20 active eligible synthetic candidates and
generate again. Expected result: exactly 20 entries appear, while the summary and
note retain the full eligible count and report how many fell outside the bound.

An older run is not yet labelled stale after candidate or vacancy data changes.
That behavior belongs to `MATCH-004` and is not a defect in this checkpoint.

## 13. Test organization isolation

In Django admin:

1. Create `Other Organization Test` with slug `other-test`.
2. Create a second non-staff user and give that user an active recruiter
   membership only in `Other Organization Test`.
3. Create one candidate and vacancy in each organization.

Sign in as each user in turn (a private/incognito window helps). Copy a candidate
or vacancy URL from the other organization into the address bar.

Expected result:

- The inaccessible organization/object returns `404` or the safe no-access
  response.
- Names, descriptions, candidate contacts, extracted text, and requirement
  values from the other organization are not displayed.
- Django staff/superuser status alone still does not bypass the normal app's
  membership requirement.

## 14. What is intentionally unavailable

The following are not defects at this milestone:

- No AI extraction or AI matching request.
- No automatic stale-result warning or invalidation yet.
- No recruiter-facing typed-rule or candidate-skill editor yet; `MATCH-001`
  exposes the data contract and Django admin inspection only.
- No candidate-profile extraction from CV text yet.
- No private CV download route.
- No OCR for scanned PDFs.
- No outreach workflow.

## 15. Final acceptance checklist

The current milestone is behaving correctly when all of these are true:

- `uv run python scripts/check.py` passes.
- Manual candidate entry and both CSV reports match the expectations above.
- Valid PDF and DOCX CVs extract successfully; unsafe fixtures are rejected.
- Recruiters can create direct-employer and client-associated vacancies.
- Requirements can be saved, confirmed, copied to a new version, and confirmed
  again without mutating history.
- Recruiters can open, pause, close, and reopen vacancies only through the
  documented lifecycle transitions.
- Candidate deletion removes private candidate content and CV files; vacancy
  deletion hides the vacancy without destroying requirements history.
- Requirement skills normalize case and spacing without merging meaningful
  punctuation, and typed rules keep unknown candidate facts eligible for review.
- Deterministic filtering shows inspectable pass/fail/unknown rule outcomes and
  excludes only candidates with an explicit failed fact.
- Shortlist generation is POST-only, excludes explicit failures, shows the
  70/30 skill formula and evidence, persists version-labelled history, and never
  exceeds 20 entries.
- Confirmed matching definitions cannot be edited; correction drafts copy them.
- Cross-organization URLs do not disclose data.
- No AI key or live AI request is required.

## 16. Reset disposable local test data

Only if this database and uploaded-media folder contain nothing you need:

```powershell
Stop-Process -Name python -ErrorAction SilentlyContinue
Remove-Item db.sqlite3 -ErrorAction SilentlyContinue
Remove-Item media -Recurse -Force -ErrorAction SilentlyContinue
uv run python manage.py migrate
uv run python manage.py createsuperuser
```

Do not run the removal commands against a shared, production, or valuable local
environment. The SQLite database and `media/` directory are ignored by Git and
must not be committed.
