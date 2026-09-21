import hashlib
from datetime import date
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from docx import Document as DocxDocument

from accounts.models import OrganizationMembership, User
from candidates.bulk_intake import (
    create_candidate_from_intake_item,
    create_candidate_intake_batch,
    upload_candidate_intake_cv,
)
from candidates.documents import DOCX_CONTENT_TYPE
from candidates.intake_mapping import apply_candidate_intake_csv
from candidates.models import (
    Candidate,
    CandidateIntakeBatch,
    CandidateIntakeItem,
    CandidateProfile,
    CandidateSource,
)
from candidates.profile_batch import IntakeProfileReviewRow, review_intake_profiles
from matching.models import ReviewDecision
from operations.services import queue_candidate_profile_documents
from organizations.models import Organization
from outreach.models import OutreachDraft

pytestmark = pytest.mark.django_db


def add_member(user: User, organization: Organization) -> None:
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )


def docx_upload(name: str, text: str) -> SimpleUploadedFile:
    document = DocxDocument()
    for line in text.splitlines():
        document.add_paragraph(line)
    output = BytesIO()
    document.save(output)
    return SimpleUploadedFile(name, output.getvalue(), content_type=DOCX_CONTENT_TYPE)


def batch_values() -> dict:
    return {
        "source_name": "Synthetic shared source",
        "lawful_basis": CandidateSource.LawfulBasis.LEGITIMATE_INTERESTS,
        "consent_status": CandidateSource.ConsentStatus.NOT_REQUIRED,
        "contact_permission": CandidateSource.ContactPermission.UNKNOWN,
        "permission_notes": "Synthetic records only.",
        "candidate_retention_until": date(2027, 8, 24),
        "source_retention_until": date(2027, 8, 24),
        "document_retention_until": date(2027, 8, 24),
    }


def make_batch() -> tuple[User, Organization, CandidateIntakeBatch]:
    user = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    batch = create_candidate_intake_batch(
        organization=organization,
        user=user,
        values=batch_values(),
    )
    return user, organization, batch


def accept_item(*, batch, user, filename, name, email):
    text = f"{name}\n{email} | Prishtina\nPython experience"
    item = upload_candidate_intake_cv(
        batch=batch,
        user=user,
        uploaded_file=docx_upload(filename, text),
    )
    return accept_uploaded_item(item=item, user=user, name=name, email=email, text=text)


def accept_uploaded_item(*, item, user, name, email, text):
    result = create_candidate_from_intake_item(
        item=item,
        user=user,
        candidate_values={
            "full_name": name,
            "email": email,
            "phone": "",
            "location": "Prishtina",
        },
        source_reference=f"ref-{item.pk}",
    )
    item.refresh_from_db()
    return item, result.document, text


def create_profile(*, item, document, text, user, ambiguities=()):
    return CandidateProfile.objects.create(
        candidate=item.candidate,
        source_document=document,
        version=1,
        source_document_sha256=document.sha256,
        source_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        relevant_experience_summary="Python experience",
        skills=[
            {
                "name": "Python",
                "years_experience": None,
                "evidence": "Python experience",
            }
        ],
        fact_evidence={
            "relevant_experience_summary": "Python experience",
        },
        ambiguities=list(ambiguities),
        created_by=user,
    )


