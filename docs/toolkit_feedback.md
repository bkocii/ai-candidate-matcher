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
| `HYP-001` | Django integration may need clearer guidance for service-layer use and test substitution. | `AI-001`, `AI-006` | Fully evaluated — app-owned gateway and fake sufficient |
| `HYP-002` | Batch structured requests may need a reusable API or documented pattern. | `AI-003`, `AI-004` | Evaluated — app-owned orchestration sufficient |
| `HYP-003` | Available result metadata may not cover all app usage-reporting needs. | `AI-005`, `PROD-004` | Fully evaluated — explicit availability is sufficient; no toolkit change |
| `HYP-004` | Generic PDF/DOCX loaders could be useful, but safe CV extraction may belong in the app or a separate package. | `DATA-004` | Evaluated — app-owned |
| `HYP-005` | Persistent vector-store integration may be useful if embedding retrieval is adopted. | `EVAL-002` | Unverified |

## Evaluated hypotheses

### `HYP-001` — 2026-08-11

The published v1.0.0 Django integration successfully constructs a configured
client for an application service. The recruitment application still needs its
own domain-neutral result envelope, bounded public errors, privacy policy, lazy
lifecycle, and fake-construction seam. Those are application responsibilities,
and constructor/factory substitution works without changing the toolkit. No
toolkit bug or API gap was reproduced in `AI-001`.

`AI-006` completed the evaluation with a reusable application `FakeAIGateway`,
shared input/result contract tests against both fake and toolkit-backed adapters,
and a separately opted-in synthetic live smoke test. Domain services substitute
the application protocol cleanly, while the published integration retains lazy
construction and safe structured result translation. No toolkit-owned fake,
contract abstraction, documentation correction, or API change is needed for the
current application.

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

`PROD-003` confirmed this boundary on 2026-08-15. Durable jobs, leases,
idempotency, saved-result recovery, and per-target failure isolation were added
entirely in the application while each task continued to use the existing
ordinary structured-request gateway contract. No toolkit batch API or toolkit
change was required.

### `HYP-003` — fully evaluated, 2026-08-15

For successful requests, toolkit v1.0.0 supplies the request ID, model, duration,
retry count, optional token counts, and optional estimated cost needed by
`AI-005`. The application persists these fields separately without storing raw
request or response content. Translated gateway exceptions do not carry request
ID, timing, retry, token, or cost metadata. `AI-005` therefore records its own
attempt/completion timestamps and bounded failure category while leaving
unavailable provider fields blank.

`PROD-004` confirmed that this is sufficient for safe operational reporting.
Successful and application-validation-complete responses contribute available
provider metrics. Gateway failures contribute application timestamps, status,
workflow, and allow-listed failure stage/code while provider-only metrics are
shown as unavailable rather than inferred. This preserves honest coverage and
supports useful failure reporting without storing exception detail or expanding
the gateway contract. No toolkit defect or API change is proposed.

## Confirmed observations

### `APP-001` — Candidate evidence correction — 2026-08-15

Schema-valid candidate-profile responses can still paraphrase evidence or attach
an exact excerpt that does not contain its claimed fact. This is a recruitment-
specific post-schema validation failure, not a reproduced toolkit structured-
response defect. The application keeps its exact grounding validator and makes
one bounded correction request through the existing public gateway, with a
separate usage event and no failed provider output in the repair prompt. No
toolkit source, dependency, API, or retry behavior changed.

The follow-up narrative-skill completeness rule is also application-owned. It
instructs the same structured request to scan the complete CV for explicitly
named job-relevant skills instead of favoring a Skills heading, while the
existing exact-evidence validator prevents synonym or umbrella-skill inference.
No generic toolkit behavior changed.
