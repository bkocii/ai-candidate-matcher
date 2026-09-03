# Manual Testing Review

This file records functional defects and visual improvements found during page-by-page browser testing. Confirmed defects are kept separate from optional improvements so stable behavior is not changed unnecessarily.

## UX review principle

- Minimize recruiter steps and clicks while preserving explicit approval boundaries: combine save-and-continue actions, avoid separate pages for closely related work, reuse confirmed data, keep routine controls inline, and reveal advanced or exceptional controls only when needed.

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
- **Functional status:** Profile review, correction, and confirmation passed; matching consumption pending

#### Completed functional checks

- **Pass:** Profile version 1 is visibly labelled **Draft** and names its accepted source CV.
- **Pass:** Confirmation remains an explicit separate action and has not occurred automatically.
- **Pass:** Relevant experience, location, skills, and employment history include bounded CV evidence.
- **Pass:** Unknown work mode, employment preference, availability, languages, education, and certifications remain unknown rather than being invented.
- **Pass:** No raw CV text, candidate contact details, prompt, or provider response is displayed.
- **Pass:** The profile history shows a separate immutable version record.
- **Pass:** Confirmation is clearly described as publishing facts for matching, not approving, rejecting, assessing, or contacting the candidate.
- **Pass:** After correcting the candidate record to `Gjilan`, Profile v1 shows the same evidence-backed location and no confirmation-blocked conflict panel.
- **Pass:** The draft callout now says **Not yet confirmed for matching**, and CV evidence is visually labelled instead of appearing as unexplained duplicate text.
- **Pass:** **Correct profile** opens a pre-populated correction form, keeps the existing supported skills selected, and explains that removing a misclassified skill means unchecking it.
- **Pass:** The correction action is labelled **Create corrected draft**, making it clear that the existing profile is not edited in place.
- **Pass:** Removing **validated imports** created Profile v2 as a separate draft; the questionable skill is absent while the other supported skills and their evidence remain.
- **Pass:** Profile history retains both v2 and v1 with separate version links, creator, source, status, and timestamps.
- **Pass:** The corrected profile remains **Draft** and was not automatically confirmed for matching.
- **Pass:** Opening Profile v1 after creating v2 still shows **validated imports**, confirming that recruiter correction did not mutate the original version.
- **Pass:** Explicit confirmation changes Profile v2 from **Draft** to **Confirmed** while Profile v1 remains a separate draft in history.
- **Pass:** The confirmed v2 continues to show the corrected evidence-backed skill set without **validated imports**.

#### Pending functional checks

- Batch eligibility correctly distinguishes clean profiles from unresolved discrepancies.
- A shortlist run consumes only the confirmed v2 facts and not the removed v1 skill.
- Re-extraction does not silently replace or confirm the existing draft.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-011-F01 | Functional defect | High | The recruiter-supplied CSV location is Prishtina, while the CV-derived profile location is Gjilan, but the profile reports **None recorded** under ambiguities. Confirming can publish a conflicting location into matching without highlighting the discrepancy. | Compare recruiter-supplied candidate fields with extracted profile facts. Present material conflicts as explicit review exceptions and exclude them from batch confirmation until resolved. | Passed browser retest — 2026-08-29 |
| MT-011-F02 | Functional defect | High | The draft offers only **Confirm** or **Extract new version**; there is no recruiter correction workflow. Questionable facts such as treating **validated imports** as a skill cannot be removed or corrected deterministically. | Add an auditable correction action that creates a recruiter-reviewed profile version with edited facts and retained source evidence; never mutate a confirmed version. | Passed browser retest — 2026-08-29 |
| MT-011-C01 | Usability defect | High | **AI output is not matching evidence yet** reads as an evidence-validation failure, although the intended meaning is that the draft is not yet used for candidate matching. | Rename it to **Draft profile — review before matching** or **Not yet confirmed for matching**. Show a separate explicit warning only when evidence validation actually fails. | Passed browser retest — 2026-08-29 |
| MT-011-V01 | Visual defect | Medium | Relevant-experience and location values are immediately repeated by unlabeled evidence excerpts, making correct evidence look like duplicated content. | Label and visually distinguish **Profile value** from **CV evidence**, using quote/evidence styling consistent with the skills table. | Passed browser retest — 2026-08-29 |
| MT-011-V02 | Visual defect | Medium | Empty ambiguity and unknown-data cards consume substantial space, making the evidence page unnecessarily long. | Compact absent fields into a single **Not stated in CV** summary and give exceptions prominence only when present. | Open |
| MT-011-V03 | Visual defect | Low | Every skill repeats **Unknown** in the Years column, adding visual noise without information. | Hide the Years column when no skill has a supported duration, or show it only for rows with a known value. | Open |
| MT-011-V04 | Visual defect | Medium | The correction form is a long, narrow single column with large empty evidence fields, while most desktop width is unused. Correcting one questionable skill requires scrolling through several screens. | Group fields into compact **Profile facts**, **Evidence**, **Skills**, and **Ambiguities** sections. Use a wider two-column desktop layout and collapse empty optional evidence sections. | Open |
| MT-011-V05 | Visual defect | Medium | Skill checkboxes sit far to the right of their labels and evidence text, so the control-to-skill relationship is weak and slower to scan. | Render each skill as a compact selectable row or card with the checkbox beside the skill name and its CV evidence as secondary text. | Open |
| MT-011-V06 | Visual defect | Low | **Confirmed** and **Draft** appear as plain table text in profile history, making version state slower to distinguish. | Use compact status badges with both text and restrained semantic styling. | Open |
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
- **Visual status:** Pass for corrected source-card layout; polish remains proposed
- **Functional status:** Candidate/source correction and confirmed-profile linkage passed

#### Completed functional checks

- **Pass:** The candidate record persisted Drita's mapped email and Prishtina location.
- **Pass:** The source record persisted exact source reference `CV-MAP-001` and the batch's safe privacy defaults.
- **Pass:** The accepted private DOCX is listed with size, successful extraction state, draft profile link, upload time, and authorized download action.
- **Pass:** Candidate data, source provenance, private documents, and profile status remain organization-scoped and inspectable.
- **Pass:** The normal-app source editor loaded the existing source name/reference and safe privacy values.
- **Pass:** Saving changed the reason to **Legitimate interests**, consent to **Not required**, allowed contact to **Future roles allowed**, and notes to `Synthetic manual test` while preserving `CV-MAP-001`.
- **Pass:** The source card remained contained at desktop width with no page-level horizontal overflow.
- **Pass:** The candidate-details editor loaded Drita's existing name, email, phone, location, and retention date.
- **Pass:** Saving changed the candidate location from `Prishtina` to `Gjilan`, preserved email/phone, returned a visible audited-success message, and removed the known candidate/profile location disagreement at the data level.
- **Pass:** After confirmation, the candidate's private-document row links to **Profile v2 · Confirmed**; the corrected version is recognized instead of the historical v1 draft.

#### Pending functional checks

- Authorized private download returns attachment-only bytes and no cacheable public URL.
- Candidate/source correction records an actor and timestamp and makes stale dependent matching inputs explicit.
- Deletion request freezes the candidate before any permanent purge.
- Role restrictions prevent unauthorized candidate/source updates or deletion actions.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-013-F01 | Functional defect | Critical | Safe-default source values (**Not recorded**, **Not confirmed**) are displayed but cannot be edited anywhere in the normal app. The recruiter cannot later record the processing reason or contact permission, so outreach remains blocked unless a technical administrator changes data. | Add an authorized candidate-source edit workflow with clear validation, actor/time audit history, and tenant isolation. Preserve source provenance and never treat an edit as legal certification. | Passed browser retest — 2026-08-29 |
| MT-013-F02 | Functional defect | High | Candidate identity/contact fields have no edit action. Recruiters cannot correct names, email, phone, or location, or resolve the Prishtina/Gjilan discrepancy. | Add an auditable **Edit candidate details** action with duplicate rechecks and staleness handling for matching/profile conflicts. | Passed browser retest — 2026-08-29 |
| MT-013-U01 | Usability defect | Medium | The mapped phone number is stored and appears on candidate lists but is omitted from the candidate detail header and page. | Show available email, phone, and location together in a concise contact summary. | Passed browser retest — 2026-08-29 |
| MT-013-V01 | Visual defect | High | The source/privacy table expands beyond its panel and makes the entire page wider than a 1920px viewport. Horizontal scrolling clips the candidate name, navigation, and actions. | Prevent body-level overflow. Stack the panel content and use responsive source cards or a contained table whose overflow does not move the whole application shell. | Passed browser retest — 2026-08-29 |
| MT-013-V02 | Visual defect | Medium | The six-column source table is difficult to scan for a single provenance record and visually detaches from its explanatory panel. | Present each source as a labelled responsive record card with grouped **Provenance**, **Privacy/contact**, and **Retention** values plus an edit action. | Passed browser retest — 2026-08-29 |
| MT-013-V03 | Visual defect | Low | The saved source note `Synthetic manual test` appears as unlabelled trailing text below the source fields, so its meaning is unclear. | Display a visible **Notes** label and preserve the note as secondary text inside the source card. | Open |
| MT-013-U02 | Improvement | Low | The page has no direct context link back to the intake batch that created this candidate. | Add a source/intake link where the candidate originated from a reviewed batch. | Proposed |

### MT-014 — Empty vacancy workspace

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/vacancies/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Pass with minor improvements
- **Functional status:** Empty state passed; vacancy creation pending

#### Completed functional checks

- **Pass:** The organization-scoped vacancy workspace loads without an error when no vacancies exist.
- **Pass:** The empty state clearly explains that a vacancy description is followed by structured-requirement review and confirmation.
- **Pass:** **Add vacancy** is visible as the single primary page action.
- **Pass:** The page follows the established typography, spacing, card, and color system without overflow.

#### Pending functional checks

- **Add vacancy** opens the correct organization-scoped creation form.
- An optional active hiring client can be selected without requiring one for a direct employer.
- Saving creates one vacancy with the original description preserved.
- The created vacancy appears in this list and updates organization counts.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-014-U01 | Improvement | Medium | The empty-state guidance and the **Add vacancy** action are separated across the page, so the explanation does not directly lead into its next step. | Add **Add vacancy** inside the empty-state card while retaining or removing the page-level action according to the final page-action pattern. | Proposed |
| MT-014-V01 | Improvement | Low | The generic **V** icon communicates little beyond repeating the page name. | Replace it with a restrained vacancy/job icon when the shared empty-state icon system is polished. | Proposed |

### MT-015 — Add vacancy form

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/vacancies/new/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Pass with wording improvements
- **Functional status:** Form structure passed; creation pending

#### Completed functional checks

- **Pass:** **Add vacancy** opens the correct organization-scoped form.
- **Pass:** The form asks only for title, optional client relationship, and the original job description.
- **Pass:** Direct-employer mode is the safe default and does not require a client-company record.
- **Pass:** Helper text explains that only active client companies from the current organization are available.
- **Pass:** An administrator shortcut to organization client-company settings is available.
- **Pass:** **Create and review requirements** clearly communicates that saving the vacancy leads to a separate review step.

#### Pending functional checks

- A direct-employer vacancy can be created without a client company.
- Title and original description are preserved exactly after creation.
- AI extraction creates a reviewable requirements draft without confirming it automatically.
- Cancel returns safely to the organization vacancy list.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-015-C01 | Usability defect | Medium | The field is labelled **Client company**, although the approved recruiter-facing wording is **Hiring client (optional)**. The current label can be mistaken for the organization/tenant itself. | Rename the label to **Hiring client (optional)** and the empty choice to **No hiring client (direct employer)** without changing the underlying model. | Open |
| MT-015-C02 | Improvement | Low | **Description** is generic beside otherwise domain-specific wording. | Use **Job description** so the expected complete vacancy text is immediately clear. | Proposed |

### MT-016 — Vacancy requirements draft and eligibility rules

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/vacancies/14/requirements/33/edit/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Improvements required
- **Functional status:** AI extraction, recruiter correction, and explicit v1 confirmation passed; filtering consumption pending

#### Completed functional checks

- **Pass:** Creating the vacancy produced requirements version 1 as a separate draft.
- **Pass:** Optional AI assistance explicitly says it replaces only draft structured fields and never confirms the version or creates executable filtering rules.
- **Pass:** The page separates draft saving from explicit review and confirmation.
- **Pass:** No typed filtering rule exists by default.
- **Pass:** Missing candidate facts are described as remaining eligible for recruiter review rather than failing automatically.
- **Pass:** AI extraction populated a source-grounded summary, 4.0 minimum years, `Prishtina, Kosovo`, hybrid work mode, professional English, and full-time employment.
- **Pass:** Docker and CI/CD remained nice-to-have rather than mandatory.
- **Pass:** Education and certification stayed blank; the absent degree requirement and on-call information were recorded as ambiguities rather than invented facts.
- **Pass:** AI-generated hard-constraint text remained non-executable notes and did not create typed filtering rules automatically.
- **Pass:** The vacancy detail preserves and displays the complete original description separately from matching inputs.
- **Pass:** Requirements history records v1 as an AI-assisted draft with its creator and creation time; no requirements are shown as confirmed before explicit confirmation.
- **Pass:** Reopening the saved draft verified `Python` as the first must-have, removed `Code review`, retained Docker and CI/CD as nice-to-have, and retained 4.0 minimum years.
- **Pass:** Explicit confirmation changed requirements v1 from **Draft** to **Confirmed** and recorded the confirming user and timestamp in requirements history.
- **Pass:** The current matching input displays the recruiter-corrected must-have skills (`Python`, Django, REST APIs, PostgreSQL, and automated testing); `Code review` is absent.
- **Pass:** Docker and CI/CD remain nice-to-have, 4.0 minimum years and the other verified criteria are retained, and the original vacancy description remains separate.
- **Pass:** No typed hard-constraint rule was created or activated during AI extraction, correction, or confirmation.

