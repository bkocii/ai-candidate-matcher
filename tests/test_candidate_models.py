from datetime import date

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import OrganizationMembership, User
from candidates.models import Candidate, CandidateDocument, CandidateSource
from organizations.models import Organization
from organizations.permissions import has_organization_object_access

pytestmark = pytest.mark.django_db


def add_member(user: User, organization: Organization) -> None:
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )


def test_candidate_records_identity_and_retention_metadata() -> None:
    creator = User.objects.create_user(username="creator")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Arta Krasniqi",
        email="arta@example.com",
        phone="+383 44 000 000",
        location="Prishtina",
        retention_until=date(2027, 8, 10),
        created_by=creator,
    )

    assert str(candidate) == "Arta Krasniqi"
    assert candidate.status == Candidate.Status.ACTIVE
    assert organization.candidates.get() == candidate


def test_candidate_email_is_not_globally_unique() -> None:
    first = Organization.objects.create(name="First", slug="first")
    second = Organization.objects.create(name="Second", slug="second")

    Candidate.objects.create(
        organization=first,
        full_name="Shared Person",
        email="shared@example.com",
    )
    Candidate.objects.create(
        organization=second,
        full_name="Shared Person",
        email="shared@example.com",
    )

    assert Candidate.objects.filter(email="shared@example.com").count() == 2


def test_deletion_states_require_their_audit_timestamp() -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")

    with pytest.raises(IntegrityError), transaction.atomic():
        Candidate.objects.create(
            organization=organization,
            full_name="Missing Request Timestamp",
            status=Candidate.Status.DELETION_REQUESTED,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        Candidate.objects.create(
            organization=organization,
            full_name="Missing Deletion Timestamp",
            status=Candidate.Status.DELETED,
        )

    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Deletion Recorded",
        status=Candidate.Status.DELETED,
        deleted_at=timezone.now(),
    )

    assert candidate.status == Candidate.Status.DELETED


def test_database_rejects_unknown_candidate_status() -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")

    with pytest.raises(IntegrityError), transaction.atomic():
        Candidate.objects.create(
            organization=organization,
            full_name="Invalid Status",
            status="archived_forever",
        )


def test_candidate_source_preserves_provenance_and_permission_metadata() -> None:
    recorder = User.objects.create_user(username="recorder")
    organization = Organization.objects.create(name="Acme", slug="acme")
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Luan Berisha",
    )
    source = CandidateSource.objects.create(
        candidate=candidate,
        source_type=CandidateSource.SourceType.ATS_IMPORT,
        source_name="Customer ATS export",
        source_reference="candidate-4821",
        lawful_basis=CandidateSource.LawfulBasis.LEGITIMATE_INTERESTS,
        consent_status=CandidateSource.ConsentStatus.NOT_REQUIRED,
        contact_permission=CandidateSource.ContactPermission.PERMITTED,
        consent_updated_at=timezone.now(),
        permission_notes="Imported under the organization's documented policy.",
        retention_until=date(2027, 8, 10),
        recorded_by=recorder,
    )

    assert source.organization == organization
    assert str(source) == "Luan Berisha — Customer ATS export"
    assert candidate.sources.get() == source


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("source_type", "scraped"),
        ("lawful_basis", "probably_ok"),
        ("consent_status", "assumed"),
        ("contact_permission", "assumed"),
    ],
)
def test_database_rejects_unknown_candidate_source_choices(
    field: str,
    invalid_value: str,
) -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Candidate",
    )
    values = {
        "candidate": candidate,
        "source_type": CandidateSource.SourceType.MANUAL_ENTRY,
        "source_name": "Manual record",
        field: invalid_value,
    }

    with pytest.raises(IntegrityError), transaction.atomic():
        CandidateSource.objects.create(**values)


