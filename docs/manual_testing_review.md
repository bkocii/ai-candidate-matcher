# Manual Testing Review

This file records functional defects and visual improvements found during page-by-page browser testing. Confirmed defects are kept separate from optional improvements so stable behavior is not changed unnecessarily.

## Finding types

- **Functional defect:** behavior does not work or violates an approved requirement.
- **Visual defect:** presentation harms clarity, consistency, responsiveness, or accessibility.
- **Improvement:** useful polish that is not required for correct operation.

## Review log

### MT-001 — Sign-in page

- **Date:** 2026-08-28
- **Route:** `/accounts/login/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Pass
- **Functional status:** In progress

#### Observations

- The centered card, restrained color palette, spacing, and typography look clean and professional.
- Branding is clear without competing with the sign-in task.
- Form labels are visible, the focused field has a clear focus state, and the primary action is prominent.
- Invalid credentials produce a clearly visible, generic error that does not reveal whether the username exists.
- After an unsuccessful attempt, the username is preserved and the password is cleared.
- No immediate visual change is required for this page.

#### Pending functional checks

- Valid credentials redirect the user to the correct organization workspace.
- A suspended organization member cannot enter the workspace.

#### Completed functional checks

- **Pass:** Invalid credentials show a clear, generic error without exposing account details.
- **Pass:** The username remains populated and the password is cleared after an unsuccessful attempt.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-001-F01 | Improvement | Medium | The page has no visible recovery route for a user who cannot sign in. | Before external production use, add a controlled password-recovery flow or clearly document administrator-assisted recovery. Do not introduce public signup. | Open |
| MT-001-V01 | Improvement | Low | The password field has no show/hide control. | Consider adding an accessible password-visibility toggle after higher-priority workflow testing. | Proposed |

### MT-002 — Organization landing page

- **Date:** 2026-08-28
- **Route:** `/organizations/second-agency-test/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Improvements proposed
- **Functional status:** In progress

#### Completed functional checks

- **Pass:** Valid credentials redirect to the user's organization workspace.
- **Pass:** The organization name and administrator role are displayed.
- **Pass:** The empty organization dashboard loads without an error and shows zero-value summaries.
- **Pass:** Administrator-only organization settings are visible to the administrator.

#### Pending functional checks

- Candidate and vacancy summary links open the correct organization-scoped pages.
- Organization settings opens the correct organization and does not expose another tenant.
- Counts update correctly after candidates, clients, and vacancies are created.
- Recruiters do not see administrator-only organization controls.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-002-V01 | Visual defect | Medium | The separate **Your role** card duplicates the administrator badge beside the page title and leaves two-thirds of its grid row empty. | Keep the compact role badge and remove the redundant card, allowing the actionable sections to move upward. | Open |
| MT-002-V02 | Visual defect | Medium | **Open organization settings** wraps across three lines inside a narrow desktop button. | Use a wider action area or shorten the label to **Manage settings** so it stays on one line. | Open |
| MT-002-V03 | Visual defect | Low | Candidate and vacancy summary cards have actions, while the client-company card has no equivalent administrator action. | Use consistent card affordances; provide **Manage client companies** for administrators or make all actionable cards consistently clickable. | Open |
| MT-002-C01 | Improvement | Low | The large **Secure workspace** panel contains generic descriptive copy but no status detail or action. | Replace it with meaningful operational status information or reduce/remove the panel to keep the dashboard task-focused. | Proposed |

### MT-003 — Empty candidate pool

