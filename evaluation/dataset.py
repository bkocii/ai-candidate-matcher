from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

DATASET_PATH = Path(__file__).with_name("datasets") / "eval-001.json"

Code = Annotated[str, StringConstraints(pattern=r"^[A-Z][0-9]{2}$")]
NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CandidateSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: Code
    full_name: NonBlankText
    location: NonBlankText
    summary: NonBlankText
    skills: list[NonBlankText] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_unique_skills(self) -> CandidateSpec:
        normalized = [skill.casefold() for skill in self.skills]
        if len(normalized) != len(set(normalized)):
            raise ValueError(f"Candidate {self.code} contains duplicate skills.")
        return self


class ExpectedRank(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_code: Code
    score: Decimal = Field(ge=0, le=100, decimal_places=2)


class VacancySpec(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: Code
    title: NonBlankText
    description: NonBlankText
    summary: NonBlankText
    must_have_skills: list[NonBlankText] = Field(min_length=1, max_length=20)
    nice_to_have_skills: list[NonBlankText] = Field(default_factory=list, max_length=20)
    expected_top: list[ExpectedRank] = Field(min_length=1, max_length=20)
    relevance_judgments: dict[Code, int]

    @model_validator(mode="after")
    def validate_skills_and_expected_ranks(self) -> VacancySpec:
        skills = self.must_have_skills + self.nice_to_have_skills
        normalized = [skill.casefold() for skill in skills]
        if len(normalized) != len(set(normalized)):
            raise ValueError(f"Vacancy {self.code} contains duplicate skills.")
        expected_codes = [item.candidate_code for item in self.expected_top]
        if len(expected_codes) != len(set(expected_codes)):
            raise ValueError(f"Vacancy {self.code} repeats an expected candidate.")
        if any(
            grade not in {0, 1, 2, 3} for grade in self.relevance_judgments.values()
        ):
            raise ValueError("Relevance judgments must use grades 0 through 3.")
        return self


class EvaluationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    dataset_id: NonBlankText
    schema_version: NonBlankText
    notice: NonBlankText
    candidates: list[CandidateSpec] = Field(min_length=20)
    vacancies: list[VacancySpec] = Field(min_length=3)

    @model_validator(mode="after")
    def validate_cross_references(self) -> EvaluationDataset:
        candidate_codes = [candidate.code for candidate in self.candidates]
        vacancy_codes = [vacancy.code for vacancy in self.vacancies]
        if len(candidate_codes) != len(set(candidate_codes)):
            raise ValueError("Candidate codes must be unique.")
        if len(vacancy_codes) != len(set(vacancy_codes)):
            raise ValueError("Vacancy codes must be unique.")

        candidate_code_set = set(candidate_codes)
        for vacancy in self.vacancies:
            expected_codes = {item.candidate_code for item in vacancy.expected_top}
            if not expected_codes.issubset(candidate_code_set):
                raise ValueError(
                    f"Vacancy {vacancy.code} references an unknown expected candidate."
                )
            if set(vacancy.relevance_judgments) != candidate_code_set:
                raise ValueError(
                    f"Vacancy {vacancy.code} must judge every candidate exactly once."
                )
        return self


def load_evaluation_dataset(path: Path = DATASET_PATH) -> EvaluationDataset:
    """Load and strictly validate the version-controlled synthetic dataset."""
    return EvaluationDataset.model_validate_json(path.read_text(encoding="utf-8"))


def canonical_dataset_json(dataset: EvaluationDataset) -> str:
    """Return stable JSON for dataset identity and later measurement reports."""
    return json.dumps(
        dataset.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
