# Manual Testing Guide

This guide verifies the application from the Django foundation through
`PROD-005`, `INTAKE-001`, `EVAL-001` through `EVAL-003`, `DEMO-001`, and
`DEF-001`, and `CR-004`. Use only the
synthetic files in `manual_testing/fixtures` or other
invented data. Do not upload real candidate records or CVs to a development
machine merely for testing.

## 1. Prepare the local project

Open PowerShell in the project root (the directory containing `manage.py`):

```powershell
uv sync --extra dev --locked
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv run python manage.py migrate
uv run python scripts/check.py
```

Expected result:

- The shared quality gate finishes successfully.
- Django reports no migration drift.
- The ordinary test suite makes no live AI request.
- No OpenAI API key is required.
- The deployment-check subprocess supplies its own complete production security
  settings and therefore passes even though the local development `.env` keeps
  HTTPS redirect and secure cookies disabled.

The guarded copy command deliberately preserves an existing `.env`; never use an
unguarded `Copy-Item .env.example .env` against a configured project. A blank
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
   **Vacancies**, **Reviews**, **Jobs**, **AI usage**, **Privacy & audit**,
   **Django admin**, and **Sign out**.
5. Confirm the dashboard initially shows zero active candidates and zero open
   vacancies.
6. Select **Sign out** and confirm you return to the login page.

Expected security behavior:

- Logout is a POST action protected by CSRF, not a state-changing link.
- A signed-in user without any active membership receives a safe access page.
- An inactive user, organization, or membership cannot enter the workspace.

## 4. Test manual candidate entry

Open **Candidates** and select **Quick add**. Enter:

- Full name: `Arben Testi`
- Email: `arben.testi@example.test`
- Phone: `+383 44 111 222`
- Location: `Prishtina`
- Source name: `Synthetic manual test`
- Source reference: `MAN-001`
- Reason for storing data: `Not recorded`
- Consent: `Not recorded`
- Allowed contact: `Not confirmed`
- Privacy and contact notes: `Synthetic test record; no real person.`
- CV file: optionally select `synthetic-arben-testi-cv.pdf`

Expected result:

- The candidate is created and appears in the organization candidate list.
- The provenance record and optional validated private CV are created in the
  same action. An invalid CV rolls back the candidate and source instead of
  leaving a partial record.
- Not-recorded consent and not-confirmed contact remain explicit; neither is
  silently treated as approval.

Confirm the form also shows:

- **Source name:** `Where this candidate record came from.`
- **Source reference:** `Optional stable ID or reference from the original source.`
- **Delete or review on** wording for candidate, source, and attached-CV dates.

Leave all delete/review dates blank. Expected result: the app does not invent a
retention date when the organization has no configured retention policy.

Only the full name is required identity data. The prefilled source name and safe
not-recorded/unknown values can be accepted without completing every optional
contact, retention, or permission field. Use **Create candidates from CVs** for
the normal CV-first path instead of repeating quick-add for several people.

Repeat the entry using the same email or the same source reference.

Expected result: the app reports a possible duplicate and creates no second
candidate. A matching name by itself is not treated as a duplicate.

## 5. Test candidate CSV import

Open **Candidates** > **Import CSV**. The page also offers the exact header-only
template used by the application.

### Valid import

Upload `manual_testing/fixtures/candidate-import-valid.csv` and set:

- Source name: `Synthetic valid CSV test`
- Reason for storing data: `Not recorded`
- Consent: `Not recorded`
- Allowed contact: `Not confirmed`

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

## 6. Test reviewed bulk CV candidate intake

Open **Candidates** and confirm **Create candidates from CVs** is the primary
creation action. Select it and record the shared source details below. The same
flow supports one CV or several CVs:

- Source name: `Synthetic reviewed bulk intake`
- Reason for storing data: `Not recorded`
- Consent: `Not recorded`
- Allowed contact: `Not confirmed`
- Privacy and contact notes: `Synthetic fixtures only; no real people.`
- Candidate, source, and CV delete/review dates: leave blank for this test

Expected result: an open tenant-scoped batch is created. Its shared provenance
and retention values are visible before any candidate exists; none of these
values is inferred by AI.

Select these three files together in **Add CVs**:

- `synthetic-drita-shembull-cv.docx`
- `synthetic-arben-testi-cv.pdf`
- `rejected-invalid-signature.pdf`

Expected result:

- The valid DOCX and PDF become separate pending review rows.
- The invalid PDF is rejected independently and stores neither a review row nor
  private bytes; it does not roll back the valid files.
- Drita's proposed name, email, phone, and location come from local deterministic
  parsing and are editable. The page exposes no extracted CV text or storage
  path.
- Arben is visibly marked as a possible email/phone duplicate because section 4
  already created that candidate. The application does not merge or overwrite
  the existing record.

Before creating candidates, upload
`manual_testing/fixtures/candidate-cv-mapping.csv` under **Apply candidate
details from CSV**.

Expected result:

- Each row maps only to the pending CV whose `cv_filename` is an exact match.
- Drita and Arben's editable identity/source-reference fields use the CSV values.
- A missing filename, repeated CSV filename, duplicate pending filename, or
  invalid row appears as unresolved/invalid and is not guessed by name.
- The CSV report shows mapped, unresolved, and invalid counts. It does not create
  a candidate by itself.

Select only Drita's row. Keep **Queue only newly created CVs for background AI
profile drafts** checked, then select **Create selected candidates**.

Expected result:

- Exactly one candidate, one shared-provenance source record, and one private CV
  record are committed together for Drita.
- The created row no longer retains its temporary extracted text or staging file.
- A targeted background job contains only Drita's newly created CV. Run
  `uv run python manage.py run_background_worker --burst` to process it when an
  AI provider is configured; otherwise leave the job queued for section 24.
- Any resulting profile is a draft requiring individual evidence review and
  confirmation. No match decision or outreach action occurs.
- Selecting Arben for creation remains blocked as a duplicate. Use **Discard**
  on that row, or **Discard remaining intake items**, and confirm the pending
  temporary file, extracted text, and identity proposal are cleared without
  changing Drita or Arben.

Start another batch and upload `synthetic-drita-shembull-cv.docx` again.
Expected result: the exact tenant-local document is blocked before staging.
A member of another organization cannot open either batch URL or use its items.

Run the focused provider-free coverage:

```powershell
uv run pytest -q tests/test_candidate_unified_intake.py tests/test_candidate_bulk_intake.py tests/test_candidate_intake.py tests/test_candidate_documents.py tests/test_candidate_ai_extraction.py tests/test_background_jobs.py
```

### Batch-confirm clean profile drafts

After the background worker creates profile drafts, return to the intake batch
and select **Review profile confirmation**.

Expected result:

- The screen shows included and excluded counts before any confirmation.
- A clean evidence-validated draft with no ambiguity, sensitive-content flag,
  source change, duplicate conflict, or candidate-state exception is included.
- Pending/failed extraction, ambiguities, sensitive-content flags, changed CVs,
  inactive/deleting candidates, missing exact accepted-CV links, and already
  confirmed profiles are excluded with a bounded reason.
- Every available profile has an individual link and can be opened before the
  batch action.
- **Confirm all eligible profiles** is one explicit POST action. Each included
  profile separately becomes confirmed with the acting recruiter and timestamp;
  excluded drafts remain unchanged.
- The action publishes grounded profile facts only. It does not approve, reject,
  revisit, assess, contact, create outreach, or send anything for a candidate.

## 7. Test private CV upload and extraction

Open `Arben Testi`, select **Upload CV**, and upload
`synthetic-arben-testi-cv.pdf`.

Expected result:

