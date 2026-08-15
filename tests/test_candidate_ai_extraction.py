import hashlib
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
from audit.models import AIUsageEvent
from candidates.ai_extraction import (
    MAX_PROFILE_SOURCE_CHARACTERS,
    CandidateProfileExtraction,
    build_candidate_profile_prompt,
    confirm_candidate_profile,
    extract_candidate_profile,
    redact_candidate_contact_data,
    validate_profile_evidence,
)
from candidates.models import Candidate, CandidateDocument, CandidateProfile
from candidates.services import delete_candidate, request_candidate_deletion
from matching.evaluation import RuleOutcome, evaluate_candidate_constraints
from matching.models import CandidateSkill, HardConstraintRule
from matching.services import (
    assign_candidate_skill,
    create_hard_constraint_rule,
    sync_requirement_skills,
)
from matching.staleness import candidate_input_signature
from organizations.models import Organization
from vacancies.models import Vacancy, VacancyRequirements
from vacancies.services import confirm_requirements_draft

pytestmark = pytest.mark.django_db

CV_TEXT = """Arta Krasniqi
Email: arta@example.test
Phone: +383 44 111 222
https://example.test/arta
Date of birth: 1990-01-01
Senior Python Engineer at Northstar, 2020-2025.
Built Django APIs and PostgreSQL data services.
Python: 5 years
English C1
BSc Computer Science, University of Prishtina
Prefers remote full-time work. Available with one month notice.
Location: Prishtina
"""

ARBEN_CV_TEXT = "\n".join(
    (
        "Arben Testi",
        "arben.testi@example.test | +383 44 111 222 | Prishtina",
        "SYNTHETIC TEST FIXTURE - This document does not describe a real person.",
        "Profile",
        (
            "Senior backend developer with six years of invented experience "
            "building secure Python and Django applications, REST APIs, and "
            "automated testing systems."
        ),
        "Experience",
        "Senior Python Developer - Sample Cloud (2021-2026)",
        (
            "Designed Django services, PostgreSQL data models, REST APIs, and "
            "pytest suites."
        ),
        (
            "Reviewed code, improved CI pipelines, and supported containerized "
            "deployments."
        ),
        "Python Developer - Fictional Tech (2019-2021)",
        (
            "Maintained Python applications, implemented validated CSV imports, "
            "and documented operational procedures."
        ),
        "Skills",
        "Python, Django, Django REST Framework, PostgreSQL, pytest, Git, Docker, CI/CD",
        "Languages and education",
        "English (professional), Albanian (native)",
        "Synthetic BSc in Computer Science - Example University",
        "Generated only for AI Candidate Matcher manual testing.",
        "",
    )
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
        full_name="Arta Krasniqi",
        email="arta@example.test",
        phone="+383 44 111 222",
        created_by=user,
    )
    document = CandidateDocument.objects.create(
        candidate=candidate,
        document_type=CandidateDocument.DocumentType.CV,
        original_filename="arta-cv.pdf",
        file="candidate_documents/arta-cv.pdf",
        content_type="application/pdf",
        size_bytes=1_024,
        sha256="a" * 64,
        extraction_status=CandidateDocument.ExtractionStatus.SUCCEEDED,
        extracted_text=CV_TEXT,
        extracted_at=timezone.now(),
        uploaded_by=user,
    )
    return user, organization, candidate, document