def test_candidate_and_related_records_are_organization_scoped() -> None:
    recruiter = User.objects.create_user(username="recruiter")
    first = Organization.objects.create(name="First", slug="first")
    second = Organization.objects.create(name="Second", slug="second")
    add_member(recruiter, first)
    visible_candidate = Candidate.objects.create(
        organization=first,
        full_name="Visible Candidate",
    )
    hidden_candidate = Candidate.objects.create(
        organization=second,
        full_name="Hidden Candidate",
    )
    visible_source = CandidateSource.objects.create(
        candidate=visible_candidate,
        source_type=CandidateSource.SourceType.MANUAL_ENTRY,
        source_name="Manual entry",
    )
    CandidateSource.objects.create(
        candidate=hidden_candidate,
        source_type=CandidateSource.SourceType.MANUAL_ENTRY,
        source_name="Manual entry",
    )

    assert list(Candidate.objects.visible_to(recruiter)) == [visible_candidate]
    assert list(Candidate.objects.for_organization(first)) == [visible_candidate]
    assert list(CandidateSource.objects.visible_to(recruiter)) == [visible_source]
    assert list(CandidateSource.objects.for_organization(first)) == [visible_source]
    assert has_organization_object_access(recruiter, visible_source) is True


def test_anonymous_user_cannot_see_candidates_or_related_records() -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Hidden Candidate",
    )
    CandidateSource.objects.create(
        candidate=candidate,
        source_type=CandidateSource.SourceType.MANUAL_ENTRY,
        source_name="Manual entry",
    )

    assert not Candidate.objects.visible_to(AnonymousUser()).exists()
    assert not CandidateSource.objects.visible_to(AnonymousUser()).exists()


def test_candidate_document_uses_private_opaque_storage_path(
    tmp_path,
    settings,
) -> None:
    settings.MEDIA_ROOT = tmp_path
    uploader = User.objects.create_user(username="uploader")
    organization = Organization.objects.create(name="Acme", slug="acme")
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Arta Krasniqi",
    )
    CandidateSource.objects.create(
        candidate=candidate,
        source_type=CandidateSource.SourceType.DOCUMENT_UPLOAD,
        source_name="Recruiter upload",
    )
    document = CandidateDocument.objects.create(
        candidate=candidate,
        document_type=CandidateDocument.DocumentType.CV,
        original_filename="Arta Krasniqi CV.pdf",
        file=SimpleUploadedFile(
            "Arta Krasniqi CV.pdf",
            b"synthetic test document",
            content_type="application/pdf",
        ),
        content_type="application/pdf",
        size_bytes=23,
        sha256="a" * 64,
        uploaded_by=uploader,
    )

    assert document.organization == organization
    assert document.file.name.startswith(
        f"candidate_documents/{organization.pk}/{candidate.pk}/"
    )
    assert document.file.name.endswith(".pdf")
    assert "Arta" not in document.file.name
    assert str(document.storage_key) in document.file.name


def test_document_hash_validator_rejects_non_sha256_value() -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Candidate",
    )
    document = CandidateDocument(
        candidate=candidate,
        original_filename="cv.pdf",
        file="candidate_documents/test.pdf",
        sha256="NOT-A-SHA256",
    )

    with pytest.raises(ValidationError, match="SHA-256"):
        document.full_clean()


def test_candidate_document_visibility_follows_candidate_organization() -> None:
    recruiter = User.objects.create_user(username="recruiter")
    first = Organization.objects.create(name="First", slug="first")
    second = Organization.objects.create(name="Second", slug="second")
    add_member(recruiter, first)
    visible_candidate = Candidate.objects.create(
        organization=first,
        full_name="Visible Candidate",
    )
    hidden_candidate = Candidate.objects.create(
        organization=second,
        full_name="Hidden Candidate",
    )
    visible_document = CandidateDocument.objects.create(
        candidate=visible_candidate,
        original_filename="visible.pdf",
        file="candidate_documents/visible.pdf",
    )
    CandidateDocument.objects.create(
        candidate=hidden_candidate,
        original_filename="hidden.pdf",
        file="candidate_documents/hidden.pdf",
    )

    assert list(CandidateDocument.objects.visible_to(recruiter)) == [visible_document]
    assert list(CandidateDocument.objects.for_organization(first)) == [visible_document]
    assert has_organization_object_access(recruiter, visible_document) is True


def test_deleting_candidate_removes_source_and_document_rows() -> None:
    organization = Organization.objects.create(name="Acme", slug="acme")
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Candidate",
    )
    CandidateSource.objects.create(
        candidate=candidate,
        source_type=CandidateSource.SourceType.MANUAL_ENTRY,
        source_name="Manual entry",
    )
    CandidateDocument.objects.create(
        candidate=candidate,
        original_filename="cv.pdf",
        file="candidate_documents/cv.pdf",
    )

    candidate.delete()

    assert not CandidateSource.objects.exists()
    assert not CandidateDocument.objects.exists()