#### Pending functional checks

- Extracted skills use canonical identities while retaining source wording.
- Confirmed requirements and filtering rules become immutable together.
- Deterministic filtering consumes only explicitly approved eligibility rules.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-016-U01 | Usability defect | High | Recruiters face two competing representations: **Hard-constraint notes (not executable)** and a separate **Typed hard-constraint rules** editor. It is easy to enter a real requirement in the notes and incorrectly expect it to affect filtering. | Rename the executable concept to **Eligibility rules**. Keep ordinary notes under **Other requirements**, and clearly state that only enabled eligibility rules affect filtering. | Open |
| MT-016-U02 | Usability defect | High | Adding a rule leaves the requirements page, asks the recruiter to choose a technical rule type, and exposes source wording plus payload fields that are irrelevant to most selected types. Required-skill rules also require saving the skills form first. | Integrate rules into the requirements page. Show only the value control relevant to the chosen criterion and save the structured requirements plus rule selections in one validated action. | Open |
| MT-016-U03 | Usability defect | High | Existing structured fields and executable rules must be entered separately even when they express the same requirement, such as four years, Python, location, work mode, language, or employment type. | Add a recruiter-controlled **Required for eligibility** toggle beside each supported structured criterion. Create the typed rule behind the scenes and show its effect in plain language. | Open |
| MT-016-C01 | Usability defect | Medium | **Typed hard-constraint**, **executable**, **deterministic filtering**, and **unknown outcome** are implementation terms rather than normal recruiter language. | Use **Eligibility rule**, **Affects candidate filtering**, and **If information is missing: keep for review**. Reserve technical terms for audit/detail views. | Open |
| MT-016-V01 | Visual defect | Medium | The long narrow form stacks many large empty text areas, while most desktop width is unused and the rule section begins only after several screens of scrolling. | Group the draft into compact sections, use skill chips/list rows instead of large textareas, and use a wider two-column desktop layout with a sticky review summary. | Open |
| MT-016-F01 | Functional defect | Medium | AI classified **Code review** as a must-have skill even though the source describes reviewing code as a role responsibility, not an explicit mandatory qualification. Confirming it could overstate the requirement in matching. | Require explicit requirement language before promoting a responsibility to must-have; otherwise retain it in the role summary or responsibilities and flag uncertain classifications for review. | Open |
| MT-016-U04 | Usability defect | Medium | The must-have textarea displays the raw phrase **Python development experience** without showing that matching will canonicalize it to **Python**. Recruiters cannot inspect the identity that deterministic matching will use. | Present each skill as a row/chip with **Canonical skill: Python** and **Source wording: Python development experience**, allowing correction without losing provenance. | Open |
| MT-016-U05 | Usability defect | High | **Review and confirm** is a navigation link and does not save current form edits. Its placement beside **Save draft** makes it reasonable to assume both actions preserve changes, creating a data-loss risk during review. | Make **Review changes** submit and validate the current draft before opening confirmation, or disable it while the form is dirty and clearly require saving first. | Open |
| MT-016-F02 | Functional defect | High | The supposed confirmation page does not display the draft structured requirements. It shows the original vacancy description, an empty **Current confirmed requirements** panel, and an immediately executable **Confirm version 1** button. The recruiter cannot verify the corrected skills, experience, location, or ambiguities at the final approval boundary. | Add a dedicated confirmation preview that displays every draft field and eligibility rule beside the original source, including a clear changes summary. Place the final POST confirmation only after this preview and provide an **Edit draft** action. | Open |
| MT-016-V02 | Visual defect | Medium | Before first confirmation, the right-hand **Current confirmed requirements** card is mostly empty but matches the full height of the source-description card, creating a large blank panel while the actual draft is absent. | Use the right-hand panel for **Draft to be confirmed** during review; after confirmation, switch it to **Current matching input**. | Open |
| MT-016-U06 | Usability defect | Medium | After confirming v1, the recruiter remains at the bottom of a long detail page. The confirmed history is visible, but the page-level success state and likely next action are out of view, requiring a long scroll and extra orientation. | After confirmation, focus a concise success summary beside the next recommended action. Offer **Confirm and open vacancy** when appropriate, while retaining **Confirm only** for recruiters who are not ready to open it. | Open |

#### Recommended interaction

- AI-extracted criteria appear as editable suggestions, never enabled rules.
- Must-have skills, minimum experience, location, work mode, language, education, certification, and employment type each support an explicit **Required for eligibility** toggle where deterministic evaluation is supported.
- Enabling a toggle shows a plain-language preview such as **Explicitly lacking Python will exclude; missing skill information stays for review**.
- Source evidence is prefilled when available and remains inspectable in an expandable **Why this requirement?** detail.
- One action saves the draft and its rule selections; final confirmation remains separate and explicit.
- Protected or unsupported characteristics remain unavailable as rule types.

### MT-017 — Vacancy lifecycle: open

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/vacancies/14/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Pass with workflow improvement proposed
- **Functional status:** Opening passed; later lifecycle transitions pending

#### Completed functional checks

- **Pass:** Changing the vacancy from **Draft** to **Open** produced a visible success message.
- **Pass:** The lifecycle panel now reports **Vacancy status: Open**.
- **Pass:** The status transition did not alter the confirmed requirements or the rest of the vacancy record.

#### Pending functional checks

- Candidate evaluation is available for the open vacancy and consumes confirmed requirements only.
- The next valid lifecycle transitions are bounded and do not modify confirmed requirements.
- Unauthorized roles cannot change the vacancy lifecycle.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-017-U01 | Improvement | Medium | A recruiter must confirm requirements, return to the long vacancy detail page, scroll to the lifecycle section, and perform a second action to open a routine vacancy. | On the confirmation boundary, offer **Confirm requirements and open vacancy** as the primary routine action and **Confirm only** as the secondary option. Keep both transitions explicit and audited. | Proposed |
| MT-017-C01 | Improvement | Low | **Choose the next valid lifecycle state** describes the system model rather than the recruiter's task. | Use direct guidance such as **Open, pause, close, or archive this vacancy when its hiring stage changes. Confirmed requirements remain unchanged.** Show only currently available actions. | Proposed |

### MT-018 — Candidate eligibility filtering

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/vacancies/14/filter/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Improvements required
- **Functional status:** Pass for the current no-rule configuration; shortlist generation pending

#### Completed functional checks

- **Pass:** The filter explicitly uses confirmed requirements version 1.
- **Pass:** One candidate was evaluated and remained eligible; summary counts agree with the candidate result.
- **Pass:** Because no explicit eligibility rule was confirmed, the page transparently states that Drita passes this filtering stage by default.
- **Pass:** Unknown information is retained for recruiter review rather than silently treated as a failure.
- **Pass:** The page distinguishes eligibility filtering from a hiring decision.

#### Pending functional checks

- Generating a shortlist ranks Drita from the confirmed candidate profile and corrected confirmed vacancy requirements.
- Shortlist scoring uses `Python` and does not use the removed candidate skill or removed vacancy criterion `Code review`.
- A future vacancy with an explicitly approved eligibility rule produces inspectable pass, review, and fail outcomes.
- A changed confirmed candidate/vacancy input makes an existing shortlist stale.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-018-U01 | Usability defect | High | The prominent **Passed** result can be read as “the candidate meets the vacancy requirements,” but no must-have skill, experience, location, language, or work-eligibility criterion was actually used as an exclusion rule. The candidate passed only because no eligibility rules exist. | Use **Eligible for scoring** as the outcome and show a visible warning: **No eligibility rules are active; all candidates continue to scoring.** Provide a direct **Review eligibility rules** action for authorized recruiters. | Open |
| MT-018-U02 | Improvement | High | **Evaluate candidates** and **Generate shortlist** are separate routine steps even though filtering has no recruiter input on this page. This adds a page and click before every shortlist. | Make **Generate shortlist** the normal vacancy action and run eligibility filtering plus scoring together. Show the filter report inside the resulting shortlist; keep a separate preview only when the recruiter explicitly requests it or exceptions need review. | Proposed |
| MT-018-C01 | Usability defect | Medium | **Deterministic filtering**, **hard-constraint results**, and **passes this filtering stage by default** are implementation-oriented and difficult for a recruiter to interpret. | Use **Eligibility check**, **Eligibility results**, and **No eligibility rules are active, so this candidate continues to scoring**. Keep algorithm terminology in audit details. | Open |
| MT-018-V01 | Visual defect | Low | Four large metric cards consume most of the first screen for a one-candidate result, while the decisive no-rule explanation is lower and visually quieter. | Use a compact result summary and elevate the no-rule state above the counts. Expand to richer metrics only for larger candidate pools. | Open |

### MT-019 — Deterministic shortlist

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/vacancies/14/shortlists/47/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Clear and inspectable; workflow and precision improvements proposed
- **Functional status:** Deterministic shortlist passed; AI assessment and recruiter decision pending

#### Completed functional checks

- **Pass:** One eligible candidate produced one bounded shortlist entry at rank 1.
- **Pass:** Drita's confirmed profile matched `Python`, Django, REST APIs, PostgreSQL, and Docker with visible source evidence.
- **Pass:** `Automated testing` and CI/CD are explicitly **Not recorded** and receive zero points rather than being treated as proven negative evidence.
- **Pass:** The removed vacancy criterion `Code review` does not appear in the scoring breakdown.
- **Pass:** The removed candidate-profile skill `validated imports` does not influence the result.
- **Pass:** The displayed counts are correct: 4/5 must-have skills and 1/2 nice-to-have skills.
- **Pass:** The score of 75.01 follows the documented weighting: four must-haves at about 16.67 points plus Docker at about 8.33 points.
- **Pass:** No AI assessment or recruiter decision was created automatically by shortlist generation.
- **Pass:** The page states that the shortlist supports recruiter decisions and does not approve, reject, contact, or hire anyone.

#### Pending functional checks

- AI assessment generation uses this exact shortlist entry, confirmed candidate profile, and requirements v1.
- The assessment remains separate from the deterministic score and cannot change eligibility or rank.
- The review queue permits an explicit current recruiter decision while preserving assessment and decision version history.
- Regenerating after an input change marks this run stale and preserves it as inspectable history.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-019-U01 | Improvement | High | The normal path currently requires separate actions/pages for eligibility evaluation, shortlist generation, AI assessment generation, opening assessment review, and recording the recruiter decision. Most of those stages require no routine recruiter input. | Offer one **Create shortlist and assess candidates** action that runs filtering, scoring, and resumable assessment generation in the background. Bring the recruiter directly to an exception-focused review queue when work completes; retain every intermediate report for inspection. | Proposed |
| MT-019-U02 | Improvement | Medium | The page offers both whole-shortlist assessment and per-candidate assessment actions. For normal runs this makes the recruiter choose an execution method rather than a hiring task. | Make batch assessment the default routine action, label it **Assess shortlisted candidates**, and reserve per-candidate generation for retries or intentional reassessment. | Proposed |
| MT-019-U03 | Improvement | Medium | After generating the only candidate's assessment, the recruiter must still locate and open a separate assessment review before recording a decision. | For a one-candidate shortlist, redirect directly to its completed assessment review. For larger batches, redirect to the pending review queue with exceptions first. | Proposed |
| MT-019-V01 | Visual defect | Low | `75.01 of 100` and row values such as `16.67 / 16.67` imply more decision precision than the simple weighting policy supports. | Display the overall score as a rounded whole number or percentage and keep detailed unrounded calculation only in an expandable audit explanation. | Open |
| MT-019-V02 | Improvement | Low | The scoring-method panel and full evidence table make the page long even for one candidate, pushing the next action below the fold. | Keep the candidate summary and next action visible first; collapse calculation details and the full evidence breakdown behind **Show score details** by default. | Proposed |

### MT-020 — AI assessment embedded in shortlist

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/vacancies/14/shortlists/47/#assessment-entry-276`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Redesign required for density and task flow
- **Functional status:** Assessment content/versioning passed; deterministic-versus-AI skill discrepancy found

#### Completed functional checks

- **Pass:** The latest assessment is explicitly versioned as assessment v2 and is bound to candidate Profile v2 and requirements v1.
- **Pass:** Historical assessment v1 remains separately inspectable and collapsed by default.
- **Pass:** Assessment v2 resulted from an intentional second generation click; the separate v1/v2 records are expected immutable versioning, not accidental duplicate persistence.
- **Pass:** The AI score is labelled as separate from deterministic rank and cannot change hard-filter eligibility.
- **Pass:** The assessment identifies Python, Django, REST APIs, PostgreSQL, automated testing, and Docker as evidence-backed matches.
- **Pass:** The candidate's Gjilan location versus the vacancy's Prishtina location is recorded as an evidence-backed gap.
- **Pass:** CI/CD, four years of professional Python experience, hybrid attendance, full-time availability, professional English, and Kosovo work eligibility remain verification items rather than invented facts.
- **Pass:** The recruiter-review focus summarizes the unresolved evidence checks.
- **Pass:** No recruiter decision or outreach was created automatically.

#### Pending functional checks