def extracted_output(**overrides) -> CandidateProfileExtraction:
    values = {
        "relevant_experience_summary": "Senior engineer with backend experience.",
        "relevant_experience_summary_evidence": (
            "Senior Python Engineer at Northstar, 2020-2025."
        ),
        "skills": [
            {
                "name": "Python",
                "evidence": "Python: 5 years",
                "years_experience": "5.0",
            },
            {
                "name": "Django",
                "evidence": "Built Django APIs and PostgreSQL data services.",
                "years_experience": None,
            },
        ],
        "employment_history": [
            {
                "job_title": "Senior Python Engineer",
                "employer": "Northstar",
                "period": "2020-2025",
                "evidence": ("Senior Python Engineer at Northstar, 2020-2025."),
            }
        ],
        "location": "Prishtina",
        "work_mode_preference": "remote",
        "languages": [
            {
                "language": "English",
                "proficiency": "C1",
                "evidence": "English C1",
            }
        ],
        "education": [
            {
                "qualification": "BSc Computer Science",
                "institution": "University of Prishtina",
                "evidence": "BSc Computer Science, University of Prishtina",
            }
        ],
        "certifications": [],
        "employment_type_preferences": ["full_time"],
        "availability": "One month notice",
        "location_evidence": "Location: Prishtina",
        "work_mode_preference_evidence": "Prefers remote full-time work.",
        "employment_type_preferences_evidence": ("Prefers remote full-time work."),
        "availability_evidence": "Available with one month notice.",
        "ambiguities": ["No certification information is stated"],
        "excluded_sensitive_content_detected": False,
    }
    values.update(overrides)
    return CandidateProfileExtraction.model_validate(values)


def metadata() -> AIGatewayMetadata:
    return AIGatewayMetadata(
        request_id="profile-request-123",
        model="test-model",
        duration_ms=75.0,
        retries_used=0,
        token_usage=None,
        estimated_cost_usd=None,
    )


class RecordingGateway(FakeAIGateway):
    def __init__(self, *, output=None, error: Exception | None = None) -> None:
        super().__init__(
            response=output or extracted_output(),
            error=error,
            metadata=metadata(),
        )


class SuccessfulGateway(RecordingGateway):
    pass


class FailingGateway(RecordingGateway):
    def __init__(self) -> None:
        super().__init__(error=AIGatewayUnavailableError())


class SequenceGateway(FakeAIGateway):
    def __init__(self, *outputs: CandidateProfileExtraction) -> None:
        self.outputs = outputs
        super().__init__(responder=self._next_output, metadata=metadata())

    def _next_output(self, _prompt, _response_type):
        index = len(self.calls) - 1
        if index >= len(self.outputs):
            raise AssertionError("The service made an unexpected extra AI request.")
        return self.outputs[index]


class RepairingGateway(SequenceGateway):
    def __init__(self) -> None:
        paraphrased = extracted_output(
            relevant_experience_summary_evidence=(
                "Senior Python Engineer at Northstar from 2020 to 2025."
            )
        )
        super().__init__(paraphrased, extracted_output())


def extraction_url(organization, candidate, document) -> str:
    return reverse(
        "candidates:candidate-profile-extract",
        args=[organization.slug, candidate.pk, document.pk],
    )


def profile_url(organization, candidate, profile) -> str:
    return reverse(
        "candidates:candidate-profile-detail",
        args=[organization.slug, candidate.pk, profile.pk],
    )


def confirmation_url(organization, candidate, profile) -> str:
    return reverse(
        "candidates:candidate-profile-confirm",
        args=[organization.slug, candidate.pk, profile.pk],
    )


def test_profile_schema_rejects_duplicate_skills_and_extra_fields() -> None:
    with pytest.raises(PydanticValidationError):
        extracted_output(
            skills=[
                {"name": "Python", "evidence": "Python: 5 years"},
                {"name": "python", "evidence": "Python: 5 years"},
            ]
        )

    payload = extracted_output().model_dump()
    payload["candidate_name"] = "Must not be accepted"
    with pytest.raises(PydanticValidationError):
        CandidateProfileExtraction.model_validate(payload)


def test_profile_schema_requires_supported_fact_or_ambiguity() -> None:
    with pytest.raises(PydanticValidationError, match="supported fact"):
        CandidateProfileExtraction()