- The upload succeeds.
- The candidate page shows filename, type, size, extraction status, and time.
- No extracted CV text or private storage path is displayed.
- A **Download original** link is available only inside the authenticated
  organization workspace.

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

### Private CV delivery

Select **Download original** for each accepted synthetic PDF and DOCX.

Expected result:

- The browser downloads the exact original file as an attachment instead of
  rendering it as a public page.
- The downloaded filename is the safe original basename. No opaque media/storage
  path appears in the page, URL, response headers, or filename.
- In browser developer tools, the response has the saved PDF/DOCX content type,
  `Content-Disposition: attachment`, `Cache-Control: private, no-store,
  max-age=0`, `X-Content-Type-Options: nosniff`, and a sandbox content-security
  policy.
- Signing out prevents access. A recruiter who lacks membership in the owning
  organization receives no candidate or document disclosure.
- Deleting the disposable candidate makes its former document URL unavailable
  and removes the stored bytes as described below.

The deterministic automated regression for active-content rejection, archive
hardening, cross-tenant access, byte-integrity checking, and private headers is:

```powershell
uv run pytest -q tests/test_candidate_documents.py
```

### Candidate deletion

Create a disposable synthetic candidate, add a provenance record, and upload one
of the synthetic CVs. Open the candidate and select **Request deletion**.

Expected result:

- A separate confirmation page explains that this first step freezes the
  candidate but does not purge data.
- Cancel returns to the unchanged candidate.
- Confirming the request returns to the candidate detail. Its source, document,
  and profile data still exist, but upload, extraction, and matching actions are
  unavailable.
- An organization administrator can cancel the request and restore the exact
  prior `Active` or `Inactive` status.
- The administrator can instead select **Review purge**, inspect a second
  irreversible confirmation, and explicitly select **Permanently purge
  candidate data**.
- The candidate no longer appears and its former detail URL returns `404`.
- Contact fields, provenance records, document rows, stored CV bytes, and
  extracted text are removed.
- Django admin retains only a non-identifying candidate tombstone and deletion
  timestamps. The privacy ledger separately records request and purge actor/time
  without copying candidate identity, contact, CV, or decision content.

## 8. Test vacancy creation and requirements version 1

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

## 9. Test confirmation and immutable corrections

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

## 10. Test blank confirmation protection

Create another vacancy, do not enter any structured requirements, return to its
detail page, and select **Confirm version 1**.

Expected result: confirmation is refused with a message asking for at least one
structured requirement. The version remains a draft.

## 11. Test vacancy lifecycle and dashboard count

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

## 12. Inspect skills, typed rules, and deterministic filtering

Use only synthetic evidence. Candidate skills can be published by confirming an
AI-extracted profile as described in section 17; Django admin remains useful for
precise manual test setup. Vacancy hard-constraint rules are managed in the
normal recruiter application.

1. Create or open an unconfirmed vacancy requirements draft in the normal app.
2. Enter `Python` and `Django` as must-have skills and `PostgreSQL` as a
   nice-to-have skill, then select **Save draft**.
3. Return to the draft editor. The **Typed hard-constraint rules** section must
   be visible below the normal requirements form.

You may use Django admin to inspect **Matching → Requirement skills**. Expected
result: the version has three ordered links. `Python` and `Django` are must-have;
`PostgreSQL` is nice-to-have. **Matching → Skills** contains one
organization-owned canonical record for each name. Changing case or surrounding
spaces in the draft does not create another skill, while `C`, `C#`, and `C++`
remain different skills.

### Canonical skill wording correction

Create a fresh draft using the vacancy text in
`manual_testing/fixtures/vacancy-description.txt`, or enter `Python development`
as a must-have skill. Save the draft and inspect its requirement skills.

Expected result:

- Recruiter-facing requirements retain `Python development` as the original
  source wording.
- The linked canonical skill is `Python`.
- A candidate with a grounded `Python` skill passes a typed required-skill rule
  based on that requirement and receives its Python shortlist points.
- Existing confirmed records that separately saved `Python` and `Python
  development` also match after regenerating the shortlist; no profile or
  vacancy re-extraction is required.
- `PYTHON DEVELOPMENT`, extra whitespace, and the controlled
  `Python-development` wording behave the same.
- `Java` does not match `JavaScript`, and unlisted phrases remain distinct rather
  than being guessed through substring or AI matching.
- The shortlist still displays the vacancy's original skill wording, the
  candidate's recorded wording, and evidence.

Run the focused provider-free regression:

```powershell
uv run pytest -q tests/test_skill_canonicalization.py tests/test_matching_models.py tests/test_matching_filtering.py tests/test_matching_shortlist.py tests/test_matching_staleness.py
```

To record synthetic candidate evidence, open **Matching → Candidate skills** and
add:

- Candidate: a synthetic candidate in the same organization
- Skill: the organization’s `Python` skill
- Source label: `Python`
- Evidence: `Built a synthetic Django API project.`
- Years experience: `3.0`

Cross-organization candidate, document, and skill combinations must be rejected.

In the normal draft editor, select **Add typed rule** and add:

- Rule type: `Required skill`
- Exact source wording: `Python is explicitly required.`
- Required must-have skill: `Python`

The app selects `Has skill`, assigns the next position, and fixes a missing fact
as **Keep for recruiter review**. Those internal fields are not recruiter-editable.

Add a second typed rule:

- Rule type: `Location`
- Exact source wording: `Candidate must be based in Prishtina`
- Required value: `Prishtina`

Expected result: both rules appear in the draft table. Edit the location rule,
save a different synthetic value, and then restore `Prishtina`. Open **Delete**
and select **Keep rule**. A GET of the confirmation screen must not delete data.

Try removing `Python` from the draft's must-have skills while the required-skill
rule still exists. Expected result: saving is rejected, the previous skill list
is preserved, and the page explains that the rule must reference a must-have
skill. Delete or edit the dependent rule before removing the skill.

Free-text values previously entered in the vacancy’s **Hard-constraint notes
(not executable)** box
remain recruiter notes. They are not silently converted into executable rules.

Before confirming, create three active synthetic candidates in the same
organization:

- `Synthetic Pass`: location `Prishtina`, with the recorded `Python` skill.
- `Synthetic Review`: blank location and no recorded `Python` skill.
- `Synthetic Fail`: location `Peja`, with or without the `Python` skill.

Confirm the requirements in the normal app. Expected result: the vacancy detail
page shows the confirmed typed-rule table without edit or delete actions. Opening
an old draft rule edit URL redirects back to the read-only vacancy. Create a
correction draft and confirm that the normalized links and typed rules were copied
instead of changing history; continue this test with the original confirmed
version.

Return to the vacancy detail page and select
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

## 13. Test deterministic scoring and bounded shortlist

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
- Every must-have skill has two weight units and every nice-to-have skill has one;
  the combined weights are apportioned to exactly `100.00` points.
- Algorithm v3 matches controlled canonical skill identities while preserving
  the existing two-to-one weighting and original evidence display.
- With two must-have and two nice-to-have skills, a candidate matching one of
  each receives `50.00`: `33.33` must-have points plus `16.67` nice-to-have
  points.
- With five must-have and two nice-to-have skills, the must-have rows receive
  `16.67` or `16.66` each and the nice-to-have rows receive `8.33` each. The
  possible points total exactly `100.00`, and one nice-to-have can no longer be
  worth more than one must-have.
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

## 14. Test stale-result detection and regeneration

Keep the shortlist from the previous section open in one browser tab.

### Candidate matching-input change

In Django admin, change one active synthetic candidate's `location`, recorded
skill, experience years, or skill evidence. Alternatively, add another active
synthetic candidate to the same organization or confirm a new candidate-profile
draft containing a matching fact. Refresh the saved shortlist.

Expected result:

