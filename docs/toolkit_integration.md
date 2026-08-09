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

### Candidate profile extraction

Input: text extracted by the application from a lawfully stored CV.

Output: a validated application-owned Pydantic schema containing relevant employment evidence and unknowns.

### Match assessment

Input: confirmed vacancy requirements and a minimized candidate profile.

Output: a validated application-owned Pydantic schema containing score, evidence, gaps, uncertainties, and a recommendation for human review.

### Outreach draft

Input: an approved match plus organization-approved facts.

Output: editable subject and body. The application never instructs the toolkit to send the message.

## Application wrapper

The `ai_gateway` module will expose application concepts rather than toolkit objects to the rest of Django. Expected interfaces include:

- `extract_vacancy_requirements(text)`
- `extract_candidate_profile(text)`
- `assess_match(requirements, candidate_profile)`
- `draft_outreach(vacancy, candidate, assessment)`

Views, forms, model methods, and templates must not call Python AI Toolkit directly.

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

