# Codex Instructions

## Required reading

Before changing code, read:

1. `docs/project_state.md`
2. `docs/roadmap.md`
3. `docs/product_spec.md`
4. `docs/architecture.md`
5. `docs/toolkit_integration.md`
6. `docs/toolkit_feedback.md`

## Working rules

- Implement only the next approved roadmap item.
- Inspect existing code and tests before editing.
- Preserve the approved architecture unless a concrete conflict is found.
- Record new ideas in `docs/future_backlog.md`; do not silently expand the active sprint.
- Keep this application separate from the Python AI Toolkit source repository.
- Use the published dependency `python-ai-toolkit[django]==1.0.0` until an intentional upgrade is approved.
- Never copy, vendor, or import toolkit code from another local directory.
- Do not invent toolkit APIs. Check the v1.0.0 documentation or inspect the installed package when necessary.
- Keep AI-provider calls behind application service interfaces.
- Do not log CV text, candidate contact details, prompts containing personal data, or raw model responses in production logs.
- Do not scrape LinkedIn or arbitrary websites. External sources require documented permission and a dedicated approved connector.
- Do not use protected or sensitive personal characteristics in matching.
- Do not automatically reject candidates or send outreach. A recruiter must make the decision and approve the exact draft.
- Keep deterministic eligibility rules separate from AI assessments.
- Any suspected toolkit issue must follow `docs/toolkit_feedback.md` before the toolkit repository is changed.

## Definition of done

An implementation task is complete only when:

- Its acceptance criteria pass.
- Relevant tests are added or updated.
- Django system checks and the test suite pass.
- Formatting and lint checks pass once configured.
- Security and privacy implications have been considered.
- Documentation and `docs/project_state.md` reflect the result.
- No unrelated changes are included.

## Standard commands

Run from the repository root:

```text
uv sync --extra dev
uv run python scripts/check.py
```

The quality script runs Django checks, the production deployment check,
migration-drift detection, pytest, Ruff, and dependency compatibility checks.
CI must call this same script rather than maintain a second command list.