- **Date:** 2026-08-28
- **Route:** `/organizations/second-agency-test/candidates/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Improvements required
- **Functional status:** In progress

#### Completed functional checks

- **Pass:** The dashboard candidate link opens the correct organization-scoped candidate pool.
- **Pass:** The empty candidate pool loads without an error.
- **Pass:** The page communicates that no candidates exist and presents available intake methods.
- **Pass:** The CV-first intake action has the strongest visual priority.

#### Pending functional checks

- CV-first intake opens and creates candidates only inside the current organization.
- Intake history, pending extraction, CSV import, and quick-add actions open their correct workflows.
- Candidate records become visible and update the organization count after creation.
- Recruiters see only the navigation and actions allowed by their role.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-003-V01 | Visual defect | High | The desktop header is crowded and multiple navigation labels wrap onto two lines, including **AI usage**, **Privacy & audit**, **Change password**, and **Sign out**. | Introduce a compact account menu for password/sign-out actions and group lower-frequency administrator links so primary navigation remains single-line and scannable. | Open |
| MT-003-V02 | Visual defect | Medium | Five page-level actions compete for attention and several button labels wrap, making the intake choices harder to scan. | Keep **Create candidates from CVs** as the primary action and group secondary or operational actions in a compact menu or clearly separated secondary area. | Open |
| MT-003-U01 | Improvement | Medium | The empty-state card explains how to begin but contains no action of its own. | Add the primary **Create candidates from CVs** button inside the empty state while retaining the page-level action. | Proposed |
| MT-003-U02 | Improvement | Low | **Queue pending profile extraction** is technical wording and is shown even when the organization has no candidates. | Use recruiter-facing wording, show a pending count, and hide or disable the action when there is nothing eligible to queue. | Proposed |
| MT-003-V03 | Improvement | Low | The generic **C** empty-state icon adds little product meaning. | Replace it with a restrained candidate/profile icon when the shared visual system is polished. | Proposed |

### MT-004 — Create candidates from CVs: shared details

- **Date:** 2026-08-28
- **Route:** `/organizations/second-agency-test/candidates/intake/new/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Improvements required
- **Functional status:** In progress

#### Completed functional checks

- **Pass:** The primary candidate action opens the correct organization-scoped intake form.
- **Pass:** Consent defaults to **Not recorded**, never **Given**.
- **Pass:** Allowed contact defaults to **Not confirmed**.
- **Pass:** Source/privacy values can be supplied once for the intake batch.

#### Pending functional checks

- The form creates an intake batch and continues to CV upload.
- Shared values are copied correctly to every selected candidate source.
- Retention dates and documented exceptions behave consistently with organization policy.
- Cancel returns safely to the organization candidate pool.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-004-U01 | Usability defect | High | A recruiter choosing **Create candidates from CVs** must complete or pass through a long compliance form before seeing any CV upload control. The main task is not visible on the first screen. | Lead with the upload step, then show shared source/privacy settings in a clearly labelled optional or expandable section before final creation. | Open |
| MT-004-U02 | Usability defect | Medium | The multi-step workflow has no progress indicator, and **Create intake batch** does not explain that CV upload comes next. | Show a short step indicator such as **1. Upload → 2. Shared details → 3. Review**, and use an outcome-focused label such as **Continue to upload CVs** if this order is retained. | Open |
| MT-004-V01 | Visual defect | Medium | The narrow single-column card produces a long multi-screen form while leaving most of the desktop width unused. | Use a wider, grouped layout on desktop, with separate **Source**, **Contact**, and **Retention** sections; keep a single column on smaller screens. | Open |
| MT-004-U03 | Improvement | Medium | Candidate, source, and CV each expose a separate manual delete/review date with nearly identical help text. This is repetitive and difficult for normal recruiters to interpret. | Add an organization candidate-retention default and calculate these dates where possible. Present one policy summary during intake and reserve per-object dates for authorized exceptions. | Proposed |
| MT-004-C01 | Improvement | Low | Long and repeated helper text makes the form appear more legalistic despite the plain-language labels. | Keep one concise explanation per section and move detailed compliance guidance to contextual help. | Proposed |

### MT-005 — Open bulk-CV intake batch

