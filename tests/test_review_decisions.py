import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import override_settings
from django.urls import reverse

from candidates.models import CandidateSource
from candidates.services import delete_candidate, request_candidate_deletion
from matching.decisions import (
    assess_review_decision_eligibility,
    record_review_decision,
)
from matching.models import ReviewDecision
from outreach.models import OutreachDraft
from tests.test_match_ai_assessment import make_workspace
from tests.test_recruiter_review import create_assessment

pytestmark = pytest.mark.django_db


def decision_url(organization, assessment):
    return reverse(
        "matching:assessment-review-decide",
        args=[organization.slug, assessment.pk],
    )


def detail_url(organization, assessment):
    return reverse(
        "matching:assessment-review-detail",
        args=[organization.slug, assessment.pk],
    )


def queue_url(organization, *, scope=None):
    url = reverse("matching:assessment-review-queue", args=[organization.slug])
    return f"{url}?scope={scope}" if scope else url


def test_decisions_are_actor_attributed_versioned_and_immutable():
    user, _, _, _, profile, _, _, entry = make_workspace()
    assessment = create_assessment(user, profile, entry)

    approved = record_review_decision(
        assessment=assessment,
        user=user,
        decision=ReviewDecision.Decision.APPROVED,
        notes="Evidence checked against the confirmed profile.",
    )
    revisit = record_review_decision(
        assessment=assessment,
        user=user,
        decision=ReviewDecision.Decision.REVISIT,
        notes="Revisit after the recruiter verifies the stated uncertainty.",
    )

    assert approved.version == 1
    assert revisit.version == 2
    assert approved.assessment == assessment
    assert approved.shortlist_entry == entry
    assert approved.created_by == user
    assert approved.created_at is not None
    approved.notes = "Changed"
    with pytest.raises(ValidationError, match="immutable"):
        approved.save()


def test_decision_validation_requires_supported_choice_notes_and_matching_entry():
    user, _, _, _, profile, _, _, entry = make_workspace(username="owner")
    assessment = create_assessment(user, profile, entry)
    other_user, _, _, _, other_profile, _, _, other_entry = make_workspace(
        username="other"
    )
    other_assessment = create_assessment(other_user, other_profile, other_entry)

    with pytest.raises(ValidationError, match="supported recruiter decision"):
        record_review_decision(
            assessment=assessment,
            user=user,
            decision="automatic_reject",
            notes="Invalid choice",
        )
    with pytest.raises(ValidationError, match="recruiter notes"):
        record_review_decision(
            assessment=assessment,
            user=user,
            decision=ReviewDecision.Decision.REJECTED,
            notes="   ",
        )

    mismatched = ReviewDecision(
        shortlist_entry=entry,
        assessment=other_assessment,
        version=1,
        decision=ReviewDecision.Decision.REJECTED,
        notes="Cross-entry decision",
        created_by=user,
    )
    with pytest.raises(ValidationError, match="this shortlist entry"):
        mismatched.full_clean()
    assert ReviewDecision.objects.count() == 0


def test_older_assessment_and_changed_inputs_cannot_receive_current_decision():
    user, _, candidate, _, profile, _, _, entry = make_workspace()
    older = create_assessment(user, profile, entry, score=70)
    latest = create_assessment(user, profile, entry, score=82)

    older_eligibility = assess_review_decision_eligibility(
        assessment=older,
        user=user,
    )
    assert older_eligibility.can_record is False
    assert "latest assessment" in older_eligibility.reason
    with pytest.raises(ValidationError, match="latest assessment"):
        record_review_decision(
            assessment=older,
            user=user,
            decision=ReviewDecision.Decision.APPROVED,
            notes="Attempted against old evidence",
        )

    candidate.location = "Changed after assessment"
    candidate.save(update_fields=("location", "updated_at"))
    latest_eligibility = assess_review_decision_eligibility(
        assessment=latest,
        user=user,
    )
    assert latest_eligibility.can_record is False
    assert "shortlist inputs changed" in latest_eligibility.reason
    with pytest.raises(ValidationError, match="shortlist inputs changed"):
        record_review_decision(
            assessment=latest,
            user=user,
            decision=ReviewDecision.Decision.REJECTED,
            notes="Attempted against stale evidence",
        )
    assert ReviewDecision.objects.count() == 0


def test_recruiter_records_individual_decision_and_queue_updates(client):
    user, organization, _, _, profile, _, _, entry = make_workspace()
    assessment = create_assessment(user, profile, entry)
    client.force_login(user)

    get_response = client.get(decision_url(organization, assessment))
    detail_before = client.get(detail_url(organization, assessment))
    post_response = client.post(
        decision_url(organization, assessment),
        {
            "decision": ReviewDecision.Decision.APPROVED,
            "notes": "The recruiter inspected the supplied evidence.",
        },
        follow=True,
    )
    pending_queue = client.get(queue_url(organization))
    all_queue = client.get(queue_url(organization, scope="all"))
    content = post_response.content.decode()
    before_content = detail_before.content.decode()
    expected_detail_url = detail_url(organization, assessment)

    assert get_response.status_code == 405
    assert detail_before.status_code == 200
    assert "Your decision" in before_content
    assert before_content.count('class="decision-option-card"') == 3
    assert before_content.index('class="decision-options"') < before_content.index(
        'class="field decision-notes-field"'
    )
    assert post_response.status_code == 200
    assert post_response.redirect_chain == [
        (f"{expected_detail_url}?decision=1#decision-saved", 302)
    ]
    assert "Decision version 1 was recorded as approve" in content
    assert "Decision saved" in content
    assert 'id="decision-saved" data-page-focus' in content
    assert "Current decision · v1" in content
    assert "Change decision" in content
    assert "This creates decision v2" in content
    assert "Email was not prepared" in content
    assert "Review source and contact" in content
    assert 'class="review-secondary-detail"' in content
    assert "The recruiter inspected the supplied evidence" in content
    assert user.username in content
    assert "No assessments in this view" in pending_queue.content.decode()
    assert "Decision: Approve" in all_queue.content.decode()
    decision = ReviewDecision.objects.get()
    assert decision.created_by == user
    assert decision.assessment == assessment
    assert not OutreachDraft.objects.exists()


