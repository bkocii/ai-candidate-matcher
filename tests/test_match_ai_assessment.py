import json
import re
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError

from accounts.models import OrganizationMembership, User
from ai_gateway import (
    AIGatewayMetadata,
    AIGatewayUnavailableError,
)
from ai_gateway.testing import FakeAIGateway
from candidates.models import Candidate, CandidateDocument, CandidateProfile
from candidates.services import delete_candidate
from matching.ai_assessment import (
    MAX_ASSESSMENT_CONTEXT_CHARACTERS,
    MatchAssessmentOutput,
    assess_shortlist_entry,
    build_assessment_context,
    build_match_assessment_prompt,
    validate_assessment_references,
)
from matching.models import MatchAssessment, ShortlistEntry
from matching.scoring import generate_shortlist
from matching.services import assign_candidate_skill, sync_requirement_skills
from matching.staleness import assess_match_run_staleness
from organizations.models import Organization
from vacancies.models import Vacancy, VacancyRequirements
from vacancies.services import confirm_requirements_draft

pytestmark = pytest.mark.django_db

CV_TEXT = """Private Candidate
Email: private@example.test
Python: five years
Built Django and PostgreSQL services for Example Systems.
English C1
Prefers remote work.
Location: Prishtina
"""


def metadata() -> AIGatewayMetadata:
    return AIGatewayMetadata(
        request_id="assessment-request-123",
        model="test-model",
        duration_ms=80,
        retries_used=0,
        token_usage=None,
        estimated_cost_usd=None,
    )


def make_workspace(*, username: str = "recruiter"):
    user = User.objects.create_user(username=username, password="test-password")
    organization = Organization.objects.create(
        name=f"{username.title()} Organization",
        slug=f"{username}-organization",
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Private Candidate",
        email="private@example.test",
        created_by=user,
    )
    document = CandidateDocument.objects.create(
        candidate=candidate,
        document_type=CandidateDocument.DocumentType.CV,
        original_filename="private-cv.pdf",
        file="candidate_documents/private-cv.pdf",
        content_type="application/pdf",
        size_bytes=1_000,
        sha256="a" * 64,
        extraction_status=CandidateDocument.ExtractionStatus.SUCCEEDED,
        extracted_text=CV_TEXT,
        extracted_at=timezone.now(),
        uploaded_by=user,
    )
    profile = CandidateProfile.objects.create(
        candidate=candidate,
        source_document=document,
        version=1,
        status=CandidateProfile.Status.CONFIRMED,
        source_document_sha256=document.sha256,
        source_text_sha256="b" * 64,
        relevant_experience_summary="Backend engineer with five years' experience",
        skills=[
            {
                "name": "Python",
                "evidence": "Python: five years",
                "years_experience": "5.0",
            },
            {
                "name": "Django",
                "evidence": "Built Django and PostgreSQL services",
                "years_experience": None,
            },
        ],
        employment_history=[
            {
                "job_title": "Backend Engineer",
                "employer": "Example Systems",
                "period": "",
                "evidence": (
                    "Built Django and PostgreSQL services for Example Systems."
                ),
            }
        ],
        location="Prishtina",
        work_mode_preference=CandidateProfile.WorkMode.REMOTE,
        languages=[
            {
                "language": "English",
                "proficiency": "C1",
                "evidence": "English C1",
            }
        ],
        employment_type_preferences=[],
        fact_evidence={
            "relevant_experience_summary": "Python: five years",
            "location": "Location: Prishtina",
            "work_mode_preference": "Prefers remote work.",
            "employment_type_preferences": "",
            "availability": "",
        },
        ambiguities=["No certification information is stated"],
        confirmed_by=user,
        confirmed_at=timezone.now(),
        created_by=user,
    )
    vacancy = Vacancy.objects.create(
        organization=organization,
        title="Private Vacancy Title",
        description="Python and Django role in Prishtina.",
        created_by=user,
    )
    requirements = VacancyRequirements.objects.create(
        vacancy=vacancy,
        version=1,
        source_description=vacancy.description,
        summary="Backend engineer for API services",
        must_have_skills=["Python"],
        nice_to_have_skills=["Django"],
        minimum_years_experience=Decimal("4.0"),
        location_requirement="Prishtina",
        work_mode=VacancyRequirements.WorkMode.REMOTE,
        language_requirements=["English C1"],
        created_by=user,
    )
    sync_requirement_skills(requirements=requirements, user=user)
    confirm_requirements_draft(requirements=requirements, user=user)
    assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="Python",
        evidence="Python: five years",
        years_experience=Decimal("5.0"),
        source_document=document,
    )
    assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="Django",
        evidence="Built Django and PostgreSQL services",
        source_document=document,
    )
    run = generate_shortlist(requirements=requirements, user=user)
    entry = run.entries.get(candidate=candidate)
    return user, organization, candidate, document, profile, vacancy, run, entry


