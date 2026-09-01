# Python AI Toolkit Integration

## Dependency rule

The application initially uses:

```text
python-ai-toolkit[django]==1.0.0
```

The released distribution is the integration target. Local toolkit source directories must not be placed on `PYTHONPATH`, copied into this repository, or installed in editable mode for normal application work.

## Intended toolkit responsibilities

- Django-aware configuration and client construction.
- Plain-text generation where appropriate.
- Pydantic-validated structured responses.
- Retry and structured-response repair behavior.
- Provider-independent request execution.
- Request identifiers and available token, cost, retry, and timing metadata.
- Fake-provider or application adapter support for tests.

## Initial application use cases

### Vacancy extraction

Input: recruiter-supplied job description.

Output: a validated application-owned Pydantic schema containing requirements and ambiguities.

Implemented in `AI-002` by `vacancies.ai_extraction`. The business service sends
only the preserved vacancy source-description snapshot, receives
`VacancyRequirementsExtraction`, and applies it only to an authorized draft.
It accepts an injected `AIGateway` for tests and otherwise resolves the configured
gateway. Python AI Toolkit remains unaware of Django vacancy models, recruiter
confirmation, typed hard rules, and draft concurrency policy.

### Candidate profile extraction

Input: text extracted by the application from a lawfully stored CV.

Output: a validated application-owned Pydantic schema containing relevant employment evidence and unknowns.

Implemented in `AI-003` by `candidates.ai_extraction`. The service accepts one
successfully extracted CV document, removes identity/contact and sensitive
prefixed lines, bounds the remaining input to 60,000 characters, and requests an
extra-forbidding `CandidateProfileExtraction`. Every returned fact must carry an
exact excerpt that the application can find in the redacted source. A successful
request creates a versioned draft; recruiter confirmation separately publishes
matching facts and normalized skills. The application prompt scans the complete
CV for explicitly named skills, including narrative sections, while keeping
related facts separate and prohibiting synonym or tool-to-method inference. When
a schema-valid response fails this
domain-specific evidence check, the application may issue exactly one ordinary
structured correction request using the same redacted source and privacy-safe
field labels. The replacement must pass the unchanged validator, and each actual
request receives its own usage event. Python AI Toolkit remains unaware of
candidate models, redaction policy, tenant authorization, evidence verification,
profile versioning, correction policy, and the human-confirmation boundary.

### Match assessment

Input: confirmed vacancy requirements and a minimized candidate profile.

Output: a validated application-owned Pydantic schema containing score, evidence, gaps, uncertainties, and a recommendation for human review.

Implemented in `AI-004` by `matching.ai_assessment`. One explicit recruiter
action assesses one current shortlist entry through `assess_shortlist_entry`.
The application sends a bounded minimized context whose confirmed requirements
and candidate evidence use opaque IDs, requires exact requirement coverage, and
resolves accepted references back to application-owned source wording before
storing an immutable version. Missing support remains uncertain; the application
derives the traffic-light band and rejects hiring, rejection, approval, contact,
or outreach recommendations. The deterministic filter, score, rank, and
shortlist membership are never changed. The service persists toolkit metadata
only through the separate safe `AIUsageEvent` ledger.

### Outreach draft

Input: an approved match plus organization-approved facts.

Output: editable subject and body. The application never instructs the toolkit to send the message.

Implemented for generation in `OUT-001` by `outreach.generation`. One explicit
recruiter action accepts only the latest current `ReviewDecision` when its choice
is approve. The application sends a bounded vacancy title, organization name,
and evidence-backed positive match facts with an application-owned candidate-name
placeholder. It excludes candidate identity/contact data, raw CV text, recruiter
notes, gaps, uncertainties, scores, and protected characteristics. After
structured validation, the application substitutes the candidate name and saves
an immutable actor-attributed numbered draft with safe usage metadata. The
toolkit never sees Django outreach models and never approves or sends a message.
Generation itself does not edit, finally approve, copy, export, or send.

`OUT-002` completes the application-owned human workflow without another AI
request. Recruiter edits append immutable draft versions; final approval binds
the exact subject/body after current-decision, evidence, and recorded contact-
permission checks; copy and plain-text export are manual audited actions. These
steps do not call Python AI Toolkit, create AI usage events, select a recipient,
or send outreach.

## Application wrapper

The `ai_gateway` package is the only application boundary permitted to import
the toolkit client, result, or exception contracts. It currently exposes:

- `AIGateway.request_structured(prompt=..., response_type=...)`
- `AIGatewayResult`, containing validated application data and safe metadata
- bounded application error types for configuration, availability, and invalid
  structured responses
- `get_ai_gateway()`, a configured construction seam for later fake substitution

