import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import override_settings
from django.urls import reverse
from pydantic import ValidationError as PydanticValidationError

from ai_gateway import AIGatewayUnavailableError
from ai_gateway.testing import FakeAIGateway
from audit.models import AIUsageEvent
from candidates.services import delete_candidate, request_candidate_deletion
from matching.decisions import record_review_decision
from matching.models import ReviewDecision
from outreach.generation import (
    CANDIDATE_NAME_PLACEHOLDER,
    OutreachDraftOutput,
    assess_outreach_draft_eligibility,
    generate_outreach_draft,
)
from outreach.models import OutreachDraft
from tests.test_match_ai_assessment import CV_TEXT, make_workspace
from tests.test_recruiter_review import create_assessment

pytestmark = pytest.mark.django_db


def draft_output() -> OutreachDraftOutput:
    return OutreachDraftOutput.model_validate(
        {
            "subject": "A conversation about the Senior Django Developer role",
            "body": (
                f"Hello {CANDIDATE_NAME_PLACEHOLDER},\n\n"
                "Your Python experience may be relevant to this role. Would you "
                "be open to a conversation?\n\nBest,\nRecruitment team"
            ),
        }
    )


class ConfiguredOutreachGateway(FakeAIGateway):
    def __init__(self):
        super().__init__(response=draft_output())


def approved_workspace(*, username="recruiter"):
    values = make_workspace(username=username)
    user, _, _, _, profile, _, _, entry = values
    assessment = create_assessment(user, profile, entry)
    decision = record_review_decision(
        assessment=assessment,
        user=user,
        decision=ReviewDecision.Decision.APPROVED,
        notes="The recruiter inspected the evidence and approved this match.",
    )
    return (*values, assessment, decision)


def generate_url(organization, decision):
    return reverse(
        "outreach:outreach-draft-generate",
        args=[organization.slug, decision.pk],
    )


def detail_url(organization, draft):
    return reverse(
        "outreach:outreach-draft-detail",
        args=[organization.slug, draft.pk],
    )


def review_url(organization, assessment):
    return reverse(
        "matching:assessment-review-detail",
        args=[organization.slug, assessment.pk],
    )


def test_drafts_are_versioned_actor_attributed_and_immutable():
    user, _, candidate, _, _, _, _, _, _, decision = approved_workspace()
    gateway = FakeAIGateway(response=draft_output())

    first = generate_outreach_draft(
        decision=decision,
        user=user,
        gateway=gateway,
    ).draft
    second = generate_outreach_draft(
        decision=decision,
        user=user,
        gateway=FakeAIGateway(response=draft_output()),
    ).draft

    assert (first.version, second.version) == (1, 2)
    assert first.created_by == user
    assert first.created_at is not None
    assert first.review_decision == decision
    assert candidate.full_name in first.body
    assert CANDIDATE_NAME_PLACEHOLDER not in first.body
    first.subject = "Changed"
    with pytest.raises(ValidationError, match="immutable"):
        first.save()


def test_prompt_minimizes_candidate_data_and_uses_confirmed_match_evidence():
    user, _, candidate, _, _, _, _, _, _, decision = approved_workspace()
    candidate.phone = "+383 44 000 111"
    candidate.save(update_fields=("phone", "updated_at"))
    gateway = FakeAIGateway(response=draft_output())

    generate_outreach_draft(decision=decision, user=user, gateway=gateway)

    prompt = gateway.calls[0].prompt
    assert CANDIDATE_NAME_PLACEHOLDER in prompt
    assert "Python: five years" in prompt
    assert candidate.full_name not in prompt
    assert candidate.email not in prompt
    assert candidate.phone not in prompt
    assert CV_TEXT not in prompt
    assert decision.notes not in prompt
    assert "No certification information" not in prompt


def test_only_latest_explicit_current_approval_can_generate():
    user, _, _, _, _, _, _, _, assessment, approved = approved_workspace()
    rejected = record_review_decision(
        assessment=assessment,
        user=user,
        decision=ReviewDecision.Decision.REJECTED,
        notes="The recruiter corrected the earlier decision.",
    )

    older = assess_outreach_draft_eligibility(decision=approved, user=user)
    latest = assess_outreach_draft_eligibility(decision=rejected, user=user)

    assert older.can_generate is False
    assert "latest recruiter decision" in older.reason
    assert latest.can_generate is False
    assert "explicit current approval" in latest.reason
    with pytest.raises(ValidationError, match="latest recruiter decision"):
        generate_outreach_draft(
            decision=approved,
            user=user,
            gateway=FakeAIGateway(response=draft_output()),
        )
    assert not OutreachDraft.objects.exists()
    assert not AIUsageEvent.objects.filter(
        workflow=AIUsageEvent.Workflow.OUTREACH_DRAFT
    ).exists()


def test_changed_matching_inputs_invalidate_existing_approval():
    user, _, candidate, _, _, _, _, _, _, decision = approved_workspace()
    candidate.location = "Changed after approval"
    candidate.save(update_fields=("location", "updated_at"))

    eligibility = assess_outreach_draft_eligibility(decision=decision, user=user)

    assert eligibility.can_generate is False
    assert "shortlist inputs changed" in eligibility.reason
    with pytest.raises(ValidationError, match="shortlist inputs changed"):
        generate_outreach_draft(
            decision=decision,
            user=user,
            gateway=FakeAIGateway(response=draft_output()),
        )
    assert not AIUsageEvent.objects.filter(
        workflow=AIUsageEvent.Workflow.OUTREACH_DRAFT
    ).exists()