- A prominent **This shortlist is stale** warning appears.
- The warning says that the active candidate pool or candidate matching evidence
  changed.
- The saved ranks, scores, and evidence snapshot remain unchanged; no automatic
  recomputation occurs.
- The vacancy and filter pages label the latest historical link **(stale)**.

Changing only a candidate email, phone, source/consent metadata, or retention
date does not make the deterministic result stale because those values are not
filtering, scoring, or score-explanation inputs.

### Vacancy requirements change

Select **Create correction draft**, change a must-have or nice-to-have skill,
save, and confirm the new requirements version. Open the older shortlist again.

Expected result:

- The old run remains available under its original requirements version.
- It is labelled stale because the vacancy's confirmed matching requirements
  changed.
- Confirming or editing only a draft does not replace the current matching input;
  confirmation is the point at which the old run becomes stale.

A shortlist created with scoring algorithm v1 or v2 is also labelled stale after
this upgrade. Its saved score remains unchanged as historical evidence, and
regeneration creates a separate v3 run using controlled canonical skill matching
and the existing per-skill 2:1 weighting.

### Regeneration

From the stale warning, select **Generate current shortlist**.

Expected result:

- A separate run is created using the current confirmed requirements and active
  candidate matching inputs.
- The new page shows **Current result**.
- Opening the earlier run still shows its stale warning and original history.
- No AI request, approval/rejection, outreach, or automatic hiring action occurs.

## 15. Test organization isolation

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

## 16. Test AI-assisted vacancy extraction

This is the first optional live-provider workflow. Ordinary tests and all
deterministic features still work without an API key.

1. Configure a valid `OPENAI_API_KEY` and supported `OPENAI_MODEL` in `.env`, then
   restart the development server.
2. Create a vacancy from `manual_testing/fixtures/vacancy-description.txt` or open
   an existing editable requirements draft.
3. Before clicking the AI action, note any structured values already in the
   draft. **Extract with AI** replaces these draft fields after a successful
   response.
4. Select **Extract with AI** once and wait for the request to finish.

Expected result:

- The app returns to the same editable version and reports that AI suggestions
  were saved to the draft.
- The version remains **Draft** and its method becomes **AI assisted**.
- Skills, experience, location, work mode, languages, education, certifications,
  employment type, non-executable hard-constraint notes, and ambiguities are
  populated only when supported by the source.
- Missing information stays blank, null, or **Unknown** instead of being guessed.
- Must-have and nice-to-have skills do not overlap.
- No typed hard-constraint rule is created automatically. Add any executable rule
  deliberately in the typed-rule editor.
- You can edit every suggestion before using the separate confirmation action.

To test bounded failure behavior, remove the API key, restart the server, and run
**Extract with AI** on a draft containing a recognizable manual summary.

Expected result:

- A safe configuration message appears without provider details, prompts, or raw
  output.
- The manual summary and all other draft values remain unchanged.
- Confirmed versions do not expose the extraction action, and the extraction URL
  rejects a confirmed version.

Do not use real candidate data for this vacancy-only test. The request produces a
safe usage event as described in section 22.

## 17. Test AI-assisted candidate-profile extraction

This is an optional live-provider workflow. Use only a synthetic candidate and
one of the supplied synthetic CVs. Ordinary tests and deterministic matching
still work without an API key.

1. Configure a valid `OPENAI_API_KEY` and supported `OPENAI_MODEL` in `.env`, then
   restart the development server.
2. Open a synthetic candidate whose PDF or DOCX CV shows extraction status
   **Succeeded**.
3. In the CV table, select **Extract profile** once and wait for the request.
4. Review the new numbered profile page before selecting **Confirm profile**.

Expected draft result:

- A new profile version is created as **Draft** and identifies its source CV by
  safe filename and hash only.
- The review shows bounded structured employment, skills, location/work mode,
  languages, education, certifications, employment preferences, availability,
  exact source excerpts, and explicit ambiguities when present.
- Unsupported fields remain **Unknown** or empty. The profile contains no hiring
  recommendation or candidate assessment.
- Candidate name, email, phone, URL/contact lines, sensitive prefixed content,
  raw extracted CV text, the prompt, storage path, and raw provider output are
  absent from the review page.
- Creating the draft alone does not publish candidate skills, change deterministic
  filtering, or mark an existing shortlist stale.
- With `synthetic-arben-testi-cv.pdf`, confirm **Automated testing** is included
  with the profile sentence mentioning `automated testing systems`, even though
  it is outside the Skills heading. Confirm **pytest** is also a separate skill
  with its own exact experience excerpt.
- A tool does not imply a broader competency. If a synthetic CV mentions only
  `pytest` and never states automated testing, the profile must not invent an
  **Automated testing** skill.

If the first schema-valid response paraphrases an excerpt or attaches a fact to
the wrong excerpt, the application automatically makes one correction request
using the same redacted CV. When this occurs, the success message says that the
source evidence was corrected automatically. Confirm that:

- only the corrected, fully grounded profile becomes a draft;
- the evidence shown is still copied from the CV rather than loosely paraphrased;
- the failed first request and successful correction appear as separate safe AI
  usage events; and
- you still inspect and confirm the profile separately.

The provider may return valid evidence on its first attempt, so the deterministic
automated test for this path is:

```powershell
uv run pytest -q tests/test_candidate_ai_extraction.py
```

Select **Confirm profile** only after checking every fact against its displayed
source excerpt.

Expected confirmed result:

- The version becomes **Confirmed**, records the recruiter and time, and cannot
  be confirmed or edited again.
- Grounded skills become inspectable candidate-skill evidence. Existing manual
  assertions remain intact.
- Confirmed location, work mode, language, education, certification, and
  employment-type facts can satisfy their exact deterministic rules. Missing or
  non-matching profile facts remain **Needs review**, not automatic failure.
- Any saved shortlist affected by the newly published profile is labelled stale;
  its historical score remains unchanged until a recruiter regenerates it.

Run **Extract new version** from the confirmed page. Confirm that the next result
is a higher-numbered draft and does not replace the current confirmed profile.
After confirming the newer version, only older AI-published skills from that same
CV are replaced; manually recorded skills remain.

To test bounded failure, remove the API key, restart the server, and select
**Extract profile** again.

Expected result:

- A safe error appears on the candidate page without provider text, prompt,
  contact data, or raw output.
- If the one automatic evidence correction also fails, the error identifies only
  a safe schema area such as `skill item 1`; it exposes no fact or excerpt and
  makes no third request.
- No new profile version or candidate skill is created.
- Non-CV, failed/textless, deleted, changed-during-request, and oversized source
  documents are also rejected without partial persistence.

Each actual request produces a safe usage event as described in section 22.

## 18. Test evidence-based AI match assessment

This is an optional live-provider workflow for one shortlisted candidate at a
time. Use a synthetic candidate whose latest AI profile is confirmed and a
vacancy with confirmed requirements.

1. Configure a valid `OPENAI_API_KEY` and supported `OPENAI_MODEL` in `.env`, then
   restart the development server.
2. Generate a fresh deterministic shortlist after the candidate profile and
   vacancy requirements are confirmed.
3. Open the shortlist and locate the candidate. Record the deterministic rank,
   score, and filter outcome.
4. Select **Generate AI assessment** once and wait for the request.

Expected result:

- Only that candidate receives **AI assessment version 1**. Other shortlist
  entries remain usable and unchanged.
- The result shows a separate AI score and application-derived red, amber, or
  green band, evidence-linked matching requirements, gaps, uncertainties, and a
  recruiter review focus.
- Every confirmed requirement appears once in exactly one result group. Matches
  and gaps display candidate evidence from the confirmed profile. Missing support
  is shown as uncertainty rather than an invented fact or automatic rejection.