- The dedicated assessment review displays the same immutable assessment and enables an explicit current recruiter decision.
- A decision records notes, actor, time, assessment version, profile version, and requirements version.
- An older assessment cannot receive a new current decision after inputs or assessment versions change.
- Outreach remains blocked until a current explicit approval exists.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-020-F01 | Functional defect | High | Deterministic scoring reports **Automated testing — Not recorded**, but the AI assessment identifies it as a match using explicit candidate evidence for automated test suites and pytest coverage. The saved CV also explicitly states both. The shortlist therefore understates an inspectable must-have match. | Extend the controlled, tested skill taxonomy so unambiguous variants such as `pytest`, `automated test suites`, and `test automation` can match canonical **Automated testing** while preserving original wording/evidence. Bump the shortlist algorithm version and add unsafe-near-match regression tests. | Open |
| MT-020-U01 | Usability defect | High | After assessment generation, the redirect targets the top of the entire candidate entry. The recruiter lands above the full deterministic evidence table and must scroll to find the newly created AI result. | Redirect and move keyboard focus directly to the new assessment summary or its dedicated review page. Show a concise success state and the primary **Review assessment** action immediately. | Open |
| MT-020-V01 | Visual defect | High | Candidate rank, deterministic score, seven-row evidence table, AI score, assessment summary, three finding columns, review focus, and version history are stacked into one very long card. Results feel scattered and the next decision is several screens away. | Use one compact candidate row/card showing rank, candidate, eligibility, skill score, AI signal, match/gap/verify counts, and **Review**. Move deterministic evidence and full AI findings into expandable details or the dedicated review page. | Open |
| MT-020-V02 | Visual defect | Medium | The three assessment columns contain many separate cards with unequal lengths and large blank areas, making related evidence difficult to compare. | Replace them with compact labelled rows or accordions: **Matches (6)**, **Gap (1)**, and **Verify (6)**. Open only the gap and verification summary by default; keep full source evidence one click away. | Open |
| MT-020-U02 | Usability defect | Medium | The deterministic score and AI score both display approximately `75`, but their different meanings are separated vertically and easy to confuse or interpret as duplicate confirmation. | Show a compact side-by-side summary labelled **Skill match: 75%** and **AI assessment: 75/100 · Green**, with short explanations and no blended total. | Open |
| MT-020-U03 | Improvement | Medium | **Generate new assessment** is prominent before the existing assessment has been reviewed, while **Open assessment review** is visually secondary. Reassessment creates another immutable AI version and consumes additional AI usage. | Make **Review assessment** the primary action. Move **Generate new assessment** into a secondary menu and explain that it creates a new version and incurs AI usage; require a reason when no input changed. | Proposed |

#### Recommended compact candidate presentation

- One row/card per candidate: rank and name; **Eligible for scoring**; rounded skill match; AI signal; counts for matched, gaps, and verify; one **Review** action.
- Expand **Score evidence** only when deterministic details are needed.
- Expand **Assessment findings** only when reviewing source evidence; keep the dedicated assessment page as the full decision surface.
- Keep historical versions in a collapsed **History** section rather than the main reading path.

### MT-021 — Dedicated assessment review and decision form

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/reviews/assessments/90/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Redesign required for compact decision-focused review
- **Functional status:** Evidence, validation, immutable decision versioning, and approval-gated outreach passed

#### Completed functional checks

- **Pass:** The dedicated page presents the same matching requirements, evidence-backed location gap, uncertainties, and recruiter-review focus as assessment v2 on the shortlist.
- **Pass:** The confirmed reusable profile reports no recorded profile ambiguity.
- **Pass:** No recruiter decision exists before an explicit form submission.
- **Pass:** The form offers only the supported human decisions: **Approve**, **Reject**, and **Revisit later**.
- **Pass:** Recruiter notes are requested as part of the immutable decision record.
- **Pass:** Outreach generation is blocked and explains that a current explicit approval is required.
- **Pass:** Assessment history preserves both explicitly generated versions and identifies v2 as the current page.
- **Pass:** The page explains that decisions cannot alter deterministic ranking or AI evidence and that outreach remains a separate action.
- **Pass:** Selecting **Revisit later** without notes was rejected and created no decision.
- **Pass:** Submitting **Revisit later** with notes created immutable decision v1 tied to assessment v2.
- **Pass:** Decision history displays the decision state, saved notes, assessment version, actor (`platform-owner-test`), and timestamp.
- **Pass:** The non-approval decision leaves outreach generation blocked with the correct explicit-approval explanation.
- **Pass:** A later **Approve** submission created decision v2 rather than editing or deleting the earlier **Revisit later** decision v1.
- **Pass:** Decision v2 retains the meaningful approval note and is attributed to assessment v2, `platform-owner-test`, and its own timestamp.
- **Pass:** The latest current approval enables **Generate outreach draft**; no draft was generated automatically by recording approval.

#### Pending functional checks

- Generating outreach creates an inspectable draft tied to decision v2 without approving or sending it.
- A stale or superseded approval cannot generate current outreach.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-021-U01 | Usability defect | High | The recruiter must scroll through several screens of repeated evidence before reaching the actual decision form. The summary, evidence, review focus, and decision are visually separate even though they belong to one task. | Make the page decision-focused: keep a compact candidate/assessment summary and sticky **Approve / Reject / Revisit** action area visible; place matches, gaps, uncertainties, and full source evidence in expandable sections. | Open |
| MT-021-V01 | Visual defect | High | The three-column findings layout creates long unequal columns and scattered cards, followed by several full-width panels for profile exceptions, review focus, decision, history, outreach, and versions. | Replace finding cards with compact rows/accordions and use one main review card. Move history and outreach into secondary collapsed sections or tabs. | Open |
| MT-021-V02 | Visual defect | Medium | Decision radio controls are horizontally detached from their labels and presented as a sparse vertical form beside a large empty left area. This weakens control association and looks unfinished. | Render each decision as a compact selectable card or segmented radio row with its control, label, and short consequence together. Place notes immediately below across the useful card width. | Open |
| MT-021-U02 | Improvement | Medium | The empty **Profile evidence exceptions** panel occupies a separate card even though there are no ambiguities. | Hide the empty section or show a small **No profile exceptions** badge in the summary. Expand the section only when exceptions exist. | Proposed |
| MT-021-U03 | Improvement | Medium | The blocked outreach panel is shown before any approval exists, adding another full section to an already long decision page. | Until a current approval exists, show a compact lock message after the decision form. Reveal the full outreach workflow only after approval. | Proposed |
| MT-021-C01 | Improvement | Low | **Record individual recruiter decision** and the long immutability explanation are accurate but formal for the primary task. | Use **Your decision** with concise supporting text: **Saved with this assessment; later changes create a new version.** | Proposed |
| MT-021-U04 | Usability defect | Medium | After decision v1 is saved, the empty decision form remains above the current decision history with the same primary **Record decision** action. The saved current state is visually secondary, increasing the chance of an unintended extra version. | Show the latest decision as the primary current state and replace the open form with a secondary **Change decision** action. Expanding it should explicitly state that a new immutable version will be created. | Open |
| MT-021-U05 | Improvement | Low | The required-notes check accepts the placeholder-like value `notes`, which satisfies non-empty validation but adds little audit value. | Provide decision-specific prompts/examples and require a modest meaningful length while still allowing concise recruiter reasoning. | Proposed |
| MT-021-U06 | Usability defect | High | After recording a decision, the page returns to the top. The saved decision, history, and newly enabled outreach action are several screens below, so the recruiter receives no immediate in-context confirmation or next step. | Redirect to and focus a **Decision saved** summary containing the current decision and next valid action. After approval, place **Generate outreach draft** beside that summary; after reject/revisit, offer **Next candidate** or **Back to review queue**. | Open |

#### Recommended compact decision surface

- Header: candidate, vacancy, assessment/profile/requirements versions, rounded skill score, AI signal, gap and verify counts.
- Default-open sections: evidence-backed gap and recruiter-review focus.
- Collapsed sections: matches, uncertainties, complete source evidence, assessment history, and decision history.
- Sticky or adjacent decision controls: **Approve**, **Reject**, **Revisit later**, notes, and one **Save decision** action.
- Show outreach only after approval; keep its generation and final approval separate.

### MT-022 — Outreach draft and email completion

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/outreach/drafts/9/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Workflow redesign required
- **Functional status:** Safe draft generation passed; application workflow ends before email delivery

#### Completed functional checks

- **Pass:** Approved decision v2 generated a separate outreach draft v1; nothing was approved or sent automatically.
- **Pass:** The draft identifies its creator, time, candidate, vacancy, and approved decision version.
- **Pass:** Subject and body are inspectable before external use.
- **Pass:** The contact-safety panel shows **Future roles allowed**, **Consent: Not required**, and **Reason for storing data: Legitimate interests** from the candidate source.
- **Pass:** The app correctly does not require consent when consent is not the selected processing reason.
- **Pass:** Copy/export remain unavailable until the current exact draft receives final approval.
- **Pass:** Draft version history remains immutable and inspectable.
- **Pass:** No application email was sent and the page does not falsely report delivery.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-022-U01 | Usability defect | Critical | A routine recruiter must approve the candidate, separately generate outreach, enter another approval note, tick a compliance declaration, approve the exact draft, then copy/export it for manual work elsewhere. The repeated boundaries make the workflow too slow for normal hiring. | Replace the sequence with the approved two-stage workflow below. Keep immutable versions and safety checks behind the actions rather than requiring separate pages and approvals. | Open |
| MT-022-F01 | Missing functionality | High | The application produces approved text but cannot address an email, open an email client, or send through a connected mailbox. The main recruiter workflow therefore ends before contact occurs. | Add staged email completion: first **Open in email app**, then Gmail/Microsoft 365 OAuth delivery. Preserve exact-recipient verification, provider result, actor/time audit, and failure visibility. | Proposed |
| MT-022-U02 | Usability defect | High | The final approval form repeats compliance confirmation already represented by stored source/contact values and repeats recruiter reasoning already captured in the candidate decision. | Run the recorded source/contact check automatically. Show one actionable blocker only when it fails. Treat the recruiter's final reviewed email action as approval of that exact recipient, subject, and body. | Open |
| MT-022-C01 | Usability defect | Medium | The safety explanation is long and combines lawful reason, consent, allowed contact, rediscovery, final approval, copy, and export in one paragraph. | Show a compact status such as **Contact allowed · Legitimate interests · Consent not required**, with details expandable and direct correction links when blocked. | Open |
| MT-022-V01 | Visual defect | Medium | Draft content, contact basis, final approval, copy/export availability, action history, version history, and safety notices are separate full-width panels, producing another long workflow page. | Use one email composer card with recipient, subject, body, safety status, and final action. Move audit/version history into collapsed secondary details. | Open |

#### Approved simplified workflow direction

1. **Approve candidate and prepare email**
   - One recruiter action records the candidate decision and creates/queues the outreach draft.
   - Existing source, allowed-contact, processing-reason, assessment, and staleness checks run automatically.
   - If contact is blocked, show one precise reason and a direct correction action; do not create a unusable draft.
2. **Review and send**
   - Open one email-composer screen with exact recipient, editable subject/body, and a compact safety status.
   - **Open in email app** or **Send email** is itself the explicit final approval of that exact recipient, subject, and body; no separate approval-notes form or checkbox is required.
   - Saving edits may create immutable draft versions behind the scenes without making the recruiter manage versions during routine work.
   - Copy and export remain secondary options under **More**, not the main completion path.

Consent is required only when consent is the selected processing reason. Every send/handoff still requires an allowed-contact state and current processing reason.

#### Proposed email delivery stages

1. **First delivery:** **Open in email app** using the candidate's exact recorded email, reviewed subject, and reviewed body. Record the handoff actor/time but do not claim the email was sent.
2. **Professional delivery:** connect Gmail and Microsoft 365 using organization-authorized OAuth. Send from the recruiter's mailbox and store provider message ID, result, actor, and time without storing mailbox passwords.
3. **Optional later delivery:** support a verified organization sending domain through a transactional provider for organizations that do not use recruiter mailboxes.

Direct Gmail/Microsoft 365 sending should be treated as proposed product scope and receive implementation approval after the remaining manual review is complete.

### MT-023 — Assessment review queue

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/reviews/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Good compact foundation; prioritization and summary polish required
- **Functional status:** Latest-assessment queue and scopes passed

#### Completed functional checks

- **Pass:** The queue contains one latest assessment for Drita rather than duplicate cards for assessment v1 and v2.
- **Pass:** Summary counts show one latest assessment, zero pending decisions, one approved latest decision, zero rejected, and zero revisit-later current decisions.
- **Pass:** The earlier **Revisit later** decision v1 does not incorrectly replace or double-count the latest **Approve** decision v2.
- **Pass:** The default pending scope is empty because a current decision exists.
- **Pass:** **Needs focus** contains Drita despite approval because the latest assessment has one evidence-backed gap and five uncertainties.
- **Pass:** **Changed inputs** is zero because Profile v2, requirements v1, and the shortlist evidence boundary remain current.
- **Pass:** **All** contains the same single latest assessment.
- **Pass:** The candidate card exposes vacancy/shortlist context, candidate, assessment/profile versions, AI score, gap and uncertainty counts, latest decision, summary, review focus, and an inspect action.

#### Pending functional checks

