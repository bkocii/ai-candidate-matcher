# Toolkit Feedback Log

This log separates application development problems from genuine Python AI Toolkit improvements.

## Classification

Each observation receives one classification:

- `APP`: specific to AI Candidate Matcher and fixed only here.
- `DOCS`: the toolkit works, but its public guidance is unclear or incomplete.
- `BUG`: documented toolkit behavior fails in a minimal reproduction.
- `API`: multiple applications would benefit from a new or changed public abstraction.
- `PERFORMANCE`: toolkit overhead is measured and materially affects the workflow.
- `DEFER`: useful idea without enough evidence yet.

## Required evidence

Before changing the toolkit, record:

- Date and app roadmap item.
- Published toolkit version.
- Expected behavior.
- Actual behavior.
- Minimal reproduction independent of Django business models where possible.
- App-level workaround.
- Why the need is reusable across projects.
- Backward-compatibility impact.
- Proposed toolkit test.

## Decision rule

Keep a change in the app when it concerns candidate data, recruitment prompts, privacy policy, database persistence, UI, or workflow.

Consider a toolkit change when the problem concerns provider-independent request execution, structured-output validation, framework integration, metadata, retry behavior, generic loaders, or another abstraction likely to serve unrelated Python applications.

Do not patch a local copy of the toolkit inside the app. Confirmed toolkit work happens in its own repository and release cycle.

## Hypotheses to validate, not accepted defects

| ID | Hypothesis | Validation point | Status |
| --- | --- | --- | --- |
| `HYP-001` | Django integration may need clearer guidance for service-layer use and test substitution. | `AI-001`, `AI-006` | Evaluated — app-owned gateway sufficient |
| `HYP-002` | Batch structured requests may need a reusable API or documented pattern. | `AI-003`, `AI-004` | Evaluated — app-owned orchestration sufficient |
| `HYP-003` | Available result metadata may not cover all app usage-reporting needs. | `AI-005`, `PROD-004` | Unverified |
| `HYP-004` | Generic PDF/DOCX loaders could be useful, but safe CV extraction may belong in the app or a separate package. | `DATA-004` | Evaluated — app-owned |
| `HYP-005` | Persistent vector-store integration may be useful if embedding retrieval is adopted. | `EVAL-002` | Unverified |

## Evaluated hypotheses

### `HYP-001` — 2026-08-11

The published v1.0.0 Django integration successfully constructs a configured
client for an application service. The recruitment application still needs its
own domain-neutral result envelope, bounded public errors, privacy policy, lazy
lifecycle, and fake-construction seam. Those are application responsibilities,
and constructor/factory substitution works without changing the toolkit. No
toolkit bug or API gap was reproduced in `AI-001`; fake and live contract
coverage remains scheduled for `AI-006`.

### `HYP-004` — 2026-08-10

`DATA-004` required recruitment-specific file limits, private persistence,
organization authorization, duplicate policy, safe recruiter errors, and CV-text
retention rules around ordinary PDF/DOCX parsing. Those controls belong to the
Django application. No provider-independent AI request or generic toolkit loader
failure was reproduced, so no Python AI Toolkit change is proposed.

### `HYP-002` — 2026-08-12

`AI-003` extracts one bounded CV per explicit recruiter action, so the published
structured-request contract is sufficient and batching would add no value to
this workflow. `AI-004` has a bounded shortlist of at most 20 candidates but
requires independent authorization, current-profile checks, stale-input checks,
versioned persistence, and failure isolation for each candidate. The application
therefore issues one ordinary structured request per explicit candidate action;
completed entries remain usable when another request fails, and background bulk
orchestration can be added at the application layer in `PROD-003`. No toolkit
defect or reusable batch API gap was reproduced.

## Confirmed observations

None yet. Planning hypotheses must not be described as toolkit shortcomings.