- The deterministic rank, score, filter outcome, and shortlist membership are
  unchanged. There is no approve/reject, hiring, ranking, contact, or outreach
  action.
- Candidate email/phone, raw CV text, prompt content, provider output, and vacancy
  identity are absent from the assessment display.

Select **Generate new assessment version** for the same candidate. Confirm that
version 2 is added and version 1 remains inspectable and unchanged.

To test safeguards:

- Confirm a newer profile or change a matching input, then reopen the old run.
  It is stale and exposes no assessment action until a fresh shortlist is
  generated.
- Use a shortlisted synthetic candidate without a confirmed profile. The page
  explains that profile confirmation is required and exposes no action.
- Remove the API key, restart, and request an assessment from a current eligible
  entry. A bounded error appears; the shortlist and any earlier assessment
  versions remain intact, and no partial version is created.

Safe request metadata or a bounded failure category is recorded as described in
section 22. Whole-shortlist background assessment is tested in section 24.

## 19. Test the recruiter assessment review workflow

After generating assessments for at least two synthetic shortlisted candidates,
open **Reviews** in the organization navigation.

Expected queue behavior:

- **Decision pending** is selected initially and shows the latest assessment per
  shortlist entry that still needs an individual human decision, not every
  historical version.
- Changed shortlist/profile inputs appear before current items. Gaps,
  uncertainties, confirmed-profile ambiguities, and unknown hard-filter facts
  are visible as compact counts.
- **Needs focus** isolates evidence exceptions, **Changed inputs** isolates
  assessments whose evidence boundary is no longer current, and **All** also
  displays routine or already-decided latest assessments.
- Candidate contact details, raw CV text, prompts, provider responses, and
  protected characteristics do not appear.

Open **Inspect and decide** for one queue item.

Expected detail behavior:

- The AI score and deterministic score remain separate.
- Matching requirements, evidence-backed gaps, uncertainties, vacancy evidence,
  candidate evidence, confirmed-profile ambiguities, and recruiter review focus
  are individually inspectable.
- Every immutable assessment version for that shortlist entry is linked. Opening
  an older version does not alter it.
- If candidate or vacancy matching evidence changed, the page clearly labels the
  assessment historical and explains why.
- Decision controls appear only for the latest assessment while its shortlist
  and confirmed profile remain current. Decision behavior is tested next.

Confirm a new candidate profile or change a deterministic matching fact, then
return to **Reviews**. Confirm that the item appears under **Changed inputs** and
the saved assessment remains readable as history. Confirm that no profile is
re-extracted or reconfirmed merely by opening either review screen.

## 20. Test individual recruiter decisions

Use a current latest assessment from section 18 and select **Inspect and decide**.
The page must show the full evidence before the decision form.

1. Select **Approve**.
2. Enter notes such as `Evidence inspected; suitable for the next recruiter-controlled step.`
3. Select **Record decision**.

Expected result:

- **Decision version 1** is added with **Approve**, the exact notes, your username,
  and a timestamp.
- The decision references the exact assessment version shown on the page.
- The assessment, AI score, deterministic score, evidence, rank, and shortlist
  membership remain unchanged.
- The candidate leaves the default **Decision pending** queue and appears under
  **All** with **Decision: Approve**.
- No outreach draft is created, approved, copied, exported, or sent.

Record another decision from the same current assessment, choosing **Revisit
later** with new notes. Expected result: decision version 2 is appended while
version 1 remains visible and unchanged. Repeat with **Reject** on another
synthetic candidate to confirm all three explicit choices work. No decision is
automatic, and no score or traffic-light band selects a decision for you.

Test validation and currentness:

- Submit without notes. The app reports that both a decision and recruiter notes
  are required and creates no decision.
- Open an older assessment version after a newer one exists. The page shows the
  decision history but says to open the latest assessment before recording a new
  decision.
- Change a matching fact or confirm a newer profile, then open the previous
  assessment. The page marks the evidence boundary historical and requires a
  current shortlist and assessment before another decision.
- Sign in as a member of another organization and try the copied decision URL.
  The route returns `404` and discloses no candidate, assessment, notes, or actor.

In Django admin, open **Review decisions** under **Matching**. Confirm records are
read-only and show the shortlist entry, exact assessment, decision version,
choice, notes, actor, and timestamp. Candidate deletion removes that candidate's
decision history together with the private shortlist/assessment history.

## 21. Test the outreach draft review workflow

Return to a current latest assessment from section 19. If its latest decision is
**Revisit later** or **Reject**, first record a new individual **Approve** decision
with non-blank recruiter notes. The outreach panel must use only the latest
decision; an older approval never authorizes a draft after a later correction.

Select **Generate outreach draft**.

Expected result:

- The action is POST-only and creates outreach draft version 1 only from the
  exact latest approved decision while the assessment, confirmed profile, and
  shortlist inputs remain current.
- The resulting page shows a bounded subject and plain-text body, the candidate
  name, source decision version, generating recruiter, and timestamp.
- The page clearly labels the result **Generated only — not approved or sent**.
- Editing is available, but final approval, copy, and export remain unavailable
  until an explicitly permitted candidate source exists. There is no send,
  email, ATS, or platform-messaging action.
- The recruiter approval notes, candidate email/phone, raw CV, gaps,
  uncertainties, protected characteristics, prompt, and raw provider response
  were not supplied to or returned from the AI workflow. The application inserts
  the candidate name after validating a provider-generated name placeholder.
- The approved decision and assessment remain unchanged. Generating a draft does
  not make a hiring decision, alter scores/rank, or contact the candidate.

Return to the assessment review page and select **Generate outreach draft**
again. Expected result: version 2 is added while version 1 remains linked and
unchanged. Both versions show their exact source decision, actor, and timestamp.

### Edit without overwriting history

Open the latest draft, select **Edit into new version**, change the subject and
body, and save.

Expected result:

- A new numbered recruiter-edited version is created with the prior version as
  its parent, your username, and a timestamp.
- The generated version remains unchanged and inspectable.
- The edited version is not finally approved, even if its parent was approved.
- Blank values, overlong values, and unsafe control characters are rejected
  without creating a version.

### Establish allowed contact and approve the exact version

The synthetic candidate created earlier has **Not confirmed** allowed contact and
no recorded reason. Confirm that final approval is blocked and the page explains
both requirements. In Django admin, edit one of that candidate's synthetic
**Candidate sources** and set the underlying stored values shown below (the
normal recruiter page displays the plain labels in parentheses):

- Lawful basis: `Legitimate interests` (**Reason for storing data**)
- Consent status: `Not required` (**Consent**)
- Contact permission: `Permitted` (**Allowed contact: Future roles allowed**)
- Permission notes: `Synthetic manual test permission only.`

Return to the latest outreach draft, add approval notes, check the explicit
source/consent/allowed-contact attestation, and select **Approve exact draft**.

Expected result:

- Approval binds only the exact displayed subject and body.
- The approval records notes, your username, and a timestamp.
- The draft is labelled approved but still **not sent**.
- Missing notes or an unchecked attestation creates no approval.
- Application only, Do not contact, or Not confirmed allowed contact blocks
  approval. A missing reason also blocks approval.
- When **Consent** is selected as the reason for storing data, Consent must be
  **Given**. Not recorded, Not required, or Withdrawn blocks approval for that
  consent-based source.

Open the candidate page before approving and confirm the source table displays
Source name, Source reference, Reason for storing data, Consent, Allowed contact,
and Delete or review on without the older legalistic field labels.

### Copy and export only after approval

Select **Copy approved text**, paste into a local scratch editor, and confirm the
subject and body exactly match the approved version. Select **Export approved
text** and open the downloaded UTF-8 `.txt` file.

Expected result:

- Both actions are explicit POST actions and expose only the exact approved,
  current draft.
- The download uses a generic, non-identifying filename and a private no-store
  response.
- The action history records copy/export, exact draft version, your username,
  and timestamp.
- Nothing is sent and no recipient is selected.

Edit the approved draft into another version. The new version must be
unapproved, and the older approval must not authorize copying or exporting the
new text. Approve the new exact version before those controls return.

Finally, change the stored contact permission to **Withdrawn** (**Do not
contact**), refresh the draft page, and confirm copy/export is blocked. A direct
POST to either action must return no draft text or file. Restore **Future roles
allowed** if continuing other tests.

Test the authorization and currentness guards:

1. Record **Revisit later** or **Reject** as a newer decision. Confirm the older
   approval no longer exposes an eligible generation action.
2. Record a new approval, then change a deterministic candidate fact or confirm
   a newer profile. Confirm the historical approval cannot generate a draft and
   the page requires a current shortlist, assessment, and approval.
3. Sign in as a member of another organization and try a copied generation or
   draft-detail URL. It returns `404` without disclosing the candidate or draft.
4. Remove the API key, restart, and generate from an otherwise eligible approval.
   A bounded error appears, no partial draft is created, and existing versions
   remain unchanged.
5. After generating a draft, record a newer reject/revisit decision or change a
   matching input. Confirm editing, final approval, copy, and export are blocked
   while the historical draft remains inspectable.

In Django admin, open **Outreach drafts**, **Outreach draft approvals**, and
**Outreach draft actions** under **Outreach**. Confirm all records are read-only.
Deleting a disposable synthetic candidate removes its drafts, approvals, and
actions with the private shortlist, assessment, and decision history.

Run the focused provider-free CR-005 coverage:

```powershell
uv run pytest -q tests/test_candidate_privacy_fields.py tests/test_candidate_intake.py tests/test_candidate_bulk_intake.py tests/test_candidate_unified_intake.py tests/test_outreach_workflow.py tests/test_audit_retention.py
```

## 22. Inspect safe AI usage events

Sign in to Django admin and open **AI usage events** under **Audit** after running
at least one successful and one deliberately failed synthetic AI action from
sections 16 through 18 or section 21.

Expected successful event:

- Organization, actor, workflow, generic target/result types and numeric IDs,
  schema version, succeeded status, request ID, model, duration, retry count,
  optional token counts/cost, and start/completion times are visible.
- The result type matches the workflow: vacancy requirements, candidate profile,
  match assessment, or outreach draft. Outreach uses a generic review-decision
  target and outreach-draft result ID, never recruiter notes or candidate data.
- The record has no edit, add, or delete action.

Expected failed event:

- Configuration, unavailable-provider, invalid-response, generic-request, or
  application-validation failure is represented by a bounded code and stage.
- A failure before a validated response has no invented request/model/token/cost
  values. A completed response rejected by application validation may retain its
  safe operational metadata.
- Provider messages, exception details, validation text, prompts, source vacancy
  descriptions, CV text, candidate names/contact values, and raw responses are
  absent.

Submit an invalid local action that is rejected before gateway construction—for
example, extraction from a confirmed requirements version. Confirm that no usage
event is created because no AI attempt occurred.

Editing, final approval, copy, and export are local human actions and therefore
must not create AI usage events.

## 23. Test privacy audit, retention review, and minimization

Open **Privacy & audit** in the organization navigation.

Expected result:

- The summary distinguishes pending deletion requests, active/inactive candidate
  records whose retention date is due, missing candidate retention dates, and
  deleted-record minimization issues.
- Pending requests show candidate identity only where needed for an individual
  deletion decision. Only an organization administrator sees **Review purge**.
- Candidate, source, and document retention exceptions are individually linked
  for review. A due date is shown as a policy-review signal, not legal advice or
  an automatic purge instruction.
- Privacy events show controlled action, generic object type/ID, actor, and time.
  Workflow summaries show safe IDs/status/version/actor information for AI
  attempts, CSV-created source records, assessments, recruiter decisions,
  outreach approvals, and copy/export actions.
- The page contains no source names/references, permission notes, contact fields,
  CV text, prompts, raw AI responses, recruiter decision notes, approval notes,
  or outreach subject/body.
- A member of another organization receives `404` and no names or counts from
  this organization.

### Retention command

First run a read-only report with a fixed synthetic date:

```powershell
uv run python manage.py process_retention --as-of 2026-08-15 --organization northstar-test
```

Expected result: the command prints only the organization slug and aggregate
candidate count. It prints no candidate name or contact value and explicitly
says it is a dry run. No status changes.

Then create a disposable active or inactive candidate whose candidate-level
retention date is on or before the test date and run:

```powershell
uv run python manage.py process_retention --as-of 2026-08-15 --organization northstar-test --apply
```

Expected result: the candidate becomes **Deletion requested**, appears in the
dashboard queue, and receives a system retention-expiry audit event. No source,
document, candidate, or stored-file data is purged. Running the same command
again reports zero newly due candidates and creates no duplicate event.

Source- and document-level expiry remain visible exceptions for individual
review; this command intentionally stages only candidate-level expiry.

Run the focused automated coverage:

```powershell
uv run pytest -q tests/test_audit_retention.py tests/test_candidate_documents.py tests/test_vacancy_intake.py
```

### Organization lifecycle policy (CR-002)

Sign in as an organization administrator, open the organization dashboard, and
select **Open retention settings**.

Expected result:

- The dry-run shows separate counts for abandoned pending intake, completed
  jobs, obsolete shortlists, abandoned outreach chains, old metadata, and
  blocked records. It shows only counts/IDs and an estimated temporary-byte
  total, never CV text, contact data, decision notes, or outreach content.
- Defaults are 7/90/180/365 days with a 30-day organization recovery window.
- A recruiter membership receives `403`; a member of another organization gets
  no counts or object access.
- Enabling **Pause all scheduled deletion (legal hold)** makes every purgeable
  count zero and moves otherwise eligible rows to blocked. A scoped exception
  protects either its entered object ID or the full group when ID is blank.
- Applying cleanup requires the exact phrase `PURGE ELIGIBLE DATA`. A fresh or
  current shortlist, any run with a recruiter decision/outreach, and any outreach
  chain with final approval/copy/export remain untouched.

Preview the scheduled dependency cleanup without changing data:

```powershell
uv run python manage.py process_data_lifecycle --organization northstar-test
```

For disposable synthetic data only, apply the recalculated safe plan:

```powershell
uv run python manage.py process_data_lifecycle --organization northstar-test --apply --confirm "PURGE ELIGIBLE DATA"
```

From the retention page, review **Delete organization**. The exact phrase
`DELETE ORGANIZATION` immediately suspends access and sends the administrator to
the recovery page. Select **Restore access** before the displayed deadline and
confirm the workspace returns. Do not test expiry/purge against needed data.

The scheduled whole-organization command is dry-run by default:

```powershell
uv run python manage.py process_organization_deletions
```

Its apply form is intended for the supervised daily service after backup and
recovery procedures are verified:

```powershell
uv run python manage.py process_organization_deletions --apply --confirm "PURGE ORGANIZATIONS"
```

Run the CR-002 automated coverage:

```powershell
uv run pytest -q tests/test_data_lifecycle.py tests/test_audit_retention.py tests/test_dashboard.py tests/test_organization_permissions.py tests/test_background_jobs.py tests/test_matching_shortlist.py tests/test_outreach_workflow.py
```

## 24. Test background profile and whole-shortlist processing

Start a second PowerShell window in the project root. Keep the web server in the
first window. For a development walkthrough, process all currently queued work
and exit after each queue action:

```powershell
uv run python manage.py run_background_worker --burst
```

