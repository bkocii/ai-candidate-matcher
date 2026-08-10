import zipfile
from datetime import date
from io import BytesIO

import pytest
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.urls import reverse
from docx import Document as DocxDocument
from pypdf import PdfWriter

from accounts.models import OrganizationMembership, User
from candidates.documents import (
    DOCX_CONTENT_TYPE,
    CandidateDocumentDuplicateError,
    CandidateDocumentUploadError,
    extract_cv_text,
    upload_candidate_cv,
)
from candidates.models import Candidate, CandidateDocument
from organizations.models import Organization

pytestmark = pytest.mark.django_db


def add_member(user: User, organization: Organization) -> None:
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )


def text_pdf(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    return bytes(pdf)


def docx_bytes(text: str = "Arta Krasniqi — Python and Django") -> bytes:
    document = DocxDocument()
    document.add_heading("Curriculum Vitae", level=1)
    document.add_paragraph(text)
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Experience"
    table.cell(0, 1).text = "Five years"
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def pdf_upload(content: bytes | None = None) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        "candidate.pdf",
        content or text_pdf("Candidate Python Django PostgreSQL"),
        content_type="application/pdf",
    )


def test_extracts_text_from_pdf_and_docx() -> None:
    pdf = extract_cv_text(
        raw=text_pdf("Arta Krasniqi Python Django"),
        filename="arta.pdf",
        declared_content_type="application/pdf",
    )
    docx = extract_cv_text(
        raw=docx_bytes(),
        filename="arta.docx",
        declared_content_type=DOCX_CONTENT_TYPE,
    )

    assert pdf.content_type == "application/pdf"
    assert "Python Django" in pdf.text
    assert docx.content_type == DOCX_CONTENT_TYPE
    assert "Arta Krasniqi" in docx.text
    assert "Five years" in docx.text


@pytest.mark.parametrize(
    ("filename", "content_type", "raw", "code"),
    [
        ("candidate.doc", "application/msword", b"legacy", "unsupported_extension"),
        ("candidate.pdf", "text/plain", b"%PDF-fake", "content_type_mismatch"),
        ("candidate.pdf", "application/pdf", b"not a pdf", "invalid_pdf_signature"),
        (
            "candidate.docx",
            DOCX_CONTENT_TYPE,
            b"not a zip package",
            "invalid_docx_signature",
        ),
    ],
)
def test_rejects_unsupported_mismatched_or_disguised_files(
    filename: str,
    content_type: str,
    raw: bytes,
    code: str,
) -> None:
    with pytest.raises(CandidateDocumentUploadError) as captured:
        extract_cv_text(
            raw=raw,
            filename=filename,
            declared_content_type=content_type,
        )

    assert captured.value.code == code


def test_rejects_encrypted_or_textless_pdf() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("synthetic-password")
    encrypted = BytesIO()
    writer.write(encrypted)

    with pytest.raises(CandidateDocumentUploadError) as captured:
        extract_cv_text(raw=encrypted.getvalue(), filename="private.pdf")
    assert captured.value.code == "encrypted_pdf"

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    blank = BytesIO()
    writer.write(blank)
    with pytest.raises(CandidateDocumentUploadError) as captured:
        extract_cv_text(raw=blank.getvalue(), filename="scan.pdf")
    assert captured.value.code == "no_extractable_text"


def test_pdf_page_and_extracted_text_limits_are_enforced() -> None:
    raw = text_pdf("Candidate text longer than the configured limit")

    with pytest.raises(CandidateDocumentUploadError) as captured:
        extract_cv_text(raw=raw, filename="candidate.pdf", max_pdf_pages=0)
    assert captured.value.code == "too_many_pdf_pages"

    with pytest.raises(CandidateDocumentUploadError) as captured:
        extract_cv_text(raw=raw, filename="candidate.pdf", max_extracted_characters=5)
    assert captured.value.code == "extracted_text_too_large"


def test_docx_archive_expansion_limits_are_enforced() -> None:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", " " * 2_000_000)

    with pytest.raises(CandidateDocumentUploadError) as captured:
        extract_cv_text(
            raw=output.getvalue(),
            filename="candidate.docx",
            max_docx_expanded_bytes=1_000_000,
        )

    assert captured.value.code in {
        "docx_entry_too_large",
        "docx_expansion_too_large",
        "unsafe_docx_compression",
    }


def test_docx_with_entity_declarations_is_rejected() -> None:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr(
            "word/document.xml",
            '<!DOCTYPE document [<!ENTITY cv "private">]><document>&cv;</document>',
        )

    with pytest.raises(CandidateDocumentUploadError) as captured:
        extract_cv_text(raw=output.getvalue(), filename="candidate.docx")

    assert captured.value.code == "unsafe_docx_xml"


def test_upload_stores_private_metadata_hash_and_extracted_text(
    settings,
    tmp_path,
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Arta Krasniqi",
    )

    document = upload_candidate_cv(
        candidate=candidate,
        user=user,
        uploaded_file=SimpleUploadedFile(
            "folder/Arta CV.docx",
            docx_bytes(),
            content_type=DOCX_CONTENT_TYPE,
        ),
        retention_until=date(2027, 8, 10),
    )

    assert document.original_filename == "Arta CV.docx"
    assert document.document_type == CandidateDocument.DocumentType.CV
    assert document.extraction_status == CandidateDocument.ExtractionStatus.SUCCEEDED
    assert "Python and Django" in document.extracted_text
    assert document.extracted_at is not None
    assert document.extraction_error_code == ""
    assert document.size_bytes == len(docx_bytes())
    assert len(document.sha256) == 64
    assert document.uploaded_by == user
    assert document.retention_until == date(2027, 8, 10)
    assert document.file.name.startswith(
        f"candidate_documents/{organization.pk}/{candidate.pk}/"
    )
    assert "Arta" not in document.file.name
    assert document.file.storage.exists(document.file.name)


