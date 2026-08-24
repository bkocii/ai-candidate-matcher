"""Provider-free synthetic showcase built through normal application services."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.core.files.storage import default_storage
from django.db import transaction

from accounts.models import User
from ai_gateway.testing import FakeAIGateway
from candidates.models import CandidateDocument
from evaluation.dataset import EvaluationDataset
from evaluation.services import InstalledEvaluationDataset, install_evaluation_dataset
from matching.ai_assessment import (
    AssessmentContext,
    MatchAssessmentOutput,
    assess_shortlist_entry,
    build_assessment_context,
)
from matching.decisions import record_review_decision
from matching.models import MatchAssessment, ReviewDecision
from outreach.generation import OutreachDraftOutput, generate_outreach_draft
from outreach.models import OutreachDraft

DEMO_VACANCY_CODE = "V01"


@dataclass(frozen=True)
class PreparedDemo:
    installed: InstalledEvaluationDataset
    assessments: tuple[MatchAssessment, ...]
    decisions: tuple[ReviewDecision, ...]
    outreach_draft: OutreachDraft


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _assessment_output(
    *,
    context: AssessmentContext,
    deterministic_score: Decimal,
) -> MatchAssessmentOutput:
    evidence_by_label = {
        _normalized(item.label): item for item in context.candidate_evidence
    }
    findings: list[dict[str, object]] = []
    matched_count = 0
    for requirement in context.requirements:
        evidence = evidence_by_label.get(_normalized(requirement.label))
        if evidence is None:
            findings.append(
                {
                    "requirement_id": requirement.identifier,
                    "outcome": "uncertain",
                    "candidate_evidence_ids": [],
                    "explanation": (
                        "The supplied evidence does not resolve this requirement."
                    ),
                }
            )
            continue
        matched_count += 1
        findings.append(
            {
                "requirement_id": requirement.identifier,
                "outcome": "match",
                "candidate_evidence_ids": [evidence.identifier],
                "explanation": "The linked evidence supports this match.",
            }
        )

    total_count = len(context.requirements)
    if matched_count == total_count:
        summary = "Every confirmed requirement has linked supporting evidence."
    else:
        summary = "Review the linked evidence and unresolved requirement findings."
    score = int(deterministic_score.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return MatchAssessmentOutput.model_validate(
        {
            "score": score,
            "summary": summary,
            "requirement_assessments": findings,
            "review_recommendation": "Verify every uncertain requirement.",
        }
    )


def _create_demo_state(
    *,
    dataset: EvaluationDataset,
    user: User,
    organization_slug: str,
    stored_names: list[str],
) -> PreparedDemo:
    installed = install_evaluation_dataset(
        dataset=dataset,
        user=user,
        organization_slug=organization_slug,
    )
    stored_names.extend(
        CandidateDocument.objects.for_organization(installed.organization).values_list(
            "file", flat=True
        )
    )
    organization = installed.organization
    organization.name = "Synthetic Demo — AI Candidate Matcher"
    organization.full_clean()
    organization.save(update_fields=("name", "updated_at"))

    run = installed.match_runs[DEMO_VACANCY_CODE]
    assessments: list[MatchAssessment] = []
    for entry in run.entries.select_related("candidate").order_by("rank", "id"):
        profile = entry.candidate.current_profile
        context = build_assessment_context(entry=entry, profile=profile)
        output = _assessment_output(
            context=context,
            deterministic_score=entry.score,
        )
        result = assess_shortlist_entry(
            entry=entry,
            user=user,
            gateway=FakeAIGateway(response=output),
        )
        assessments.append(result.assessment)

    decisions: list[ReviewDecision] = []
    decision_specs = (
        (
            ReviewDecision.Decision.APPROVED,
            "Synthetic demo approval after individual evidence review.",
        ),
        (
            ReviewDecision.Decision.REVISIT,
            "Synthetic demo revisit: verify unresolved requirements.",
        ),
        (
            ReviewDecision.Decision.REJECTED,
            "Synthetic demo rejection after individual evidence review.",
        ),
    )
    for assessment, (decision, notes) in zip(
        assessments[:3],
        decision_specs,
        strict=True,
    ):
        decisions.append(
            record_review_decision(
                assessment=assessment,
                user=user,
                decision=decision,
                notes=notes,
            )
        )

    outreach_output = OutreachDraftOutput.model_validate(
        {
            "subject": "A conversation about a synthetic Django role",
            "body": (
                "Hello [Candidate name],\n\n"
                "Your recorded Python and Django experience may be relevant to "
                "our synthetic backend vacancy. Would you be open to a "
                "conversation?\n\nBest,\nSynthetic recruiting team"
            ),
        }
    )
    outreach_draft = generate_outreach_draft(
        decision=decisions[0],
        user=user,
        gateway=FakeAIGateway(response=outreach_output),
    ).draft
    return PreparedDemo(
        installed=installed,
        assessments=tuple(assessments),
        decisions=tuple(decisions),
        outreach_draft=outreach_draft,
    )


def prepare_demo(
    *,
    dataset: EvaluationDataset,
    user: User,
    organization_slug: str,
) -> PreparedDemo:
    """Create an isolated showcase; clean private fixture files on any rollback."""
    stored_names: list[str] = []
    try:
        with transaction.atomic():
            prepared = _create_demo_state(
                dataset=dataset,
                user=user,
                organization_slug=organization_slug,
                stored_names=stored_names,
            )
            return prepared
    except Exception:
        for stored_name in stored_names:
            default_storage.delete(stored_name)
        raise