- **Inspect decision** opens the already-tested current assessment/decision page without selecting an older version.
- A later candidate/profile/vacancy correction moves the item into **Changed inputs** and blocks a new current decision until regeneration.
- Pagination and organization isolation remain correct with multiple assessments.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-023-U01 | Usability defect | High | The queue defaults to **Decision pending (0)** and displays an empty state even though **Needs focus (1)** contains the only actionable assessment. The recruiter must notice and click another scope before seeing work. | Default to a unified **Needs attention** queue combining pending decisions, evidence gaps/uncertainties, and changed inputs. If kept separate, automatically open the first non-empty priority scope. | Open |
| MT-023-U02 | Usability defect | Medium | A green traffic-light badge appears beside an item explicitly classified as **Needs focus** with one gap and five uncertainties. Green can be read as “no review needed” even though it represents only the AI signal. | Label it **AI assessment: Green · 75** and keep **Needs attention** as the dominant workflow status. Never use the AI traffic light as the card's overall state. | Open |
| MT-023-V01 | Visual defect | Medium | Five large summary cards do not fit one row; **Revisit later** wraps alone onto a second row and leaves substantial empty space. | Use one compact status strip or smaller inline metrics, prioritizing **Needs attention**, **Pending**, **Approved**, and total. Move less-used counts into filters. | Open |
| MT-023-C01 | Usability defect | Low | The decision badge reads **Decision: Approve**, using the action label rather than the saved state. | Display **Decision: Approved**; use **Approve** only on an action control. | Open |
| MT-023-C02 | Usability defect | Medium | The bottom notice says outreach remains a separate, later approved action. That wording reinforces the workflow now approved for simplification and conflicts with **Approve candidate and prepare email → Review and send**. | Update the notice after the workflow redesign: decisions remain human-controlled, and preparing an email does not send it; the reviewed send/handoff action is the explicit final boundary. | Open |
| MT-023-V02 | Improvement | Low | The full recruiter-review recommendation occupies a large highlighted block inside every queue card. This will make multi-candidate queues vertically long. | Show a one- or two-line focus summary with **Show details**; keep gap/verify counts and the primary review action visible. | Proposed |

### MT-024 — Background jobs list

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/jobs/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Pass
- **Functional status:** Pass for the single completed-job state

#### Completed functional checks

- **Pass:** The organization-scoped list loads and contains the candidate-profile extraction job tested in MT-009 and MT-010.
- **Pass:** The row reports a succeeded state, complete `1 / 1` progress, zero exceptions, and the expected queued timestamp.
- **Pass:** The job name provides a clear route to the previously tested job detail.
- **Pass:** The compact table is easy to scan and does not repeat the detailed job metrics unnecessarily.
- **Pass:** The page correctly directs recruiters to start work from Candidates or a shortlist rather than presenting background processing as a separate creation workflow.

#### Pending functional checks

- Multiple jobs are ordered predictably and remain usable with pagination or a longer history.
- Shortlist-assessment jobs appear with the correct recruiter-facing type and progress.
- Organization isolation and role permissions prevent cross-tenant access.
- Completed jobs expire according to the organization's retention policy without affecting candidate profiles, assessments, or decisions.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-024-C01 | Improvement | Low | **Background jobs** and “durable profile extraction and shortlist assessment batches” are accurate but technical recruiter-facing language. | Consider **Processing activity** as the navigation/page label and use plain row labels such as **Create candidate profiles** and **Assess shortlist**; retain technical terminology in administrator or diagnostic detail. | Proposed |
| MT-024-C02 | Improvement | Low | The queued timestamp has no timezone label or relative context, consistent with the broader timestamp issue recorded in MT-008-U03 and MT-010-U01. | Apply the shared display-timezone treatment rather than adding a page-specific solution. | Proposed |

### MT-025 — Organization AI usage report

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/ai-usage/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Corrected; compact summary and readable operational values require browser retest
- **Functional status:** Aggregate totals and configured live cost calculation pass; filters require follow-up

#### Completed functional checks

- **Pass:** The default boundary is **Past 30 days · All workflows**.
- **Pass:** Six completed attempts reconcile to five succeeded, one failed, zero pending, and an 83.3% success rate.
- **Pass:** The 11,225-token total agrees across the summary, model breakdown, workflow rows, and daily row.
- **Pass:** Workflow totals reconcile: two candidate-profile attempts, two match assessments, one outreach draft, and one vacancy-requirements attempt.
- **Pass:** The model table reports the same six attempts, five successes, one failure, 11,225 tokens, 5,284 ms average latency, and zero retries.
- **Pass:** The safe failure report exposes only the application-safety-validation category and count; the page does not display prompts, responses, CV content, candidate/contact data, recruiter notes, or outreach content.
- **Pass:** Metadata availability reports complete coverage for all six attempts, and the single daily row reconciles with the report totals.
- **Pass:** The previously displayed zero cost came from the toolkit v1.0.0
  placeholder price table, not verified free provider usage. The application now
  trusts cost estimates only when both operator rates are explicit.
- **Pass:** The environment examples configure the official `gpt-5.4-mini` API
  rates verified on 2026-09-01: `$0.75` input and `$4.50` output per one million
  tokens. Missing rate configuration produces unavailable cost metadata.
- **Pass:** A recorded browser test after configuration showed seven attempts,
  13,642 tokens, and a non-zero `$0.003305` estimate, confirming that new live
  usage uses the configured rates.
- **Implemented:** Four primary metrics, a compact operational strip, and a
  collapsed technical-details section replace the former equally weighted long
  report layout.
- **Implemented:** Token counts use thousands separators, sub-cent positive cost
  is displayed as `< $0.01`, zero remains `$0.00`, and latency uses seconds when
  at least one second.
- **Implemented:** Failure stages and application-validation failures use plain
  administrator wording without exposing private provider or validation detail.

#### Pending functional checks

- Change the period to 7 days, 90 days, and all time and confirm every summary/table uses the same boundary.
- Filter each workflow and verify its totals against the corresponding unfiltered workflow row.
- Reopen the corrected report and confirm the compact layout, readable values,
  and collapsed technical details at desktop and narrow viewport widths.
- Create an old pending attempt and confirm it is counted separately after 15 minutes rather than treated as failed.
- Confirm another organization receives `404` and cannot infer any totals.
- Decide whether aggregate tokens, costs, models, latency, and failures should be restricted to organization administrators; the current implementation permits every active organization member.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-025-U01 | Usability defect | Medium | Eight large summary cards consume two full rows before the useful workflow breakdown, then five reporting sections receive similar visual weight. The result is a long technical page that is difficult to scan. | Keep four primary metrics at the top: **AI attempts**, **Success rate**, **Tokens**, and **Estimated cost**. Put latency, retries, failures, and pending into a compact operational strip. Collapse **Model**, **Failure**, and **Metadata availability** under **Technical details** by default. | Implemented — browser retest pending |
| MT-025-V01 | Visual defect | Medium | Operational values use raw machine-like formatting: `11225`, `$0.000000`, and `5284 ms`. This weakens the otherwise professional presentation. | Use locale-aware separators and readable units: **11,225 tokens**, **$0.00** or **< $0.01**, and **5.3 s**. Retain precise values only in a tooltip/export if needed. | Implemented — browser retest pending |
| MT-025-C01 | Usability defect | Medium | Failure labels such as **Application validation** and **Application safety validation** are implementation terminology and do not tell an administrator what action is possible. | Use a plain summary such as **AI output did not pass safety checks**, with an optional technical-category disclosure. Link to the relevant safe job/exception list when remediation is possible, without exposing private AI content. | Implemented — browser retest pending |
| MT-025-A01 | Product/access decision | Medium | The report includes organization-wide cost, model, failure, and operational metadata but is currently available to every active member, not only organization administrators. This also adds a low-frequency technical item to every recruiter's primary navigation. | Restrict the full report to organization administrators, or provide recruiters only a minimal processing-status view. Move the full report under organization settings/administration as part of CR-001 navigation and role work. | Implemented — 2026-09-01 |
| MT-025-F01 | Correctness check | High | All six attempts claimed available estimated-cost metadata because the toolkit v1.0.0 built-in `gpt-5.4-mini` table contained placeholder zeroes. This could falsely imply that AI usage was free. | Explicitly configure the verified model rates, forward estimates only when both rates are configured, and leave missing prices unavailable. Do not rewrite historical events. | Resolved — 2026-09-01 |

### MT-026 — Privacy, retention, and audit dashboard

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/privacy/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Retention summary and activity history corrected; browser retest pending
- **Functional status:** Current summary and minimized histories pass

#### Completed functional checks

- **Pass:** The summary reports zero pending deletions, zero candidate records due, one candidate missing a retention date, and zero deleted-record minimization issues.
- **Pass:** The detailed retention review agrees with the summary: no candidate, source, or document is due; one candidate, one source, and one document are missing dates.
- **Pass:** The empty candidate-deletion queue states that no request is pending and distinguishes a staged request from permanent administrator purge.
- **Pass:** The data-minimization integrity result reports no retained identity, source, document, skill, or shortlist data for a deleted candidate.
- **Pass:** Privacy events show only time, generic action, object type/ID, and actor for the tested profile, candidate, and source changes.
- **Pass:** Workflow history reconciles with prior tests: six AI attempts, two match-assessment versions, and two recruiter-decision versions; CSV-created sources, outreach approvals, and outreach copy/export are empty.
- **Pass:** No source/reference text, contact fields, CV content, prompt/response content, decision notes, approval notes, or outreach subject/body are exposed.
- **Pass:** **Open retention settings** is visible for the current administrator/platform-owner test account.

#### Pending functional checks

- Open retention settings and verify its dry run, policy defaults, legal holds/exceptions, cleanup confirmation, and role restrictions.
- Create a due candidate and confirm scheduled retention creates one staged deletion request without purging data or duplicating the request when rerun.
- Confirm a non-administrator cannot review or execute a purge and another organization receives `404` without seeing counts or actor names.
- Confirm a purged candidate leaves only the intended minimized event/tombstone information and no private files.
- Verify long audit histories are bounded or paginated and preserve stable ordering.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-026-V01 | Visual defect | Medium | Four summary metrics render as three cards followed by **Minimization issues** alone on a second row, leaving a large empty area at desktop width. | Use one compact four-item status strip or size the four cards to fit one row. Give warning styling only to non-zero actionable counts. | Implemented — browser retest pending |
| MT-026-U01 | Usability defect | High | The retention review gives three large cards to empty categories (`None`) while the only actionable condition—missing dates—is the fourth card. Administrators must scan substantial empty space to find the issue. | Lead with a consolidated **Needs attention** list. Hide zero-result panels by default or reduce them to compact status rows; show direct links for the candidate/source/document missing a date. | Implemented — browser retest pending |
| MT-026-U02 | Usability defect | Medium | Workflow history is split into six large cards containing raw bullet lists. This repeats reporting already available elsewhere, creates a very long page, and will become unmanageable as records accumulate. | Replace the cards with one compact, paginated **Audit log** table with type/status/date filters. Show the latest entries first and link to safe internal details; keep full content excluded. | Implemented — browser retest pending |
| MT-026-C01 | Usability defect | Medium | Labels such as **Frozen for explicit review**, **candidate-level policy review**, **deleted-record integrity checks**, and raw values such as `candidate_profile #71` require implementation knowledge. | Use plain administrator wording, for example **Deletion requests**, **Retention dates missing**, and **Deletion integrity**. Keep object IDs as secondary audit references and provide a safe inspect link where the object still exists. | Implemented — browser retest pending |
| MT-026-A01 | Product/access decision | Medium | Organization-wide privacy history, actor names, retention counts, and workflow audit summaries are visible to every active organization member, while only retention settings/actions are administrator-gated. This also keeps another low-frequency administrative link in recruiter navigation. | Make the full **Data retention & audit** workspace organization-admin-only under organization settings. Keep only candidate-specific privacy information available to recruiters where their workflow needs it. Resolve this with CR-001 role/navigation work. | Implemented — 2026-09-01 |

The first browser pass of the activity filters showed the heading compressed
beside three native select controls. The corrected filter bar now occupies its
own bordered three-column row with labels above full-width controls and stacks
to one column on narrow screens. The stale recruiter-visible navigation test was
also corrected to enforce the already-approved administrator-only boundary.

### MT-027 — Retention settings and deletion controls

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/retention/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Major form and hierarchy improvements required
- **Functional status:** Read-only preview and safeguards present; mutation paths not yet executed

#### Completed functional checks

- **Pass:** The administrator page provides separate dry-run counts for temporary intake, completed jobs, obsolete shortlists, abandoned outreach chains, old metadata, and blocked bundles.
- **Pass:** The current dry run reports zero in every category, zero eligible bundles, and zero estimated temporary private-file bytes.
- **Pass:** Policy v1 contains the approved defaults: 7 days for abandoned intake, 90 days for completed jobs, 180 days for uncommitted workflows, 365 days for usage/audit metadata, and a 30-day organization recovery window.
- **Pass:** A global legal-hold control states that it blocks scheduled cleanup and organization purge.
- **Pass:** Scoped retention exceptions support a scope, optional object, required reason, and optional expiry.
- **Pass:** Applying cleanup requires the exact typed phrase `PURGE ELIGIBLE DATA` and states that eligibility is recalculated inside the deletion transaction.
- **Pass:** Organization deletion is visually separated as staged tenant deletion and explains suspension, the 30-day recovery window, scheduled purge, private-file removal, and content-free lifecycle evidence.
- **Pass:** No cleanup or organization deletion was executed during this visual pass.

#### Pending functional checks