- **Date:** 2026-08-28
- **Route:** `/organizations/second-agency-test/candidates/intake/11/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Improvements required
- **Functional status:** In progress

#### Completed functional checks

- **Pass:** The shared-details form creates an open organization-scoped intake batch.
- **Pass:** A success message explains that CV upload is the next task.
- **Pass:** Safe shared values and unset retention dates are shown for inspection.
- **Pass:** CV upload and optional exact CSV mapping are kept as separate operations.
- **Pass:** The destructive batch-discard action is visually separated and explains its effect.

#### Pending functional checks

- One or more valid synthetic CVs pass local validation and appear as pending items.
- Invalid, oversized, or unsupported files are rejected without being stored as private content.
- Submitting without a selected CV produces a clear error and does not change the batch.
- Exact CSV mapping remains optional and never guesses a candidate by name.
- Discard requires appropriate confirmation and removes only remaining temporary intake items.
- Verify whether redirecting from the shared-details form consistently lands at a non-zero scroll position.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-005-V01 | Visual defect | High | The native browser file picker looks unfinished and does not provide a professional upload surface or selected-file summary. | Use an accessible drag-and-drop upload area with a normal browse fallback, accepted-format/size guidance, and a removable selected-file list. | Open |
| MT-005-U01 | Usability defect | Medium | **Validate and add CVs** appears active when no file is selected, and “validate” exposes an internal safety step rather than the recruiter's outcome. | Disable submission until files are selected and label the action **Add CVs**; report validation transparently after submission. | Open |
| MT-005-U02 | Improvement | Medium | Optional CSV mapping occupies an equally prominent full card even when the recruiter is using the standard CV-only workflow. | Keep CV upload primary and collapse CSV mapping behind **Add details from CSV (optional)** until requested. | Proposed |
| MT-005-V02 | Visual defect | Medium | Large zero-value summary cards consume substantial vertical space before the upload task. | Use a compact status row while the batch is empty and expand reporting once items exist. | Open |
| MT-005-U03 | Improvement | Medium | The redirected page was shown with the global header partly clipped, suggesting that the previous form's scroll position may have been restored. | Reproduce the transition; if confirmed, focus the success heading and reset the new page to the top after redirect. | Needs reproduction |
| MT-005-C01 | Improvement | Low | **Apply exact CSV mappings** is accurate but technical wording. | Prefer **Import candidate details from CSV**, retaining exact-filename behavior in the helper text. | Proposed |

### MT-006 — Mixed CV validation and identity review

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/candidates/intake/11/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Improvements required
- **Functional status:** In progress

#### Completed functional checks

- **Pass:** Two valid PDF/DOCX CVs were independently accepted into the review queue.
- **Pass:** The invalid PDF was independently rejected without rolling back either valid file.
- **Pass:** The page explicitly confirms that rejected private bytes were not stored.
- **Pass:** The pending-review count updated from zero to two.
- **Pass:** Local deterministic parsing proposed correct names, emails, phone numbers, and locations for both synthetic CVs.
- **Pass:** Proposed identity fields are editable, while raw CV text and private storage paths are not exposed.
- **Pass:** Both records are marked routine in this empty organization; no unsupported duplicate claim is shown.

#### Pending functional checks

- The optional CSV maps candidate details only through exact `cv_filename` values.
- Selecting one row creates only that candidate and accepted CV.
- Submitting with no selected row produces a clear bounded error and changes nothing.
- A known tenant-local identity/document duplicate is blocked without merging or overwriting data.
- Background profile-draft queuing targets only newly created accepted CVs.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-006-V01 | Visual defect | High | The candidate review table requires horizontal scrolling on a 1920px desktop. Selection and filenames disappear when source-reference/discard controls are visible, so a recruiter cannot review one row as a whole. | Replace the wide editable table with responsive candidate cards or a compact grid that keeps status, editable identity, selection, and row actions visible together. | Open |
| MT-006-V02 | Visual defect | Medium | Long filenames wrap across several lines in a narrow column and dominate each row. | Show a shortened filename with the complete value available through a tooltip or expandable detail. | Open |
| MT-006-C01 | Usability defect | Medium | **Routine** and **CV / exceptions** are internal-sounding labels that do not clearly tell the recruiter whether a row can be created. | Use direct states such as **Ready**, **Needs review**, **Possible duplicate**, or **Cannot create**, with a concise reason beside exceptions. | Open |
| MT-006-U01 | Usability defect | Medium | **Create selected candidates** appears active when no candidate is selected. | Disable the action until at least one eligible row is selected and announce the selected count in its label or nearby summary. | Open |
| MT-006-U02 | Improvement | Medium | There is no quick way to select all clean eligible rows in a larger batch. | Add **Select all ready** while keeping exception and duplicate rows unselected and individually reviewable. | Proposed |
| MT-006-V03 | Visual defect | Medium | Upload success, file rejection, and private-storage confirmation use nearly identical neutral banners. | Apply accessible success/warning/error treatments with icons or clear status labels while retaining sufficient contrast. | Open |
| MT-006-C02 | Usability defect | Low | The rejection message identifies only **File 1**, forcing the recruiter to infer which selected file failed. | Display the rejected filename in the immediate response without retaining its private bytes. | Open |
| MT-006-C03 | Improvement | Low | **Queue only newly created CVs for background AI profile drafts** is long and implementation-oriented. | Use **Create AI profile drafts in background** and keep the targeting/safety explanation as helper text. | Proposed |

### MT-007 — Exact CSV-to-CV mapping

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/candidates/intake/11/apply-csv/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Pass with previously recorded table issues
- **Functional status:** Pass for valid exact mappings

#### Completed functional checks

- **Pass:** Both CSV rows mapped only to pending CVs with exact `cv_filename` matches.
- **Pass:** The report shows `2 mapped`, `0 unresolved`, and `0 invalid`.
- **Pass:** The report identifies the originating CSV row and exact filename for each result.
- **Pass:** Mapped identity values and source references (`CV-MAP-001` and `CV-MAP-002`) are visible and remain editable before candidate creation.
- **Pass:** The mapping operation did not create a candidate by itself.

#### Pending functional checks

- Missing, repeated, conflicting, and unknown filenames remain unresolved and are never guessed by candidate name.
- Invalid CSV structure produces a bounded error without changing existing proposals.
- Refreshing or navigating back after a successful mapping does not accidentally repeat the POST operation.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-007-F01 | Functional defect | Medium | After successful mapping, the server renders the result directly at the POST-only `/apply-csv/` URL instead of redirecting. Refreshing can trigger a browser form-resubmission warning and repeat the operation. | Use Post/Redirect/Get. Redirect to the batch detail route after success and carry a bounded mapping summary through a safe one-time result mechanism. | Open |
| MT-007-U01 | Improvement | Low | The report's **Details** column displays only an em dash when all rows map successfully. | Omit the empty column for an all-success report or use it only for unresolved/invalid explanations. | Proposed |

### MT-008 — Create one selected candidate

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/candidates/intake/11/?job=18`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Improvements required
- **Functional status:** Pass for selective creation and queuing