def test_contact_redaction_removes_known_and_generic_contact_data() -> None:
    _, _, candidate, _ = make_workspace()

    redacted = redact_candidate_contact_data(candidate=candidate, text=CV_TEXT)

    assert "Arta Krasniqi" not in redacted
    assert "arta@example.test" not in redacted
    assert "+383 44 111 222" not in redacted
    assert "https://example.test/arta" not in redacted
    assert "1990-01-01" not in redacted
    assert "Python: 5 years" in redacted
    assert "2020-2025" in redacted


def test_untraceable_evidence_is_rejected() -> None:
    output = extracted_output(
        skills=[{"name": "Go", "evidence": "Built production Go services"}]
    )

    with pytest.raises(ValidationError, match="not present in the source CV"):
        validate_profile_evidence(output=output, sanitized_source=CV_TEXT)

    punctuation_only = extracted_output(
        relevant_experience_summary_evidence="...",
    )
    with pytest.raises(ValidationError, match="not present in the source CV"):
        validate_profile_evidence(
            output=punctuation_only,
            sanitized_source=CV_TEXT,
        )


def test_evidence_matching_accepts_harmless_document_punctuation_changes() -> None:
    source = "• Senior Python Developer - Sample Cloud (2021-2026)\nUsed C++."
    output = extracted_output(
        relevant_experience_summary="",
        relevant_experience_summary_evidence="",
        skills=[
            {
                "name": "C++",
                "evidence": "“Used C++.”",
            }
        ],
        employment_history=[
            {
                "job_title": "Senior Python Developer",
                "employer": "Sample Cloud",
                "period": "2021-2026",
                "evidence": "Senior Python Developer — Sample Cloud (2021–2026)",
            }
        ],
        location="",
        location_evidence="",
        work_mode_preference="unknown",
        work_mode_preference_evidence="",
        languages=[],
        education=[],
        employment_type_preferences=[],
        employment_type_preferences_evidence="",
        availability="",
        availability_evidence="",
    )

    validate_profile_evidence(output=output, sanitized_source=source)


def test_fact_not_supported_by_its_real_source_excerpt_is_rejected() -> None:
    output = extracted_output(skills=[{"name": "Java", "evidence": "Python: 5 years"}])

    with pytest.raises(ValidationError, match="skill.*not supported"):
        validate_profile_evidence(output=output, sanitized_source=CV_TEXT)


def test_fact_grounding_preserves_meaningful_skill_punctuation() -> None:
    output = extracted_output(
        skills=[{"name": "C++", "evidence": "Used C# in production"}]
    )

    with pytest.raises(ValidationError, match="skill.*not supported"):
        validate_profile_evidence(
            output=output,
            sanitized_source=CV_TEXT + "\nUsed C# in production",
        )


def test_prompt_extracts_explicit_skills_from_the_complete_cv() -> None:
    output = CandidateProfileExtraction.model_validate(
        {
            "skills": [
                {
                    "name": "Automated testing",
                    "evidence": (
                        "building secure Python and Django applications, REST "
                        "APIs, and automated testing systems."
                    ),
                },
                {
                    "name": "pytest",
                    "evidence": (
                        "Designed Django services, PostgreSQL data models, REST "
                        "APIs, and pytest suites."
                    ),
                },
            ]
        }
    )
    prompt = build_candidate_profile_prompt(ARBEN_CV_TEXT)
    normalized_prompt = " ".join(prompt.split())

    validate_profile_evidence(output=output, sanitized_source=ARBEN_CV_TEXT)

    assert "Inspect the entire source" in normalized_prompt
    assert "do not limit skill extraction" in normalized_prompt
    assert 'both "pytest" and "automated testing"' in normalized_prompt
    assert "Do not infer" in normalized_prompt
    assert "automated testing systems" in prompt


