from datetime import date
from io import BytesIO

import pytest
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from accounts.models import OrganizationMembership, User
from candidates.models import Candidate, CandidateSource
from candidates.services import (
    CandidateImportFileError,
    import_candidate_csv,
    normalize_phone,
)
from organizations.models import Organization

pytestmark = pytest.mark.django_db


def add_member(user: User, organization: Organization) -> None:
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )


def import_defaults() -> dict:
    return {
        "source_type": CandidateSource.SourceType.CSV_IMPORT,
        "source_name": "Legacy ATS export",
        "lawful_basis": CandidateSource.LawfulBasis.LEGITIMATE_INTERESTS,
        "consent_status": CandidateSource.ConsentStatus.NOT_REQUIRED,
        "contact_permission": CandidateSource.ContactPermission.PERMITTED,
        "permission_notes": "Synthetic test data.",
        "retention_until": date(2027, 8, 10),
    }


def csv_upload(content: str, name: str = "candidates.csv") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content.encode(), content_type="text/csv")


def test_manual_candidate_entry_creates_candidate_and_source(client) -> None:
    user = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    client.force_login(user)

    response = client.post(
        reverse(
            "candidates:candidate-create",
            kwargs={"organization_slug": organization.slug},
        ),
        {
            "full_name": "  Arta Krasniqi  ",
            "email": "arta@example.com",
            "phone": "+383 44 000 000",
            "location": "Prishtina",
            "candidate_retention_until": "2027-08-10",
            "source_name": "Recruiter referral",
            "source_reference": "ref-101",
            "lawful_basis": CandidateSource.LawfulBasis.CONSENT,
            "consent_status": CandidateSource.ConsentStatus.GRANTED,
            "contact_permission": CandidateSource.ContactPermission.PERMITTED,
            "permission_notes": "Candidate agreed to be contacted.",
            "source_retention_until": "2027-08-10",
        },
    )

    candidate = Candidate.objects.get()
    source = candidate.sources.get()
    assert response.status_code == 302
    assert candidate.organization == organization
    assert candidate.full_name == "Arta Krasniqi"
    assert candidate.created_by == user
    assert candidate.retention_until == date(2027, 8, 10)
    assert source.source_type == CandidateSource.SourceType.MANUAL_ENTRY
    assert source.source_reference == "ref-101"
    assert source.recorded_by == user


def test_manual_entry_reports_existing_organization_duplicate(client) -> None:
    user = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    existing = Candidate.objects.create(
        organization=organization,
        full_name="Existing Candidate",
        email="same@example.com",
    )
    client.force_login(user)

    response = client.post(
        reverse(
            "candidates:candidate-create",
            kwargs={"organization_slug": organization.slug},
        ),
        {
            "full_name": "New Candidate",
            "email": "SAME@example.com",
            "source_name": "Manual source",
            "lawful_basis": CandidateSource.LawfulBasis.NOT_RECORDED,
            "consent_status": CandidateSource.ConsentStatus.UNKNOWN,
            "contact_permission": CandidateSource.ContactPermission.UNKNOWN,
        },
    )

    assert response.status_code == 200
    assert Candidate.objects.count() == 1
    assert response.context["form"].non_field_errors()
    content = response.content.decode()
    assert existing.full_name in content
    assert "matched by email" in content


def test_manual_duplicate_check_does_not_cross_organizations(client) -> None:
    user = User.objects.create_user(username="recruiter")
    first = Organization.objects.create(name="First", slug="first")
    second = Organization.objects.create(name="Second", slug="second")
    add_member(user, first)
    Candidate.objects.create(
        organization=second,
        full_name="Other Tenant Candidate",
        email="shared@example.com",
    )
    client.force_login(user)

    response = client.post(
        reverse(
            "candidates:candidate-create",
            kwargs={"organization_slug": first.slug},
        ),
        {
            "full_name": "First Tenant Candidate",
            "email": "shared@example.com",
            "source_name": "Manual source",
            "lawful_basis": CandidateSource.LawfulBasis.NOT_RECORDED,
            "consent_status": CandidateSource.ConsentStatus.UNKNOWN,
            "contact_permission": CandidateSource.ContactPermission.UNKNOWN,
        },
    )

    assert response.status_code == 302
    assert Candidate.objects.for_organization(first).count() == 1
    assert Candidate.objects.count() == 2