#### Completed functional checks

- **Pass:** Exactly one selected candidate, Drita Shembull, was created.
- **Pass:** Arben Testi remains pending and editable; he was not created implicitly.
- **Pass:** Counts updated to one pending, one created, and zero discarded.
- **Pass:** The created-candidate section records Drita, the acting platform owner, and a timestamp.
- **Pass:** Background job `#18` was queued only after the explicit checked action.
- **Pass:** The page states that no profile is confirmed automatically.
- **Pass:** No candidate decision, outreach draft, or sending action occurred.

#### Pending functional checks

- Job `#18` contains only Drita's accepted CV and processes idempotently.
- Drita has exactly one shared-provenance source and one accepted private CV.
- The completed profile draft remains unconfirmed until explicit evidence review.
- Remaining Arben temporary data can be discarded without changing Drita.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-008-U01 | Usability defect | Medium | While background extraction is merely queued, profile confirmation reports `0 eligible · 1 excluded`. “Excluded” can incorrectly suggest a validation failure rather than a draft that is not ready yet. | Separate states into **Processing**, **Ready to confirm**, and **Needs individual review**; reserve **Excluded** for a completed eligibility decision. | Open |
| MT-008-U02 | Usability defect | Medium | After candidates are staged or created, the still-expanded upload and CSV forms push the pending review, created candidates, and profile status far down the page. | Prioritize current batch progress and candidate review; collapse completed/optional intake tools behind **Add more CVs** and **Import CSV details** actions. | Open |
| MT-008-U03 | Improvement | Medium | Audit timestamps are rendered in UTC without a timezone label or organization/user timezone preference. | Add an organization or user display timezone and show an explicit timezone where ambiguity matters, while retaining UTC storage. | Proposed |