def test_exact_csv_mapping_updates_only_one_to_one_pending_filename(
    settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user, _, batch = make_batch()
    first = upload_candidate_intake_cv(
        batch=batch,
        user=user,
        uploaded_file=docx_upload(
            "first-cv.docx", "Local Proposal\nlocal@example.test\nPython"
        ),
    )
    second = upload_candidate_intake_cv(
        batch=batch,
        user=user,
        uploaded_file=docx_upload(
            "second-cv.docx", "Second Proposal\nsecond@example.test\nDjango"
        ),
    )
    csv_file = SimpleUploadedFile(
        "mapping.csv",
        (
            b"cv_filename,full_name,email,phone,location,source_reference\n"
            b"first-cv.docx,CSV Candidate,csv@example.test,,Prishtina,ATS-001\n"
            b"missing.docx,Unmatched Candidate,,,,ATS-002\n"
        ),
        content_type="text/csv",
    )

    result = apply_candidate_intake_csv(
        batch=batch,
        user=user,
        uploaded_file=csv_file,
    )

    first.refresh_from_db()
    second.refresh_from_db()
    assert result.mapped_count == 1
    assert result.unresolved_count == 1
    assert first.proposed_full_name == "CSV Candidate"
    assert first.proposed_source_reference == "ATS-001"
    assert second.proposed_full_name == "Second Proposal"
    assert result.rows[1].details == ("No pending CV has this exact filename.",)


def test_repeated_csv_filename_is_unresolved_and_never_applied(
    settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user, _, batch = make_batch()
    item = upload_candidate_intake_cv(
        batch=batch,
        user=user,
        uploaded_file=docx_upload("candidate.docx", "Local Name\nPython"),
    )
    original_name = item.proposed_full_name
    csv_file = SimpleUploadedFile(
        "mapping.csv",
        (
            b"cv_filename,full_name\n"
            b"candidate.docx,First CSV Name\n"
            b"candidate.docx,Second CSV Name\n"
        ),
        content_type="text/csv",
    )

    result = apply_candidate_intake_csv(
        batch=batch,
        user=user,
        uploaded_file=csv_file,
    )

    item.refresh_from_db()
    assert result.mapped_count == 0
    assert result.unresolved_count == 2
    assert item.proposed_full_name == original_name


def test_quick_add_can_create_candidate_source_and_cv_together(
    client, settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user = User.objects.create_user(username="quick-add")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    client.force_login(user)

    response = client.post(
        reverse("candidates:candidate-create", args=[organization.slug]),
        {
            "full_name": "Quick Add Candidate",
            "source_name": "Recruiter referral",
            "lawful_basis": CandidateSource.LawfulBasis.NOT_RECORDED,
            "consent_status": CandidateSource.ConsentStatus.UNKNOWN,
            "contact_permission": CandidateSource.ContactPermission.UNKNOWN,
            "cv_file": docx_upload(
                "quick-add.docx", "Quick Add Candidate\nPython experience"
            ),
        },
    )

    candidate = Candidate.objects.get()
    assert response.status_code == 302
    assert candidate.sources.count() == 1
    assert candidate.documents.count() == 1
    assert candidate.documents.get().original_filename == "quick-add.docx"


def test_invalid_quick_add_cv_rolls_back_candidate_and_source(
    client, settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user = User.objects.create_user(username="quick-add")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    client.force_login(user)

    response = client.post(
        reverse("candidates:candidate-create", args=[organization.slug]),
        {
            "full_name": "Unsafe Quick Add",
            "source_name": "Recruiter entry",
            "lawful_basis": CandidateSource.LawfulBasis.NOT_RECORDED,
            "consent_status": CandidateSource.ConsentStatus.UNKNOWN,
            "contact_permission": CandidateSource.ContactPermission.UNKNOWN,
            "cv_file": SimpleUploadedFile(
                "unsafe.pdf", b"not a pdf", content_type="application/pdf"
            ),
        },
    )

    assert response.status_code == 200
    assert not Candidate.objects.exists()
    assert not CandidateSource.objects.exists()
    assert b"valid PDF" in response.content


def test_batch_profile_confirmation_includes_clean_and_excludes_ambiguity(
    client, settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user, organization, batch = make_batch()
    clean_text = "Clean Candidate\nclean@example.test | Prishtina\nPython experience"
    ambiguous_text = (
        "Ambiguous Candidate\nambiguous@example.test | Prishtina\nPython experience"
    )
    clean_pending = upload_candidate_intake_cv(
        batch=batch,
        user=user,
        uploaded_file=docx_upload("clean.docx", clean_text),
    )
    ambiguous_pending = upload_candidate_intake_cv(
        batch=batch,
        user=user,
        uploaded_file=docx_upload("ambiguous.docx", ambiguous_text),
    )
    clean_item, clean_document, _ = accept_uploaded_item(
        item=clean_pending,
        user=user,
        name="Clean Candidate",
        email="clean@example.test",
        text=clean_text,
    )
    ambiguous_item, ambiguous_document, _ = accept_uploaded_item(
        item=ambiguous_pending,
        user=user,
        name="Ambiguous Candidate",
        email="ambiguous@example.test",
        text=ambiguous_text,
    )
    clean_profile = create_profile(
        item=clean_item,
        document=clean_document,
        text=clean_text,
        user=user,
    )
    ambiguous_profile = create_profile(
        item=ambiguous_item,
        document=ambiguous_document,
        text=ambiguous_text,
        user=user,
        ambiguities=("Employment dates require review.",),
    )

    review = review_intake_profiles(batch=batch, user=user)
    assert len(review.eligible_rows) == 1
    assert review.eligible_rows[0].profile == clean_profile
    assert len(review.excluded_rows) == 1
    assert review.excluded_rows[0].profile == ambiguous_profile

    client.force_login(user)
    page = client.get(
        reverse(
            "candidates:candidate-intake-confirm-profiles",
            args=[organization.slug, batch.pk],
        )
    )
    assert page.status_code == 200
    assert b"<span>Ready to confirm</span><strong>1</strong>" in page.content
    assert b"<span>Needs individual review</span><strong>1</strong>" in page.content
    assert b"Ready to confirm</span>" in page.content
    assert b"Needs individual review</span>" in page.content
    assert b">Excluded<" not in page.content
    assert b"Profile v1" in page.content
    assert "1 skill · 1 other fact" in page.content.decode()
    assert b"0 location conflicts" in page.content
    assert b"Confirm 1 ready profile</button>" in page.content
    assert b"profile(s)" not in page.content

    response = client.post(
        reverse(
            "candidates:candidate-intake-confirm-profiles",
            args=[organization.slug, batch.pk],
        ),
        follow=True,
    )
    clean_profile.refresh_from_db()
    ambiguous_profile.refresh_from_db()
    assert response.status_code == 200
    assert clean_profile.status == CandidateProfile.Status.CONFIRMED
    assert clean_profile.confirmed_by == user
    assert clean_profile.confirmed_at is not None
    assert ambiguous_profile.status == CandidateProfile.Status.DRAFT
    assert clean_item.candidate.skill_records.count() == 1
    assert b"Confirmed 1 profile." in response.content
    assert b"1 profile from this intake is already confirmed." in response.content
    assert not ReviewDecision.objects.exists()
    assert not OutreachDraft.objects.exists()


def test_queued_profile_is_processing_instead_of_excluded(
    client, settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user, organization, batch = make_batch()
    item, document, _ = accept_item(
        batch=batch,
        user=user,
        filename="queued.docx",
        name="Queued Candidate",
        email="queued@example.test",
    )
    queue_candidate_profile_documents(
        organization=organization,
        user=user,
        document_ids=[document.pk],
    )

    review = review_intake_profiles(batch=batch, user=user)
    assert len(review.processing_rows) == 1
    assert review.processing_rows[0].item == item
    assert not review.eligible_rows
    assert not review.needs_review_rows

    client.force_login(user)
    page = client.get(
        reverse(
            "candidates:candidate-intake-confirm-profiles",
            args=[organization.slug, batch.pk],
        )
    )
    content = page.content.decode()
    assert page.status_code == 200
    assert "Processing</span><strong>1</strong>" in content
    assert "Profile creation is still processing" in content
    assert "Excluded" not in content
    assert "0 skills" not in content
    assert "0 location conflicts" not in content


def test_batch_profile_confirmation_excludes_candidate_profile_conflict(
    client, settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user, organization, batch = make_batch()
    text = "Conflict Candidate\nconflict@example.test | Gjilan\nPython experience"
    pending = upload_candidate_intake_cv(
        batch=batch,
        user=user,
        uploaded_file=docx_upload("conflict.docx", text),
    )
    item, document, _ = accept_uploaded_item(
        item=pending,
        user=user,
        name="Conflict Candidate",
        email="conflict@example.test",
        text=text,
    )
    profile = create_profile(
        item=item,
        document=document,
        text=text,
        user=user,
    )
    profile.location = "Gjilan"
    profile.fact_evidence["location"] = "Gjilan"
    profile.save()

    review = review_intake_profiles(batch=batch, user=user)

    assert not review.eligible_rows
    assert review.excluded_rows[0].profile == profile
    assert "do not match" in review.excluded_rows[0].reason
    assert review.excluded_rows[0].conflict_count == 1

    client.force_login(user)
    url = reverse(
        "candidates:candidate-intake-confirm-profiles",
        args=[organization.slug, batch.pk],
    )
    page = client.get(url)
    assert b"1 location conflict" in page.content
    assert b"No profiles are ready to confirm" in page.content
    response = client.post(url, follow=True)
    assert b"No profile drafts are ready for confirmation." in response.content
    profile.refresh_from_db()
    assert profile.status == CandidateProfile.Status.DRAFT
    assert profile.confirmed_by is None


def test_batch_summary_counts_saved_facts_without_evidence_duplicates() -> None:
    candidate = Candidate(location="Prishtina")
    item = CandidateIntakeItem(candidate=candidate)
    profile = CandidateProfile()
    row = IntakeProfileReviewRow(item, profile, "ready", "")
    assert (row.skill_count, row.fact_count, row.conflict_count) == (0, 0, 0)

    profile.relevant_experience_summary = "Python experience"
    profile.location = "Gjilan"
    profile.availability = "Available immediately"
    profile.work_mode_preference = CandidateProfile.WorkMode.REMOTE
    profile.skills = [{"name": "Python"}, {"name": "Django"}]
    profile.employment_history = [{"role": "Developer"}]
    profile.languages = [{"language": "English"}, {"language": "Albanian"}]
    profile.education = [{"qualification": "Degree"}]
    profile.certifications = [{"name": "Certificate"}]
    profile.employment_type_preferences = ["full_time"]
    profile.fact_evidence = {"location": "Gjilan"}
    profile.ambiguities = ["Needs individual review"]
    assert (row.skill_count, row.fact_count, row.conflict_count) == (2, 10, 1)

    missing = IntakeProfileReviewRow(item, None, "processing", "")
    assert (missing.skill_count, missing.fact_count, missing.conflict_count) == (
        0,
        0,
        0,
    )


def test_batch_confirmation_confirms_two_clean_profiles_and_preserves_conflict(
    client, settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user, organization, batch = make_batch()
    profiles = []
    pending_items = []
    for index in range(3):
        location = "Gjilan" if index == 2 else "Prishtina"
        text = (
            f"Synthetic {index}\nexample{index}@example.test | {location}\n"
            "Python experience"
        )
        pending = upload_candidate_intake_cv(
            batch=batch,
            user=user,
            uploaded_file=docx_upload(f"synthetic-{index}.docx", text),
        )
        pending_items.append((index, pending, location, text))
    # Stage the whole batch before accepting its final pending item closes it.
    for index, pending, location, text in pending_items:
        item, document, _ = accept_uploaded_item(
            item=pending,
            user=user,
            name=f"Synthetic {index}",
            email=f"example{index}@example.test",
            text=text,
        )
        profile = create_profile(item=item, document=document, text=text, user=user)
        profile.location = location
        profile.fact_evidence["location"] = location
        profile.save()
        profiles.append(profile)

    client.force_login(user)
    url = reverse(
        "candidates:candidate-intake-confirm-profiles",
        args=[organization.slug, batch.pk],
    )
    page = client.get(url)
    assert b"Confirm 2 ready profiles</button>" in page.content
    assert "1 skill · 2 other facts" in page.content.decode()
    assert b"1 location conflict" in page.content
    assert b"profile(s)" not in page.content
    response = client.post(url, follow=True)
    assert b"Confirmed 2 profiles." in response.content
    assert b"2 profiles from this intake are already confirmed." in response.content
    for profile in profiles[:2]:
        profile.refresh_from_db()
        assert profile.status == CandidateProfile.Status.CONFIRMED
        assert profile.confirmed_by == user
        assert profile.confirmed_at is not None
    profiles[2].refresh_from_db()
    assert profiles[2].status == CandidateProfile.Status.DRAFT
    assert profiles[2].confirmed_by is None
    assert profiles[2].confirmed_at is None
    assert not profiles[2].candidate.skill_records.exists()
    assert not ReviewDecision.objects.exists()
    assert not OutreachDraft.objects.exists()


def test_unified_intake_routes_are_tenant_scoped(client, settings, tmp_path) -> None:
    settings.MEDIA_ROOT = tmp_path
    owner, organization, batch = make_batch()
    outsider = User.objects.create_user(username="outsider")
    other = Organization.objects.create(name="Other", slug="other")
    add_member(outsider, other)
    client.force_login(outsider)

    confirm_page = client.get(
        reverse(
            "candidates:candidate-intake-confirm-profiles",
            args=[other.slug, batch.pk],
        )
    )
    mapping = client.post(
        reverse(
            "candidates:candidate-intake-apply-csv",
            args=[other.slug, batch.pk],
        ),
        {"csv_file": SimpleUploadedFile("map.csv", b"cv_filename,full_name\n")},
    )

    assert owner != outsider
    assert confirm_page.status_code == 404
    assert mapping.status_code == 404


def test_candidate_detail_links_only_its_own_organization_intake(
    client, settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user, organization, batch = make_batch()
    item, _, _ = accept_item(
        batch=batch,
        user=user,
        filename="origin.docx",
        name="Origin Candidate",
        email="origin@example.test",
    )
    client.force_login(user)
    detail_url = reverse(
        "candidates:candidate-detail", args=[organization.slug, item.candidate_id]
    )
    intake_url = reverse(
        "candidates:candidate-intake-detail", args=[organization.slug, batch.pk]
    )
    response = client.get(detail_url)
    assert response.status_code == 200
    assert f'href="{intake_url}">Intake #{batch.pk}</a>' in response.content.decode()
    assert client.get(intake_url).status_code == 200

    other = Organization.objects.create(name="Other", slug="other")
    outsider = User.objects.create_user(username="outsider")
    add_member(outsider, other)
    client.force_login(outsider)
    assert client.get(detail_url).status_code == 404
    assert client.get(intake_url).status_code == 404

    # Even malformed legacy cross-organization relations must not expose a link.
    CandidateIntakeBatch.objects.filter(pk=batch.pk).update(organization=other)
    client.force_login(user)
    response = client.get(detail_url)
    assert response.status_code == 200
    assert "Created from intake:" not in response.content.decode()
    assert intake_url not in response.content.decode()


def test_candidate_list_promotes_cv_first_intake(client) -> None:
    user = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    client.force_login(user)

    response = client.get(
        reverse("candidates:candidate-list", args=[organization.slug])
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert content.count('class="primary-button button-link"') == 1
    assert "Create candidates from CVs" in content
    assert '<details class="candidate-more-actions">' in content
    assert "<summary>More actions</summary>" in content
    assert "Quick add" in content
    assert "Import CSV" in content
    assert "Intake history" in content
    assert "Queue pending profile extraction" in content