def test_candidate_list_is_tenant_scoped(client) -> None:
    user = User.objects.create_user(username="recruiter")
    first = Organization.objects.create(name="First", slug="first")
    second = Organization.objects.create(name="Second", slug="second")
    add_member(user, first)
    Candidate.objects.create(organization=first, full_name="Visible Candidate")
    Candidate.objects.create(organization=second, full_name="Hidden Candidate")
    client.force_login(user)

    response = client.get(
        reverse(
            "candidates:candidate-list",
            kwargs={"organization_slug": first.slug},
        )
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Visible Candidate" in content
    assert "Hidden Candidate" not in content


@pytest.mark.parametrize(
    "route_name",
    [
        "candidate-list",
        "candidate-create",
        "candidate-import",
        "candidate-import-template",
    ],
)
def test_candidate_intake_routes_hide_other_organizations(client, route_name) -> None:
    user = User.objects.create_user(username="recruiter")
    visible = Organization.objects.create(name="Visible", slug="visible")
    hidden = Organization.objects.create(name="Hidden", slug="hidden")
    add_member(user, visible)
    client.force_login(user)

    response = client.get(
        reverse(
            f"candidates:{route_name}",
            kwargs={"organization_slug": hidden.slug},
        )
    )

    assert response.status_code == 404
    assert "Hidden" not in response.content.decode()


def test_csv_import_creates_valid_rows_with_shared_provenance() -> None:
    user = User.objects.create_user(username="importer")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    content = (
        "full_name,email,phone,location,source_reference,retention_until\n"
        "Arta Krasniqi,arta@example.com,+38344000000,Prishtina,ats-1,2027-08-10\n"
        "Luan Berisha,luan@example.com,,Mitrovica,ats-2,\n"
    )

    result = import_candidate_csv(
        uploaded_file=BytesIO(content.encode()),
        organization=organization,
        user=user,
        source_defaults=import_defaults(),
    )

    assert result.total_count == 2
    assert result.created_count == 2
    assert result.duplicate_count == 0
    assert result.invalid_count == 0
    assert Candidate.objects.for_organization(organization).count() == 2
    arta = Candidate.objects.get(email="arta@example.com")
    assert arta.retention_until == date(2027, 8, 10)
    assert arta.sources.get().source_name == "Legacy ATS export"
    assert arta.sources.get().source_reference == "ats-1"


def test_csv_import_keeps_valid_rows_and_reports_invalid_rows() -> None:
    user = User.objects.create_user(username="importer")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    content = (
        "full_name,email,phone,location,source_reference,retention_until\n"
        "Valid Candidate,valid@example.com,,,,\n"
        ",invalid-email,,,,not-a-date\n"
    )

    result = import_candidate_csv(
        uploaded_file=BytesIO(content.encode()),
        organization=organization,
        user=user,
        source_defaults=import_defaults(),
    )

    assert result.created_count == 1
    assert result.invalid_count == 1
    invalid = result.rows[1]
    assert invalid.row_number == 3
    assert invalid.status == "invalid"
    assert any("full name" in detail for detail in invalid.details)
    assert Candidate.objects.count() == 1


def test_csv_import_reports_existing_and_in_file_duplicates() -> None:
    user = User.objects.create_user(username="importer")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    existing = Candidate.objects.create(
        organization=organization,
        full_name="Existing",
        phone="+383 44 123 456",
    )
    CandidateSource.objects.create(
        candidate=existing,
        source_type=CandidateSource.SourceType.CSV_IMPORT,
        source_name="Earlier import",
        source_reference="ats-existing",
    )
    content = (
        "full_name,email,phone,location,source_reference\n"
        "Phone duplicate,,+383-44-123-456,,\n"
        "Reference duplicate,,,,ats-existing\n"
        "New Candidate,new@example.com,,,ats-new\n"
        "Repeated New,NEW@example.com,,,different-reference\n"
    )

    result = import_candidate_csv(
        uploaded_file=BytesIO(content.encode()),
        organization=organization,
        user=user,
        source_defaults=import_defaults(),
    )

    assert result.created_count == 1
    assert result.duplicate_count == 3
    assert result.invalid_count == 0
    assert result.rows[0].details == ("phone",)
    assert result.rows[1].details == ("source reference",)
    assert result.rows[3].details == ("email",)
    assert Candidate.objects.count() == 2


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("email\narta@example.com\n", "Missing required column"),
        ("full_name,unexpected\nArta,value\n", "Unsupported column"),
        ("full_name,full_name\nArta,Other\n", "duplicate column headers"),
        ("", "empty or has no header"),
    ],
)
def test_csv_import_rejects_invalid_file_headers(content: str, message: str) -> None:
    user = User.objects.create_user(username="importer")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)

    with pytest.raises(CandidateImportFileError, match=message):
        import_candidate_csv(
            uploaded_file=BytesIO(content.encode()),
            organization=organization,
            user=user,
            source_defaults=import_defaults(),
        )

    assert not Candidate.objects.exists()


