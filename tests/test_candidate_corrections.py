import hashlib

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from accounts.models import OrganizationMembership, User
from audit.models import AuditEvent
from candidates.ai_extraction import confirm_candidate_profile
from candidates.models import (
    Candidate,
    CandidateDocument,
    CandidateProfile,
    CandidateSource,
)
from candidates.profile_review import candidate_profile_conflicts
from organizations.models import Organization

pytestmark = pytest.mark.django_db

CV_TEXT = """Synthetic Candidate
candidate@example.test | +383 44 111 222 | Gjilan
Backend developer with Python experience.
Location: Gjilan
Skills: Python, validated imports
"""


def make_workspace(*, slug: str = "northstar"):
    user = User.objects.create_user(username=f"recruiter-{slug}")
    organization = Organization.objects.create(name=slug.title(), slug=slug)
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Synthetic Candidate",
        email="candidate@example.test",
        phone="+383 44 111 222",
        location="Prishtina",
        created_by=user,
    )
    source = CandidateSource.objects.create(
        candidate=candidate,
        source_type=CandidateSource.SourceType.CSV_IMPORT,
        source_name="Migration CSV",
        source_reference="REF-001",
        recorded_by=user,
    )
    document = CandidateDocument.objects.create(
        candidate=candidate,
        document_type=CandidateDocument.DocumentType.CV,
        original_filename="candidate.docx",
        file="candidate_documents/candidate.docx",
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        size_bytes=1_024,
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
        source_document_sha256=document.sha256,
        source_text_sha256=hashlib.sha256(CV_TEXT.encode()).hexdigest(),
        relevant_experience_summary="Backend developer",
        skills=[
            {
                "name": "Python",
                "years_experience": None,
                "evidence": "Skills: Python, validated imports",
            },
            {
                "name": "validated imports",
                "years_experience": None,
                "evidence": "Skills: Python, validated imports",
            },
        ],
        location="Gjilan",
        fact_evidence={
            "relevant_experience_summary": (
                "Backend developer with Python experience."
            ),
            "location": "Location: Gjilan",
            "work_mode_preference": "",
            "employment_type_preferences": "",
            "availability": "",
        },
        created_by=user,
    )
    return user, organization, candidate, source, document, profile


def test_location_conflict_blocks_direct_confirmation() -> None:
    user, _, candidate, _, _, profile = make_workspace()

    conflicts = candidate_profile_conflicts(candidate=candidate, profile=profile)

    assert len(conflicts) == 1
    assert conflicts[0].field == "location"
    with pytest.raises(ValidationError, match="do not match"):
        confirm_candidate_profile(profile=profile, user=user)
    profile.refresh_from_db()
    assert profile.status == CandidateProfile.Status.DRAFT


def test_recruiter_can_correct_candidate_and_resolve_conflict(client) -> None:
    user, organization, candidate, _, _, profile = make_workspace()
    client.force_login(user)

    response = client.post(
        reverse("candidates:candidate-edit", args=[organization.slug, candidate.pk]),
        {
            "full_name": candidate.full_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "location": "Gjilan",
            "retention_until": "",
        },
    )

    candidate.refresh_from_db()
    assert response.status_code == 302
    assert candidate.location == "Gjilan"
    assert not candidate_profile_conflicts(candidate=candidate, profile=profile)
    event = AuditEvent.objects.get(action=AuditEvent.Action.CANDIDATE_UPDATED)
    assert event.object_id == candidate.pk
    assert event.actor == user


def test_candidate_edit_rechecks_duplicates_without_matching_itself(client) -> None:
    user, organization, candidate, _, _, _ = make_workspace()
    Candidate.objects.create(
        organization=organization,
        full_name="Existing Candidate",
        email="existing@example.test",
    )
    client.force_login(user)

    same = client.post(
        reverse("candidates:candidate-edit", args=[organization.slug, candidate.pk]),
        {
            "full_name": candidate.full_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "location": candidate.location,
            "retention_until": "",
        },
    )
    duplicate = client.post(
        reverse("candidates:candidate-edit", args=[organization.slug, candidate.pk]),
        {
            "full_name": candidate.full_name,
            "email": "existing@example.test",
            "phone": candidate.phone,
            "location": candidate.location,
            "retention_until": "",
        },
    )

    assert same.status_code == 302
    assert duplicate.status_code == 200
    assert b"Possible duplicate" in duplicate.content
    candidate.refresh_from_db()
    assert candidate.email == "candidate@example.test"


