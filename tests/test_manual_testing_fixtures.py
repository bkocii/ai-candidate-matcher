from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import OrganizationMembership, User
from candidates.documents import CandidateDocumentUploadError, extract_cv_text
from candidates.models import CandidateSource
from candidates.services import import_candidate_csv
from organizations.models import Organization

pytestmark = pytest.mark.django_db

FIXTURE_ROOT = Path(__file__).parents[1] / "manual_testing" / "fixtures"


def source_defaults(name: str) -> dict:
    return {
        "source_type": CandidateSource.SourceType.CSV_IMPORT,
        "source_name": name,
        "lawful_basis": CandidateSource.LawfulBasis.NOT_RECORDED,
        "consent_status": CandidateSource.ConsentStatus.UNKNOWN,
        "contact_permission": CandidateSource.ContactPermission.UNKNOWN,
        "permission_notes": "Synthetic fixture validation.",
        "retention_until": None,
    }


def test_candidate_csv_fixtures_match_documented_reports() -> None:
    user = User.objects.create_user(username="fixture-tester")
    organization = Organization.objects.create(name="Fixture Test", slug="fixture")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )

    valid_bytes = (FIXTURE_ROOT / "candidate-import-valid.csv").read_bytes()
    valid = import_candidate_csv(
        uploaded_file=SimpleUploadedFile(
            "candidate-import-valid.csv", valid_bytes, content_type="text/csv"
        ),
        organization=organization,
        user=user,
        source_defaults=source_defaults("Valid fixture"),
    )
    mixed_bytes = (FIXTURE_ROOT / "candidate-import-mixed.csv").read_bytes()
    mixed = import_candidate_csv(
        uploaded_file=SimpleUploadedFile(
            "candidate-import-mixed.csv", mixed_bytes, content_type="text/csv"
        ),
        organization=organization,
        user=user,
        source_defaults=source_defaults("Mixed fixture"),
    )

    assert (valid.total_count, valid.created_count) == (3, 3)
    assert (valid.duplicate_count, valid.invalid_count) == (0, 0)
    assert (mixed.total_count, mixed.created_count) == (6, 2)
    assert (mixed.duplicate_count, mixed.invalid_count) == (2, 2)


@pytest.mark.parametrize(
    ("filename", "content_type", "expected_fragment"),
    [
        (
            "synthetic-arben-testi-cv.pdf",
            "application/pdf",
            "Senior backend developer",
        ),
        (
            "synthetic-amina-berisha-cv.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "Backend developer with five years",
        ),
        (
            "synthetic-drita-shembull-cv.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "Backend developer with invented experience",
        ),
    ],
)
def test_accepted_cv_fixtures_extract_text(
    filename: str,
    content_type: str,
    expected_fragment: str,
) -> None:
    extracted = extract_cv_text(
        raw=(FIXTURE_ROOT / filename).read_bytes(),
        filename=filename,
        declared_content_type=content_type,
    )

    assert expected_fragment in extracted.text


@pytest.mark.parametrize(
    ("filename", "expected_code"),
    [
        ("rejected-textless-cv.pdf", "no_extractable_text"),
        ("rejected-invalid-signature.pdf", "invalid_pdf_signature"),
    ],
)
def test_rejected_pdf_fixtures_have_documented_error_codes(
    filename: str,
    expected_code: str,
) -> None:
    with pytest.raises(CandidateDocumentUploadError) as error:
        extract_cv_text(
            raw=(FIXTURE_ROOT / filename).read_bytes(),
            filename=filename,
            declared_content_type="application/pdf",
        )

    assert error.value.code == expected_code