For an ordinary long-running worker, omit `--burst`. `--once` processes at most
one target, and `--job 12` limits either mode to job 12.

### Batch profile extraction and reusable profiles

1. Ensure at least two active synthetic candidates have successfully parsed CVs.
2. Confirm that one CV already has a draft or confirmed profile and one newest CV
   has no profile version.
3. Open **Candidates** and select **Queue pending profile extraction**.
4. Open the queued job, run the worker command, then refresh the job page.

Expected result:

- Only the newest successful, unprofiled CV per active candidate is queued.
- A CV with any existing draft or confirmed profile is reused and is not sent to
  AI again. Uploading a corrected CV creates a new eligible source.
- Each successful target links to an individually inspectable candidate-profile
  draft. No draft is confirmed and no matching skill is published automatically.
- Selecting the same queue action before inputs change returns the same job and
  creates no duplicate target or routine AI request. When nothing is pending, the
  app reports that safely instead of creating an empty job.

Inspect exception drafts individually. For CV-first intake batches, the intake's
**Review profile confirmation** screen can explicitly confirm all clean eligible
drafts together after showing included/excluded counts. Every result still has
its own confirmed profile version, actor, timestamp, and detail page; exceptions
remain individual.

### Whole-shortlist assessment and exception isolation

1. Open a current deterministic shortlist containing synthetic candidates.
2. Leave at least one entry without a confirmed profile if you want to exercise
   the exception path.
3. Select **Assess whole shortlist** and open the created job.
4. Run the worker command and refresh the job page.

Expected result:

- There is one isolated task for every shortlist entry. Candidates with current
  confirmed profiles receive evidence-based assessments; a missing confirmed
  profile appears as **Needs attention** and does not block other candidates.
- An assessment already saved for the exact shortlist entry, confirmed profile,
  and requirements snapshot is reused without another AI request.
- Job totals show succeeded, needs-attention, and failed targets. Candidate names
  and result links are resolved only in the authorized workspace; operational
  records and worker output do not copy CV, contact, prompt, response, decision,
  or outreach content.
- Assessment links open the existing individual review detail. No candidate is
  approved, rejected, revisited, contacted, or sent outreach automatically.

If a provider failure is available in a safe development configuration, confirm
that one target becomes **Failed** while later targets still run. Select **Retry
exceptions**, rerun the worker, and confirm only failed or skipped targets gain
another attempt. Successful targets remain complete. A worker interrupted while
a target is running can reclaim it after its lease expires; if the domain result
was already saved, recovery marks it reused without another AI call.

Run the focused provider-free coverage:

```powershell
uv run pytest -q tests/test_background_jobs.py tests/test_candidate_ai_extraction.py tests/test_match_ai_assessment.py tests/test_matching_staleness.py tests/test_recruiter_review.py tests/test_review_decisions.py tests/test_outreach_workflow.py
```

## 25. Test organization AI usage reporting

After creating successful and deliberately failed synthetic AI attempts in
sections 16 through 18, 21, or 24, open **AI usage** in the organization
navigation.

Expected result:

- The default report covers the past 30 days and all workflows. The period can
  be changed to 7, 30, or 90 days or all time, and the workflow filter can select
  vacancy requirements, candidate profiles, match assessments, or outreach
  drafts.
- Attempts, successes, failures, pending attempts, success rate, total/input/
  output tokens, estimated cost, average latency, and retry totals agree with the
  safe usage records inside the chosen boundary.
- Workflow and model tables, safe failure categories, and the daily trend use
  organization-scoped aggregate data. The daily table is bounded to the most
  recent 90 displayed days even for an all-time report.
- Provider metadata that was not supplied is displayed as unavailable (`—`) and
  included in the coverage counts. A failed request without provider metadata
  does not invent zero tokens, zero cost, a model, latency, or retry data.
- Pending attempts older than 15 minutes are counted separately for operational
  review. Pending work is not treated as either success or failure.
- The report contains no request IDs, prompts, raw responses, source descriptions,
  CV text, candidate names/contact data, recruiter notes, decision content, or
  outreach subject/body.
- A member of another organization receives `404` for a copied report URL and
  sees none of this organization's totals.

Run the focused provider-free coverage:

```powershell
uv run pytest -q tests/test_ai_usage_reporting.py tests/test_ai_usage_events.py tests/test_audit_retention.py
```

## 26. Test production checks and health endpoints

The ordinary quality gate now collects static assets under an isolated synthetic
production configuration before running Django's warning-strict deployment
check. It does not connect to a production database or provider.

Run the focused provider-free coverage:

```powershell
uv run pytest -q tests/test_environment.py tests/test_production_operations.py tests/test_deployment_artifacts.py tests/test_foundation.py
```

Start the development server and open these URLs:

```text
http://127.0.0.1:8000/health/live/
http://127.0.0.1:8000/health/ready/
```

Expected result:

- Both return only `{"status": "ok"}` with `Cache-Control: no-store` while the
  development database is available.
- Liveness does not query application data. Readiness performs only `SELECT 1`.
- A database outage makes readiness return HTTP 503 with
  `{"status": "unavailable"}` and no connection, credential, path, candidate,
  or exception details.
- Running `uv run python manage.py check_production` in development fails safely
  because that command is reserved for an actual production-configured runtime.

In an isolated staging environment, follow `docs/deployment.md`: configure
PostgreSQL and persistent private media, run migrations and `collectstatic`, then
run:

```powershell
uv run python manage.py check --deploy --fail-level WARNING
uv run python manage.py check_production
```

Expected staging result: both pass. The runtime command verifies PostgreSQL,
migration state, collected CSS, and a private-media save/read/delete round trip.
It prints only controlled check names. Verify the web service, continuous worker,
and retention timer are separately supervised and confirm the reverse proxy has
no public `/media/` route.

Never point a staging test at production data or media. Backup and restore drills
must use an isolated destination as described in the deployment guide.

## 27. Run the optional synthetic live gateway smoke test

This developer test is separate from the browser workflows and ordinary quality
gate. It may incur one small provider charge. It sends no candidate, vacancy, CV,
contact, database, or other private content.

After configuring a valid provider key and model in `.env`, run from PowerShell:

```powershell
$env:RUN_LIVE_AI_SMOKE = "1"
uv run pytest -q -m live_ai live_tests/test_ai_gateway_live.py
Remove-Item Env:RUN_LIVE_AI_SMOKE
```

Expected result: `1 passed`, with a validated `status=ok` structured result and
safe request metadata. Without the environment switch, the same explicit command
reports `1 skipped`. The ordinary `uv run pytest` and
`uv run python scripts/check.py` commands never collect `live_tests` because the
configured test path is only `tests`.

Never edit this smoke test to send real recruitment data. A live failure does not
change any candidate, vacancy, profile, assessment, or audit record because the
test calls only the application gateway contract.

## 28. Load and inspect the EVAL-001 synthetic dataset

This provider-free test creates a separate organization containing exactly 20
invented candidates, generated private DOCX CVs, grounded confirmed profiles, 3
invented vacancies, and 3 already-verified deterministic shortlists. Replace
`admin` below with an existing active Django username:

```powershell
uv run python manage.py load_evaluation_dataset --username admin --organization-slug synthetic-eval-001
```

Expected command result:

- `20 candidates, 3 vacancies, and 3 verified shortlists` is reported.
- No API key, provider request, usage event, assessment, decision, outreach
  draft, or send action is created.
- Running the same command with the same organization slug is refused without
  changing the existing fixtures. Use a new slug for a separate clean run.

Sign in as that user and select **Synthetic Evaluation —
eval-001.synthetic-multirole.v1**. Confirm **Candidates** contains 20 obvious
`Synthetic Candidate` records. Each candidate has one private DOCX, one
confirmed source-grounded profile, no email or phone, and a restricted-contact
synthetic source.

