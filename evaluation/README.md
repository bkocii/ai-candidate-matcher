# Synthetic Evaluation Dataset and Ranking Measurement

This directory contains the version-controlled source of truth for the first
product evaluation dataset. Every person, organization, vacancy, document, and
fact is invented for software testing. Do not replace it with real recruitment
data.

`datasets/eval-001.json` contains:

- 20 synthetic candidates across backend, data, frontend, platform, QA, and
  unrelated comparison profiles;
- 3 synthetic vacancies with explicit must-have and nice-to-have skills;
- a frozen expected deterministic top five, including exact scores; and
- a complete human-authored relevance grade from 0 (not relevant) through 3
  (ideal) for every candidate/vacancy pair.

Install it into a new isolated organization owned by an existing active user:

```powershell
uv run python manage.py load_evaluation_dataset --username admin --organization-slug synthetic-eval-001
```

The command refuses to overwrite an existing organization. It generates one
private DOCX CV per candidate from the manifest, validates the documents through
the ordinary upload boundary, creates exact-evidence confirmed synthetic
profiles, confirms and opens the three vacancies, and generates their
deterministic shortlists. The whole database operation rolls back and generated
files are removed if a frozen expected rank or score does not match.

No provider request, AI usage event, assessment, recruiter decision, outreach
draft, or send action is created. All synthetic sources have contact permission
set to restricted.

## Frozen deterministic top five

| Vacancy | Expected candidates and scores |
| --- | --- |
| V01 — Django backend | C01 100.00, C02 85.72, C03 71.43, C04 71.42, C14 57.14 |
| V02 — Data analyst | C06 100.00, C07 85.71, C09 71.43, C10 71.43, C08 57.14 |
| V03 — React frontend | C11 100.00, C12 85.72, C14 85.72, C13 71.43, C15 57.15 |

## EVAL-002 ranking quality

Measure the installed workspace without making an AI request:

```powershell
uv run python manage.py measure_evaluation_dataset --username admin --organization-slug synthetic-eval-001
```

The report measures each vacancy and the macro average at cutoff 5 using:

- graded `nDCG@5` against the complete 0–3 relevance judgments;
- `precision@5`, where grades 2 and 3 count as relevant; and
- overlap between the measured and frozen expected top-five candidate sets.

The deterministic ordering comes only from the latest current shortlist. The
AI-assisted ordering comes only from each entry's latest assessment score, with
the deterministic rank used solely as a stable tie-break. The two scores are
never added, averaged, or otherwise blended.

AI quality is available for a vacancy only when every one of its 20 shortlist
entries has a latest assessment tied to the current confirmed profile and
requirements. Partial or stale coverage is reported as unavailable, never as a
zero or a partial quality estimate. Use `--require-complete-ai` when complete AI
coverage is a required gate, and `--format json` for machine-readable output.

Reports contain only dataset identity, organization slug, vacancy codes,
metrics, and coverage counts. They contain no candidate names/contact data, CV
text, evidence, prompts, raw responses, decisions, or outreach content. The
measurement is read-only and creates no AI usage event.
