import json
import re
from dataclasses import dataclass
from typing import Annotated

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_validator,
    model_validator,
)

from accounts.models import User
from ai_gateway import (
    AIGateway,
    AIGatewayError,
    AIGatewayMetadata,
    AIGatewayResult,
    get_ai_gateway,
)
from audit.models import AIUsageEvent
from audit.services import (
    complete_ai_usage_failure,
    complete_ai_usage_success,
    start_ai_usage_event,
)
from matching.decisions import assess_review_decision_eligibility
from matching.models import ReviewDecision, ShortlistEntry
from organizations.permissions import require_organization_object_access
from outreach.models import OutreachDraft

OUTREACH_DRAFT_SCHEMA_VERSION = "outreach_draft.v2"
CANDIDATE_NAME_PLACEHOLDER = "[Candidate name]"
MAX_OUTREACH_CONTEXT_CHARACTERS = 20_000
MAX_MATCH_FACTS = 8
MAX_CANDIDATE_GUIDANCE_CHARACTERS = 1_000

MESSAGE_PURPOSES = {
    ReviewDecision.Decision.APPROVED: "approved_outreach",
    ReviewDecision.Decision.REVISIT: "revisit_status_update",
    ReviewDecision.Decision.REJECTED: "rejection",
}

OutreachSubject = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
OutreachBody = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=5_000),
]

_UNSUPPORTED_CONTACT_RE = re.compile(
    r"(?:https?://|www\.|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\+?\d[\d ()-]{6,}\d)",
    re.IGNORECASE,
)
_DECISION_OR_OFFER_RE = re.compile(
    r"\b(?:you(?:'re| are) hired|we (?:are )?offering you|job offer|"
    r"guaranteed (?:job|role|position)|automatically approved)\b",
    re.IGNORECASE,
)