def output_for_context(context, *, score=82) -> MatchAssessmentOutput:
    evidence_ids = [item.identifier for item in context.candidate_evidence]
    values = []
    for position, requirement in enumerate(context.requirements):
        if position == 0:
            outcome = "match"
            selected_evidence = evidence_ids[:1]
        elif position == 1:
            outcome = "gap"
            selected_evidence = evidence_ids[1:2] or evidence_ids[:1]
        else:
            outcome = "uncertain"
            selected_evidence = []
        values.append(
            {
                "requirement_id": requirement.identifier,
                "outcome": outcome,
                "candidate_evidence_ids": selected_evidence,
                "explanation": f"Evidence-based {outcome} explanation.",
            }
        )
    return MatchAssessmentOutput.model_validate(
        {
            "score": score,
            "summary": "The supplied evidence shows relevant backend experience.",
            "requirement_assessments": values,
            "review_recommendation": (
                "The recruiter should verify the explicitly uncertain requirements."
            ),
        }
    )


class RecordingGateway(FakeAIGateway):
    def __init__(self, output=None, error=None):
        super().__init__(response=output, error=error, metadata=metadata())


class ConfiguredAssessmentGateway(FakeAIGateway):
    def __init__(self):
        super().__init__(responder=self._respond, metadata=metadata())

    def _respond(self, prompt, response_type):
        match = re.search(
            r"<minimized_match_context_json>\n(.*)\n</minimized_match_context_json>",
            prompt,
            flags=re.S,
        )
        payload = json.loads(match.group(1))
        requirements = payload["vacancy_context"]["requirements"]
        evidence = payload["candidate_context"]["evidence"]
        evidence_ids = [item["id"] for item in evidence]
        output = response_type.model_validate(
            {
                "score": 82,
                "summary": "Relevant evidence is recorded for recruiter review.",
                "requirement_assessments": [
                    {
                        "requirement_id": item["id"],
                        "outcome": "match" if evidence_ids else "uncertain",
                        "candidate_evidence_ids": evidence_ids[:1],
                        "explanation": "The supplied evidence supports this result.",
                    }
                    for item in requirements
                ],
                "review_recommendation": (
                    "The recruiter should verify any remaining uncertainty."
                ),
            }
        )
        return output


def assessment_url(organization, vacancy, run, entry):
    return reverse(
        "matching:shortlist-assessment-generate",
        args=[organization.slug, vacancy.pk, run.pk, entry.pk],
    )


def test_schema_rejects_extra_fields_duplicate_requirements_and_ungrounded_gap():
    base = {
        "score": 50,
        "summary": "Summary",
        "requirement_assessments": [
            {
                "requirement_id": "requirement:1",
                "outcome": "uncertain",
                "candidate_evidence_ids": [],
                "explanation": "Unknown",
            }
        ],
        "review_recommendation": "Recruiter should verify the source.",
    }
    with pytest.raises(PydanticValidationError):
        MatchAssessmentOutput.model_validate({**base, "candidate_name": "Private"})

    duplicate = {**base, "requirement_assessments": base["requirement_assessments"] * 2}
    with pytest.raises(PydanticValidationError, match="exactly once"):
        MatchAssessmentOutput.model_validate(duplicate)

    missing_evidence = json.loads(json.dumps(base))
    missing_evidence["requirement_assessments"][0]["outcome"] = "gap"
    with pytest.raises(PydanticValidationError, match="requires candidate evidence"):
        MatchAssessmentOutput.model_validate(missing_evidence)


def test_prompt_contains_only_minimized_versioned_evidence_context():
    _, _, candidate, _, profile, vacancy, _, entry = make_workspace()
    context = build_assessment_context(entry=entry, profile=profile)
    prompt = build_match_assessment_prompt(context)

    assert vacancy.title not in prompt
    assert candidate.full_name not in prompt
    assert candidate.email not in prompt
    assert CV_TEXT not in prompt
    assert "Python: five years" in prompt
    assert f'"candidate_profile_version": {profile.version}' in prompt
    assert "not recommend hiring" in prompt