### MT-009 — Queued candidate-profile job

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/jobs/18/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Pass with operational improvements proposed
- **Functional status:** Pass for queued state

#### Completed functional checks

- **Pass:** Job `#18` is organization-scoped and labelled **Candidate profile extraction**.
- **Pass:** The job contains exactly one candidate: Drita Shembull.
- **Pass:** Before worker execution, status is **Queued**, attempts are zero, and the bounded outcome is **Waiting for worker**.
- **Pass:** Summary totals are internally consistent: one total and zero succeeded, needs-attention, or failed.
- **Pass:** The page reiterates that background work creates drafts only and cannot confirm profiles, decide, or perform outreach.
- **Pass:** The candidate name links to an individually inspectable record.

#### Pending functional checks

- Worker execution changes the job and item states exactly once.
- Successful extraction creates a reviewable draft without confirming it.
- Retry/failure states expose bounded safe information without prompt, response, CV text, or secrets.
- Another organization cannot open job `#18`.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-009-U01 | Usability defect | Medium | The job is queued, but the summary cards omit a queued or running count; all three outcome cards show zero. | Include **Queued** and **Running** in the compact status summary so the current total is immediately explained. | Open |
| MT-009-U02 | Usability defect | Medium | The status page has no visible refresh action, last-updated indicator, or automatic update behavior. A recruiter can continue seeing **Waiting for worker** after processing completes. | Add lightweight polling or a clear **Refresh status** action with a last-updated timestamp, stopping automatically at a terminal state. | Open |
| MT-009-U03 | Improvement | Low | The page does not provide a direct route back to the intake batch that created the job. | Add a contextual **Back to intake** link when a job originated from an intake batch. | Proposed |
| MT-009-V01 | Improvement | Low | The large green safety banner has greater visual emphasis than the actual queued item status. | Reduce it to a compact informational note after the safety model is familiar elsewhere in the product. | Proposed |

### MT-010 — Completed candidate-profile job

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/jobs/18/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Pass with minor operational improvements
- **Functional status:** Pass

#### Completed functional checks

- **Pass:** The worker moved job `#18` from queued to succeeded.
- **Pass:** Exactly one attempt processed exactly one candidate item.
- **Pass:** Totals are consistent: one total, one succeeded, zero needs-attention, and zero failed.
- **Pass:** The item outcome is **Created**, indicating a profile draft was produced.
- **Pass:** The result provides an explicit **Inspect candidate profile** link instead of confirming the draft automatically.
- **Pass:** No failure detail, private CV content, prompt, response, credential, decision, or outreach content is exposed.

#### Pending functional checks

- The linked profile is a draft and requires explicit evidence review before confirmation.
- Running the worker again does not create a second profile or increment successful work incorrectly.
- The profile contains only evidence-grounded facts from the accepted Drita CV.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-010-U01 | Improvement | Medium | The completed job shows only its queued timestamp; it does not show when processing started or completed, or how long it took. | Display queued, started, and completed times plus duration using the configured display timezone. | Proposed |
| MT-010-V01 | Visual defect | Low | Queued and succeeded status pills use nearly identical neutral styling, weakening quick status recognition. | Use accessible, restrained semantic styling for queued, running, succeeded, attention, and failed states without relying on color alone. | Open |

### MT-011 — Evidence-based candidate profile draft

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/candidates/69/profiles/70/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Improvements required
- **Functional status:** Draft safety passes; correction workflow is incomplete

#### Completed functional checks

