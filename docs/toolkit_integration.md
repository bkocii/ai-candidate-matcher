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
matching facts and normalized skills. Python AI Toolkit remains unaware of
candidate models, redaction policy, tenant authorization, evidence verification,
profile versioning, and the human-confirmation boundary.

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
shortlist membership are never changed. Toolkit metadata is returned by the
service only transiently until `AI-005`.

### Outreach draft

Input: an approved match plus organization-approved facts.

Output: editable subject and body. The application never instructs the toolkit to send the message.

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
- `draft_outreach(vacancy, candidate, assessment)`

Views, forms, model methods, and templates must not call Python AI Toolkit directly.
Those later business services accept an `AIGateway` rather than constructing or
patching a provider client themselves.

## Configuration

Django maps `AI_PROVIDER`, provider-specific API key/model variables, generic
`AI_API_KEY` / `AI_MODEL` fallbacks, `AI_EMBEDDING_MODEL`, and
`AI_MAX_RETRIES` into `AI_TOOLKIT`. For the default provider, `OPENAI_API_KEY`
and `OPENAI_MODEL` take precedence over the generic fallbacks. File logging is
always disabled by the application configuration.

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