class OutreachDraftOutput(BaseModel):
    """Bounded provider output; identity is inserted only after validation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    subject: OutreachSubject
    body: OutreachBody

    @field_validator("subject")
    @classmethod
    def reject_subject_placeholder(cls, value: str) -> str:
        if CANDIDATE_NAME_PLACEHOLDER in value:
            raise ValueError("Keep the candidate-name placeholder in the body only.")
        return value

    @model_validator(mode="after")
    def enforce_safe_draft_boundary(self):
        if self.body.count(CANDIDATE_NAME_PLACEHOLDER) != 1:
            raise ValueError(
                "The body must contain the candidate-name placeholder exactly once."
            )
        combined = f"{self.subject}\n{self.body}"
        if _UNSUPPORTED_CONTACT_RE.search(combined):
            raise ValueError("Do not invent contact details or links.")
        if _DECISION_OR_OFFER_RE.search(combined):
            raise ValueError("The draft must not make a hiring decision or job offer.")
        return self


@dataclass(frozen=True)
class OutreachDraftEligibility:
    can_generate: bool
    reason: str = ""


@dataclass(frozen=True)
class OutreachDraftResult:
    draft: OutreachDraft
    metadata: AIGatewayMetadata


def assess_outreach_draft_eligibility(
    *,
    decision: ReviewDecision,
    user: User,
) -> OutreachDraftEligibility:
    """Require the latest explicit recruiter decision against current evidence."""
    require_organization_object_access(user, decision)
    entry = decision.shortlist_entry
    latest_decision = (
        ReviewDecision.objects.filter(shortlist_entry=entry)
        .order_by("-version", "-created_at", "-id")
        .first()
    )
    if latest_decision is None or latest_decision.pk != decision.pk:
        return OutreachDraftEligibility(
            False,
            "Only the latest recruiter decision can authorize a new email draft.",
        )
    if decision.decision not in MESSAGE_PURPOSES:
        return OutreachDraftEligibility(
            False,
            "Record a supported current recruiter decision before preparing email.",
        )
    decision_eligibility = assess_review_decision_eligibility(
        assessment=decision.assessment,
        user=user,
    )
    if not decision_eligibility.can_record:
        return OutreachDraftEligibility(False, decision_eligibility.reason)
    return OutreachDraftEligibility(True)


def _bounded_text(value: object, *, maximum: int) -> str:
    return str(value).strip()[:maximum]


def build_outreach_context(
    *,
    decision: ReviewDecision,
    candidate_facing_guidance: str = "",
    follow_up_date: str = "",
) -> dict[str, object]:
    """Build minimized, source-grounded context without candidate identity/contact."""
    assessment = decision.assessment
    match_facts: list[dict[str, object]] = []
    findings = (
        assessment.matching_requirements
        if decision.decision == ReviewDecision.Decision.APPROVED
        else []
    )
    for finding in findings[:MAX_MATCH_FACTS]:
        if not isinstance(finding, dict):
            continue
        evidence_values: list[str] = []
        candidate_evidence = finding.get("candidate_evidence", [])
        if not isinstance(candidate_evidence, list):
            continue
        for evidence in candidate_evidence[:3]:
            if isinstance(evidence, dict) and evidence.get("evidence"):
                evidence_values.append(_bounded_text(evidence["evidence"], maximum=500))
        label = _bounded_text(finding.get("requirement_label", ""), maximum=300)
        if label and evidence_values:
            match_facts.append(
                {
                    "vacancy_requirement": label,
                    "candidate_evidence": evidence_values,
                }
            )
    context: dict[str, object] = {
        "schema_version": OUTREACH_DRAFT_SCHEMA_VERSION,
        "candidate_name_placeholder": CANDIDATE_NAME_PLACEHOLDER,
        "message_purpose": MESSAGE_PURPOSES[decision.decision],
        "organization_name": _bounded_text(
            decision.organization.name,
            maximum=200,
        ),
        "vacancy_title": _bounded_text(
            assessment.requirements.vacancy.title,
            maximum=200,
        ),
        "approved_match_facts": match_facts,
    }
    guidance = _bounded_text(
        candidate_facing_guidance,
        maximum=MAX_CANDIDATE_GUIDANCE_CHARACTERS,
    )
    if guidance:
        context["candidate_facing_guidance"] = guidance
    if decision.decision == ReviewDecision.Decision.REVISIT and follow_up_date:
        context["follow_up_date"] = _bounded_text(follow_up_date, maximum=10)
    serialized = json.dumps(context, ensure_ascii=True, sort_keys=True)
    if len(serialized) > MAX_OUTREACH_CONTEXT_CHARACTERS:
        raise ValidationError("The approved outreach context is too large.")
    return context


def build_outreach_prompt(context: dict[str, object]) -> str:
    payload = json.dumps(context, ensure_ascii=True, sort_keys=True)
    purpose = context["message_purpose"]
    purpose_instruction = {
        "approved_outreach": (
            "Invite the candidate to discuss the named vacancy. Mention at most two "
            "supplied match facts and ask whether they are open to a conversation."
        ),
        "revisit_status_update": (
            "Write a neutral status update saying the application remains under "
            "consideration. Include the supplied follow-up date when present, but do "
            "not promise a decision or outcome."
        ),
        "rejection": (
            "Write a concise, respectful rejection for the named vacancy. Do not "
            "state or invent a rejection reason."
        ),
    }[purpose]
    return (
        "Create a concise candidate email draft from only the supplied JSON. "
        "Return a subject and plain-text body. Address the person using the exact "
        f"token {CANDIDATE_NAME_PLACEHOLDER} exactly once in the body and do not put "
        f"it in the subject. {purpose_instruction} Candidate-facing guidance is an "
        "optional recruiter instruction, not verified evidence; use it only when it "
        "is compatible with these rules. Do not invent employers, experience, "
        "skills, compensation, contact "
        "details, links, deadlines, or availability. Do not mention scores, internal "
        "notes, ranking, gaps, uncertainty, protected characteristics, or source "
        "evidence. Do not make a job offer or promise. This is a draft for later human "
        "editing and approval; do not send anything.\n\n"
        f"Minimized context:\n{payload}"
    )


def generate_outreach_draft(
    *,
    decision: ReviewDecision,
    user: User,
    gateway: AIGateway | None = None,
    candidate_facing_guidance: str = "",
    follow_up_date: str = "",
) -> OutreachDraftResult:
    """Generate one inspectable draft without approving or sending it."""
    require_organization_object_access(user, decision)
    decision = ReviewDecision.objects.select_related(
        "assessment__requirements__vacancy__organization",
        "assessment__candidate_profile",
        "shortlist_entry__candidate",
        "shortlist_entry__match_run__requirements__vacancy",
    ).get(pk=decision.pk)
    eligibility = assess_outreach_draft_eligibility(decision=decision, user=user)
    if not eligibility.can_generate:
        raise ValidationError(eligibility.reason)
    context = build_outreach_context(
        decision=decision,
        candidate_facing_guidance=candidate_facing_guidance,
        follow_up_date=follow_up_date,
    )
    usage_event = start_ai_usage_event(
        organization=decision.organization,
        actor=user,
        workflow=AIUsageEvent.Workflow.OUTREACH_DRAFT,
        target_type=AIUsageEvent.ObjectType.REVIEW_DECISION,
        target_id=decision.pk,
    )
    gateway_result: AIGatewayResult[OutreachDraftOutput] | None = None
    try:
        active_gateway = gateway if gateway is not None else get_ai_gateway()
        gateway_result = active_gateway.request_structured(
            prompt=build_outreach_prompt(context),
            response_type=OutreachDraftOutput,
        )
        output = gateway_result.data
        with transaction.atomic():
            entry = ShortlistEntry.objects.select_for_update().get(
                pk=decision.shortlist_entry_id
            )
            locked_decision = ReviewDecision.objects.select_related(
                "assessment__requirements__vacancy__organization",
                "assessment__candidate_profile",
                "shortlist_entry__candidate",
                "shortlist_entry__match_run__requirements__vacancy",
            ).get(pk=decision.pk, shortlist_entry=entry)
            current_eligibility = assess_outreach_draft_eligibility(
                decision=locked_decision,
                user=user,
            )
            if not current_eligibility.can_generate:
                raise ValidationError(
                    f"Decision or matching inputs changed while email was being "
                    f"generated. No draft was saved. {current_eligibility.reason}"
                )
            version = (
                OutreachDraft.objects.filter(shortlist_entry=entry).aggregate(
                    Max("version")
                )["version__max"]
                or 0
            ) + 1
            draft = OutreachDraft.objects.create(
                shortlist_entry=entry,
                review_decision=locked_decision,
                version=version,
                schema_version=OUTREACH_DRAFT_SCHEMA_VERSION,
                subject=output.subject,
                body=output.body.replace(
                    CANDIDATE_NAME_PLACEHOLDER,
                    entry.candidate.full_name,
                ),
                created_by=user,
            )
            complete_ai_usage_success(
                event=usage_event,
                metadata=gateway_result.metadata,
                result_type=AIUsageEvent.ObjectType.OUTREACH_DRAFT,
                result_id=draft.pk,
            )
    except (AIGatewayError, ValidationError) as error:
        complete_ai_usage_failure(
            event=usage_event,
            error=error,
            metadata=gateway_result.metadata if gateway_result is not None else None,
        )
        raise
    return OutreachDraftResult(draft=draft, metadata=gateway_result.metadata)
