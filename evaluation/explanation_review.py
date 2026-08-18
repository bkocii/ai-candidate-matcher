"""Read-only EVAL-003 review of stored AI assessment explanations."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass

from accounts.models import User
from candidates.models import CandidateProfile
from evaluation.dataset import EvaluationDataset, canonical_dataset_json
from evaluation.measurement import (
    _candidate_map,
    _latest_assessments,
    _vacancy_map,
    measure_evaluation_quality,
)
from matching.ai_assessment import AssessmentContext, build_assessment_context
from matching.explanation_safety import (
    contains_protected_attribute_language,
    measured_claims,
    normalize_explanation_text,
    quoted_claims,
)
from matching.models import MatchAssessment, MatchRun
from organizations.models import Organization

_TOKEN_RE = re.compile(r"\b[\w+#.]{2,}\b", flags=re.UNICODE)
_MATCH_STOPWORDS = {
    "and",
    "at",
    "candidate",
    "experience",
    "for",
    "has",
    "have",
    "least",
    "must",
    "of",
    "required",
    "requires",
    "skill",
    "the",
    "with",
    "year",
    "years",
}


@dataclass(frozen=True)
class ExplanationIssue:
    code: str
    location: str


@dataclass(frozen=True)
class AssessmentExplanationReview:
    vacancy_code: str
    candidate_code: str
    assessment_version: int
    status: str
    issues: tuple[ExplanationIssue, ...]


@dataclass(frozen=True)
class ExplanationReviewReport:
    dataset_id: str
    dataset_sha256: str
    organization_slug: str
    status: str
    reviewed_count: int
    expected_count: int
    clean_count: int
    flagged_count: int
    issue_counts: dict[str, int]
    assessments: tuple[AssessmentExplanationReview, ...]

    @property
    def is_complete(self) -> bool:
        return self.reviewed_count == self.expected_count

    @property
    def is_clean(self) -> bool:
        return self.is_complete and self.flagged_count == 0


def _source_texts(context: AssessmentContext) -> tuple[str, ...]:
    return tuple(
        value for item in context.requirements for value in (item.label, item.evidence)
    ) + tuple(
        value
        for item in context.candidate_evidence
        for value in (item.label, item.evidence)
    )


def _unsupported_text_issues(
    *,
    text: str,
    sources: tuple[str, ...],
    location: str,
) -> list[ExplanationIssue]:
    issues: list[ExplanationIssue] = []
    if contains_protected_attribute_language([text]):
        issues.append(ExplanationIssue("protected_attribute_language", location))

    source_claims = {claim for source in sources for claim in measured_claims(source)}
    if any(claim not in source_claims for claim in measured_claims(text)):
        issues.append(ExplanationIssue("unsupported_measured_claim", location))

    normalized_sources = tuple(normalize_explanation_text(item) for item in sources)
    if any(
        not any(claim in source for source in normalized_sources)
        for claim in quoted_claims(text)
    ):
        issues.append(ExplanationIssue("unsupported_quoted_claim", location))
    return issues


def _meaningful_tokens(values: tuple[str, ...]) -> set[str]:
    text = normalize_explanation_text(" ".join(values))
    return {
        token
        for token in _TOKEN_RE.findall(text)
        if token not in _MATCH_STOPWORDS and not token.isdecimal()
    }


def _review_finding(
    *,
    finding: object,
    outcome: str,
    location: str,
    context: AssessmentContext,
    seen_requirements: set[str],
) -> list[ExplanationIssue]:
    issues: list[ExplanationIssue] = []
    if not isinstance(finding, dict):
        return [ExplanationIssue("invalid_finding_structure", location)]

    requirements = {item.identifier: item for item in context.requirements}
    evidence = {item.identifier: item for item in context.candidate_evidence}
    requirement_id = finding.get("requirement_id")
    requirement = requirements.get(requirement_id)
    if requirement is None or requirement_id in seen_requirements:
        issues.append(ExplanationIssue("invalid_requirement_snapshot", location))
    else:
        seen_requirements.add(requirement_id)
        if any(
            finding.get(key) != expected
            for key, expected in (
                ("requirement_label", requirement.label),
                ("requirement_evidence", requirement.evidence),
                ("category", requirement.category),
            )
        ):
            issues.append(ExplanationIssue("invalid_requirement_snapshot", location))

    stored_evidence = finding.get("candidate_evidence")
    resolved_evidence = []
    evidence_valid = isinstance(stored_evidence, list)
    seen_evidence: set[str] = set()
    if evidence_valid:
        for item in stored_evidence:
            if not isinstance(item, dict):
                evidence_valid = False
                continue
            identifier = item.get("id")
            reference = evidence.get(identifier)
            if reference is None or identifier in seen_evidence:
                evidence_valid = False
                continue
            seen_evidence.add(identifier)
            resolved_evidence.append(reference)
            if any(
                item.get(key) != expected
                for key, expected in (
                    ("label", reference.label),
                    ("evidence", reference.evidence),
                )
            ):
                evidence_valid = False
    if not evidence_valid:
        issues.append(ExplanationIssue("invalid_evidence_snapshot", location))
    if outcome in {"match", "gap"} and not resolved_evidence:
        issues.append(ExplanationIssue("missing_required_evidence", location))

    explanation = finding.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        issues.append(ExplanationIssue("invalid_explanation_text", location))
        return issues

    sources: tuple[str, ...] = ()
    if requirement is not None:
        sources += (requirement.label, requirement.evidence)
    sources += tuple(
        value for item in resolved_evidence for value in (item.label, item.evidence)
    )
    issues.extend(
        _unsupported_text_issues(
            text=explanation,
            sources=sources,
            location=location,
        )
    )
    if outcome == "match" and requirement is not None and resolved_evidence:
        requirement_tokens = _meaningful_tokens(
            (requirement.label, requirement.evidence)
        )
        evidence_tokens = _meaningful_tokens(
            tuple(
                value
                for item in resolved_evidence
                for value in (item.label, item.evidence)
            )
        )
        if requirement_tokens and not requirement_tokens & evidence_tokens:
            issues.append(ExplanationIssue("match_without_lexical_support", location))
    return issues


def _review_assessment(
    *,
    assessment: MatchAssessment,
    context: AssessmentContext,
    vacancy_code: str,
    candidate_code: str,
) -> AssessmentExplanationReview:
    issues: list[ExplanationIssue] = []
    all_sources = _source_texts(context)
    issues.extend(
        _unsupported_text_issues(
            text=assessment.summary,
            sources=all_sources,
            location="summary",
        )
    )
    issues.extend(
        _unsupported_text_issues(
            text=assessment.review_recommendation,
            sources=all_sources,
            location="review_recommendation",
        )
    )
    seen_requirements: set[str] = set()
    for field_name, outcome in (
        ("matching_requirements", "match"),
        ("gaps", "gap"),
        ("uncertainties", "uncertain"),
    ):
        findings = getattr(assessment, field_name)
        if not isinstance(findings, list):
            issues.append(ExplanationIssue("invalid_finding_structure", field_name))
            continue
        for position, finding in enumerate(findings):
            issues.extend(
                _review_finding(
                    finding=finding,
                    outcome=outcome,
                    location=f"{field_name}[{position}]",
                    context=context,
                    seen_requirements=seen_requirements,
                )
            )
    expected_requirements = {item.identifier for item in context.requirements}
    if seen_requirements != expected_requirements:
        issues.append(
            ExplanationIssue("incomplete_requirement_coverage", "requirements")
        )
    unique_issues = tuple(dict.fromkeys(issues))
    return AssessmentExplanationReview(
        vacancy_code=vacancy_code,
        candidate_code=candidate_code,
        assessment_version=assessment.version,
        status="clean" if not unique_issues else "flagged",
        issues=unique_issues,
    )


def review_evaluation_explanations(
    *,
    dataset: EvaluationDataset,
    organization: Organization,
    user: User,
) -> ExplanationReviewReport:
    """Audit current stored explanations without making a provider request."""
    measurement = measure_evaluation_quality(
        dataset=dataset,
        organization=organization,
        user=user,
    )
    candidate_codes_by_id = _candidate_map(
        organization=organization,
        dataset=dataset,
    )
    vacancies = _vacancy_map(organization=organization, dataset=dataset)
    reviews: list[AssessmentExplanationReview] = []

    for vacancy_spec in dataset.vacancies:
        vacancy = vacancies[vacancy_spec.code]
        run = (
            MatchRun.objects.for_organization(organization)
            .filter(requirements=vacancy.current_requirements)
            .order_by("-created_at", "-id")
            .first()
        )
        entries = list(
            run.entries.select_related("candidate", "match_run__requirements")
            .prefetch_related(
                "match_run__requirements__skill_records__skill",
                "match_run__requirements__hard_constraint_rules__skill",
            )
            .order_by("rank", "id")
        )
        latest_assessments = _latest_assessments(entries)
        profiles: dict[int, CandidateProfile] = {}
        for profile in CandidateProfile.objects.filter(
            candidate_id__in={entry.candidate_id for entry in entries},
            status=CandidateProfile.Status.CONFIRMED,
        ).order_by("candidate_id", "-version", "-created_at", "-id"):
            profiles.setdefault(profile.candidate_id, profile)
        for entry in entries:
            profile = profiles.get(entry.candidate_id)
            assessment = latest_assessments.get(entry.pk)
            if (
                assessment is None
                or profile is None
                or assessment.requirements_id != run.requirements_id
                or assessment.candidate_profile_id != profile.pk
            ):
                continue
            context = build_assessment_context(entry=entry, profile=profile)
            reviews.append(
                _review_assessment(
                    assessment=assessment,
                    context=context,
                    vacancy_code=vacancy_spec.code,
                    candidate_code=candidate_codes_by_id[entry.candidate_id],
                )
            )

    reviews.sort(key=lambda item: (item.vacancy_code, item.candidate_code))
    issue_counts = Counter(issue.code for review in reviews for issue in review.issues)
    reviewed_count = len(reviews)
    expected_count = measurement.ai_expected_count
    flagged_count = sum(review.status == "flagged" for review in reviews)
    dataset_sha256 = hashlib.sha256(
        canonical_dataset_json(dataset).encode("utf-8")
    ).hexdigest()
    return ExplanationReviewReport(
        dataset_id=dataset.dataset_id,
        dataset_sha256=dataset_sha256,
        organization_slug=organization.slug,
        status="complete" if reviewed_count == expected_count else "unavailable",
        reviewed_count=reviewed_count,
        expected_count=expected_count,
        clean_count=reviewed_count - flagged_count,
        flagged_count=flagged_count,
        issue_counts=dict(sorted(issue_counts.items())),
        assessments=tuple(reviews),
    )