def test_narrative_skill_is_published_without_inferring_it_from_pytest() -> None:
    user, _, candidate, document = make_workspace()
    candidate.full_name = "Arben Testi"
    candidate.email = "arben.testi@example.test"
    candidate.phone = "+383 44 111 222"
    candidate.save(update_fields=("full_name", "email", "phone"))
    document.extracted_text = ARBEN_CV_TEXT
    document.save(update_fields=("extracted_text",))
    explicit_output = CandidateProfileExtraction.model_validate(
        {
            "skills": [
                {
                    "name": "Automated testing",
                    "evidence": (
                        "building secure Python and Django applications, REST "
                        "APIs, and automated testing systems."
                    ),
                },
                {
                    "name": "pytest",
                    "evidence": (
                        "Designed Django services, PostgreSQL data models, REST "
                        "APIs, and pytest suites."
                    ),
                },
            ]
        }
    )

    gateway = RecordingGateway(output=explicit_output)
    profile = extract_candidate_profile(
        document=document,
        user=user,
        gateway=gateway,
    ).profile
    confirm_candidate_profile(profile=profile, user=user)

    assert {skill["name"] for skill in profile.skills} == {
        "Automated testing",
        "pytest",
    }
    assert set(
        CandidateSkill.objects.filter(candidate=candidate).values_list(
            "skill__name",
            flat=True,
        )
    ) == {"Automated testing", "pytest"}
    assert candidate.full_name not in gateway.calls[0].prompt
    assert candidate.email not in gateway.calls[0].prompt
    assert candidate.phone not in gateway.calls[0].prompt

    inferred_only = CandidateProfileExtraction.model_validate(
        {
            "skills": [
                {
                    "name": "Automated testing",
                    "evidence": "Used pytest suites.",
                }
            ]
        }
    )
    with pytest.raises(ValidationError, match="skill.*not supported"):
        validate_profile_evidence(
            output=inferred_only,
            sanitized_source="Used pytest suites.",
        )


def arben_output(
    *,
    summary_evidence: str,
    skill_evidence: str,
) -> CandidateProfileExtraction:
    return CandidateProfileExtraction.model_validate(
        {
            "relevant_experience_summary": (
                "Senior backend developer with Python and Django experience."
            ),
            "relevant_experience_summary_evidence": summary_evidence,
            "skills": [
                {
                    "name": "Docker",
                    "evidence": skill_evidence,
                    "years_experience": None,
                }
            ],
            "ambiguities": ["No availability information is stated"],
        }
    )


def test_service_repairs_paraphrased_and_misaligned_evidence_once() -> None:
    user, organization, candidate, document = make_workspace()
    candidate.full_name = "Arben Testi"
    candidate.email = "arben.testi@example.test"
    candidate.phone = "+383 44 111 222"
    candidate.save(update_fields=("full_name", "email", "phone"))
    document.extracted_text = ARBEN_CV_TEXT
    document.save(update_fields=("extracted_text",))
    invalid = arben_output(
        summary_evidence=(
            "Senior backend developer with six years of experience building "
            "secure Python and Django applications, REST APIs, and automated "
            "testing systems."
        ),
        skill_evidence="supported containerized deployments.",
    )
    repaired = arben_output(
        summary_evidence=(
            "Senior backend developer with six years of invented experience "
            "building secure Python and Django applications, REST APIs, and "
            "automated testing systems."
        ),
        skill_evidence=(
            "Python, Django, Django REST Framework, PostgreSQL, pytest, Git, "
            "Docker, CI/CD"
        ),
    )
    gateway = SequenceGateway(invalid, repaired)

    result = extract_candidate_profile(
        document=document,
        user=user,
        gateway=gateway,
    )

    assert result.evidence_repair_used is True
    assert result.profile.skills[0]["evidence"] == repaired.skills[0].evidence
    assert len(gateway.calls) == 2
    repair_prompt = gateway.calls[1].prompt
    assert "only automatic evidence-correction attempt" in repair_prompt
    assert "relevant-experience summary" in repair_prompt
    assert "skill item 1" in repair_prompt
    assert "six years of experience building secure Python" not in repair_prompt
    assert candidate.full_name not in repair_prompt
    assert candidate.email not in repair_prompt
    assert candidate.phone not in repair_prompt
    events = list(AIUsageEvent.objects.filter(organization=organization).order_by("id"))
    assert [event.status for event in events] == [
        AIUsageEvent.Status.FAILED,
        AIUsageEvent.Status.SUCCEEDED,
    ]
    assert events[0].failure_stage == AIUsageEvent.FailureStage.APPLICATION
    assert events[1].result_id == result.profile.pk