`ToolkitAIGateway` constructs the toolkit's Django client lazily and delegates
structured validation and repair to `AIClient.ask()`. It deliberately does not
return `AIResult.raw_response` or `AIResult.original_raw_response`.

Application business services expose or will expose concepts such as:

- `extract_vacancy_requirements(requirements, user)`
- `extract_candidate_profile(document, user)`
- `confirm_candidate_profile(profile, user)`
- `assess_shortlist_entry(entry, user)`
- `generate_outreach_draft(decision, user)`

Views, forms, model methods, and templates must not call Python AI Toolkit directly.
Those later business services accept an `AIGateway` rather than constructing or
patching a provider client themselves.

## Safe usage persistence

`AI-005` adds an application-owned `AIUsageEvent` around each existing business
service call. The toolkit remains unaware of organizations, users, domain target
IDs, result IDs, and application validation. Successful events persist only the
safe fields already exposed by `AIGatewayMetadata`. Gateway exceptions expose no
request metadata in v1.0.0, so failed events retain the application error code,
stage, actor/organization, workflow/target IDs, and timestamps while leaving
request/model/token/cost fields blank. A completed response later rejected by
application validation can retain its safe metadata.

The ledger never receives a prompt, raw/original response, toolkit/provider
message, exception detail, source description, CV text, or candidate identity or
contact value. Toolkit file logging remains disabled.

`PROD-004` derives the tenant-scoped **AI usage** report directly from this
ledger. Available success metadata supports token, cost, latency, retry, model,
workflow, and daily aggregates; application timestamps and allow-listed codes
support attempt/outcome/pending/failure reporting. Missing provider fields on
gateway failures remain explicitly unavailable. Reporting makes no toolkit call,
stores no additional copy, and requires no toolkit contract change.

## Test contract

`ai_gateway.testing.FakeAIGateway` is the provider-free application test double.
It and `ToolkitAIGateway` share the same non-blank prompt and Pydantic response-
type validation. Shared tests verify the runtime protocol, normalized request,
validated `AIGatewayResult`, safe `AIGatewayMetadata`, and absence of raw response
fields. Domain suites supply their own application-owned output schemas through
the fake without importing toolkit result types.

The separately invoked `live_tests/test_ai_gateway_live.py` verifies one tiny
synthetic structured request through the published v1.0.0 Django integration.
It is outside ordinary `testpaths`, requires `RUN_LIVE_AI_SMOKE=1`, may incur a
provider charge, uses no database or recruitment data, and is never a CI gate.

## Configuration

Django maps `AI_PROVIDER`, provider-specific API key/model variables, generic
`AI_API_KEY` / `AI_MODEL` fallbacks, `AI_EMBEDDING_MODEL`, and
`AI_MAX_RETRIES` into `AI_TOOLKIT`. Explicit
`AI_INPUT_COST_PER_1M_TOKENS` and `AI_OUTPUT_COST_PER_1M_TOKENS` values are also
mapped together. For the default provider, `OPENAI_API_KEY` and `OPENAI_MODEL`
take precedence over the generic fallbacks. File logging is always disabled by
the application configuration.

The supplied environment examples configure the official OpenAI API prices
verified for `gpt-5.4-mini` on 2026-09-01: `$0.75` input and `$4.50` output per
one million tokens. The rates are runtime configuration, not permanent product
constants, and must be reviewed whenever the model or provider price changes.
The application forwards toolkit cost estimates only when both explicit rates
are configured. Missing rates therefore produce unavailable cost metadata rather
than trusting the toolkit v1.0.0 placeholder zero-price table.

No key is validated at Django startup. The first intentional gateway request
constructs and validates the toolkit client; a missing or invalid configuration
then becomes the application's safe configuration error.

## PII boundary

- Send only information necessary for the active assessment.
- Remove photographs and protected/sensitive attributes from AI inputs.
- Avoid sending candidate contact information for scoring.
- Do not persist raw prompts or raw responses in ordinary logs.
- Persist validated outputs and safe request metadata separately.

## Features not forced into the MVP

- RAG is not used merely to demonstrate it; candidate matching is not a document question-answering problem.
- Embeddings are added only if benchmarks show they improve shortlist retrieval.
- The in-memory vector store is not treated as production persistence.
- Multi-agent orchestration is not needed for this workflow.
- Streaming is optional and unnecessary for batch assessment.

## Upgrade rule

The app upgrades the toolkit only after:

1. A reusable issue is reproduced against the published version.
2. The issue is recorded in `toolkit_feedback.md`.
3. A fix is implemented and tested in the toolkit repository.
4. A new toolkit version is released.
5. The app dependency is updated deliberately and its contract tests pass.