- Save a harmless policy change and confirm versioning, validation bounds, success feedback, dry-run recalculation, and audit attribution.
- Activate the legal hold and confirm both lifecycle cleanup and organization purge are blocked; then verify safe hold removal and its audit trail.
- Add group-wide and object-specific exceptions, verify expiry behavior, remove them, and confirm only the intended organization records are affected.
- Create one eligible record in each cleanup category and confirm the preview identifies the correct dependency-safe bundle without exposing private content.
- Test an incorrect purge confirmation phrase, then apply a controlled disposable cleanup and confirm idempotency and file deletion.
- Confirm a recruiter receives `403` and another organization's member receives `404`.
- Inspect the organization-deletion review page without submitting a deletion request.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-027-V01 | Visual defect | High | The policy and exception forms render as largely unstyled browser controls inside oversized two-column panels. Labels, inputs, help text, and checkboxes do not align consistently, making an administrator screen look unfinished. | Replace `form.as_p` rendering with the product's standard field components. Use a compact labelled grid, consistent input widths, aligned help/error text, and restrained button widths; stack cleanly on smaller screens. | Implemented — browser retest pending |
| MT-027-U01 | Safety/usability defect | High | An exception requires an administrator to choose a scope and manually type an internal object ID. The default scope appears as `---------`, and a typo or cross-scope ID can make the administrator believe data is protected when no real bundle matches. | Label the placeholder **Choose what to protect** and replace raw IDs with an organization-scoped searchable selector for eligible intake, job, shortlist, outreach, or organization records. At minimum, validate that the entered ID exists, belongs to this organization, and matches the selected scope before saving. | Implemented — browser retest pending |
| MT-027-U02 | Usability defect | Medium | Six large preview cards are displayed even though every count is zero, pushing the actual policy controls below the first viewport. | Use one compact dry-run summary. Lead with **Nothing eligible for deletion** when all counts are zero; expand category details only when a count is non-zero or the administrator requests them. | Implemented — browser retest pending |
| MT-027-U03 | Safety/usability defect | Medium | The destructive confirmation field and **Purge eligible bundles** button remain available when zero bundles are eligible. This creates unnecessary risk cues and invites a meaningless submission. | Disable or hide the confirmation form when the current plan is empty and show **Nothing to delete**. Reveal it only after a non-zero preview, with the preview timestamp/policy version visible. | Implemented — browser retest pending |
| MT-027-C01 | Usability defect | Medium | Labels such as **Uncommitted workflow history**, **Metadata**, **Apply current dry-run**, and **record bundles** require knowledge of the lifecycle implementation and do not clearly describe the consequences. | Use plain labels with concise examples: **Unused shortlists and abandoned outreach**, **AI usage and audit history**, and **Delete the items shown above**. Add short “what is protected” guidance beside each retention limit. | Implemented — browser retest pending |
| MT-027-U04 | Improvement | Low | **Back to dashboard** returns to the general organization dashboard even though this page was opened from Privacy & audit, adding navigation distance during compliance work. | Use a breadcrumb or **Back to Privacy & audit** link, while keeping Organization settings available through the administrator navigation. | Implemented — browser retest pending |
| MT-027-S01 | Safety improvement | Medium | The global legal hold is a checkbox embedded in the numeric policy form and has no visible reason, expiry, activation actor/time, or special confirmation when it is removed. Its operational importance is easy to miss. | Give legal hold a separate status panel. Record a non-private reason, actor/time, and optional expiry; make activating it easy, but require explicit confirmation to remove it because removal re-enables deletion. | Proposed |

### MT-028 — Organization suspension and deletion confirmation

- **Date:** 2026-08-29
- **Route:** `/organizations/second-agency-test/delete/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Clear foundation; safety context and form styling required
- **Functional status:** Confirmation boundary displayed; no suspension submitted

#### Completed functional checks

- **Pass:** Opening **Review organization deletion** does not suspend the organization or mutate tenant data.
- **Pass:** The page clearly states that submission immediately blocks workspace access and schedules later deletion of the tenant dependency graph and private files.
- **Pass:** A typed confirmation is required before submission.
- **Pass:** The destructive action is labelled **Suspend organization**, accurately describing the immediate state change rather than claiming an immediate purge.
- **Pass:** A visible **Cancel** action returns to retention settings.
- **Pass:** No deletion request was submitted during this test.
- **Verified from the implemented recovery rules:** An active organization administrator can restore the suspended organization before the purge deadline even if a platform owner requested the deletion. The cancellation is recorded as a lifecycle event.

#### Pending functional checks

- Submit an incorrect confirmation phrase and verify an inline validation error with no state change.
- Use a disposable organization to verify suspension, immediate workspace denial, exact recovery deadline, recovery by an active organization administrator, and restored access.
- Verify the scheduled purge cannot run before the deadline and is blocked by an active legal hold or organization-level exception.
- Verify behavior after the recovery deadline and confirm that only content-free tombstone/lifecycle evidence remains after purge.
- Confirm recruiters and cross-organization members cannot open or submit this page.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-028-S01 | Safety/usability defect | High | The confirmation content never displays the organization name **Second Agency Test**. In a managed multi-organization system, an administrator or platform owner can reach a correct-looking generic page for the wrong tenant. | Show the organization name prominently in the heading and danger panel. Include the slug/identifier as secondary text and require an organization-specific confirmation such as typing the organization name or `SUSPEND SECOND AGENCY TEST`. | Implemented — browser retest pending |
| MT-028-S02 | Safety/usability defect | High | The page says recovery remains available until “the policy deadline” but does not show the configured 30-day window or calculate the exact purge date/time before confirmation. | Display **Access stops immediately**, **Recovery available for 30 days**, and the exact projected purge deadline in the configured display timezone. Recalculate the actual deadline transactionally at submission. | Implemented — browser retest pending |
| MT-028-C01 | Usability defect | Medium | The phrase `DELETE ORGANIZATION` confirms an action whose immediate button and result are **Suspend organization**. The mixed terminology makes it harder to understand whether data disappears immediately. | Use one explicit sequence throughout: **Suspend now and schedule deletion**. The confirmation should name the organization and state that permanent purge occurs only after the displayed recovery deadline. | Implemented — browser retest pending |
| MT-028-V01 | Visual defect | Medium | The confirmation field uses the same unstyled, narrow browser input seen in the retention forms, and the label/input sit on one long line inside an oversized panel. | Render a focused danger confirmation card with a short consequence summary, full-width labelled confirmation field, inline validation, and aligned **Cancel** / destructive actions. | Implemented — browser retest pending |
| MT-028-S03 | Safety improvement | Medium | The page does not show whether a legal hold or organization retention exception currently blocks final purge. Suspension can still be valid, but the administrator cannot see that permanent deletion is blocked. | Show current hold/exception status and explain separately whether it affects immediate suspension, scheduled purge, or both. Link administrators back to the relevant retention control. | Implemented — browser retest pending |

### MT-029 — Platform organization list

- **Date:** 2026-08-30
- **Route:** `/platform/organizations/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Clean and professional list; operational scaling controls required
- **Functional status:** Visible tenant-management metadata passes; creation and permissions remain pending

#### Completed functional checks

- **Pass:** The platform-owner view lists organizations without exposing candidates, CVs, vacancies, assessments, decisions, or outreach content.
- **Pass:** Each visible row provides organization name, stable slug, active/suspended status, active-administrator count, membership count, and a **Manage** action.
- **Pass:** Organizations with duplicate/similar names remain distinguishable through their slugs.
- **Pass:** **Second Agency Test** reports two active administrators and four memberships, consistent with the organization used during this review.
- **Pass:** The table is compact, aligned, and easy to scan at the tested row count.
- **Pass:** The follow-up top-of-page screenshot confirms a clear **Platform management · Organizations** heading, concise tenant-isolation explanation, and prominent **Create organization** action.
- **Pass:** The platform-owner header is substantially less crowded than the recruiter workspace header.

#### Pending functional checks

- Confirm a non-platform account and a technical superuser without the explicit platform-owner capability receive `403`.
- Open **Manage** for Second Agency Test and verify status, administrators, isolation messaging, and lifecycle controls.
- Test organization creation with a new first administrator, duplicate names/slugs, existing-user linking, password validation, and rollback on failure.
- Verify suspended organizations show the recovery state/deadline clearly and remain recoverable without exposing tenant content.
- Verify search, filtering, ordering, and pagination with a production-sized organization list.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-029-O01 | Operational defect | High | The visible active organization `test3` has zero active administrators and zero memberships, yet receives the same healthy **Active** presentation as accessible tenants. It is effectively orphaned and has no in-app administrator who can operate it. | Add a prominent **Needs administrator** state and platform alert for active tenants with no active admin. Provide a direct **Add administrator** recovery action. Preserve the service rule that prevents removal of the final active administrator, and add a periodic integrity check for records created outside the normal service. | Resolved — browser tested 2026-09-03 |
| MT-029-U01 | Usability defect | Medium | The organization list has no visible search, status/health filters, or pagination. Repeated **Manage** rows are acceptable for test data but will not scale as a managed SaaS control plane. | Add search by name/slug, filters for **Active**, **Suspended**, and **Needs attention**, predictable sortable columns, and bounded pagination. | Resolved — browser tested 2026-09-03 |
| MT-029-C01 | Usability defect | Medium | **Memberships** counts all membership records, while **Active administrators** counts only active administrators. The mixed counting boundary is not visible and can mislead a platform owner when inactive memberships exist. | Show **Active members** and optionally a secondary total, or label the current value explicitly as **Total memberships**. Add recruiter/admin breakdown only in organization detail. | Resolved — browser tested 2026-09-03 |
| MT-029-U02 | Improvement | Low | The list does not surface the most important platform exceptions, such as suspended tenants nearing purge or tenants with no administrator, until each row is inspected. | Add a compact summary above the list for **Active**, **Suspended**, **Needs administrator**, and **Purge approaching**; emphasize only non-zero exception counts. | Partially implemented — active, suspended, and administrator exceptions shown |
| MT-029-N01 | Navigation issue | Low | The platform-owner header contains both **Organizations** and **Platform**. In this context, one opens member workspaces while the other manages tenants, but the distinction is not self-evident. | Rename them **Workspaces** and **Platform admin**, or place the control plane under a clearly labelled administrator menu. | Proposed |

### MT-030 — Platform organization management

- **Date:** 2026-08-30
- **Route:** `/platform/organizations/10/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Clean and focused; action semantics need refinement
- **Functional status:** Read-only organization/admin state passes; access mutations not submitted

#### Completed functional checks

- **Pass:** The page is limited to organization lifecycle and administrator membership management.
- **Pass:** The organization status panel identifies slug `second-agency-test`, active state, and the staged **Suspend and schedule deletion** action.
- **Pass:** The isolation panel explicitly states that platform ownership alone does not expose candidates, CVs, vacancies, assessments, decisions, or outreach.
- **Pass:** Administrator state reconciles with the list: `platform-owner-test` and `second-admin2` have active administrator memberships, while `second-admin` is inactive.
- **Pass:** The platform owner can add an administrator and restore an inactive administrator membership.
- **Pass:** The page states that at least one administrator must remain active, matching the service-level safeguard.
- **Pass:** No recruiter-management or recruitment-content controls appear in the platform workspace; recruiters remain an organization-administrator responsibility.
- **Pass:** No membership or lifecycle state was changed during this visual pass.

#### Pending functional checks

- The **Add administrator** form is visually reviewed in MT-031; still test new-user creation, existing-user linking, validation, invitation/password handling, and duplicate membership behavior.
- Attempt to remove the final active administrator and confirm the service blocks it without changing state.
- Remove and restore a disposable administrator membership and verify audit attribution and organization-list counts.
- Confirm the platform owner cannot open tenant content without the separate active membership shown in this table.
- Suspend a disposable organization and verify this page switches to recovery status with the exact deadline and recover action.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-030-S01 | Safety/usability defect | High | **Remove access** is an immediate POST action with no confirmation page or visible identity/context check. A platform owner can revoke an administrator through one accidental click. | Add a concise confirmation dialog/page naming the administrator and organization, describing the effect, and confirming how many active administrators will remain. Disable the action client-side and reject it server-side when it would remove the final active administrator. | Resolved — browser tested 2026-09-03 |
| MT-030-C01 | Usability defect | Medium | The status pill says **Inactive**, but the action is toggling only this organization membership—not necessarily disabling the person's global account. The label can be misread as an account-wide state. | Label the column **Organization access** and use **Active** / **Access removed**. Keep global account status separate if it is later managed by the platform. | Resolved — browser tested 2026-09-03 |
| MT-030-C02 | Improvement | Medium | The isolation message is correct, but `platform-owner-test` simultaneously appears as an active organization administrator. Without an explicit distinction, a platform owner may not understand that their workspace access comes from this separate membership. | Add a small **Separate workspace membership** note/badge on platform-owner rows and explain that removing it removes tenant-content access while preserving platform-owner capability. | Resolved — browser tested 2026-09-03 |
| MT-030-U01 | Improvement | Low | The administrator table shows username and optional full name but no account identifier such as email, which can make similarly named users difficult to distinguish before access changes. | Show the verified account email or another stable non-sensitive identifier appropriate for platform account management, especially in the confirmation step. | Resolved — browser tested 2026-09-03 |

### MT-031 — Add organization administrator form

- **Date:** 2026-08-30
- **Route:** `/platform/organizations/10/administrators/new/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Consistent field styling; workflow simplification and security improvements required
- **Functional status:** Form displayed; no administrator submitted

#### Completed functional checks

- **Pass:** The form offers username, email, first name, last name, temporary password, and password confirmation.
- **Pass:** Help text distinguishes fields required only for creating a new account from the existing-account path.
- **Pass:** The action grants an administrator membership for the selected organization rather than general platform ownership.
- **Pass:** Password values are masked, and a separate confirmation field is provided.
- **Pass:** **Cancel** returns without creating or linking an account.
- **Pass:** Fields and buttons use the main product styling and remain readable at the tested desktop width.
- **Pass:** No administrator account or membership was created during this pass.

