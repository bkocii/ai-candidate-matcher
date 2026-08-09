# AI Candidate Matcher

AI-assisted candidate rediscovery and shortlisting for small recruitment agencies and employers.

The application searches a lawful, organization-controlled candidate pool. Recruiters create a vacancy, the system applies deterministic filters, AI produces evidence-based match assessments, and a human approves every shortlist and outreach draft.

This repository is intentionally separate from Python AI Toolkit. The application consumes the published package:

```text
python-ai-toolkit[django]==1.0.0
```

## Current status

Sprint 0 is complete. Sprint 1 is in progress, and `FOUND-001` through
`FOUND-002` are complete.

The repository now has a Django 5.2 LTS foundation, custom user model,
organizations, organization memberships, administrator/recruiter roles,
reproducible dependency locking, tests, and Ruff checks. It uses the verified
published `python-ai-toolkit==1.0.0` distribution.

The next approved task is `FOUND-003 — Add optional client companies and
organization-scoped permissions`.

## Local setup

Python 3.11 through 3.14 and [uv](https://docs.astral.sh/uv/) are supported.

```powershell
uv sync --extra dev
Copy-Item .env.example .env
uv run python manage.py migrate
uv run python manage.py check
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

An OpenAI API key is not needed for Django startup or the ordinary test suite.
Add it to `.env` only when a later opt-in AI request is intentionally run:

```env
OPENAI_API_KEY=
```

## Source of truth

- `docs/product_spec.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/project_state.md`
- `docs/toolkit_integration.md`
- `docs/toolkit_feedback.md`
- `docs/future_backlog.md`
- `docs/session_handoff.md`