- **Pass:** Profile version 1 is visibly labelled **Draft** and names its accepted source CV.
- **Pass:** Confirmation remains an explicit separate action and has not occurred automatically.
- **Pass:** Relevant experience, location, skills, and employment history include bounded CV evidence.
- **Pass:** Unknown work mode, employment preference, availability, languages, education, and certifications remain unknown rather than being invented.
- **Pass:** No raw CV text, candidate contact details, prompt, or provider response is displayed.
- **Pass:** The profile history shows a separate immutable version record.
- **Pass:** Confirmation is clearly described as publishing facts for matching, not approving, rejecting, assessing, or contacting the candidate.

#### Pending functional checks

- Batch eligibility correctly distinguishes clean profiles from unresolved discrepancies.
- Confirmation publishes only the reviewed facts and changes deterministic matching inputs.
- A correction produces an auditable new version without mutating a confirmed profile.
- Re-extraction does not silently replace or confirm the existing draft.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-011-F01 | Functional defect | High | The recruiter-supplied CSV location is Prishtina, while the CV-derived profile location is Gjilan, but the profile reports **None recorded** under ambiguities. Confirming can publish a conflicting location into matching without highlighting the discrepancy. | Compare recruiter-supplied candidate fields with extracted profile facts. Present material conflicts as explicit review exceptions and exclude them from batch confirmation until resolved. | Fixed in CR-006 — browser retest pending |
| MT-011-F02 | Functional defect | High | The draft offers only **Confirm** or **Extract new version**; there is no recruiter correction workflow. Questionable facts such as treating **validated imports** as a skill cannot be removed or corrected deterministically. | Add an auditable correction action that creates a recruiter-reviewed profile version with edited facts and retained source evidence; never mutate a confirmed version. | Fixed in CR-006 — browser retest pending |
| MT-011-C01 | Usability defect | High | **AI output is not matching evidence yet** reads as an evidence-validation failure, although the intended meaning is that the draft is not yet used for candidate matching. | Rename it to **Draft profile — review before matching** or **Not yet confirmed for matching**. Show a separate explicit warning only when evidence validation actually fails. | Fixed in CR-006 — browser retest pending |
| MT-011-V01 | Visual defect | Medium | Relevant-experience and location values are immediately repeated by unlabeled evidence excerpts, making correct evidence look like duplicated content. | Label and visually distinguish **Profile value** from **CV evidence**, using quote/evidence styling consistent with the skills table. | Fixed in CR-006 — browser retest pending |
| MT-011-V02 | Visual defect | Medium | Empty ambiguity and unknown-data cards consume substantial space, making the evidence page unnecessarily long. | Compact absent fields into a single **Not stated in CV** summary and give exceptions prominence only when present. | Open |
| MT-011-U01 | Improvement | Medium | The primary confirmation action appears before the recruiter has scrolled through the evidence and there is no correction option beside it. | Keep efficient confirmation, but pair it with **Correct profile** and repeat or place the action after the review content with a concise confirmation summary. | Proposed |
| MT-011-U02 | Improvement | Low | **Extract new version** does not explain when re-extraction is appropriate or that it invokes AI again. | Use **Re-extract from CV** with helper/confirmation text explaining that it creates another draft and does not correct the current version automatically. | Proposed |

### MT-012 — Batch profile-confirmation eligibility

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/candidates/intake/11/confirm-profiles/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Pass with minor improvements
- **Functional status:** Fail — unsafe eligibility classification

#### Completed functional checks

- **Pass:** Included and excluded counts are shown before confirmation.
- **Pass:** Every row retains direct candidate and profile links for individual inspection.
- **Pass:** The page explains that profile confirmation does not approve/reject candidates or generate/approve outreach.
- **Pass:** No confirmation occurred merely by opening the page.
- **Fail:** Drita's conflicting location data was not treated as a review exception; the profile is incorrectly included for batch confirmation.

#### Pending functional checks

