import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from candidates.models import CandidateProfile
from matching.ai_assessment import MatchAssessmentOutput, assess_shortlist_entry
from matching.review import build_assessment_review_queue
from tests.test_match_ai_assessment import (
    CV_TEXT,
    RecordingGateway,
    make_workspace,
    output_for_context,
)

pytestmark = pytest.mark.django_db


def queue_url(organization, *, scope=None):
    url = reverse("matching:assessment-review-queue", args=[organization.slug])
    return f"{url}?scope={scope}" if scope else url


def detail_url(organization, assessment):
    return reverse(
        "matching:assessment-review-detail",
        args=[organization.slug, assessment.pk],
    )


def create_assessment(user, profile, entry, *, score=82):
    from matching.ai_assessment import build_assessment_context

    context = build_assessment_context(entry=entry, profile=profile)
    return assess_shortlist_entry(
        entry=entry,
        user=user,
        gateway=RecordingGateway(output_for_context(context, score=score)),
    ).assessment


def routine_output(context) -> MatchAssessmentOutput:
    evidence_id = context.candidate_evidence[0].identifier
    return MatchAssessmentOutput.model_validate(
        {
            "score": 90,
            "summary": "Every requirement has supplied supporting evidence.",
            "requirement_assessments": [
                {
                    "requirement_id": requirement.identifier,
                    "outcome": "match",
                    "candidate_evidence_ids": [evidence_id],
                    "explanation": "The supplied evidence supports this requirement.",
                }
                for requirement in context.requirements
            ],
            "review_recommendation": "The recruiter should inspect the evidence.",
        }
    )


def test_review_queue_has_safe_empty_state_and_navigation(client):
    user, organization, *_ = make_workspace()
    client.force_login(user)

    response = client.get(queue_url(organization))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Assessment review queue" in content
    assert "No assessments are ready for review" in content
    assert "Confirmed candidate profiles can be reused across vacancies" in content
    assert queue_url(organization) in content


def test_queue_consolidates_versions_and_prioritizes_evidence_exceptions(client):
    user, organization, candidate, _, profile, _, _, entry = make_workspace()
    first = create_assessment(user, profile, entry, score=70)
    latest = create_assessment(user, profile, entry, score=82)
    client.force_login(user)

    response = client.get(queue_url(organization))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Latest assessments</span><strong>1" in content
    assert "Assessment v2" in content
    assert "Assessment v1" not in content
    assert "1 gap" in content
    assert "uncertaint" in content
    assert detail_url(organization, latest) in content
    assert detail_url(organization, first) not in content
    assert candidate.email not in content
    assert CV_TEXT not in content


def test_routine_assessment_is_compact_but_remains_inspectable(client):
    user, organization, _, _, profile, _, _, entry = make_workspace()
    CandidateProfile.objects.filter(pk=profile.pk).update(ambiguities=[])
    profile.refresh_from_db()
    from matching.ai_assessment import build_assessment_context

    context = build_assessment_context(entry=entry, profile=profile)
    assessment = assess_shortlist_entry(
        entry=entry,
        user=user,
        gateway=RecordingGateway(routine_output(context)),
    ).assessment
    client.force_login(user)

    focused = client.get(queue_url(organization))
    all_items = client.get(queue_url(organization, scope="all"))

    assert "No assessments in this view" in focused.content.decode()
    assert "No recorded exception" in all_items.content.decode()
    assert detail_url(organization, assessment) in all_items.content.decode()


def test_changed_inputs_are_visible_and_assessment_detail_keeps_history(client):
    user, organization, candidate, _, profile, vacancy, run, entry = make_workspace()
    first = create_assessment(user, profile, entry, score=70)
    latest = create_assessment(user, profile, entry, score=82)
    candidate.location = "Changed after assessment"
    candidate.save(update_fields=("location", "updated_at"))
    client.force_login(user)

    queue_response = client.get(queue_url(organization, scope="changed"))
    detail_response = client.get(detail_url(organization, latest))
    queue_content = queue_response.content.decode()
    detail_content = detail_response.content.decode()

    assert queue_response.status_code == 200
    assert "Inputs changed" in queue_content
    assert detail_response.status_code == 200
    assert "Inspect as historical assessment" in detail_content
    assert (
        "active candidate pool or candidate matching evidence changed" in detail_content
    )
    assert "Matching requirements" in detail_content
    assert "Evidence-backed gaps" in detail_content
    assert "Profile evidence exceptions" in detail_content
    assert f"Version {latest.version}" in detail_content
    assert f"Version {first.version}" in detail_content
    assert (
        reverse(
            "matching:shortlist-detail",
            args=[organization.slug, vacancy.pk, run.pk],
        )
        in detail_content
    )
    assert candidate.email not in detail_content
    assert CV_TEXT not in detail_content


def test_review_routes_and_service_do_not_disclose_another_organization(client):
    owner, organization, _, _, profile, _, _, entry = make_workspace(username="owner")
    assessment = create_assessment(owner, profile, entry)
    outsider, other_organization, *_ = make_workspace(username="outsider")
    client.force_login(outsider)

    queue_response = client.get(queue_url(organization))
    detail_response = client.get(detail_url(organization, assessment))
    mismatched_response = client.get(detail_url(other_organization, assessment))

    assert queue_response.status_code == 404
    assert detail_response.status_code == 404
    assert mismatched_response.status_code == 404
    with pytest.raises(PermissionDenied):
        build_assessment_review_queue(organization=organization, user=outsider)