def test_successful_assessment_is_versioned_resolved_and_immutable():
    user, _, _, _, profile, _, _, entry = make_workspace()
    context = build_assessment_context(entry=entry, profile=profile)
    gateway = RecordingGateway(output_for_context(context))

    first = assess_shortlist_entry(entry=entry, user=user, gateway=gateway)
    second = assess_shortlist_entry(entry=entry, user=user, gateway=gateway)

    assessment = first.assessment
    assert assessment.version == 1
    assert second.assessment.version == 2
    assert assessment.score == 82
    assert assessment.traffic_light == MatchAssessment.TrafficLight.GREEN
    assert assessment.requirements == entry.match_run.requirements
    assert assessment.candidate_profile == profile
    assert assessment.matching_requirements[0]["requirement_evidence"] == "Python"
    assert (
        assessment.matching_requirements[0]["candidate_evidence"][0]["evidence"]
        == "Python: five years"
    )
    assert first.metadata.request_id == "assessment-request-123"
    assert not hasattr(assessment, "request_id")
    assessment.summary = "Changed"
    with pytest.raises(ValidationError, match="immutable"):
        assessment.save()


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0, "red"), (49, "red"), (50, "amber"), (74, "amber"), (75, "green")],
)
def test_traffic_light_is_derived_from_score(score, expected):
    assert MatchAssessment.traffic_light_for_score(score) == expected


def test_assessment_model_requires_derived_light_and_at_least_one_result():
    user, _, _, _, profile, _, _, entry = make_workspace()
    values = {
        "shortlist_entry": entry,
        "requirements": entry.match_run.requirements,
        "candidate_profile": profile,
        "version": 1,
        "score": 80,
        "summary": "Summary",
        "review_recommendation": "Recruiter review",
        "created_by": user,
    }

    wrong_light = MatchAssessment(
        **values,
        traffic_light="red",
        matching_requirements=[{"requirement_id": "requirement:1"}],
    )
    with pytest.raises(ValidationError, match="derived from the score"):
        wrong_light.full_clean()

    empty = MatchAssessment(**values, traffic_light="green")
    with pytest.raises(ValidationError, match="at least one requirement result"):
        empty.full_clean()


def test_unknown_or_incomplete_evidence_references_save_nothing():
    user, _, _, _, profile, _, _, entry = make_workspace()
    context = build_assessment_context(entry=entry, profile=profile)
    missing = output_for_context(context).model_copy(
        update={
            "requirement_assessments": output_for_context(
                context
            ).requirement_assessments[:-1]
        }
    )
    with pytest.raises(ValidationError, match="every confirmed requirement"):
        validate_assessment_references(output=missing, context=context)

    values = output_for_context(context).model_dump()
    values["requirement_assessments"][0]["candidate_evidence_ids"] = ["outside:1"]
    unknown = MatchAssessmentOutput.model_validate(values)
    with pytest.raises(ValidationError, match="outside the confirmed profile"):
        assess_shortlist_entry(
            entry=entry,
            user=user,
            gateway=RecordingGateway(unknown),
        )
    assert MatchAssessment.objects.count() == 0


def test_gateway_failure_and_decision_language_save_nothing():
    user, _, _, _, profile, _, _, entry = make_workspace()
    with pytest.raises(AIGatewayUnavailableError):
        assess_shortlist_entry(
            entry=entry,
            user=user,
            gateway=RecordingGateway(error=AIGatewayUnavailableError()),
        )

    context = build_assessment_context(entry=entry, profile=profile)
    unsafe = output_for_context(context).model_copy(
        update={"review_recommendation": "We recommend hiring the candidate."}
    )
    with pytest.raises(ValidationError, match="recruitment decision"):
        assess_shortlist_entry(
            entry=entry,
            user=user,
            gateway=RecordingGateway(unsafe),
        )
    assert MatchAssessment.objects.count() == 0


def test_missing_profile_and_stale_run_are_rejected_before_gateway():
    user, _, candidate, _, profile, _, run, entry = make_workspace()
    profile.delete()
    gateway = RecordingGateway()
    with pytest.raises(ValidationError, match="Confirm a candidate profile"):
        assess_shortlist_entry(entry=entry, user=user, gateway=gateway)
    assert gateway.calls == []

    stale_user, _, candidate, _, profile, _, run, entry = make_workspace(
        username="stale"
    )
    candidate.location = "Changed matching input"
    candidate.save(update_fields=("location", "updated_at"))
    assert assess_match_run_staleness(run=run, user=stale_user).is_stale is True
    with pytest.raises(ValidationError, match="shortlist is stale"):
        assess_shortlist_entry(entry=entry, user=stale_user, gateway=gateway)
    assert gateway.calls == []