- After conflict detection is fixed, conflicting profiles are excluded with a bounded actionable reason.
- Clean profiles can still be confirmed together without additional per-profile approval.
- One batch action records an individual confirmation actor and timestamp for every included profile.
- Excluded profiles remain unchanged after confirming eligible profiles.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-012-F01 | Functional defect | Critical | Drita is shown as **Included** with the reason “Evidence validated with no recorded review exception,” despite the known Prishtina/Gjilan conflict. The batch action would publish a materially conflicting profile without individual review. | Extend eligibility checks beyond AI-provided ambiguities and excerpt grounding. Compare extracted matching facts with recruiter-supplied candidate values and other trusted current data; exclude material conflicts until explicitly resolved. | Fixed in CR-006 — browser retest pending |
| MT-012-U01 | Improvement | Medium | The batch row reports only a generic eligibility reason and no compact indication of what facts will be published. | Show a compact fact/skill count and any detected conflict count while keeping full evidence behind the profile link. | Proposed |
| MT-012-V01 | Visual defect | Low | Included/excluded count cards are oversized for two single-number summaries. | Use a compact status summary so individual results and the confirmation boundary appear higher on the page. | Open |
| MT-012-C01 | Improvement | Low | **Confirm 1 eligible profile(s)** uses mechanical pluralization. | Render **Confirm 1 eligible profile** and pluralize only for other counts. | Proposed |

### MT-013 — Candidate details and source/privacy record

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/candidates/69/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Fail — page-level horizontal overflow
- **Functional status:** Fail — incomplete records cannot be corrected in-app

#### Completed functional checks

- **Pass:** The candidate record persisted Drita's mapped email and Prishtina location.
- **Pass:** The source record persisted exact source reference `CV-MAP-001` and the batch's safe privacy defaults.
- **Pass:** The accepted private DOCX is listed with size, successful extraction state, draft profile link, upload time, and authorized download action.
- **Pass:** Candidate data, source provenance, private documents, and profile status remain organization-scoped and inspectable.
- **Fail:** The persisted candidate location confirms the profile's Gjilan value conflicts with trusted current candidate data.

#### Pending functional checks

- Authorized private download returns attachment-only bytes and no cacheable public URL.
- Candidate/source correction records an actor and timestamp and makes stale dependent matching inputs explicit.
- Deletion request freezes the candidate before any permanent purge.
- Role restrictions prevent unauthorized candidate/source updates or deletion actions.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-013-F01 | Functional defect | Critical | Safe-default source values (**Not recorded**, **Not confirmed**) are displayed but cannot be edited anywhere in the normal app. The recruiter cannot later record the processing reason or contact permission, so outreach remains blocked unless a technical administrator changes data. | Add an authorized candidate-source edit workflow with clear validation, actor/time audit history, and tenant isolation. Preserve source provenance and never treat an edit as legal certification. | Fixed in CR-006 — browser retest pending |
| MT-013-F02 | Functional defect | High | Candidate identity/contact fields have no edit action. Recruiters cannot correct names, email, phone, or location, or resolve the Prishtina/Gjilan discrepancy. | Add an auditable **Edit candidate details** action with duplicate rechecks and staleness handling for matching/profile conflicts. | Fixed in CR-006 — browser retest pending |
| MT-013-U01 | Usability defect | Medium | The mapped phone number is stored and appears on candidate lists but is omitted from the candidate detail header and page. | Show available email, phone, and location together in a concise contact summary. | Fixed in CR-006 — browser retest pending |
| MT-013-V01 | Visual defect | High | The source/privacy table expands beyond its panel and makes the entire page wider than a 1920px viewport. Horizontal scrolling clips the candidate name, navigation, and actions. | Prevent body-level overflow. Stack the panel content and use responsive source cards or a contained table whose overflow does not move the whole application shell. | Fixed in CR-006 — browser retest pending |
| MT-013-V02 | Visual defect | Medium | The six-column source table is difficult to scan for a single provenance record and visually detaches from its explanatory panel. | Present each source as a labelled responsive record card with grouped **Provenance**, **Privacy/contact**, and **Retention** values plus an edit action. | Fixed in CR-006 — browser retest pending |
| MT-013-U02 | Improvement | Low | The page has no direct context link back to the intake batch that created this candidate. | Add a source/intake link where the candidate originated from a reviewed batch. | Proposed |