def test_service_stops_after_one_failed_evidence_repair() -> None:
    user, organization, _, document = make_workspace()
    invalid = extracted_output(
        skills=[{"name": "Go", "evidence": "Built production Go services"}]
    )
    gateway = SequenceGateway(invalid, invalid)

    with pytest.raises(
        ValidationError,
        match=r"automatic correction attempt.*skill item 1",
    ) as error:
        extract_candidate_profile(
            document=document,
            user=user,
            gateway=gateway,
        )

    assert "Built production Go services" not in error.value.messages[0]
    assert "Go" not in error.value.messages[0]
    assert len(gateway.calls) == 2
    assert not CandidateProfile.objects.exists()
    events = list(AIUsageEvent.objects.filter(organization=organization).order_by("id"))
    assert len(events) == 2
    assert all(event.status == AIUsageEvent.Status.FAILED for event in events)
    assert all(event.failure_code == "ai_application_validation" for event in events)


def test_service_creates_versioned_profile_draft_without_matching_changes() -> None:
    user, _, candidate, document = make_workspace()
    gateway = RecordingGateway()

    first = extract_candidate_profile(
        document=document,
        user=user,
        gateway=gateway,
    )
    second = extract_candidate_profile(
        document=document,
        user=user,
        gateway=gateway,
    )

    assert first.profile.version == 1
    assert second.profile.version == 2
    assert first.profile.status == CandidateProfile.Status.DRAFT
    assert first.profile.source_document == document
    assert first.profile.source_document_sha256 == document.sha256
    assert (
        first.profile.source_text_sha256
        == hashlib.sha256(document.extracted_text.encode()).hexdigest()
    )
    assert first.profile.skills[0]["name"] == "Python"
    assert first.profile.excluded_sensitive_content_detected is True
    assert "Protected or sensitive" in first.profile.ambiguities[-1]
    assert first.metadata.request_id == "profile-request-123"
    assert first.evidence_repair_used is False
    assert CandidateSkill.objects.filter(candidate=candidate).count() == 0
    prompt, response_type = gateway.calls[0]
    assert response_type is CandidateProfileExtraction
    assert candidate.full_name not in prompt
    assert candidate.email not in prompt
    assert candidate.phone not in prompt
    assert "1990-01-01" not in prompt
    assert "Python: 5 years" in prompt


def test_gateway_failure_or_changed_document_saves_no_profile() -> None:
    user, _, _, document = make_workspace()

    with pytest.raises(AIGatewayUnavailableError):
        extract_candidate_profile(
            document=document,
            user=user,
            gateway=RecordingGateway(error=AIGatewayUnavailableError()),
        )

    class MutatingGateway(RecordingGateway):
        def request_structured(self, *, prompt, response_type):
            CandidateDocument.objects.filter(pk=document.pk).update(
                extracted_text=document.extracted_text + "\nConcurrent edit"
            )
            return super().request_structured(
                prompt=prompt,
                response_type=response_type,
            )

    with pytest.raises(ValidationError, match="changed while extraction was running"):
        extract_candidate_profile(
            document=document,
            user=user,
            gateway=MutatingGateway(),
        )

    assert CandidateProfile.objects.count() == 0