Open each vacancy and its latest deterministic shortlist. The first five rows
must match the source references and scores below; the candidate source
reference contains the displayed `Cxx` code:

| Vacancy | Expected top five |
| --- | --- |
| Synthetic Senior Django Backend Engineer | C01 100.00, C02 85.72, C03 71.43, C04 71.42, C14 57.14 |
| Synthetic Data Analyst | C06 100.00, C07 85.71, C09 71.43, C10 71.43, C08 57.14 |
| Synthetic React Frontend Engineer | C11 100.00, C12 85.72, C14 85.72, C13 71.43, C15 57.15 |

The management command generates private media. Use only a disposable local or
isolated evaluation database/storage location. It never deletes or replaces an
existing organization. The complete frozen data and relevance judgments are in
`evaluation/datasets/eval-001.json`; do not silently adjust them to make a later
measurement look better.

Run the focused provider-free coverage:

```powershell
uv run pytest -q tests/test_evaluation_dataset.py tests/test_matching_shortlist.py tests/test_matching_staleness.py
```

## 29. Measure EVAL-002 ranking quality separately

Run the content-minimized provider-free report against the organization loaded
in the previous section:

```powershell
uv run python manage.py measure_evaluation_dataset --username admin --organization-slug synthetic-eval-001
```

Expected initial result:

- Each V01–V03 deterministic line reports `nDCG@5`, `precision@5`, and
  `expected-top overlap@5`.
- The deterministic macro reports `nDCG@5 1.0000`, `precision@5 0.9333`, and
  `expected-top overlap@5 1.0000` for the unchanged frozen dataset.
- AI coverage is `0/60` immediately after loading EVAL-001, and every
  AI-assisted metric is explicitly unavailable.
- The command says that rankings were measured separately, no scores were
  blended, and no AI request was made.
- The output contains no candidate name, email, phone, CV text, evidence,
  prompt, raw response, decision, or outreach content.

Confirm that the strict AI gate reports the same results and then exits with an
incomplete-coverage error; it must not generate the missing assessments:

```powershell
uv run python manage.py measure_evaluation_dataset --username admin --organization-slug synthetic-eval-001 --require-complete-ai
```

To exercise real AI-assisted coverage, intentionally queue **Assess entire
shortlist** for one or more evaluation vacancies and run the separately
configured background worker. This is optional, requires valid provider
configuration, and may incur provider cost. Partial coverage must continue to
show AI quality as unavailable for that vacancy. Only after all 20 current
entries for every vacancy have current assessments may the command report the
three AI-assisted vacancy metrics and macro. Every assessment remains
individually inspectable and still requires a separate recruiter decision.

Machine-readable output is available without extra side effects:

```powershell
uv run python manage.py measure_evaluation_dataset --username admin --organization-slug synthetic-eval-001 --format json
```

Run the focused provider-free automated coverage:

```powershell
uv run pytest -q tests/test_evaluation_measurement.py tests/test_evaluation_dataset.py tests/test_matching_shortlist.py tests/test_matching_staleness.py tests/test_match_ai_assessment.py
```

## 30. Review EVAL-003 assessment explanations safely

Immediately after EVAL-001 is loaded, run the provider-free read-only review:

```powershell
uv run python manage.py review_evaluation_explanations --username admin --organization-slug synthetic-eval-001
```

Expected initial result:

- Coverage is `0/60 current assessments` and status is `unavailable`.
- Clean and flagged counts are both zero; missing coverage is not called clean.
- The command says no AI request was made and no score, assessment, decision, or
  outreach changed.
- The output contains no candidate name, email, phone, CV text, evidence,
  provider-authored explanation, prompt, raw response, recruiter decision, or
  outreach content.

Confirm that both strict gates report the same safe result and then fail. Neither
command generates the missing assessments:

```powershell
uv run python manage.py review_evaluation_explanations --username admin --organization-slug synthetic-eval-001 --require-complete
uv run python manage.py review_evaluation_explanations --username admin --organization-slug synthetic-eval-001 --require-clean
```

To exercise complete real-provider coverage, first generate a current assessment
for all 20 entries in each of V01–V03 through **Assess entire shortlist** and the
separately configured background worker. This is optional and may incur provider
cost. Then rerun the review. Expected result:

- Coverage is complete only at `60/60`; any older assessment tied to a replaced
  confirmed profile or requirements version does not count.
- Every assessment is checked for exact requirement coverage and for stored
  requirement/evidence snapshots that still equal the current application-owned
  references.
- Explicit protected/sensitive attribute terminology and unsupported measured or
  quoted claims are flagged by safe issue code/location only.
- A match citation with no direct lexical support is flagged for individual human
  inspection; the command does not infer synonyms, change the assessment, or make
  a candidate decision.
- `--require-clean` succeeds only with complete coverage and zero flagged current
  assessments.

Machine-readable output is available without additional side effects:

```powershell
uv run python manage.py review_evaluation_explanations --username admin --organization-slug synthetic-eval-001 --format json
```

Newly generated match-assessment output that explicitly mentions a protected or
sensitive personal attribute is rejected before an assessment version is saved.
The failed AI attempt retains only the existing safe usage-event failure category;
provider text is not copied into the usage ledger.

Run the focused provider-free automated coverage:

```powershell
uv run pytest -q tests/test_evaluation_explanation_review.py tests/test_evaluation_measurement.py tests/test_evaluation_dataset.py tests/test_matching_shortlist.py tests/test_matching_staleness.py tests/test_match_ai_assessment.py
```

## 31. Run the DEMO-001 reproducible showcase

Use an existing active username and a new organization slug:

```powershell
uv run python manage.py prepare_demo --username admin --organization-slug synthetic-demo-001
uv run python manage.py runserver
```

Expected command result:

- 20 synthetic candidates, 3 vacancies, and 3 deterministic shortlists are
  reported.
- V01 has 20 current assessments and exactly 3 individual decisions: one
  approve, one reject, and one revisit. The remaining 17 decisions are pending.
- Exactly one unapproved outreach draft exists for the approved entry.
- The command explicitly says no provider/network request, final approval,
  copy, export, or send occurred and that contact remains restricted.
- Output contains no candidate name/contact data, CV/evidence text, assessment
  explanation, decision note, outreach body, prompt, or raw response.

Open each route printed by the command and follow `docs/demo.md`. In particular:

1. Confirm the deterministic shortlist is current and its score/evidence is
   inspectable.
2. Confirm **Reviews** with `?scope=all` shows 20 latest assessments, 17 pending,
   and one each approved, rejected, and revisit.
3. Open the approved assessment and confirm its exact evidence plus immutable
   individual decision remain inspectable.
4. Open the outreach draft and confirm **Not finally approved or sent** appears.
5. Confirm final approval is unavailable because Allowed contact is **Application
   only**; copy/export is also unavailable and no action event exists.

Run the command again with the same slug. Expected result: it refuses to
overwrite the organization and does not add candidates, documents, assessments,
decisions, or drafts. Use a new slug to repeat the demo.

Run the focused provider-free coverage:

```powershell
uv run pytest -q tests/test_demo.py tests/test_evaluation_dataset.py tests/test_evaluation_explanation_review.py tests/test_recruiter_review.py tests/test_outreach_workflow.py
```

## 32. What is intentionally unavailable

The following are not defects at this milestone:

- Manual candidate-skill entry still uses Django admin; confirmed AI profile
  skills are published through the normal candidate workflow.
- No external monitoring integration, alert delivery, usage export, or billing
  system. **AI usage** is a read-only in-application operational report;
  production deployment and monitoring guidance is documented by `PROD-005`.
