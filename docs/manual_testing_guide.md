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

## 11. Test organization isolation

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

## 12. What is intentionally unavailable

The following are not defects at this milestone:

- No AI extraction or AI matching request.
- No deterministic shortlist yet.
- No candidate-profile extraction from CV text yet.
- No private CV download route.
- No OCR for scanned PDFs.
- No outreach workflow.

## 13. Final acceptance checklist

The current milestone is behaving correctly when all of these are true:

- `uv run python scripts/check.py` passes.
- Manual candidate entry and both CSV reports match the expectations above.
- Valid PDF and DOCX CVs extract successfully; unsafe fixtures are rejected.
- Recruiters can create direct-employer and client-associated vacancies.
- Requirements can be saved, confirmed, copied to a new version, and confirmed
  again without mutating history.
- Recruiters can open, pause, close, and reopen vacancies only through the
  documented lifecycle transitions.
- Cross-organization URLs do not disclose data.
- No AI key or live AI request is required.

## 14. Reset disposable local test data

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