@override_settings(
    AI_GATEWAY_FACTORY="tests.test_outreach_drafts.ConfiguredOutreachGateway"
)
def test_approval_prepares_email_and_opens_focused_composer(client):
    user, organization, candidate, _, profile, _, _, entry = make_workspace()
    assessment = create_assessment(user, profile, entry)
    CandidateSource.objects.create(
        candidate=candidate,
        source_type=CandidateSource.SourceType.MANUAL_ENTRY,
        source_name="Synthetic permitted source",
        lawful_basis=CandidateSource.LawfulBasis.LEGITIMATE_INTERESTS,
        consent_status=CandidateSource.ConsentStatus.NOT_REQUIRED,
        contact_permission=CandidateSource.ContactPermission.PERMITTED,
        recorded_by=user,
    )
    client.force_login(user)

    response = client.post(
        decision_url(organization, assessment),
        {
            "decision": ReviewDecision.Decision.APPROVED,
            "notes": "The recruiter approved this candidate and prepared an email.",
        },
        follow=True,
    )
    draft = OutreachDraft.objects.get()
    draft_url = reverse(
        "outreach:outreach-draft-detail",
        args=[organization.slug, draft.pk],
    )
    content = response.content.decode()

    assert response.redirect_chain == [(f"{draft_url}?prepared=1#email-composer", 302)]
    assert "Candidate approved and email draft version 1 prepared" in content
    assert "Email ready for review" in content
    assert 'id="email-ready" data-page-focus' in content
    assert "Email composer" in content
    assert candidate.email in content
    assert "Contact allowed" in content
    assert "Open in email app" in content
    assert draft.review_decision == ReviewDecision.objects.get()


@pytest.mark.parametrize(
    "decision_value",
    [ReviewDecision.Decision.REJECTED, ReviewDecision.Decision.REVISIT],
)
def test_non_approval_save_focuses_current_state_and_returns_to_queue(
    client,
    decision_value,
):
    user, organization, _, _, profile, _, _, entry = make_workspace()
    assessment = create_assessment(user, profile, entry)
    client.force_login(user)

    response = client.post(
        decision_url(organization, assessment),
        {
            "decision": decision_value,
            "notes": "The recruiter recorded the individual review outcome.",
        },
        follow=True,
    )
    content = response.content.decode()

    assert response.redirect_chain == [
        (f"{detail_url(organization, assessment)}?decision=1#decision-saved", 302)
    ]
    assert "Decision saved" in content
    assert "Back to review queue" in content
    saved_summary = content.split('id="decision-saved"', 1)[1].split("</section>", 1)[0]
    assert "Generate outreach draft" not in saved_summary
    assert "Current decision · v1" in content
    assert "Change decision" in content


def test_decision_on_older_assessment_is_not_carried_to_new_version(client):
    user, organization, _, _, profile, _, _, entry = make_workspace()
    first = create_assessment(user, profile, entry, score=70)
    record_review_decision(
        assessment=first,
        user=user,
        decision=ReviewDecision.Decision.APPROVED,
        notes="Approved against assessment version one.",
    )
    latest = create_assessment(user, profile, entry, score=82)
    client.force_login(user)

    pending_queue = client.get(queue_url(organization))
    content = pending_queue.content.decode()

    assert pending_queue.status_code == 200
    assert f"Assessment v{latest.version}" in content
    assert "Decision pending" in content
    assert "Earlier assessment has a decision" in content
    assert detail_url(organization, latest) in content


def test_invalid_and_cross_organization_decision_routes_save_nothing(client):
    owner, organization, _, _, profile, _, _, entry = make_workspace(username="owner")
    assessment = create_assessment(owner, profile, entry)
    outsider, other_organization, *_ = make_workspace(username="outsider")
    client.force_login(outsider)

    hidden = client.post(
        decision_url(organization, assessment),
        {"decision": "approved", "notes": "Should not save"},
    )
    mismatched = client.post(
        decision_url(other_organization, assessment),
        {"decision": "approved", "notes": "Should not save"},
    )

    assert hidden.status_code == 404
    assert mismatched.status_code == 404
    with pytest.raises(PermissionDenied):
        record_review_decision(
            assessment=assessment,
            user=outsider,
            decision=ReviewDecision.Decision.APPROVED,
            notes="Should not save",
        )
    assert ReviewDecision.objects.count() == 0


def test_candidate_deletion_removes_decisions_with_private_match_history(
    settings,
    tmp_path,
):
    settings.MEDIA_ROOT = tmp_path
    user, _, candidate, _, profile, _, _, entry = make_workspace()
    assessment = create_assessment(user, profile, entry)
    record_review_decision(
        assessment=assessment,
        user=user,
        decision=ReviewDecision.Decision.REJECTED,
        notes="Synthetic deletion test decision.",
    )

    request_candidate_deletion(candidate=candidate, user=user)
    delete_candidate(candidate=candidate, user=user)

    assert ReviewDecision.objects.count() == 0