def test_recruiter_can_update_source_privacy_with_safe_labels(client) -> None:
    user, organization, candidate, source, _, _ = make_workspace()
    client.force_login(user)

    response = client.post(
        reverse(
            "candidates:candidate-source-edit",
            args=[organization.slug, candidate.pk, source.pk],
        ),
        {
            "source_name": source.source_name,
            "source_reference": source.source_reference,
            "lawful_basis": CandidateSource.LawfulBasis.LEGITIMATE_INTERESTS,
            "consent_status": CandidateSource.ConsentStatus.NOT_REQUIRED,
            "contact_permission": CandidateSource.ContactPermission.PERMITTED,
            "permission_notes": "Contact permission confirmed by recruiter.",
            "retention_until": "",
        },
    )

    source.refresh_from_db()
    assert response.status_code == 302
    assert source.contact_permission == CandidateSource.ContactPermission.PERMITTED
    assert source.consent_updated_at is not None
    assert AuditEvent.objects.filter(
        action=AuditEvent.Action.CANDIDATE_SOURCE_UPDATED,
        object_id=source.pk,
    ).exists()


def test_profile_correction_creates_new_evidence_validated_version(client) -> None:
    user, organization, candidate, _, _, profile = make_workspace()
    client.force_login(user)

    response = client.post(
        reverse(
            "candidates:candidate-profile-correct",
            args=[organization.slug, candidate.pk, profile.pk],
        ),
        {
            "relevant_experience_summary": "Backend developer",
            "relevant_experience_summary_evidence": (
                "Backend developer with Python experience."
            ),
            "location": "Gjilan",
            "location_evidence": "Location: Gjilan",
            "work_mode_preference": CandidateProfile.WorkMode.UNKNOWN,
            "work_mode_preference_evidence": "",
            "availability": "",
            "availability_evidence": "",
            "retained_skills": ["0"],
            "ambiguities": "",
        },
    )

    corrected = CandidateProfile.objects.get(version=2)
    profile.refresh_from_db()
    assert response.status_code == 302
    assert profile.status == CandidateProfile.Status.DRAFT
    assert corrected.status == CandidateProfile.Status.DRAFT
    assert [skill["name"] for skill in corrected.skills] == ["Python"]
    assert corrected.created_by == user
    assert corrected.source_document == profile.source_document
    assert AuditEvent.objects.filter(
        action=AuditEvent.Action.CANDIDATE_PROFILE_CORRECTED,
        object_id=corrected.pk,
    ).exists()


def test_correction_routes_are_tenant_scoped(client) -> None:
    _, organization, candidate, source, _, profile = make_workspace()
    outsider, other, _, _, _, _ = make_workspace(slug="other")
    client.force_login(outsider)

    assert (
        client.get(
            reverse("candidates:candidate-edit", args=[organization.slug, candidate.pk])
        ).status_code
        == 404
    )
    assert (
        client.get(
            reverse(
                "candidates:candidate-source-edit",
                args=[organization.slug, candidate.pk, source.pk],
            )
        ).status_code
        == 404
    )
    assert (
        client.get(
            reverse(
                "candidates:candidate-profile-correct",
                args=[organization.slug, candidate.pk, profile.pk],
            )
        ).status_code
        == 404
    )
    assert other != organization


def test_candidate_detail_uses_responsive_sources_and_shows_phone(client) -> None:
    user, organization, candidate, _, _, _ = make_workspace()
    client.force_login(user)

    response = client.get(
        reverse("candidates:candidate-detail", args=[organization.slug, candidate.pk])
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert candidate.phone in content
    assert "source-card-grid" in content
    assert "Edit details" in content
    assert "Source reference" in content