def test_invalid_document_and_deletion_states_are_rejected_before_ai_call() -> None:
    user, _, candidate, document = make_workspace()
    gateway = RecordingGateway()
    document.document_type = CandidateDocument.DocumentType.COVER_LETTER
    document.save(update_fields=("document_type",))

    with pytest.raises(ValidationError, match="only from a CV"):
        extract_candidate_profile(
            document=document,
            user=user,
            gateway=gateway,
        )

    document.document_type = CandidateDocument.DocumentType.CV
    document.save(update_fields=("document_type",))
    candidate.status = Candidate.Status.DELETION_REQUESTED
    candidate.deletion_requested_at = timezone.now()
    candidate.status_before_deletion_request = Candidate.Status.ACTIVE
    candidate.save(
        update_fields=(
            "status",
            "deletion_requested_at",
            "status_before_deletion_request",
        )
    )
    with pytest.raises(ValidationError, match="unavailable during deletion"):
        extract_candidate_profile(
            document=document,
            user=user,
            gateway=gateway,
        )

    assert gateway.calls == []


def test_oversized_redacted_text_is_rejected_before_ai_call() -> None:
    user, _, _, document = make_workspace()
    document.extracted_text = "x" * (MAX_PROFILE_SOURCE_CHARACTERS + 1)
    document.save(update_fields=("extracted_text",))
    gateway = RecordingGateway()

    with pytest.raises(ValidationError, match="too long for profile extraction"):
        extract_candidate_profile(
            document=document,
            user=user,
            gateway=gateway,
        )

    assert gateway.calls == []


def test_cross_organization_user_is_rejected_before_ai_call() -> None:
    _, _, _, document = make_workspace(username="owner")
    outsider = User.objects.create_user(username="outsider")
    gateway = RecordingGateway()

    with pytest.raises(PermissionDenied):
        extract_candidate_profile(
            document=document,
            user=outsider,
            gateway=gateway,
        )

    assert gateway.calls == []


def test_confirmation_publishes_grounded_skills_and_preserves_manual_skill() -> None:
    user, _, candidate, document = make_workspace()
    manual, _ = assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="Django",
        evidence="Recruiter-verified Django portfolio",
    )
    document_based_manual, _ = assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="PostgreSQL",
        evidence="Recruiter verified the PostgreSQL CV evidence",
        source_document=document,
    )
    profile = extract_candidate_profile(
        document=document,
        user=user,
        gateway=RecordingGateway(),
    ).profile

    confirmed = confirm_candidate_profile(profile=profile, user=user)

    manual.refresh_from_db()
    python = CandidateSkill.objects.get(candidate=candidate, skill__name="Python")
    assert confirmed.status == CandidateProfile.Status.CONFIRMED
    assert confirmed.confirmed_by == user
    assert confirmed.confirmed_at is not None
    assert python.evidence == "Python: 5 years"
    assert python.years_experience == Decimal("5.0")
    assert python.source_document == document
    assert python.source_profile == profile
    assert manual.evidence == "Recruiter-verified Django portfolio"
    assert manual.source_document is None
    document_based_manual.refresh_from_db()
    assert document_based_manual.evidence == (
        "Recruiter verified the PostgreSQL CV evidence"
    )
    assert document_based_manual.source_profile is None


