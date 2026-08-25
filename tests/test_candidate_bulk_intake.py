from datetime import date
from io import BytesIO

import pytest
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from docx import Document as DocxDocument

from accounts.models import OrganizationMembership, User
from candidates.bulk_intake import (
    CandidateIntakeDuplicateError,
    create_candidate_from_intake_item,
    create_candidate_intake_batch,
    discard_candidate_intake_batch,
    propose_candidate_identity,
    skip_candidate_intake_item,
    upload_candidate_intake_cv,
)
from candidates.documents import (
    DOCX_CONTENT_TYPE,
    CandidateDocumentDuplicateError,
    upload_candidate_cv,
)
from candidates.forms import CandidateIntakeUploadForm
from candidates.models import (
    Candidate,
    CandidateDocument,
    CandidateIntakeBatch,
    CandidateIntakeItem,
    CandidateSource,
)
from operations.models import BackgroundJob, BackgroundTask
from operations.services import queue_candidate_profile_documents
from organizations.models import Organization

pytestmark = pytest.mark.django_db


def add_member(user: User, organization: Organization) -> None:
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )


def docx_bytes(text: str) -> bytes:
    document = DocxDocument()
    for line in text.splitlines():
        document.add_paragraph(line)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def cv_upload(
    *,
    name: str = "arben-testi.docx",
    text: str = (
        "Arben Testi\n"
        "arben.testi@example.test | +383 44 111 222 | Prishtina\n"
        "Senior Python Developer\n"
        "Built Django services and pytest suites."
    ),
) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name,
        docx_bytes(text),
        content_type=DOCX_CONTENT_TYPE,
    )


def batch_values() -> dict:
    return {
        "source_name": "Synthetic CV folder",
        "lawful_basis": CandidateSource.LawfulBasis.LEGITIMATE_INTERESTS,
        "consent_status": CandidateSource.ConsentStatus.NOT_REQUIRED,
        "contact_permission": CandidateSource.ContactPermission.UNKNOWN,
        "permission_notes": "Synthetic test records only.",
        "candidate_retention_until": date(2027, 8, 17),
        "source_retention_until": date(2027, 8, 17),
        "document_retention_until": date(2027, 8, 17),
    }


def setup_batch() -> tuple[User, Organization, CandidateIntakeBatch]:
    user = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    batch = create_candidate_intake_batch(
        organization=organization,
        user=user,
        values=batch_values(),
    )
    return user, organization, batch


def test_local_identity_proposal_is_conservative_and_flags_filename_fallback() -> None:
    proposal = propose_candidate_identity(
        text=(
            "Arben Testi\n"
            "arben.testi@example.test | +383 44 111 222 | Prishtina\n"
            "Senior Python Developer"
        ),
        filename="synthetic-arben-testi-cv.docx",
    )

    assert proposal.full_name == "Arben Testi"
    assert proposal.email == "arben.testi@example.test"
    assert proposal.phone == "+383 44 111 222"
    assert proposal.location == "Prishtina"
    assert proposal.review_flags == ()

    fallback = propose_candidate_identity(
        text="Python and Django experience\nno contact details supplied",
        filename="amina-berisha-cv.docx",
    )
    assert fallback.full_name == "Amina Berisha"
    assert "name_from_filename" in fallback.review_flags
    assert "email_missing" in fallback.review_flags
    assert "phone_missing" in fallback.review_flags


