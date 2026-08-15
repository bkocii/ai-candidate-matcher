# Manual Testing Guide

This guide verifies the application from the Django foundation through
`OUT-002`. Use only the synthetic files in `manual_testing/fixtures` or other
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
   **Vacancies**, **Reviews**, **Django admin**, and **Sign out**.
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

Use only synthetic evidence. Candidate skills can be published by confirming an
AI-extracted profile as described in section 16; Django admin remains useful for
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
- Every must-have skill has two weight units and every nice-to-have skill has one;
  the combined weights are apportioned to exactly `100.00` points.
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

## 13. Test stale-result detection and regeneration

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

A shortlist created with scoring algorithm v1 is also labelled stale after this
upgrade. Its saved 70/30 score remains unchanged as historical evidence, and
regeneration creates a separate v2 run using per-skill 2:1 weighting.

### Regeneration

From the stale warning, select **Generate current shortlist**.

Expected result:

- A separate run is created using the current confirmed requirements and active
  candidate matching inputs.
- The new page shows **Current result**.
- Opening the earlier run still shows its stale warning and original history.
- No AI request, approval/rejection, outreach, or automatic hiring action occurs.

## 14. Test organization isolation

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

## 15. Test AI-assisted vacancy extraction

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
safe usage event as described in section 21.

## 16. Test AI-assisted candidate-profile extraction

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

Each actual request produces a safe usage event as described in section 21.

## 17. Test evidence-based AI match assessment

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
section 21. Background bulk assessment remains deferred to `PROD-003`.

## 18. Test the recruiter assessment review workflow

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

## 19. Test individual recruiter decisions

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

## 20. Test the outreach draft review workflow

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

### Establish contact permission and approve the exact version

The synthetic candidate created earlier has **Unknown** contact permission.
Confirm that final approval is blocked and the page explains the permission
requirement. In Django admin, edit one of that candidate's synthetic **Candidate
sources** and set:

- Lawful basis: `Legitimate interests`
- Consent status: `Not required` or `Granted`
- Contact permission: `Permitted`
- Permission notes: `Synthetic manual test permission only.`

Return to the latest outreach draft, add approval notes, check the explicit
contact-permission attestation, and select **Approve exact draft**.

Expected result:

- Approval binds only the exact displayed subject and body.
- The approval records notes, your username, and a timestamp.
- The draft is labelled approved but still **not sent**.
- Missing notes or an unchecked attestation creates no approval.
- Restricted or withdrawn contact permission, or withdrawn consent on any
  candidate source, blocks approval.

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

Finally, change the source permission to **Withdrawn**, refresh the draft page,
and confirm copy/export is blocked. A direct POST to either action must return no
draft text or file. Restore the synthetic permission if continuing other tests.

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

## 21. Inspect safe AI usage events

Sign in to Django admin and open **AI usage events** under **Audit** after running
at least one successful and one deliberately failed synthetic AI action from
sections 15 through 17 or section 20.

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

## 22. Run the optional synthetic live gateway smoke test

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

## 23. What is intentionally unavailable

The following are not defects at this milestone:

- Manual candidate-skill entry still uses Django admin; confirmed AI profile
  skills are published through the normal candidate workflow.
- No recruiter-facing AI usage/cost/failure dashboard; safe records are currently
  read-only in Django admin.
- No private CV download route.
- No OCR for scanned PDFs.
- No automatic outreach sending, recipient selection, email/ATS/platform
  integration, or normal-workspace contact-permission editor. Manual clipboard
  copy and plain-text export deliberately stop before transmission.

## 24. Final acceptance checklist

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
- The shared fake/toolkit contract tests pass provider-free, the ordinary suite
  excludes `live_tests`, and the explicitly enabled synthetic live smoke returns
  one schema-valid result when valid provider configuration is supplied.
- Cross-organization URLs do not disclose data.
- The ordinary test suite and deterministic browser workflow require no AI key
  or live AI request; only explicit vacancy extraction, candidate extraction,
  match-assessment, or outreach-generation actions do.

## 25. Reset disposable local test data

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