def test_confirmed_profile_supplies_inspectable_deterministic_facts() -> None:
    user, organization, candidate, document = make_workspace()
    profile = extract_candidate_profile(
        document=document,
        user=user,
        gateway=RecordingGateway(),
    ).profile
    confirm_candidate_profile(profile=profile, user=user)
    vacancy = Vacancy.objects.create(
        organization=organization,
        title="Remote Python role",
        description="Python, remote, English C1, and Prishtina are required.",
        created_by=user,
    )
    requirements = VacancyRequirements.objects.create(
        vacancy=vacancy,
        source_description=vacancy.description,
        must_have_skills=["Python"],
        created_by=user,
    )
    sync_requirement_skills(requirements=requirements, user=user)
    for position, (rule_type, expected_value) in enumerate(
        (
            (HardConstraintRule.RuleType.REQUIRED_SKILL, "Python"),
            (HardConstraintRule.RuleType.LOCATION, "Prishtina"),
            (HardConstraintRule.RuleType.WORK_MODE, "remote"),
            (HardConstraintRule.RuleType.LANGUAGE, "English C1"),
            (HardConstraintRule.RuleType.EMPLOYMENT_TYPE, "full_time"),
        ),
        start=1,
    ):
        create_hard_constraint_rule(
            requirements=requirements,
            user=user,
            rule_type=rule_type,
            source_text=f"Required: {expected_value}",
            skill_label=(
                expected_value
                if rule_type == HardConstraintRule.RuleType.REQUIRED_SKILL
                else ""
            ),
            expected_value=(
                ""
                if rule_type == HardConstraintRule.RuleType.REQUIRED_SKILL
                else expected_value
            ),
            position=position,
        )
    confirm_requirements_draft(requirements=requirements, user=user)

    result = evaluate_candidate_constraints(
        requirements=requirements,
        candidate=candidate,
        user=user,
    )

    assert all(item.outcome == RuleOutcome.PASSED for item in result.rule_results)
    assert "Location: Prishtina" in result.rule_results[1].evidence
    assert "Prefers remote" in result.rule_results[2].evidence
    assert "English C1" in result.rule_results[3].evidence


def test_draft_profile_does_not_change_matching_input_signature() -> None:
    user, _, candidate, document = make_workspace()
    before_candidate = Candidate.objects.prefetch_related(
        "skill_records",
        "profile_versions",
    ).get(pk=candidate.pk)
    before = candidate_input_signature([before_candidate])
    profile = extract_candidate_profile(
        document=document,
        user=user,
        gateway=RecordingGateway(),
    ).profile
    draft_candidate = Candidate.objects.prefetch_related(
        "skill_records",
        "profile_versions",
    ).get(pk=candidate.pk)

    assert candidate_input_signature([draft_candidate]) == before

    confirm_candidate_profile(profile=profile, user=user)
    confirmed_candidate = Candidate.objects.prefetch_related(
        "skill_records",
        "profile_versions",
    ).get(pk=candidate.pk)
    assert candidate_input_signature([confirmed_candidate]) != before


def test_confirmed_profile_is_immutable_and_cannot_be_confirmed_twice() -> None:
    user, _, _, document = make_workspace()
    profile = extract_candidate_profile(
        document=document,
        user=user,
        gateway=RecordingGateway(),
    ).profile
    confirm_candidate_profile(profile=profile, user=user)

    profile.refresh_from_db()
    profile.location = "Changed"
    with pytest.raises(ValidationError, match="immutable"):
        profile.save()
    with pytest.raises(ValidationError, match="already confirmed"):
        confirm_candidate_profile(profile=profile, user=user)


def test_new_profile_confirmation_replaces_only_prior_ai_published_skills() -> None:
    user, _, candidate, document = make_workspace()
    first = extract_candidate_profile(
        document=document,
        user=user,
        gateway=RecordingGateway(),
    ).profile
    confirm_candidate_profile(profile=first, user=user)
    second = extract_candidate_profile(
        document=document,
        user=user,
        gateway=RecordingGateway(
            output=extracted_output(
                skills=[
                    {
                        "name": "PostgreSQL",
                        "evidence": "Built Django APIs and PostgreSQL data services.",
                        "years_experience": None,
                    }
                ]
            )
        ),
    ).profile

    confirm_candidate_profile(profile=second, user=user)

    assert list(
        CandidateSkill.objects.filter(candidate=candidate).values_list(
            "skill__name",
            flat=True,
        )
    ) == ["PostgreSQL"]
    published = CandidateSkill.objects.get(candidate=candidate)
    assert published.source_profile == second
    first.refresh_from_db()
    assert first.status == CandidateProfile.Status.CONFIRMED


