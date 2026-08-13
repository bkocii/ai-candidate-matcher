# Opt-in live AI smoke test

This directory is outside the ordinary `tests` path, so `pytest` and
`scripts/check.py` never collect it. The test sends only a tiny synthetic prompt
through the published Python AI Toolkit integration. It reads the configured
provider/key/model, makes one potentially billable request, and stores no result.

Run it deliberately from PowerShell:

```powershell
$env:RUN_LIVE_AI_SMOKE = "1"
uv run pytest -q -m live_ai live_tests/test_ai_gateway_live.py
Remove-Item Env:RUN_LIVE_AI_SMOKE
```

Set a valid provider key/model in `.env` first. Never replace the synthetic
prompt with candidate, vacancy, CV, contact, or other private data.
