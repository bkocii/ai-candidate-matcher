import hashlib
import zipfile
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import PurePosixPath

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from docx import Document as DocxDocument
from pypdf import PdfReader

from accounts.models import User
from candidates.models import Candidate, CandidateDocument
from organizations.permissions import require_organization_object_access

DEFAULT_MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_PDF_PAGES = 100
DEFAULT_MAX_DOCX_ENTRIES = 2_000
DEFAULT_MAX_DOCX_EXPANDED_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_DOCX_ENTRY_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_EXTRACTED_CHARACTERS = 1_000_000
MAX_DOCX_COMPRESSION_RATIO = 1_000

PDF_CONTENT_TYPE = "application/pdf"
DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
GENERIC_UPLOAD_CONTENT_TYPES = {"", "application/octet-stream"}


class CandidateDocumentUploadError(ValueError):
    """A safe, recruiter-visible CV upload failure."""

    def __init__(self, code: str, public_message: str):
        self.code = code
        self.public_message = public_message
        super().__init__(public_message)


class CandidateDocumentDuplicateError(CandidateDocumentUploadError):
    """The organization already stores the exact document bytes."""


@dataclass(frozen=True)
class ExtractedCV:
    text: str
    content_type: str
    extension: str


def _safe_original_filename(filename: str) -> str:
    cleaned = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1].strip()
    if not cleaned or any(ord(character) < 32 for character in cleaned):
        raise CandidateDocumentUploadError(
            "invalid_filename",
            "The uploaded document must have a valid filename.",
        )
    if len(cleaned) > 255:
        raise CandidateDocumentUploadError(
            "filename_too_long",
            "The uploaded filename is longer than 255 characters.",
        )
    return cleaned


def _read_bounded(uploaded_file, max_bytes: int) -> bytes:
    raw = uploaded_file.read(max_bytes + 1)
    if not raw:
        raise CandidateDocumentUploadError(
            "empty_file",
            "The uploaded document is empty.",
        )
    if len(raw) > max_bytes:
        raise CandidateDocumentUploadError(
            "file_too_large",
            f"The document exceeds the {max_bytes // (1024 * 1024)} MB limit.",
        )
    return raw


def _normalize_extracted_text(text: str, max_characters: int) -> str:
    normalized = "\n".join(
        line.rstrip() for line in text.replace("\x00", "").splitlines()
    ).strip()
    if not normalized:
        raise CandidateDocumentUploadError(
            "no_extractable_text",
            "No readable text was found. Scanned-image CVs are not supported yet.",
        )
    if len(normalized) > max_characters:
        raise CandidateDocumentUploadError(
            "extracted_text_too_large",
            "The extracted document text exceeds the supported limit.",
        )
    return normalized


def _extract_pdf_text(
    raw: bytes,
    *,
    max_pages: int,
    max_characters: int,
) -> str:
    if not raw.startswith(b"%PDF-"):
        raise CandidateDocumentUploadError(
            "invalid_pdf_signature",
            "The file content is not a valid PDF document.",
        )

    try:
        reader = PdfReader(BytesIO(raw), strict=True)
        if reader.is_encrypted:
            raise CandidateDocumentUploadError(
                "encrypted_pdf",
                "Password-protected or encrypted PDF files are not supported.",
            )
        if len(reader.pages) > max_pages:
            raise CandidateDocumentUploadError(
                "too_many_pdf_pages",
                f"The PDF exceeds the {max_pages}-page limit.",
            )

        parts: list[str] = []
        character_count = 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            character_count += len(page_text)
            if character_count > max_characters:
                raise CandidateDocumentUploadError(
                    "extracted_text_too_large",
                    "The extracted document text exceeds the supported limit.",
                )
            parts.append(page_text)
    except CandidateDocumentUploadError:
        raise
    except Exception as error:
        raise CandidateDocumentUploadError(
            "invalid_pdf",
            "The PDF is malformed or cannot be safely read.",
        ) from error

    return _normalize_extracted_text("\n".join(parts), max_characters)


def _validate_docx_archive(
    raw: bytes,
    *,
    max_entries: int,
    max_expanded_bytes: int,
    max_entry_bytes: int,
) -> None:
    if not zipfile.is_zipfile(BytesIO(raw)):
        raise CandidateDocumentUploadError(
            "invalid_docx_signature",
            "The file content is not a valid DOCX document.",
        )

    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > max_entries:
                raise CandidateDocumentUploadError(
                    "docx_too_many_entries",
                    "The DOCX package contains too many internal files.",
                )

            names = {entry.filename for entry in entries}
            required = {"[Content_Types].xml", "word/document.xml"}
            if not required.issubset(names):
                raise CandidateDocumentUploadError(
                    "invalid_docx_package",
                    "The DOCX package is missing required document content.",
                )

            expanded_size = 0
            for entry in entries:
                normalized_name = entry.filename.replace("\\", "/")
                path = PurePosixPath(normalized_name)
                if path.is_absolute() or ".." in path.parts:
                    raise CandidateDocumentUploadError(
                        "unsafe_docx_path",
                        "The DOCX package contains an unsafe internal path.",
                    )
                if entry.flag_bits & 0x1:
                    raise CandidateDocumentUploadError(
                        "encrypted_docx",
                        "Encrypted DOCX files are not supported.",
                    )
                if entry.file_size > max_entry_bytes:
                    raise CandidateDocumentUploadError(
                        "docx_entry_too_large",
                        "The DOCX package contains an oversized internal file.",
                    )
                expanded_size += entry.file_size
                if expanded_size > max_expanded_bytes:
                    raise CandidateDocumentUploadError(
                        "docx_expansion_too_large",
                        "The expanded DOCX package exceeds the supported limit.",
                    )
                if (
                    entry.file_size > 1_000_000
                    and entry.file_size
                    > max(entry.compress_size, 1) * MAX_DOCX_COMPRESSION_RATIO
                ):
                    raise CandidateDocumentUploadError(
                        "unsafe_docx_compression",
                        "The DOCX package has an unsafe compression ratio.",
                    )

            if any(name.lower().endswith("vbaproject.bin") for name in names):
                raise CandidateDocumentUploadError(
                    "macro_enabled_document",
                    "Macro-enabled Word documents are not supported.",
                )
            if archive.testzip() is not None:
                raise CandidateDocumentUploadError(
                    "corrupt_docx",
                    "The DOCX package is corrupted.",
                )
            for entry in entries:
                lowered_name = entry.filename.lower()
                if not lowered_name.endswith((".xml", ".rels")):
                    continue
                xml_content = archive.read(entry)
                lowered_content = xml_content.lower()
                if b"<!doctype" in lowered_content or b"<!entity" in lowered_content:
                    raise CandidateDocumentUploadError(
                        "unsafe_docx_xml",
                        "The DOCX package contains unsupported XML declarations.",
                    )
    except CandidateDocumentUploadError:
        raise
    except Exception as error:
        raise CandidateDocumentUploadError(
            "invalid_docx",
            "The DOCX file is malformed or cannot be safely read.",
        ) from error