#### Pending functional checks

- Link a known existing user with all creation-only fields blank and confirm their account details/password remain unchanged.
- Verify the UI identifies the matched existing account before granting access and rejects inactive or already-linked accounts.
- Create a disposable new account and test required email, password mismatch, Django password validators, atomic membership creation, and audit attribution.
- Verify whether a new user is forced to set a private password before normal workspace access; the current implementation only asks the platform owner to share a temporary password and ask the user to change it.
- Confirm non-platform users cannot open or submit the form.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-031-S01 | Access-control usability defect | High | A single username field silently decides whether to link an existing account or create a new one. A typo that happens to match another account can grant that person administrator access, while a typo that matches nobody unexpectedly switches to account creation. | Make the choice explicit: **Add existing user** with an organization-safe account search and identity confirmation, or **Invite new administrator**. Show the matched full name/email before the final grant action. | Implemented — browser retest pending |
| MT-031-S02 | Security defect | High | New accounts receive a manually shared temporary password, but the data model/workflow does not force a password change at first sign-in. The credential can remain valid indefinitely if the user ignores the help text. | Replace shared passwords with an expiring one-time invitation/password-setup link. Until email delivery is implemented, enforce a server-side **must change password** state before any workspace access and provide a safe one-time delivery procedure. | Open |
| MT-031-U01 | Usability defect | High | The temporary-password field appears browser-autofilled while username `koci` is entered. For an existing account, any password value causes server validation to reject the submission, so password-manager autofill creates a confusing failure without user intent. | Split existing/new flows and set correct autocomplete attributes (`username` for account lookup and `new-password` for both new-password fields). Hide or disable creation-only fields after an existing account is selected. | Implemented — browser retest pending |
| MT-031-U02 | Usability defect | Medium | Existing-user linking still displays email, names, and two password fields that must be left blank. The user must interpret conditional help text across a long form instead of seeing only relevant inputs. | Use progressive disclosure: first select **Existing** or **New**. Existing needs only verified account selection and confirmation; new needs name, email, and invitation setup. | Implemented — browser retest pending |
| MT-031-C01 | Improvement | Medium | The primary button always says **Add administrator**, so it does not confirm whether the outcome is linking an existing account or creating a new one. | After account resolution, use **Grant administrator access** for an existing user and **Send administrator invitation** for a new user. Include the organization name in the final confirmation. | Partially implemented — explicit grant/create actions; invitations pending |

### MT-032 — Create managed organization form

- **Date:** 2026-08-30
- **Route:** `/platform/organizations/new/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Consistent but insufficiently structured onboarding form
- **Functional status:** Provisioning form displayed; no organization submitted

#### Completed functional checks

- **Pass:** Organization name and first-administrator details are collected in one provisioning form.
- **Pass:** The underlying managed flow is designed to create the organization and its first active administrator atomically, preventing a normal partially provisioned tenant.
- **Pass:** Existing-user linking and new-account creation are both supported for the first administrator.
- **Pass:** The page states that creating the tenant does not automatically grant the platform owner workspace-content access.
- **Pass:** Organization name is the only required tenant-specific setup concept; agency client companies, recruiter accounts, and advanced retention settings are not forced into initial provisioning.
- **Pass:** The main action and **Cancel** control are clear and consistently styled.
- **Pass:** No organization, user, or membership was created during this visual pass.

#### Pending functional checks

- Create a disposable organization with a new invited/temporary administrator and confirm organization, account, membership, default retention policy, and tenant-management events are all created or all rolled back.
- Provision another organization using an existing user and confirm the user's password/profile remain unchanged while the new administrator membership is added.
- Test duplicate organization names and verify the generated slug is unique, stable, and communicated clearly.
- Test invalid organization names, duplicate/already-linked administrator cases, inactive users, email/password validation, and safe error recovery.
- Confirm the platform owner still receives `404` for the new tenant's recruitment content until separately granted an active membership.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-032-U01 | Usability defect | High | The provisioning form inherits the ambiguous combined existing-user/new-user workflow, browser-autofilled username/password behavior, and manual temporary-password weaknesses recorded in MT-031. This is more consequential here because the selected account becomes the tenant's first administrator. | Reuse the explicit **Add existing user** / **Invite new administrator** component from MT-031. Require identity confirmation for existing users and an expiring password-setup invitation for new users. | Open |
| MT-032-V01 | Visual/usability defect | Medium | Organization name and six administrator/account fields appear as one uninterrupted long form. The platform owner must infer where tenant details end and administrator setup begins. | Keep a single-submit page, but divide it into two clearly labelled sections: **Organization details** and **First administrator**. Use a compact step indicator only if later setup stages are added; do not introduce an unnecessary second confirmation click. | Open |
| MT-032-C01 | Usability defect | Medium | The organization slug/workspace URL is generated only after submission. Duplicate names silently receive numeric slug suffixes, so the platform owner cannot see the permanent identifier they are about to create. | Show a live generated slug/URL preview under the organization name and allow a validated edit before creation. Treat it as stable after provisioning and explain that duplicate names are allowed but URLs must be unique. | Open |
| MT-032-U02 | Improvement | Medium | After creation, the current success path reports that the administrator was created or linked, but there is no invitation-delivery/status concept or concise onboarding checklist. | On success, show **Organization created**, **Administrator invited/linked**, and the next safe actions: administrator sets password/signs in, then adds recruiters and optional client companies. Do not require the platform owner to enter tenant content. | Proposed |

### MT-033 — Organization settings hub

- **Date:** 2026-08-30
- **Route:** `/organizations/second-agency-test/settings/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Strong, clear foundation with minor layout and wording improvements
- **Functional status:** Administrator settings routes presented correctly; destination actions pending

#### Completed functional checks

- **Pass:** The page identifies **Second Agency Test** and presents organization-administrator controls separately from ordinary recruiter workflow pages.
- **Pass:** **Team members** explains that organization administrators manage recruiter access while platform owners manage administrator memberships separately.
- **Pass:** **Client companies** clearly states that these optional hiring customers are not workspaces, candidate owners, or user accounts.
- **Pass:** **Retention and deletion** links data lifecycle, legal holds/exceptions, cleanup, and staged organization deletion without duplicating the controls on this hub.
- **Pass:** **Manage team**, **Manage client companies**, and **Open retention settings** are distinct, understandable actions.
- **Pass:** **Back to dashboard** provides a direct exit to the organization workspace.
- **Pass:** No setting or organization data was changed during this visual pass.

#### Pending functional checks

- Confirm a recruiter receives `403` and another organization's member receives `404`.
- Open **Manage team** and verify recruiter creation/linking, access removal/restoration, role boundaries, and account invitation handling.
- Open **Manage client companies** and verify create, edit, deactivate/reactivate, historical vacancy preservation, and direct-employer mode.
- Confirm retention settings remain administrator-only and preserve the already-tested safety boundaries.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-033-C01 | Product wording defect | Medium | The client-company card is labelled **Agency workspace**, even though the product explicitly supports direct employers that may never use client companies. This implies an organization type that the data model does not require. | Use an organization-neutral eyebrow such as **Optional hiring clients** or **Vacancy organization**. Keep the current explanatory text that client companies are not tenants or accounts. | Open |
| MT-033-V01 | Visual defect | Low | The two-column grid leaves **Retention and deletion** alone on the second row with a large empty area to its right at desktop width. | Use three equal cards in one row at wide desktop sizes, or use a compact full-width administration row for lower-frequency privacy/lifecycle settings. | Proposed |
| MT-033-U01 | Improvement | Medium | The hub has no organization-profile settings for display name, display timezone, or locale. The missing timezone has already caused ambiguous timestamps throughout candidate, job, audit, and lifecycle pages. | Add an **Organization profile** area for administrator-editable display name, timezone, and locale while keeping the stable slug/platform identity protected. Use the configured timezone consistently across the UI. | Proposed |

### MT-034 — Organization team members

- **Date:** 2026-08-30
- **Route:** `/organizations/second-agency-test/settings/team/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Clean, compact, and professional; no new visual defect beyond the global navigation crowding in MT-003-V01
- **Functional status:** Role boundaries and visible access states pass; recruiter access mutations remain pending

#### Completed functional checks

- **Pass:** The page is scoped to **Second Agency Test** and clearly explains that removing access here does not disable a shared account in another workspace.
- **Pass:** Organization administrators can manage recruiter access, while administrator rows are visible for context but explicitly marked **Managed by platform owner**.
- **Pass:** The visible administrator states reconcile with the platform-management view: `platform-owner-test` and `second-admin2` are active, while `second-admin` is inactive.
- **Pass:** The inactive `shared-recruiter` membership exposes a **Restore access** action without implying that the global user account was disabled.
- **Pass:** **Add recruiter** is the clear primary action, and **Organization settings** provides a direct route back to the settings hub.
- **Pass:** The table is compact, aligned, readable, and appropriately dense at the tested team size.
- **Pass:** No membership state was changed during this visual pass.

#### Pending functional checks

- Open **Add recruiter** and test existing-user linking, new-user creation/invitation, validation, duplicate membership handling, and browser autofill.
- Remove and restore a disposable recruiter membership; verify only this organization's membership changes, the shared account and memberships in other organizations remain unchanged, and audit attribution is recorded.
- Confirm the recruiter loses access immediately after removal and receives the correct `403`/`404` behavior for unauthorized and cross-tenant routes.
- Verify organization administrators cannot modify administrator memberships through direct requests.
- Test search, filtering, ordering, and pagination with a production-sized team.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-034-S01 | Safety/usability defect | High | **Remove access** and **Restore access** are immediate POST actions. One accidental click can remove or grant access to candidate and CV data without an identity/context confirmation. | Add a compact confirmation naming the recruiter and organization. For removal, explain the immediate workspace impact and that it is reversible; for restoration, state that candidate-data access will be granted again. Keep the server-side organization/role checks authoritative. | Open |
| MT-034-C01 | Usability defect | Medium | The column and pills use **Status**, **Active**, and **Inactive**, but they represent only this organization membership—not the person's global account. | Rename the column **Organization access** and use **Active** / **Access removed**. Keep global account status separate if it is later managed by the platform. | Open |
| MT-034-U01 | Workflow defect | Medium | Team membership has no invitation/onboarding state. A newly created user and a person who has actually set up their account can appear equivalent, while the current temporary-password workflow does not prove onboarding completion. | With email invitations, use explicit states such as **Invited**, **Active**, **Access removed**, and **Invitation expired**, with resend/cancel actions where appropriate. | Proposed |
| MT-034-U02 | Scalability improvement | Low | The team table has no search, role/access filters, or pagination. This is acceptable for four records but will become slow to scan for larger organizations. | Add search by name/email, filters for role and organization access, predictable ordering, and bounded pagination when team size justifies it. | Proposed |
| MT-034-U03 | Identity improvement | Low | Rows show username and optional full name but no stable account identifier such as email, making similarly named users harder to distinguish before an access change. | Show a verified email or other stable account identifier in the access confirmation and, if space permits, as secondary row text. | Proposed |

### MT-035 — Add recruiter form

- **Date:** 2026-08-30
- **Route:** `/organizations/second-agency-test/settings/team/recruiters/new/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Consistent field styling, but the combined account/linking workflow is unnecessarily long and ambiguous
- **Functional status:** Existing-user membership created, but only after an unnecessary failed first submission and a second **Add recruiter** click

#### Completed functional checks

- **Pass:** The form supports both linking an existing account and creating a new recruiter account.
- **Pass:** New-account fields include email, first name, last name, temporary password, and password confirmation.
- **Pass:** Password values are masked and a confirmation field is provided.
- **Pass:** **Add recruiter** and **Cancel** are clear and consistently styled.
- **Pass with friction:** The existing user was ultimately added as a recruiter without creating another account.
- **Fail:** On the first submission, browser autofill had populated username `koci` and the temporary-password field. The form rejected the otherwise valid existing-user action with **Leave password fields blank when adding an existing account**, alongside the generic temporary-password help text.
- **Fail:** The administrator then had to click **Add recruiter** a second time to complete the same action. No meaningful user decision or data correction was required between submissions.

#### Pending functional checks