def test_duplicate_hash_check_is_organization_scoped(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = tmp_path
    user = User.objects.create_user(username="recruiter")
    first = Organization.objects.create(name="First", slug="first")
    second = Organization.objects.create(name="Second", slug="second")
    add_member(user, first)
    add_member(user, second)
    first_candidate = Candidate.objects.create(organization=first, full_name="First")
    second_candidate = Candidate.objects.create(
        organization=second,
        full_name="Second",
    )
    raw = text_pdf("Same synthetic CV")

    upload_candidate_cv(
        candidate=first_candidate,
        user=user,
        uploaded_file=pdf_upload(raw),
    )
    with pytest.raises(CandidateDocumentDuplicateError) as captured:
        upload_candidate_cv(
            candidate=first_candidate,
            user=user,
            uploaded_file=pdf_upload(raw),
        )
    assert captured.value.code == "duplicate_document"

    second_document = upload_candidate_cv(
        candidate=second_candidate,
        user=user,
        uploaded_file=pdf_upload(raw),
    )
    assert second_document.candidate == second_candidate
    assert CandidateDocument.objects.count() == 2


def test_upload_service_requires_membership_before_storing(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = tmp_path
    outsider = User.objects.create_user(username="outsider")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Candidate",
    )

    with pytest.raises(PermissionDenied):
        upload_candidate_cv(
            candidate=candidate,
            user=outsider,
            uploaded_file=pdf_upload(),
        )

    assert not CandidateDocument.objects.exists()
    assert not tmp_path.exists() or not any(tmp_path.rglob("*"))


def test_failed_extraction_does_not_store_file(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = tmp_path
    user = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Candidate",
    )

    with pytest.raises(CandidateDocumentUploadError):
        upload_candidate_cv(
            candidate=candidate,
            user=user,
            uploaded_file=pdf_upload(b"not a pdf"),
        )

    assert not CandidateDocument.objects.exists()
    assert not tmp_path.exists() or not any(tmp_path.rglob("*"))


def test_successful_extraction_requires_text_and_timestamp() -> None:
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Candidate",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CandidateDocument.objects.create(
                candidate=candidate,
                original_filename="candidate.pdf",
                file="candidate_documents/candidate.pdf",
                extraction_status=CandidateDocument.ExtractionStatus.SUCCEEDED,
            )


def test_recruiter_can_upload_cv_and_view_only_safe_metadata(
    client,
    settings,
    tmp_path,
) -> None:
    settings.MEDIA_ROOT = tmp_path
    user = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Arta Krasniqi",
    )
    client.force_login(user)

    response = client.post(
        reverse(
            "candidates:candidate-cv-upload",
            kwargs={
                "organization_slug": organization.slug,
                "candidate_id": candidate.pk,
            },
        ),
        {
            "cv_file": SimpleUploadedFile(
                "arta.docx",
                docx_bytes("PRIVATE-CV-TEXT Python Django"),
                content_type=DOCX_CONTENT_TYPE,
            ),
            "retention_until": "2027-08-10",
        },
    )

    document = CandidateDocument.objects.get()
    assert response.status_code == 302
    assert document.candidate == candidate
    assert "PRIVATE-CV-TEXT" in document.extracted_text

    detail = client.get(response.url)
    content = detail.content.decode()
    assert detail.status_code == 200
    assert "arta.docx" in content
    assert "Succeeded" in content
    assert "PRIVATE-CV-TEXT" not in content
    assert document.file.name not in content


@pytest.mark.parametrize("route_name", ["candidate-detail", "candidate-cv-upload"])
def test_document_routes_hide_cross_organization_candidates(client, route_name) -> None:
    user = User.objects.create_user(username="recruiter")
    visible = Organization.objects.create(name="Visible", slug="visible")
    hidden = Organization.objects.create(name="Hidden", slug="hidden")
    add_member(user, visible)
    hidden_candidate = Candidate.objects.create(
        organization=hidden,
        full_name="Hidden Candidate",
    )
    client.force_login(user)

    response = client.get(
        reverse(
            f"candidates:{route_name}",
            kwargs={
                "organization_slug": hidden.slug,
                "candidate_id": hidden_candidate.pk,
            },
        )
    )

    assert response.status_code == 404
    assert "Hidden Candidate" not in response.content.decode()


def test_upload_view_returns_safe_parser_error(client) -> None:
    user = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_member(user, organization)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Candidate",
    )
    client.force_login(user)

    response = client.post(
        reverse(
            "candidates:candidate-cv-upload",
            kwargs={
                "organization_slug": organization.slug,
                "candidate_id": candidate.pk,
            },
        ),
        {
            "cv_file": SimpleUploadedFile(
                "broken.pdf",
                b"%PDF-malformed parser internals",
                content_type="application/pdf",
            )
        },
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "malformed or cannot be safely read" in content
    assert "parser internals" not in content
    assert not CandidateDocument.objects.exists()


def test_django_admin_cannot_bypass_validated_document_creation(client) -> None:
    superuser = User.objects.create_superuser(
        username="operator",
        password="synthetic-password",
    )
    client.force_login(superuser)

    response = client.get(reverse("admin:candidates_candidatedocument_add"))

    assert response.status_code == 403