def test_csv_import_rejects_non_utf8_and_oversized_files() -> None:
    user = User.objects.create_user(username="importer")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)

    with pytest.raises(CandidateImportFileError, match="UTF-8"):
        import_candidate_csv(
            uploaded_file=BytesIO(b"full_name\n\xff\n"),
            organization=organization,
            user=user,
            source_defaults=import_defaults(),
        )

    with pytest.raises(CandidateImportFileError, match="exceeds"):
        import_candidate_csv(
            uploaded_file=BytesIO(b"full_name\nCandidate\n"),
            organization=organization,
            user=user,
            source_defaults=import_defaults(),
            max_bytes=10,
        )


def test_csv_import_enforces_row_limit_before_creating_any_rows() -> None:
    user = User.objects.create_user(username="importer")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    content = "full_name,email\nFirst,first@example.com\nSecond,second@example.com\n"

    with pytest.raises(CandidateImportFileError, match="1-row limit"):
        import_candidate_csv(
            uploaded_file=BytesIO(content.encode()),
            organization=organization,
            user=user,
            source_defaults=import_defaults(),
            max_rows=1,
        )

    assert not Candidate.objects.exists()


def test_import_service_requires_active_organization_membership() -> None:
    user = User.objects.create_user(username="outsider")
    organization = Organization.objects.create(name="Northstar", slug="northstar")

    with pytest.raises(PermissionDenied):
        import_candidate_csv(
            uploaded_file=BytesIO(b"full_name\nCandidate\n"),
            organization=organization,
            user=user,
            source_defaults=import_defaults(),
        )

    assert not Candidate.objects.exists()


def test_import_view_displays_created_duplicate_and_invalid_report(client) -> None:
    user = User.objects.create_user(username="importer")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    Candidate.objects.create(
        organization=organization,
        full_name="Existing Candidate",
        email="existing@example.com",
    )
    client.force_login(user)
    content = (
        "full_name,email\n"
        "New Candidate,new@example.com\n"
        "Duplicate Candidate,EXISTING@example.com\n"
        ",bad-email\n"
    )

    response = client.post(
        reverse(
            "candidates:candidate-import",
            kwargs={"organization_slug": organization.slug},
        ),
        {
            "csv_file": csv_upload(content),
            "source_name": "Legacy ATS export",
            "lawful_basis": CandidateSource.LawfulBasis.LEGITIMATE_INTERESTS,
            "consent_status": CandidateSource.ConsentStatus.NOT_REQUIRED,
            "contact_permission": CandidateSource.ContactPermission.PERMITTED,
            "permission_notes": "Synthetic test data.",
            "source_retention_until": "2027-08-10",
        },
    )

    assert response.status_code == 200
    result = response.context["result"]
    assert result.created_count == 1
    assert result.duplicate_count == 1
    assert result.invalid_count == 1
    content = response.content.decode()
    import_url = reverse(
        "candidates:candidate-import",
        kwargs={"organization_slug": organization.slug},
    )
    assert "3 processed rows" in content
    assert "New Candidate" in content
    assert "Duplicate Candidate" in content
    assert "Unnamed row" in content
    assert f'action="{import_url}#import-results"' in content
    assert 'id="import-results"' in content
    assert 'tabindex="-1"' in content


def test_csv_template_is_available_only_to_organization_members(client) -> None:
    user = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    client.force_login(user)

    response = client.get(
        reverse(
            "candidates:candidate-import-template",
            kwargs={"organization_slug": organization.slug},
        )
    )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment" in response["Content-Disposition"]
    assert response.content.decode().startswith(
        "full_name,email,phone,location,source_reference,retention_until"
    )


@pytest.mark.parametrize(
    ("value", "normalized"),
    [
        ("+383 44 123 456", "38344123456"),
        ("044-123-456", "044123456"),
        ("123", ""),
    ],
)
def test_phone_normalization_requires_a_useful_identity(value, normalized) -> None:
    assert normalize_phone(value) == normalized