- Confirm the newly linked existing account's email, name, password, global active state, and memberships in other organizations remained unchanged.
- Create/invite a new recruiter and verify required fields, duplicate email/username behavior, password validation, atomic account/membership creation, and audit attribution.
- Verify an inactive membership for an existing account is restored explicitly rather than producing a duplicate-membership error or silently creating another account.
- Confirm recruiters and cross-tenant administrators cannot open or submit this organization-administrator form.
- Retest browser autofill after the shared administrator/recruiter account-selection component is redesigned.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-035-S01 | Access-control usability defect | High | A single username silently selects between linking an existing account and creating a new account. A mistaken match can grant the wrong person access to candidate data, while an unmatched typo unexpectedly starts account creation. | Make the choice explicit: primary **Invite new recruiter** by email, with a secondary **Add existing account** option. For an existing account, search and show verified identity details before **Grant recruiter access**. | Open |
| MT-035-S02 | Security defect | High | A new recruiter receives a manually shared temporary password, but the workflow does not force a password change before workspace access. The credential may remain valid indefinitely. | Replace shared passwords with an expiring one-time password-setup invitation. Until email delivery exists, enforce a server-side **must change password** state and support a one-time setup link handled outside ordinary candidate pages. | Open |
| MT-035-U01 | Usability defect | High | Confirmed: browser autofill populated username and temporary password during existing-user linking. The first submission failed with **Leave password fields blank when adding an existing account**; the administrator then had to click **Add recruiter** again to complete the unchanged action. This is avoidable validation and duplicate-click friction caused by irrelevant fields. | Split the two workflows and apply correct autocomplete semantics. Existing-account lookup must not render password inputs at all; after a verified account is selected, one **Grant recruiter access** action should succeed on the first submission. The invitation flow should not ask an administrator to invent a password. | Open |
| MT-035-U02 | Workflow defect | Medium | Existing-user linking displays six fields even though only an account selection is needed. A new-user flow also asks for username and two password fields that email invitation/password setup can eliminate. | Use progressive disclosure in one page: **Invite new recruiter** requires email and optional name; **Add existing account** requires account search and identity confirmation. Generate internal usernames where necessary and keep the final action to one confirmation. | Open |
| MT-035-V01 | Visual/usability defect | Medium | The long single-column form extends beyond one desktop viewport, placing the primary action at the bottom after several fields that may be irrelevant. | After separating the workflows, show only relevant inputs in a compact card. Keep the organization name and access level visible near the action so the administrator can confirm who receives access and where. | Open |
| MT-035-C01 | Product consistency | Medium | Recruiter creation and administrator creation use the same risky combined account workflow but are documented as separate screens. Fixing only one would leave inconsistent onboarding and duplicate logic. | Build one reusable **account access invitation** component with role-specific copy and permissions, then use it for first administrator, additional administrator, and recruiter onboarding. | Proposed |

### MT-036 — Client companies list and empty state

- **Date:** 2026-08-30
- **Route:** `/organizations/second-agency-test/settings/client-companies/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Clean and understandable empty state; terminology and on-demand creation can be simplified
- **Functional status:** Optional/direct-employer behavior is communicated correctly; client creation and lifecycle actions pending

#### Completed functional checks

- **Pass:** The page clearly describes client companies as optional hiring-customer references for agency vacancies.
- **Pass:** The empty state explicitly confirms that no client companies is a valid direct-employer setup.
- **Pass:** The page does not require a client company merely because an organization exists.
- **Pass:** Deactivation behavior is explained before any records exist: a deactivated client disappears from new vacancy choices while historical vacancy links remain unchanged.
- **Pass:** **Add client company** is the clear primary action and **Organization settings** provides a direct return route.
- **Pass:** No client-company record was created during this visual pass.

#### Pending functional checks

- Create a client with and without a website; verify URL normalization, duplicate-name behavior, organization ownership, audit attribution, and validation.
- Create a client from the vacancy-form shortcut and confirm the app returns to the unchanged vacancy draft with the new company already selected.
- Edit, deactivate, and reactivate a disposable client; verify new-vacancy choices, existing vacancy links, vacancy counts, and cross-tenant isolation.
- Confirm recruiters can select active clients but cannot create, edit, deactivate, or reactivate them through direct requests.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-036-U01 | Workflow improvement | Medium | An administrator can add a client while creating a vacancy, but the current shortcut leaves the vacancy form for a separate organization-settings form before returning. Client setup is therefore optional but still feels like a prerequisite/detour when the first agency vacancy is created. | Provide a small inline **Add hiring client** expander or modal inside the vacancy form for administrators. Require only the company name, keep website optional, create it once, select it automatically, and preserve the unfinished vacancy fields. | Proposed |
| MT-036-C01 | Product wording defect | Medium | **Client companies** and especially **Organization-owned clients** are technically accurate but sound like tenant/data-model terminology. Recruiters primarily need to know which customer is hiring for a vacancy. | Prefer **Hiring clients** in the recruiter-facing UI, with **Client company** retained only where legal/business terminology requires it. Rename the section **Your hiring clients** or simply **Hiring clients**. | Open |
| MT-036-S01 | Safety/usability defect | Medium | Confirmed: **Deactivate** is an immediate POST action with no confirmation. `Acme Test Industries` was deactivated with one linked vacancy, without first showing the affected count or explaining what would and would not change. Reactivation is available and historical links are intended to remain, but the impact is not reviewed before the state change. | Add a compact confirmation naming the client and showing **1 linked vacancy**. Explain that the client will disappear from new-vacancy choices, existing vacancies remain unchanged, and restoration is available. Reactivation may remain a lightweight action if its effect is equally clear. | Open |
| MT-036-V01 | Visual improvement | Low | The empty-state card is substantially narrower than the surrounding content and leaves a large amount of unused horizontal/vertical space. It remains readable but feels less integrated than the candidate and vacancy empty states. | Align the empty state with the standard content-panel width or place it directly below the explanatory section. Keep the concise message and one optional **Add hiring client** action inside the state. | Proposed |

### MT-037 — Managed organization onboarding journey

- **Date:** 2026-08-30
- **Scope:** Platform provisioning → first administrator → team/client setup → first recruitment work
- **Status:** Architecture retained; onboarding sequence should stop presenting optional records as mandatory setup

#### Product assessment

| Item | Required? | Correct time to create | Recommended owner |
| --- | --- | --- | --- |
| Organization | Yes | Platform provisioning | Platform owner |
| First administrator access | Yes | In the same atomic provisioning action; invitation may remain **Pending setup** until accepted | Platform owner initiates; administrator accepts |
| Separate recruiter account | No | Only when another teammate needs workspace access | Organization administrator |
| Client company | No | When an agency first needs to associate a vacancy with a hiring customer | Organization administrator, preferably inline from the vacancy form |
| Retention policy | Yes, but not as manual onboarding | Safe platform defaults at provisioning; administrator may review later | System default, then organization administrator |

#### Recommended first-use journey

1. Platform owner creates the organization and sends the first administrator an expiring setup invitation in one action.
2. The organization remains **Pending setup** until the administrator accepts; it must not appear as a healthy active tenant with no usable administrator.
3. The administrator signs in and can immediately import candidates or create the first vacancy. An administrator is also an organization member and does not need a duplicate recruiter account to perform recruitment work.
4. A lightweight optional checklist offers **Invite teammates**, **Add hiring clients**, and **Review retention settings** without blocking the main workflow.
5. A direct employer skips hiring clients permanently. An agency adds the first client on demand from the vacancy form; it does not need to pre-register every customer in settings.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-037-U01 | Onboarding defect | High | The current product-spec journey starts with “An administrator creates recruiter accounts and organization settings,” which implies that a separate recruiter is required before useful work can begin. In the implemented permission model, the administrator already has organization access and can perform recruitment work. | Rewrite onboarding around the first value action: after accepting access, the administrator can **Add candidates** or **Create a vacancy** immediately. Present teammate invitations and organization settings as optional setup, not prerequisites. | Open |
| MT-037-U02 | Onboarding defect | High | The platform flow creates or links a first administrator, but the temporary-password model does not represent invitation acceptance. An organization can appear active even when its intended administrator has not securely completed setup. | Use an expiring invitation and a **Pending setup** organization/admin state. Promote the tenant to normal active operation when the first administrator completes password setup; allow the platform owner to resend or replace the invitation. | Proposed |
| MT-037-U03 | Workflow improvement | Medium | Client-company management exists as a separate settings destination, which can make agencies believe all customers must be configured before vacancies are created. | Keep the settings list for later maintenance, but make on-demand inline creation from a vacancy the primary first-client path. Never show client-company setup as required for direct employers. | Proposed |
| MT-037-U04 | Product simplification | Medium | A traditional multi-step setup wizard would add clicks for small organizations and force choices they may not yet know. | Use a dismissible dashboard checklist rather than a mandatory wizard. Required provisioning happens once; optional tasks disappear when completed and never block candidate or vacancy creation. | Proposed |
| MT-037-C01 | Role clarity | Medium | **Administrator** can be misread as a settings-only account, encouraging the customer to create another account for their own recruiting work. | Explain during onboarding: **Administrators can also perform recruiter work and manage organization settings. Recruiter accounts are for teammates who should not manage settings.** | Open |

### MT-038 — Add client company form

- **Date:** 2026-08-30
- **Route:** `/organizations/second-agency-test/settings/client-companies/new/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Pass; focused, balanced, and professionally styled
- **Functional status:** Form presentation passes; submission and vacancy return behavior pending

#### Completed functional checks

- **Pass:** The page explains that the record identifies a hiring customer and does not create another workspace or user account.
- **Pass:** Only **Client company name** is required; **Website** is visibly optional.
- **Pass:** The two-field form is short, readable, and fits comfortably within one desktop viewport.
- **Pass:** **Add client company** and **Cancel** are clear and consistently styled.
- **Pass:** No unnecessary tenant, user, candidate, recruiter, or configuration fields are requested.
- **Pass:** `Acme Test Industries` was created successfully on the first submission with the optional website left blank.
- **Pass:** The success message identifies the created company, and the list immediately shows **Not recorded** for website, **Active** status, zero linked vacancies, and **Edit** / **Deactivate** actions.
- **Fail:** On edit, entering `acme.example.com` without a scheme triggered the browser warning **Please enter a URL** and prevented submission. The request never reached the form's server-side `https://` normalization.
- **Pass:** Re-entering the website as the complete URL `https://acme.example.com` saved successfully. The success message identifies the updated company and the list renders the value as a clickable link.

#### Pending functional checks

- Verify the generated stable slug, organization ownership, and audit attribution for `Acme Test Industries` through the relevant audit/detail checks.
- After resolving the browser/server validation mismatch, retest a website without a scheme and confirm safe `https://` normalization; also test malformed and unsafe URLs.
- Test blank/whitespace names, duplicate names within one organization, and the same name in another organization.
- Repeat creation from a partly completed vacancy and confirm every vacancy field is preserved, the user returns to the form, and the new client is selected automatically.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-038-C01 | Product wording defect | Medium | The website help text says **Used only as organization-owned reference metadata**, which describes the internal data model rather than its value to an administrator. | Use plain language such as **Optional. Helps your team identify the hiring client.** If the website is displayed elsewhere, say where; otherwise avoid promising functionality it does not provide. | Open |
| MT-038-U01 | Workflow improvement | Medium | This standalone two-field form is appropriate for settings maintenance, but showing both fields in a separate page is still unnecessary when an administrator only needs a new client while creating a vacancy. | Reuse the same validation in an inline vacancy quick-add. Show **Hiring client name** first, place website under optional **More details**, create/select the client in one action, and keep the full standalone page for later editing. | Proposed |
| MT-038-C02 | Terminology consistency | Low | The heading and primary action repeat **client company**, while the surrounding product language increasingly describes the concept as the customer hiring for a vacancy. | Rename recruiter-facing copy to **Add hiring client**, **Hiring client name**, and **Add hiring client**, while retaining `ClientCompany` as an internal model name. | Proposed |
| MT-038-V01 | Visual consistency defect | Low | The newly created row shows an **Active** pill in the neutral gray style, unlike green active-state pills used on organization, membership, and other status pages. The template does not apply the active-state class conditionally. | Apply the shared green active status style when the client is active and retain neutral gray for deactivated records. Keep color supplementary to the visible text. | Open |
| MT-038-U02 | Validation defect | Medium | The Django `URLField` is configured to assume `https://`, but its browser `type="url"` input rejects a scheme-less domain such as `acme.example.com` before server validation runs. The advertised normalization therefore cannot help the user. | Accept a plain domain in a text input with `inputmode="url"`, normalize and validate it server-side, and show an example such as `company.com`. Alternatively, visibly require `https://`, but accepting and normalizing the common domain-only input is the lower-friction option. | Open |
| MT-038-V02 | Visual resilience improvement | Low | The table displays the entire stored website URL. The tested value fits, but long paths or tracking parameters can consume the row and push actions out of alignment. | Display the hostname or a safely truncated label with the full URL available through the link title/accessibility text. Keep the actual validated URL as the link target. | Proposed |

### MT-039 — Assign hiring client to an existing vacancy

- **Date:** 2026-08-30
- **Route:** `/organizations/second-agency-test/vacancies/14/`
- **Viewport:** Desktop, 1920 × 1020
- **Visual status:** Client assignment is visible; header action hierarchy remains overcrowded
- **Functional status:** Client assignment and matching-input preservation pass

#### Completed functional checks

- **Pass:** Editing vacancy details and selecting `Acme Test Industries` produced the success message **Vacancy details updated**.
- **Pass:** The vacancy header immediately displays `Acme Test Industries` beside the open status.
- **Pass:** The vacancy remained **Open** after the client assignment.
- **Pass:** The original vacancy description remained unchanged.
- **Pass:** The current confirmed requirements and the entire lower part of the vacancy page remained unchanged.
- **Pass:** Assigning a hiring client did not create a new requirements version or alter matching inputs; this is the correct boundary because the client is organizational metadata, not candidate-selection evidence.
- **Pass:** Returning to client-company settings showed the vacancy count had changed from zero to one.
- **Pass with safety issue:** Deactivation succeeded and changed the company to **Inactive**, preserved the linked-vacancy count of one, exposed **Reactivate**, and produced a clear success message; however, it occurred immediately without confirmation.
- **Pass:** Opening vacancy 14 after deactivation preserved `Acme Test Industries` as the historical hiring client.
- **Pass:** The edit form keeps the inactive client selected and labels it **inactive — current vacancy only**. The help text clearly states that it may be retained for this historical vacancy but that ordinary choices must be active.
- **Pass:** The edit form continues to state that changing the display title/client does not alter the original job-description source or confirmed requirements.
- **Pass:** On a new-vacancy form, the hiring-client dropdown was empty while `Acme Test Industries` was inactive. The client is therefore correctly excluded from every new assignment.
- **Pass:** Reactivating `Acme Test Industries` restored it to the new-vacancy dropdown without requiring recreation or changing the historical vacancy relationship.