def test_historical_assessment_page_does_not_offer_current_generation(client):
    user, organization, _, _, profile, _, _, entry, older, _ = approved_workspace()
    latest = create_assessment(user, profile, entry, score=86)
    client.force_login(user)

    older_page = client.get(review_url(organization, older)).content.decode()
    latest_page = client.get(review_url(organization, latest)).content.decode()

    assert "latest assessment version" in older_page
    assert "Generate outreach draft</button>" not in older_page
    assert "explicit approval for this latest assessment" in latest_page
    assert "Generate outreach draft</button>" not in latest_page


def test_output_schema_rejects_identity_leakage_contact_and_offer_language():
    base = {
        "subject": "Role conversation",
        "body": f"Hello {CANDIDATE_NAME_PLACEHOLDER}, are you open to a conversation?",
    }
    with pytest.raises(PydanticValidationError, match="placeholder exactly once"):
        OutreachDraftOutput.model_validate({**base, "body": "Hello there"})
    with pytest.raises(PydanticValidationError, match="contact details"):
        OutreachDraftOutput.model_validate(
            {**base, "body": f"Email us@example.test, {CANDIDATE_NAME_PLACEHOLDER}"}
        )
    with pytest.raises(PydanticValidationError, match="job offer"):
        OutreachDraftOutput.model_validate(
            {**base, "body": f"{CANDIDATE_NAME_PLACEHOLDER}, this is a job offer."}
        )
    with pytest.raises(PydanticValidationError):
        OutreachDraftOutput.model_validate({**base, "candidate_email": "private@test"})


def test_gateway_failure_records_safe_event_and_no_draft():
    user, organization, _, _, _, _, _, _, _, decision = approved_workspace()

    with pytest.raises(AIGatewayUnavailableError):
        generate_outreach_draft(
            decision=decision,
            user=user,
            gateway=FakeAIGateway(error=AIGatewayUnavailableError()),
        )

    event = AIUsageEvent.objects.get(
        organization=organization,
        workflow=AIUsageEvent.Workflow.OUTREACH_DRAFT,
    )
    assert event.status == AIUsageEvent.Status.FAILED
    assert event.target_type == AIUsageEvent.ObjectType.REVIEW_DECISION
    assert event.target_id == decision.pk
    assert event.result_id is None
    assert not OutreachDraft.objects.exists()


def test_approval_is_rechecked_after_provider_returns():
    user, organization, _, _, _, _, _, _, assessment, decision = approved_workspace()

    def supersede_approval(prompt, response_type):
        record_review_decision(
            assessment=assessment,
            user=user,
            decision=ReviewDecision.Decision.REVISIT,
            notes="Evidence changed while the draft request was running.",
        )
        return draft_output()

    with pytest.raises(ValidationError, match="Approval or matching inputs changed"):
        generate_outreach_draft(
            decision=decision,
            user=user,
            gateway=FakeAIGateway(responder=supersede_approval),
        )

    event = AIUsageEvent.objects.get(
        organization=organization,
        workflow=AIUsageEvent.Workflow.OUTREACH_DRAFT,
    )
    assert event.status == AIUsageEvent.Status.FAILED
    assert event.failure_stage == AIUsageEvent.FailureStage.APPLICATION
    assert not OutreachDraft.objects.exists()


@override_settings(
    AI_GATEWAY_FACTORY="tests.test_outreach_drafts.ConfiguredOutreachGateway"
)
def test_recruiter_generates_and_inspects_draft_but_cannot_send(client):
    user, organization, candidate, _, _, _, _, _, assessment, decision = (
        approved_workspace()
    )
    client.force_login(user)

    review = client.get(review_url(organization, assessment))
    get_generate = client.get(generate_url(organization, decision))
    response = client.post(generate_url(organization, decision), follow=True)
    content = response.content.decode()

    assert review.status_code == 200
    assert "Generate outreach draft" in review.content.decode()
    assert get_generate.status_code == 405
    assert response.status_code == 200
    assert "Outreach draft version 1 was generated for review" in content
    assert "Not finally approved or sent" in content
    assert "Edit into new version" in content
    assert "Approve this exact draft" in content
    assert candidate.full_name in content
    assert "Your Python experience may be relevant" in content
    assert "Send" not in content
    draft = OutreachDraft.objects.get()
    assert detail_url(organization, draft) in response.redirect_chain[-1][0]


def test_cross_organization_access_is_hidden_at_service_and_routes(client):
    owner, organization, _, _, _, _, _, _, _, decision = approved_workspace(
        username="owner"
    )
    outsider, other, *_ = make_workspace(username="outsider")
    client.force_login(outsider)

    response = client.post(generate_url(organization, decision))
    mismatched = client.post(generate_url(other, decision))

    assert response.status_code == 404
    assert mismatched.status_code == 404
    with pytest.raises(PermissionDenied):
        generate_outreach_draft(
            decision=decision,
            user=outsider,
            gateway=FakeAIGateway(response=draft_output()),
        )
    assert owner != outsider
    assert not OutreachDraft.objects.exists()


def test_candidate_deletion_removes_private_outreach_history(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    user, _, candidate, _, _, _, _, _, _, decision = approved_workspace()
    generate_outreach_draft(
        decision=decision,
        user=user,
        gateway=FakeAIGateway(response=draft_output()),
    )

    request_candidate_deletion(candidate=candidate, user=user)
    delete_candidate(candidate=candidate, user=user)

    assert not OutreachDraft.objects.exists()