def test_concurrent_profile_confirmation_discards_completed_output():
    user, _, candidate, document, profile, _, _, entry = make_workspace()
    context = build_assessment_context(entry=entry, profile=profile)

    class ConfirmingGateway(RecordingGateway):
        def request_structured(self, *, prompt, response_type):
            CandidateProfile.objects.create(
                candidate=candidate,
                source_document=document,
                version=2,
                status=CandidateProfile.Status.CONFIRMED,
                source_document_sha256=document.sha256,
                source_text_sha256="c" * 64,
                ambiguities=["No facts"],
                confirmed_by=user,
                confirmed_at=timezone.now(),
                created_by=user,
            )
            return super().request_structured(
                prompt=prompt,
                response_type=response_type,
            )

    with pytest.raises(ValidationError, match="profile changed"):
        assess_shortlist_entry(
            entry=entry,
            user=user,
            gateway=ConfirmingGateway(output_for_context(context)),
        )
    assert MatchAssessment.objects.count() == 0


def test_oversized_context_is_rejected_before_gateway():
    user, _, _, _, profile, _, _, entry = make_workspace()
    profile.ambiguities = ["x" * MAX_ASSESSMENT_CONTEXT_CHARACTERS]
    CandidateProfile.objects.filter(pk=profile.pk).update(
        ambiguities=profile.ambiguities
    )
    gateway = RecordingGateway()

    with pytest.raises(ValidationError, match="context is too large"):
        assess_shortlist_entry(entry=entry, user=user, gateway=gateway)
    assert gateway.calls == []


def test_tenant_boundary_and_model_source_consistency():
    owner, organization, _, _, profile, _, _, entry = make_workspace(username="owner")
    outsider, _, _, _, outsider_profile, _, _, _ = make_workspace(username="outsider")
    context = build_assessment_context(entry=entry, profile=profile)
    with pytest.raises(PermissionDenied):
        assess_shortlist_entry(
            entry=entry,
            user=outsider,
            gateway=RecordingGateway(output_for_context(context)),
        )

    assessment = MatchAssessment(
        shortlist_entry=entry,
        requirements=entry.match_run.requirements,
        candidate_profile=outsider_profile,
        version=1,
        score=80,
        traffic_light="green",
        summary="Summary",
        review_recommendation="Recruiter review",
    )
    with pytest.raises(ValidationError, match="shortlisted candidate"):
        assessment.full_clean()
    assert entry.organization == organization


@override_settings(
    AI_GATEWAY_FACTORY="tests.test_match_ai_assessment.ConfiguredAssessmentGateway"
)
def test_recruiter_generates_and_reviews_assessment_on_shortlist(client):
    user, organization, candidate, _, _, vacancy, run, entry = make_workspace()
    url = assessment_url(organization, vacancy, run, entry)
    client.force_login(user)

    get_response = client.get(url)
    response = client.post(url, follow=True)
    content = response.content.decode()

    assert get_response.status_code == 405
    assert response.status_code == 200
    assert "AI assessment version 1" in content
    assert "Evidence-based match assessment" in content
    assert "82/100" in content
    assert "Matching requirements" in content
    assert "Candidate evidence: Python: five years" in content
    assert candidate.email not in content
    assert CV_TEXT not in content
    assert MatchAssessment.objects.count() == 1


def test_assessment_route_does_not_disclose_cross_organization_data(client):
    owner, organization, _, _, _, vacancy, run, entry = make_workspace(
        username="visible"
    )
    outsider, other, *_ = make_workspace(username="hidden")
    client.force_login(outsider)

    response = client.post(assessment_url(organization, vacancy, run, entry))
    mismatched = client.post(assessment_url(other, vacancy, run, entry))

    assert response.status_code == 404
    assert mismatched.status_code == 404


def test_candidate_deletion_removes_assessment_with_shortlist_entry(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    user, _, candidate, _, profile, _, _, entry = make_workspace()
    context = build_assessment_context(entry=entry, profile=profile)
    assess_shortlist_entry(
        entry=entry,
        user=user,
        gateway=RecordingGateway(output_for_context(context)),
    )

    delete_candidate(candidate=candidate, user=user)

    assert not ShortlistEntry.objects.filter(pk=entry.pk).exists()
    assert MatchAssessment.objects.count() == 0