def test_older_draft_cannot_replace_a_newer_confirmed_profile() -> None:
    user, _, _, document = make_workspace()
    older = extract_candidate_profile(
        document=document,
        user=user,
        gateway=RecordingGateway(),
    ).profile
    newer = extract_candidate_profile(
        document=document,
        user=user,
        gateway=RecordingGateway(),
    ).profile
    confirm_candidate_profile(profile=newer, user=user)

    with pytest.raises(ValidationError, match="newer candidate profile"):
        confirm_candidate_profile(profile=older, user=user)


def test_candidate_deletion_purges_profiles_and_published_skill_evidence(
    settings,
    tmp_path,
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user, _, candidate, document = make_workspace()
    profile = extract_candidate_profile(
        document=document,
        user=user,
        gateway=RecordingGateway(),
    ).profile
    confirm_candidate_profile(profile=profile, user=user)

    request_candidate_deletion(candidate=candidate, user=user)
    delete_candidate(candidate=candidate, user=user)

    assert not CandidateProfile.objects.filter(candidate=candidate).exists()
    assert not CandidateSkill.objects.filter(candidate=candidate).exists()


@override_settings(
    AI_GATEWAY_FACTORY="tests.test_candidate_ai_extraction.SuccessfulGateway"
)
def test_recruiter_extracts_reviews_and_confirms_profile(client) -> None:
    user, organization, candidate, document = make_workspace()
    client.force_login(user)

    get_response = client.get(extraction_url(organization, candidate, document))
    response = client.post(extraction_url(organization, candidate, document))

    profile = CandidateProfile.objects.get()
    assert get_response.status_code == 405
    assert response.status_code == 302
    assert response.url == profile_url(organization, candidate, profile)

    detail = client.get(response.url)
    content = detail.content.decode()
    assert detail.status_code == 200
    assert "AI output is not matching evidence yet" in content
    assert "Python: 5 years" in content
    assert CV_TEXT not in content
    assert candidate.email not in content

    confirmation = client.post(
        confirmation_url(organization, candidate, profile),
        follow=True,
    )
    profile.refresh_from_db()
    assert confirmation.status_code == 200
    assert profile.status == CandidateProfile.Status.CONFIRMED
    assert "grounded facts and skill evidence" in confirmation.content.decode()


@override_settings(
    AI_GATEWAY_FACTORY="tests.test_candidate_ai_extraction.RepairingGateway"
)
def test_view_reports_automatic_evidence_correction(client) -> None:
    user, organization, candidate, document = make_workspace()
    client.force_login(user)

    response = client.post(
        extraction_url(organization, candidate, document),
        follow=True,
    )

    assert response.status_code == 200
    assert "automatically correcting its source evidence" in response.content.decode()
    assert CandidateProfile.objects.count() == 1
    assert AIUsageEvent.objects.filter(status=AIUsageEvent.Status.FAILED).count() == 1
    assert (
        AIUsageEvent.objects.filter(status=AIUsageEvent.Status.SUCCEEDED).count() == 1
    )


@override_settings(
    AI_GATEWAY_FACTORY="tests.test_candidate_ai_extraction.FailingGateway"
)
def test_view_shows_safe_failure_and_creates_no_profile(client) -> None:
    user, organization, candidate, document = make_workspace()
    client.force_login(user)

    response = client.post(
        extraction_url(organization, candidate, document),
        follow=True,
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "temporarily unavailable" in content
    assert "provider" not in content.casefold()
    assert not CandidateProfile.objects.exists()


def test_profile_routes_do_not_disclose_cross_organization_data(client) -> None:
    user, organization, _, _ = make_workspace(username="visible")
    hidden_user, _, hidden_candidate, hidden_document = make_workspace(
        username="hidden"
    )
    hidden_profile = extract_candidate_profile(
        document=hidden_document,
        user=hidden_user,
        gateway=RecordingGateway(),
    ).profile
    client.force_login(user)

    extraction = client.post(
        extraction_url(organization, hidden_candidate, hidden_document)
    )
    detail = client.get(profile_url(organization, hidden_candidate, hidden_profile))

    assert extraction.status_code == 404
    assert detail.status_code == 404
