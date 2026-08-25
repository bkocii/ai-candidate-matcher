import pytest
from django.urls import reverse

from accounts.models import OrganizationMembership, User
from candidates.forms import (
    CandidateCSVImportForm,
    CandidateCVUploadForm,
    CandidateIntakeBatchForm,
    CandidateManualEntryForm,
)
from candidates.models import Candidate, CandidateSource
from candidates.privacy import SOURCE_NAME_HELP_TEXT, SOURCE_REFERENCE_HELP_TEXT
from organizations.models import Organization

pytestmark = pytest.mark.django_db


def add_member(user: User, organization: Organization) -> None:
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )


@pytest.mark.parametrize(
    "form_class",
    [CandidateManualEntryForm, CandidateCSVImportForm, CandidateIntakeBatchForm],
)
def test_candidate_intake_uses_plain_privacy_labels_and_safe_defaults(form_class):
    form = form_class()

    assert form.fields["source_name"].help_text == SOURCE_NAME_HELP_TEXT
    assert form.fields["lawful_basis"].label == "Reason for storing data"
    assert form.fields["consent_status"].label == "Consent"
    assert form.fields["contact_permission"].label == "Allowed contact"
    assert form.fields["lawful_basis"].initial == "not_recorded"
    assert form.fields["consent_status"].initial == "unknown"
    assert form.fields["contact_permission"].initial == "unknown"
    assert dict(form.fields["consent_status"].choices)["unknown"] == "Not recorded"
    assert dict(form.fields["consent_status"].choices)["granted"] == "Given"
    assert dict(form.fields["contact_permission"].choices) == {
        "unknown": "Not confirmed",
        "permitted": "Future roles allowed",
        "restricted": "Application only",
        "withdrawn": "Do not contact",
    }


def test_quick_add_source_reference_and_retention_wording_is_practical():
    form = CandidateManualEntryForm()

    assert form.fields["source_reference"].help_text == SOURCE_REFERENCE_HELP_TEXT
    assert form.fields["candidate_retention_until"].label == (
        "Candidate — delete or review on"
    )
    assert form.fields["source_retention_until"].label == (
        "Source — delete or review on"
    )
    assert form.fields["document_retention_until"].label == ("CV — delete or review on")
    assert form.fields["candidate_retention_until"].initial is None
    assert form.fields["source_retention_until"].initial is None
    assert form.fields["document_retention_until"].initial is None
    assert CandidateCVUploadForm().fields["retention_until"].label == (
        "Delete or review on"
    )


def test_candidate_detail_shows_plain_source_privacy_wording(client):
    user = User.objects.create_user(username="privacy-reviewer")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Synthetic Candidate",
        created_by=user,
    )
    CandidateSource.objects.create(
        candidate=candidate,
        source_type=CandidateSource.SourceType.REFERRAL,
        source_name="Recruiter referral",
        source_reference="REF-001",
        lawful_basis=CandidateSource.LawfulBasis.CONSENT,
        consent_status=CandidateSource.ConsentStatus.GRANTED,
        contact_permission=CandidateSource.ContactPermission.PERMITTED,
        recorded_by=user,
    )
    client.force_login(user)

    response = client.get(
        reverse(
            "candidates:candidate-detail",
            args=[organization.slug, candidate.pk],
        )
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Reason for storing data" in content
    assert "Allowed contact" in content
    assert "Future roles allowed" in content
    assert "Consent" in content
    assert "Given" in content
    assert "REF-001" in content
    assert "Lawful basis" not in content
    assert "Contact permission" not in content