def _extract_docx_text(raw: bytes, *, max_characters: int) -> str:
    try:
        document = DocxDocument(BytesIO(raw))
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.extend(cell.text for cell in row.cells)
    except Exception as error:
        raise CandidateDocumentUploadError(
            "invalid_docx",
            "The DOCX file is malformed or cannot be safely read.",
        ) from error

    return _normalize_extracted_text("\n".join(parts), max_characters)


def extract_cv_text(
    *,
    raw: bytes,
    filename: str,
    declared_content_type: str = "",
    max_pdf_pages: int = DEFAULT_MAX_PDF_PAGES,
    max_docx_entries: int = DEFAULT_MAX_DOCX_ENTRIES,
    max_docx_expanded_bytes: int = DEFAULT_MAX_DOCX_EXPANDED_BYTES,
    max_docx_entry_bytes: int = DEFAULT_MAX_DOCX_ENTRY_BYTES,
    max_extracted_characters: int = DEFAULT_MAX_EXTRACTED_CHARACTERS,
) -> ExtractedCV:
    original_filename = _safe_original_filename(filename)
    extension = PurePosixPath(original_filename).suffix.lower()
    content_type = (
        (declared_content_type or "").split(";", maxsplit=1)[0].strip().lower()
    )

    if extension == ".pdf":
        allowed_types = GENERIC_UPLOAD_CONTENT_TYPES | {PDF_CONTENT_TYPE}
        if content_type not in allowed_types:
            raise CandidateDocumentUploadError(
                "content_type_mismatch",
                "The declared file type does not match a PDF document.",
            )
        text = _extract_pdf_text(
            raw,
            max_pages=max_pdf_pages,
            max_characters=max_extracted_characters,
        )
        return ExtractedCV(
            text=text,
            content_type=PDF_CONTENT_TYPE,
            extension=extension,
        )

    if extension == ".docx":
        allowed_types = GENERIC_UPLOAD_CONTENT_TYPES | {DOCX_CONTENT_TYPE}
        if content_type not in allowed_types:
            raise CandidateDocumentUploadError(
                "content_type_mismatch",
                "The declared file type does not match a DOCX document.",
            )
        _validate_docx_archive(
            raw,
            max_entries=max_docx_entries,
            max_expanded_bytes=max_docx_expanded_bytes,
            max_entry_bytes=max_docx_entry_bytes,
        )
        text = _extract_docx_text(raw, max_characters=max_extracted_characters)
        return ExtractedCV(
            text=text,
            content_type=DOCX_CONTENT_TYPE,
            extension=extension,
        )

    raise CandidateDocumentUploadError(
        "unsupported_extension",
        "Only PDF and DOCX CV files are supported.",
    )


def upload_candidate_cv(
    *,
    candidate: Candidate,
    user: User,
    uploaded_file,
    retention_until: date | None = None,
    max_bytes: int = DEFAULT_MAX_DOCUMENT_BYTES,
) -> CandidateDocument:
    require_organization_object_access(user, candidate)
    original_filename = _safe_original_filename(getattr(uploaded_file, "name", ""))
    raw = _read_bounded(uploaded_file, max_bytes)
    extracted = extract_cv_text(
        raw=raw,
        filename=original_filename,
        declared_content_type=getattr(uploaded_file, "content_type", ""),
    )
    digest = hashlib.sha256(raw).hexdigest()
    duplicate = (
        CandidateDocument.objects.for_organization(candidate.organization)
        .filter(sha256=digest, deleted_at__isnull=True)
        .select_related("candidate")
        .first()
    )
    if duplicate:
        raise CandidateDocumentDuplicateError(
            "duplicate_document",
            "This exact document is already stored for "
            f"{duplicate.candidate.full_name}.",
        )

    document = CandidateDocument(
        candidate=candidate,
        document_type=CandidateDocument.DocumentType.CV,
        original_filename=original_filename,
        file=ContentFile(raw, name=original_filename),
        content_type=extracted.content_type,
        size_bytes=len(raw),
        sha256=digest,
        extraction_status=CandidateDocument.ExtractionStatus.SUCCEEDED,
        extracted_text=extracted.text,
        extracted_at=timezone.now(),
        retention_until=retention_until,
        uploaded_by=user,
    )

    try:
        with transaction.atomic():
            document.full_clean()
            document.save()
    except Exception:
        stored_name = document.file.name
        if stored_name and stored_name != original_filename:
            document.file.storage.delete(stored_name)
        raise

    return document