#### Pending functional checks

- Verify audit attribution for the create, edit, deactivate, and reactivate events and confirm a recruiter cannot perform those administrator-only actions through direct requests.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-039-C01 | Information-design defect | Medium | The header metadata is rendered as `Acme Test Industries · Open` without labels or a status pill. A user must infer that the first value is the hiring client and the second is the vacancy lifecycle state. | Show **Hiring client: Acme Test Industries** as labelled metadata and render **Open** with the shared status pill. Preserve a clean one-line summary under the title. | Open |
| MT-039-V01 | Visual/workflow defect | Medium | Six page actions compete beside the title: **All vacancies**, **Edit vacancy**, **Evaluate candidates**, **Latest shortlist**, **Create correction draft**, and **Delete vacancy**. Two actions use primary styling and several labels wrap, obscuring the most likely next step. | Choose one state-aware primary action, normally **Open latest shortlist** when one exists or **Generate shortlist** when none exists. Keep **Edit** and **All vacancies** secondary; group correction/version actions near requirements and place deletion in a danger/overflow area. | Open |

### MT-040 — Change password form

- **Date:** 2026-08-30
- **Route:** `/accounts/password/change/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Clean and trustworthy; minor usability/navigation improvements recommended
- **Functional status:** Incorrect-old-password validation passes; successful mutation remains untested on this account

#### Completed functional checks

- **Pass:** The page clearly separates old password, new password, and new-password confirmation.
- **Pass:** Password fields are masked and the standard password requirements are visible before submission.
- **Pass:** The page explains that changing a password does not alter organization memberships.
- **Pass:** The form uses the authenticated account route and CSRF-protected POST boundary.
- **Pass:** The primary action is prominent and the form remains readable at the tested desktop width.
- **Pass:** No password was changed during this visual pass.
- **Pass:** Submitting an intentionally incorrect old password produced **Your old password was entered incorrectly. Please enter it again.**
- **Pass:** The rejected submission cleared the old password, new password, and confirmation fields. No password value was redisplayed and the account password remained unchanged.

#### Pending functional checks

- Test mismatched confirmation, too-short/common/numeric passwords, similarity validation, and server-side rejection with accessible error focus/summary.
- On a disposable account, complete a successful change and confirm the current session remains authenticated, other sessions are invalidated as intended, and organization memberships remain unchanged.
- Confirm rate limiting or equivalent abuse protection is applied to repeated old-password failures.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-040-S01 | Security workflow defect | High | The page can replace a temporary password, but nothing forces a newly provisioned account to use it before accessing the workspace. The manual onboarding instructions merely ask the user to change it later. | Preserve this form for ordinary voluntary changes, but enforce **must change password** before any workspace access until expiring invitation/password-setup links replace shared temporary passwords. This is the same root issue as MT-031-S02 and MT-035-S02. | Open |
| MT-040-U01 | Usability improvement | Low | There is no accessible show/hide control for any password field, making long generated passwords harder to verify and increasing mistyping risk. | Add an explicit keyboard-accessible **Show password** toggle per logical password group, preserving password-manager compatibility and the masked default. | Proposed |
| MT-040-U02 | Navigation defect | Medium | The form has no **Cancel** or **Back** action. A user who opens it accidentally must use global navigation or browser history, and the correct return destination varies between platform and organization contexts. | Add **Cancel** beside the primary action and return safely to the originating internal page when available, otherwise the organization/platform dashboard. Never trust an external return URL. | Open |
| MT-040-C01 | Security communication improvement | Low | The success copy states that the current session remains available but does not explain the status of other signed-in sessions. Users changing a compromised password need a clear expectation. | On success, state whether other sessions were ended and provide an explicit **Sign out other sessions** control if framework behavior or future authentication providers do not guarantee it. | Proposed |

### MT-041 — Sign out and protected-page browser history

- **Date:** 2026-08-30
- **Routes:** Authenticated page → `/accounts/logout/` → `/accounts/login/`
- **Browser:** Chrome desktop
- **Functional status:** Server-side correction implemented; browser-history and multi-browser retest pending

#### Completed functional checks

- **Pass:** Clicking **Sign out** ended the authenticated server session and redirected to the login page.
- **Pass:** Refreshing a protected page after sign-out redirected back to login; the server did not serve authenticated content with the terminated session.
- **Fail:** Pressing browser **Back** immediately displayed the previously rendered protected page from browser history/cache without contacting the server.
- **Pass after refresh only:** Refreshing that cached page enforced authentication and returned to login.
- **Automated correction check:** Authenticated HTML now returns `Cache-Control: no-store, private, max-age=0`, `Pragma: no-cache`, and `Expires: 0`; logout responses receive the same policy, while anonymous and non-HTML/static-style responses retain their existing cache policy.
- **Automated verification:** The focused response-security set passed `66` tests and the complete quality gate passed `545` tests with no migration drift.

#### Pending functional checks

- After adding authenticated-page cache controls, repeat logout/back/forward navigation in Chrome, Edge, Firefox, and mobile Safari/Chrome.
- Verify candidate details, CV/profile pages, shortlist/assessment pages, audit reports, and platform administration are never rendered from browser history after logout.
- Test logout with protected pages open in multiple tabs and confirm refresh/navigation in every tab requires authentication.
- Confirm sign-out remains a CSRF-protected POST and cannot be triggered by a cross-site GET.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-041-S01 | Privacy/security defect | High | After sign-out, browser **Back** displayed the last protected page from history until refresh. The server-side correction now marks every authenticated HTML response private/no-store with legacy-compatible directives while leaving anonymous HTML and non-HTML/static caching unchanged. | Retest browser back-forward cache behavior in the supported browser set. If a supported browser still restores a persisted page, add a minimal `pageshow` safeguard that reloads only when restored from browser history. | Implemented; browser retest pending |
| MT-041-C01 | Security communication improvement | Low | Logout redirects directly to the ordinary login page with no explicit confirmation that the account was signed out. | Show a concise **You have been signed out** success message on the login page. This does not replace the cache-control fix but reassures the user that the server session ended. | Proposed |

### MT-042 — Multi-organization chooser and platform-owner tenant access

- **Date:** 2026-08-30
- **Routes:** `/` → `/organizations/test-intake/`
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Workspace chooser is clean; access context needs clearer role information
- **Functional status:** Multi-workspace selection passes; tenant-isolation denial checks remain pending

#### Completed functional checks

- **Pass:** The platform owner did not automatically receive access to every tenant workspace. A separate organization membership had to be created before the second organization appeared in the chooser.
- **Pass:** After the platform owner was explicitly added to `test intake`, signing in displayed both `Second Agency Test` and `test intake` as separate workspace choices.
- **Pass:** Selecting `test intake` opened `/organizations/test-intake/` rather than retaining the previous tenant route.
- **Pass:** The selected workspace displayed its own organization name, administrator role, candidate/client/vacancy summaries, and organization-scoped navigation.
- **Pass:** **Switch workspace** became available inside the selected organization, while the platform-management link remained available to the platform owner.
- **Pass:** The visible `test intake` summary differs from `Second Agency Test`, providing an initial UI-level indication that organization data is scoped separately.
- **Pass:** Using **Switch workspace** to return to `Second Agency Test` restored only that organization's candidate pool; the three candidates belonging to `test intake` were not displayed.
- **Pass:** While signed in as `second-admin2`, who belongs only to `Second Agency Test`, directly requesting `/organizations/test-intake/` returned HTTP 404 with **No Organization matches the given query** and disclosed no tenant content. Returning 404 rather than 403 correctly avoids confirming that the inaccessible organization exists.
- **Pass:** While still signed in as `second-admin2`, directly requesting the known cross-tenant resource `/organizations/test-intake/candidates/62/` also returned the tenant-hiding 404 before candidate lookup. No candidate identity, attributes, CV/profile content, or existence signal was exposed.

#### Pending functional checks

- Repeat switching while inspecting vacancies, clients, jobs, reviews, AI usage, and audit data to extend the confirmed candidate-pool isolation check across every tenant-owned resource.
- Repeat the direct-route test as a recruiter and sample vacancy, shortlist, job, audit, and settings URLs copied from the other tenant.
- Remove the platform owner's `test intake` membership and verify that the workspace immediately disappears from the chooser and its direct URLs become inaccessible, while platform-level organization management remains available.
- Verify that adding the platform owner to a tenant, changing the assigned role, and removing the membership create attributable audit events.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-042-S01 | Access-governance improvement | Medium | The platform owner can grant their own account an ordinary organization-administrator membership and then access that tenant's private recruiting workspace. Explicit membership is safer than automatic global access, but unrestricted self-granting weakens the separation promised by the platform-management surface. | Keep platform management separate from tenant membership. For exceptional support access, require a deliberate **Grant myself support access** action with a reason, prominent warning, immutable audit event, and preferably an expiry; do not automatically enroll the platform owner in new organizations. For the current managed MVP, an explicit fully audited membership is acceptable if this limitation is documented. | Proposed |
| MT-042-S02 | Deployment security requirement | High | The authorization denial is correct, but the local `DEBUG = True` response exposes the view name, URL configuration, internal route inventory, and framework diagnostics. This is expected for local development but unsafe on any public deployment. | Enforce `DEBUG = False` outside development, fail deployment/startup when production configuration enables debugging, and serve a branded generic 404 page that contains no internal route or exception details. | Verify before deployment |
| MT-042-U01 | Context clarity | Medium | Organization cards show only the organization name and generic **Open workspace** copy. A user may be an administrator in one tenant and recruiter in another but cannot see that role before entering. | Show the membership role on every card, for example **Administrator** or **Recruiter**, and keep the whole card keyboard-accessible as the single open action. | Proposed |
| MT-042-V01 | Visual consistency | Low | The chooser is visually clean, but lowercase organization names such as `test intake` appear less professional beside title-cased organizations. | Preserve the stable slug internally, but encourage or normalize a title-cased display name such as **Test Intake** during organization creation/editing. | Proposed |

### MT-043 — Recruiter dashboard and visible permissions

- **Date:** 2026-08-30
- **Route:** `/organizations/second-agency-test/`
- **Account/role:** `shared-recruiter` — Recruiter
- **Viewport:** Desktop, 1920 × 1080
- **Visual status:** Role context is clear; existing dashboard/navigation density issues remain
- **Functional status:** Recruiter workspace and server-side role boundaries pass; report-visibility policy remains proposed

#### Completed functional checks

- **Pass:** Restoring the recruiter's organization membership allowed `shared-recruiter` to sign in and open `Second Agency Test`.
- **Pass:** The workspace displays a **Recruiter** role badge and recruiter role card rather than administrator status.
- **Pass:** Candidate, vacancy, review, and job workflows remain visible to the recruiter.
- **Pass:** The **Platform** navigation item is absent, so the ordinary recruiter is not offered platform-owner controls.
- **Pass:** The dashboard shows only organization-scoped counts: one active candidate, one active client company, and one open vacancy.
- **Observed by design:** **AI usage** and **Privacy & audit** remain visible to recruiters because both reports currently authorize every active organization member. This confirms the previously recorded access/product decisions MT-025-A01 and MT-026-A01 rather than introducing a new implementation discrepancy.
- **Pass:** The lower **Organization settings** panel is absent for `shared-recruiter`; administrator controls are not available through the dashboard UI.
- **Pass:** Directly requesting `/organizations/second-agency-test/settings/` as `shared-recruiter` returned HTTP 403 Forbidden and exposed no organization settings or administrator action.
- **Pass:** Directly requesting `/platform/organizations/` as `shared-recruiter` returned HTTP 403 Forbidden and exposed no platform organization registry or platform-owner action.
- **Pass:** Directly requesting `/organizations/second-agency-test/settings/team/` returned HTTP 403 Forbidden and exposed no team membership controls.
- **Pass:** Directly requesting `/organizations/second-agency-test/settings/client-companies/` returned HTTP 403 Forbidden and exposed no client-company administration controls.
- **Pass:** Directly requesting `/organizations/second-agency-test/retention/` returned HTTP 403 Forbidden and exposed no retention-policy, legal-hold, exception, preview, or cleanup controls.
- **Pass:** Directly requesting `/organizations/second-agency-test/delete/` returned HTTP 403 Forbidden and exposed no organization suspension/deletion action.

#### Pending functional checks

- Exercise representative POST mutation endpoints with CSRF-aware automated authorization tests; manual GET denial is complete and no destructive manual request is necessary.
- Decide CR-001 navigation policy for full AI-usage and privacy/audit reports: administrator-only is recommended, while candidate-specific compliance context should remain available inside recruiter workflows.

#### Findings

| ID | Type | Priority | Finding | Recommendation | Status |
| --- | --- | --- | --- | --- | --- |
| MT-043-A01 | Role/navigation decision | Medium | A recruiter correctly loses **Platform** and settings controls but still receives the organization-wide **AI usage** and **Privacy & audit** links. These pages expose aggregate cost/model/failure metadata plus organization-wide retention and actor history that are operationally useful mainly to administrators. | Implement the already proposed MT-025-A01 and MT-026-A01 decision: move full AI usage and privacy/audit into administrator settings, while keeping only task-relevant processing state and candidate-specific privacy information in recruiter workflows. | Implemented — 2026-09-01 |
| MT-043-V01 | Visual duplication | Low | The **Recruiter** badge beside the title and the separate **Your role: Recruiter** metric card communicate the same state, leaving most of the second metric row empty. | Apply MT-002-V01 consistently for both roles: retain the compact badge and remove the redundant role card. | Open |