def test_multi_file_upload_isolates_invalid_file_and_keeps_private_review_item(
    client, settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user, organization, batch = setup_batch()
    client.force_login(user)
    invalid = SimpleUploadedFile(
        "unsafe.pdf",
        b"not a pdf",
        content_type="application/pdf",
    )

    response = client.post(
        reverse(
            "candidates:candidate-intake-upload",
            args=[organization.slug, batch.pk],
        ),
        {"cv_files": [cv_upload(), invalid]},
        follow=True,
    )

    assert response.status_code == 200
    assert CandidateIntakeItem.objects.count() == 1
    item = CandidateIntakeItem.objects.get()
    assert item.status == CandidateIntakeItem.Status.PENDING
    assert item.proposed_full_name == "Arben Testi"
    assert item.proposed_email == "arben.testi@example.test"
    assert item.file.storage.exists(item.file.name)
    assert "Added 1 CV(s)" in response.content.decode()
    assert "1 file(s) were rejected" in response.content.decode()
    assert "not a pdf" not in item.extracted_text


def test_batch_creation_and_review_page_are_tenant_safe_and_hide_source_text(
    client, settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    client.force_login(user)

    response = client.post(
        reverse("candidates:candidate-intake-create", args=[organization.slug]),
        batch_values(),
    )

    assert response.status_code == 302
    batch = CandidateIntakeBatch.objects.get()
    assert batch.created_by == user
    item = upload_candidate_intake_cv(
        batch=batch,
        user=user,
        uploaded_file=cv_upload(),
    )
    response = client.get(
        reverse(
            "candidates:candidate-intake-detail",
            args=[organization.slug, batch.pk],
        )
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert item.original_filename in content
    assert "Arben Testi" in content
    assert "Built Django services and pytest suites" not in content
    assert item.file.name not in content


def test_upload_form_bounds_file_count_and_combined_request_size() -> None:
    too_many = CandidateIntakeUploadForm(
        files={
            "cv_files": [
                SimpleUploadedFile(f"candidate-{index}.pdf", b"x")
                for index in range(11)
            ]
        }
    )
    assert not too_many.is_valid()
    assert "no more than 10" in too_many.errors["cv_files"][0]

    oversized = CandidateIntakeUploadForm(
        files={
            "cv_files": [SimpleUploadedFile("large.pdf", b"x" * (10 * 1024 * 1024 + 1))]
        }
    )
    assert not oversized.is_valid()
    assert "combined upload exceeds" in oversized.errors["cv_files"][0]


def test_selected_review_creates_candidate_source_document_and_targeted_job(
    client, settings, tmp_path, django_capture_on_commit_callbacks
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user, organization, batch = setup_batch()
    item = upload_candidate_intake_cv(
        batch=batch,
        user=user,
        uploaded_file=cv_upload(),
    )
    staging_name = item.file.name
    staging_storage = item.file.storage
    client.force_login(user)

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            reverse(
                "candidates:candidate-intake-create-selected",
                args=[organization.slug, batch.pk],
            ),
            {
                f"item-{item.pk}-selected": "on",
                f"item-{item.pk}-full_name": "Arben Testi",
                f"item-{item.pk}-email": "arben.testi@example.test",
                f"item-{item.pk}-phone": "+383 44 111 222",
                f"item-{item.pk}-location": "Prishtina",
                f"item-{item.pk}-source_reference": "folder-001",
                "queue_profiles": "on",
            },
        )

    assert response.status_code == 302
    candidate = Candidate.objects.get()
    source = candidate.sources.get()
    document = candidate.documents.get()
    item.refresh_from_db()
    batch.refresh_from_db()
    assert candidate.full_name == "Arben Testi"
    assert candidate.retention_until == date(2027, 8, 17)
    assert source.source_type == CandidateSource.SourceType.DOCUMENT_UPLOAD
    assert source.source_name == "Synthetic CV folder"
    assert source.source_reference == "folder-001"
    assert source.lawful_basis == CandidateSource.LawfulBasis.LEGITIMATE_INTERESTS
    assert document.extraction_status == CandidateDocument.ExtractionStatus.SUCCEEDED
    assert document.retention_until == date(2027, 8, 17)
    assert item.status == CandidateIntakeItem.Status.CREATED
    assert item.candidate == candidate
    assert item.accepted_document == document
    assert item.file.name == ""
    assert item.extracted_text == ""
    assert item.proposed_email == ""
    assert not staging_storage.exists(staging_name)
    assert batch.status == CandidateIntakeBatch.Status.COMPLETED

    job = BackgroundJob.objects.get()
    task = job.tasks.get()
    assert job.workflow == BackgroundJob.Workflow.CANDIDATE_PROFILE_BATCH
    assert task.target_type == BackgroundTask.TargetType.CANDIDATE_DOCUMENT
    assert task.target_id == document.pk
    assert not candidate.profile_versions.exists()

    repeated = queue_candidate_profile_documents(
        organization=organization,
        user=user,
        document_ids=[document.pk],
    )
    assert repeated.job == job
    assert not repeated.created
    assert BackgroundJob.objects.count() == 1


def test_identity_duplicate_blocks_creation_and_preserves_pending_review(
    settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user, organization, batch = setup_batch()
    existing = Candidate.objects.create(
        organization=organization,
        full_name="Existing Candidate",
        email="same@example.test",
    )
    item = upload_candidate_intake_cv(
        batch=batch,
        user=user,
        uploaded_file=cv_upload(
            name="new-version.docx",
            text=(
                "Different Person\n"
                "same@example.test | +383 44 999 999 | Peja\n"
                "Python experience"
            ),
        ),
    )

    with pytest.raises(CandidateIntakeDuplicateError) as captured:
        create_candidate_from_intake_item(
            item=item,
            user=user,
            candidate_values={
                "full_name": "Different Person",
                "email": "same@example.test",
                "phone": "+383 44 999 999",
                "location": "Peja",
            },
        )

    assert captured.value.candidate == existing
    assert Candidate.objects.count() == 1
    item.refresh_from_db()
    assert item.status == CandidateIntakeItem.Status.PENDING
    assert item.file.name
    assert item.extracted_text


def test_exact_document_duplicate_is_rejected_before_intake_persistence(
    settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user, organization, batch = setup_batch()
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Existing Candidate",
    )
    upload_candidate_cv(
        candidate=candidate,
        user=user,
        uploaded_file=cv_upload(),
    )

    with pytest.raises(CandidateDocumentDuplicateError):
        upload_candidate_intake_cv(
            batch=batch,
            user=user,
            uploaded_file=cv_upload(),
        )

    assert not batch.items.exists()


def test_skipping_or_discarding_clears_temporary_private_data(
    settings, tmp_path, django_capture_on_commit_callbacks
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user, _, batch = setup_batch()
    first = upload_candidate_intake_cv(
        batch=batch,
        user=user,
        uploaded_file=cv_upload(name="first.docx"),
    )
    first_storage = first.file.storage
    first_name = first.file.name

    with django_capture_on_commit_callbacks(execute=True):
        skip_candidate_intake_item(item=first, user=user)

    first.refresh_from_db()
    batch.refresh_from_db()
    assert first.status == CandidateIntakeItem.Status.SKIPPED
    assert first.file.name == ""
    assert first.extracted_text == ""
    assert first.review_flags == []
    assert not first_storage.exists(first_name)
    assert batch.status == CandidateIntakeBatch.Status.COMPLETED

    second_batch = create_candidate_intake_batch(
        organization=batch.organization,
        user=user,
        values=batch_values(),
    )
    second = upload_candidate_intake_cv(
        batch=second_batch,
        user=user,
        uploaded_file=cv_upload(name="second.docx"),
    )
    second_name = second.file.name
    second_storage = second.file.storage

    with django_capture_on_commit_callbacks(execute=True):
        discard_candidate_intake_batch(batch=second_batch, user=user)

    second.refresh_from_db()
    second_batch.refresh_from_db()
    assert second.status == CandidateIntakeItem.Status.SKIPPED
    assert second.extracted_text == ""
    assert not second_storage.exists(second_name)
    assert second_batch.status == CandidateIntakeBatch.Status.DISCARDED


def test_intake_routes_and_services_are_tenant_scoped(
    client, settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    owner = User.objects.create_user(username="owner")
    outsider = User.objects.create_user(username="outsider")
    organization = Organization.objects.create(name="Owner", slug="owner")
    hidden = Organization.objects.create(name="Hidden", slug="hidden")
    add_member(owner, organization)
    add_member(outsider, hidden)
    batch = create_candidate_intake_batch(
        organization=organization,
        user=owner,
        values=batch_values(),
    )

    client.force_login(outsider)
    response = client.get(
        reverse(
            "candidates:candidate-intake-detail",
            args=[hidden.slug, batch.pk],
        )
    )
    assert response.status_code == 404

    with pytest.raises(PermissionDenied):
        upload_candidate_intake_cv(
            batch=batch,
            user=outsider,
            uploaded_file=cv_upload(),
        )

    assert not CandidateIntakeItem.objects.exists()