- No OCR for scanned PDFs.
- No automatic outreach sending, recipient selection, email/ATS/platform
  integration, or normal-workspace contact-permission editor. Manual clipboard
  copy and plain-text export deliberately stop before transmission.

## 33. Final acceptance checklist

The current milestone is behaving correctly when all of these are true:

- `uv run python scripts/check.py` passes.
- EVAL-001 loads exactly 20 synthetic candidates and 3 synthetic vacancies into
  a new isolated organization, reproduces all frozen top-five scores, grounds
  every confirmed profile in its generated CV, and creates no AI request,
  decision, or outreach action.
- EVAL-002 reproduces separate deterministic metrics, reports partial or stale
  AI coverage as unavailable, measures only complete current AI-assessment
  ordering, never blends scores, makes no provider request, and exposes no
  private candidate or assessment content in its report.
- EVAL-003 audits only current stored assessment explanations, verifies exact
  application-owned evidence snapshots and requirement coverage, reports partial
  coverage as unavailable, flags protected or high-confidence unsupported
  content without copying it, makes no provider request or domain write, and
  rejects new explicit protected/sensitive output before persistence.
- DEMO-001 creates only an isolated synthetic workspace, refuses overwrite,
  makes no provider/network request, uses normal validated workflow services,
  preserves clean evidence-linked explanations, records decisions individually,
  stops at an unapproved contact-restricted draft, and sends nothing.
- Manual candidate entry and both CSV reports match the expectations above.
- Reviewed bulk intake validates each CV independently, proposes only local
  identity fields, applies CSV data only by exact `cv_filename`, blocks exact/
  identity duplicates, creates only selected rows transactionally, clears
  staging data, and queues only targeted profile drafts.
- Valid PDF and DOCX CVs extract successfully; unsafe fixtures are rejected.
- Authorized CV downloads return the exact integrity-checked original only as a
  private/no-store attachment; signed-out, cross-organization, mismatched,
  deleted, missing, or changed stored documents are not delivered.
- Recruiters can create direct-employer and client-associated vacancies.
- Requirements can be saved, confirmed, copied to a new version, and confirmed
  again without mutating history.
- Recruiters can open, pause, close, and reopen vacancies only through the
  documented lifecycle transitions.
- Candidate deletion first freezes an individually inspectable request; only a
  separate administrator purge removes private candidate content and CV files.
  Cancellation restores the prior state, while vacancy deletion hides the
  vacancy without destroying requirements history.
- Retention scheduling defaults to a content-free dry run and can only stage due
  candidate records for review; it never auto-purges. Source and document due
  dates remain individual review exceptions.
- The tenant-scoped privacy dashboard exposes minimized audit/workflow summaries,
  deletion and retention queues, and tombstone-integrity findings without copied
  CV, contact, prompt, response, note, or outreach content.
- Requirement skills normalize case and spacing without merging meaningful
  punctuation; controlled unambiguous aliases match at runtime without merging
  unsafe near-matches, and typed rules keep unknown candidate facts eligible for
  review.
- Deterministic filtering shows inspectable pass/fail/unknown rule outcomes and
  excludes only candidates with an explicit failed fact.
- Shortlist generation is POST-only, excludes explicit failures, shows the
  per-skill 2:1 weighting and evidence, persists version-labelled history, and
  never exceeds 20 entries.
- Relevant candidate or confirmed-requirements changes clearly mark older runs
  stale; regeneration creates a separate current run without rewriting history.
- Confirmed matching definitions cannot be edited; correction drafts copy them.
- AI vacancy extraction is POST-only, writes only to a draft, preserves explicit
  unknowns, creates no executable typed rules, and leaves the draft unchanged on
  bounded failure.
- AI candidate-profile extraction sends only bounded redacted CV text, verifies
  exact source evidence, creates a versioned draft, and changes matching only
  after explicit confirmation. Confirmed profile facts remain inspectable,
  unknowns remain eligible for review, and bounded failure creates no profile.
- A schema-valid profile with paraphrased or misaligned evidence receives at most
  one automatic correction request; only a fully revalidated replacement is
  saved, each request has a separate safe usage event, and a second failure makes
  no third request.
- Explicit job-relevant skills stated in profile or employment narrative are
  extracted alongside Skills-section entries, while related tools, methods, and
  synonyms are not inferred from one another.
- Profile batches queue only newest unprofiled successful CVs, reuse confirmed or
  draft profiles for unchanged sources, create drafts without confirmation, and
  return the same job for the same eligible source set.
- Whole-shortlist batches require a current deterministic run, isolate every
  entry, reuse exact-input assessments, expose safe per-target exceptions, and
  resume expired work without duplicating an already saved result.
- Explicit retry requeues only failed or skipped targets. Job status contains no
  copied CV, contact, prompt, raw response, decision-note, or outreach content.
- Batch work never confirms profiles, records final candidate decisions, creates
  outreach, or sends messages. A separate explicit intake review action may
  confirm only clean eligible profile drafts, recording each profile's actor and
  timestamp; final candidate decisions and outreach remain individual and
  separately approved.
- AI match assessment is POST-only and per candidate, requires current confirmed
  inputs, preserves immutable numbered versions, resolves evidence references,
  keeps unsupported facts uncertain, and never changes the deterministic result
  or makes a recruitment/contact decision. Bounded failure creates no version.
- The review queue consolidates latest assessments, prioritizes changed inputs
  and evidence exceptions, keeps routine assessments available, and opens a
  tenant-safe evidence-linked detail/history screen.
- Approve, reject, and revisit decisions require individual POST actions and
  non-blank recruiter notes; each immutable version records the exact assessment,
  actor, and timestamp, while older or stale evidence cannot receive a current
  decision and no decision triggers outreach automatically.
- Outreach draft generation is POST-only and accepts only the exact latest
  explicit approval while its assessment/profile/shortlist evidence remains
  current. Each immutable draft version records its source decision, human actor,
  and timestamp; the AI request excludes candidate identity/contact, CV text,
  recruiter notes, gaps, and uncertainties.
- Recruiter edits append immutable versions with parent, actor, and timestamp;
  exact final approval requires notes, explicit permission attestation, and a
  currently permitted candidate source.
- Only the latest exact approved draft can be copied or exported, and every
  action records the draft, actor, and timestamp after server-side currentness
  and permission checks.
- A later edit, decision, assessment, profile/input change, or permission
  withdrawal blocks use without rewriting historical records.
- Outreach sending and recipient selection remain unavailable and separate from
  approval, copy, and export.
- Every actual AI attempt produces a tenant-scoped immutable usage event with
  safe success metadata or an allow-listed failure category, while rejected
  precondition-only actions produce no event and sensitive request/response data
  is never stored in the ledger.
- The tenant-scoped AI usage report aggregates attempts, outcomes, available
  token/cost/latency/retry metadata, workflow/model breakdowns, safe failures,
  and daily trends while marking missing provider metadata unavailable instead
  of estimating it or exposing private recruitment content.
- The shared fake/toolkit contract tests pass provider-free, the ordinary suite
  excludes `live_tests`, and the explicitly enabled synthetic live smoke returns
  one schema-valid result when valid provider configuration is supplied.
- Production fails closed without explicit HTTPS, PostgreSQL, and persistent
  private-media settings. Static collection, Django deployment checks, runtime
  database/migration/storage checks, generic health endpoints, separately
  supervised web/worker/retention processes, and backup/restore guidance are
  available without exposing private recruitment content.
- Cross-organization URLs do not disclose data.
- The ordinary test suite and deterministic browser workflow require no AI key
  or live AI request; only explicit vacancy extraction, candidate extraction,
  match-assessment, or outreach-generation actions do.

## 34. Reset disposable local test data

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
