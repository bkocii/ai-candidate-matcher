import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from candidates.documents import (
    DEFAULT_MAX_DOCUMENT_BYTES,
    CandidateDocumentDuplicateError,
    upload_candidate_cv,
    validate_candidate_cv_upload,
)
from candidates.models import (
    Candidate,
    CandidateDocument,
    CandidateIntakeBatch,
    CandidateIntakeItem,
    CandidateSource,
)
from candidates.services import CandidateDuplicateFinder, create_candidate_with_source
from organizations.models import Organization
from organizations.permissions import (
    require_organization_access,
    require_organization_object_access,
)

MAX_ITEMS_PER_INTAKE_BATCH = 50

EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])",
    re.IGNORECASE,
)
PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+\d{1,3}[\s().-]*)?(?:\d[\s().-]*){6,14}\d(?!\w)"
)
NAME_STOP_WORDS = {
    "candidate",
    "contact",
    "curriculum",
    "cv",
    "developer",
    "engineer",
    "experience",
    "details",
    "profile",
    "resume",
    "skills",
    "synthetic",
    "supplied",
    "vitae",
}
FILENAME_STOP_WORDS = NAME_STOP_WORDS | {"document", "final", "test", "fixture"}


class CandidateIntakeDuplicateError(ValidationError):
    def __init__(self, *, candidate: Candidate, reasons: tuple[str, ...]):
        self.candidate = candidate
        self.reasons = reasons
        reason_text = ", ".join(reasons)
        super().__init__(
            f"Possible duplicate of {candidate.full_name} (matched by "
            f"{reason_text}). No candidate was created."
        )


@dataclass(frozen=True)
class CandidateIdentityProposal:
    full_name: str
    email: str
    phone: str
    location: str
    review_flags: tuple[str, ...]


@dataclass(frozen=True)
class CandidateIntakeCreationResult:
    candidate: Candidate
    document: CandidateDocument


def _unique(values: list[str], *, normalize=str.casefold) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = normalize(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _looks_like_name(value: str) -> bool:
    words = value.split()
    if not 2 <= len(words) <= 6:
        return False
    lowered = {word.casefold().strip(".,:;()[]") for word in words}
    if lowered.intersection(NAME_STOP_WORDS):
        return False
    lowercase_name_particles = {"al", "bin", "da", "de", "der", "van", "von"}
    for word in words:
        cleaned = word.strip(".,:;()[]")
        if not cleaned or any(character.isdigit() for character in cleaned):
            return False
        if not all(
            character.isalpha() or character in {"-", "'", "’"} for character in cleaned
        ):
            return False
        if cleaned.casefold() not in lowercase_name_particles and not (
            cleaned[0].isupper() or cleaned.isupper()
        ):
            return False
    return True


def _name_from_filename(filename: str) -> str:
    stem = PurePosixPath(filename).stem
    words = re.split(r"[_\-\s]+", stem)
    cleaned = [
        word
        for word in words
        if word and word.casefold() not in FILENAME_STOP_WORDS and not word.isdigit()
    ]
    proposal = " ".join(cleaned).strip().title()
    return proposal if _looks_like_name(proposal) else ""


def _phone_candidates(lines: list[str], emails: list[str]) -> list[str]:
    ranked: list[tuple[int, str]] = []
    for index, line in enumerate(lines[:30]):
        without_email = line
        for email in emails:
            without_email = without_email.replace(email, " ")
        lowered = without_email.casefold()
        preferred = bool(
            "+" in without_email
            or "phone" in lowered
            or "mobile" in lowered
            or "tel" in lowered
            or "contact" in lowered
            or "@" in line
        )
        for match in PHONE_PATTERN.finditer(without_email):
            value = match.group(0).strip(" .,-()")
            digits = re.sub(r"\D", "", value)
            if not 7 <= len(digits) <= 15:
                continue
            if not preferred and re.fullmatch(r"\d{4}\s*[-–—]\s*\d{4}", value):
                continue
            ranked.append((index if preferred else index + 100, value))
    return _unique(
        [value for _, value in sorted(ranked)],
        normalize=lambda value: re.sub(r"\D", "", value),
    )


def _location_from_header(
    lines: list[str], *, full_name: str, emails: list[str], phones: list[str]
) -> str:
    separators = re.compile(r"\s*[|•·]\s*")
    for line in lines[:20]:
        if not ("@" in line or any(phone in line for phone in phones)):
            continue
        segments = [segment.strip() for segment in separators.split(line)]
        for segment in reversed(segments):
            if (
                not segment
                or segment == full_name
                or "@" in segment
                or any(phone in segment for phone in phones)
                or any(character.isdigit() for character in segment)
                or len(segment) > 200
            ):
                continue
            if 1 <= len(segment.split()) <= 5:
                return segment
    return ""


def propose_candidate_identity(
    *, text: str, filename: str
) -> CandidateIdentityProposal:
    """Conservatively propose identity locally; never send contact data to AI."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    emails = _unique([match.group(1) for match in EMAIL_PATTERN.finditer(text)])
    phones = _phone_candidates(lines, emails)

    full_name = ""
    name_from_filename = False
    for line in lines[:12]:
        candidate = re.sub(r"\s+", " ", line).strip(" -–—|•·")
        if "@" not in candidate and _looks_like_name(candidate):
            full_name = candidate
            break
    if not full_name:
        full_name = _name_from_filename(filename)
        name_from_filename = bool(full_name)

    location = _location_from_header(
        lines,
        full_name=full_name,
        emails=emails,
        phones=phones,
    )
    flags: list[str] = []
    if not full_name:
        flags.append("name_missing")
    elif name_from_filename:
        flags.append("name_from_filename")
    if not emails:
        flags.append("email_missing")
    elif len(emails) > 1:
        flags.append("multiple_emails")
    if not phones:
        flags.append("phone_missing")
    elif len(phones) > 1:
        flags.append("multiple_phones")
    if not location:
        flags.append("location_missing")

    return CandidateIdentityProposal(
        full_name=full_name,
        email=emails[0] if emails else "",
        phone=phones[0] if phones else "",
        location=location,
        review_flags=tuple(flags),
    )


def create_candidate_intake_batch(
    *, organization: Organization, user: User, values: dict
) -> CandidateIntakeBatch:
    require_organization_access(user, organization)
    batch = CandidateIntakeBatch(
        organization=organization,
        created_by=user,
        **values,
    )
    batch.full_clean()
    batch.save()
    return batch


def upload_candidate_intake_cv(
    *, batch: CandidateIntakeBatch, user: User, uploaded_file
) -> CandidateIntakeItem:
    require_organization_object_access(user, batch)
    validated = validate_candidate_cv_upload(uploaded_file=uploaded_file)
    proposal = propose_candidate_identity(
        text=validated.extracted.text,
        filename=validated.original_filename,
    )
    item = CandidateIntakeItem(
        batch=batch,
        original_filename=validated.original_filename,
        file=ContentFile(validated.raw, name=validated.original_filename),
        content_type=validated.extracted.content_type,
        size_bytes=len(validated.raw),
        sha256=validated.sha256,
        extracted_text=validated.extracted.text,
        proposed_full_name=proposal.full_name,
        proposed_email=proposal.email,
        proposed_phone=proposal.phone,
        proposed_location=proposal.location,
        review_flags=list(proposal.review_flags),
        uploaded_by=user,
    )
    try:
        with transaction.atomic():
            Organization.objects.select_for_update().get(pk=batch.organization_id)
            locked_batch = CandidateIntakeBatch.objects.select_for_update().get(
                pk=batch.pk
            )
            if locked_batch.status != CandidateIntakeBatch.Status.OPEN:
                raise ValidationError("This intake batch is no longer open.")
            if locked_batch.items.count() >= MAX_ITEMS_PER_INTAKE_BATCH:
                raise ValidationError(
                    f"An intake batch can contain at most "
                    f"{MAX_ITEMS_PER_INTAKE_BATCH} CVs."
                )
            duplicate_document = (
                CandidateDocument.objects.for_organization(locked_batch.organization)
                .filter(sha256=validated.sha256, deleted_at__isnull=True)
                .select_related("candidate")
                .first()
            )
            if duplicate_document is not None:
                raise CandidateDocumentDuplicateError(
                    "duplicate_document",
                    "This exact document is already stored for "
                    f"{duplicate_document.candidate.full_name}.",
                )
            if (
                CandidateIntakeItem.objects.for_organization(locked_batch.organization)
                .filter(
                    sha256=validated.sha256,
                    status=CandidateIntakeItem.Status.PENDING,
                )
                .exists()
            ):
                raise CandidateDocumentDuplicateError(
                    "duplicate_intake_document",
                    "This exact document is already awaiting review in an intake "
                    "batch.",
                )
            item.batch = locked_batch
            item.full_clean()
            item.save()
    except Exception:
        stored_name = item.file.name
        if stored_name and stored_name != validated.original_filename:
            item.file.storage.delete(stored_name)
        raise
    return item


def _clear_private_intake_payload(item: CandidateIntakeItem) -> str:
    stored_name = item.file.name
    item.original_filename = ""
    item.file = ""
    item.content_type = ""
    item.size_bytes = None
    item.sha256 = ""
    item.extracted_text = ""
    item.proposed_full_name = ""
    item.proposed_email = ""
    item.proposed_phone = ""
    item.proposed_location = ""
    item.proposed_source_reference = ""
    item.review_flags = []
    return stored_name


def _complete_batch_if_ready(batch: CandidateIntakeBatch) -> None:
    if batch.status != CandidateIntakeBatch.Status.OPEN:
        return
    if batch.items.filter(status=CandidateIntakeItem.Status.PENDING).exists():
        return
    batch.status = CandidateIntakeBatch.Status.COMPLETED
    batch.completed_at = timezone.now()
    batch.save(update_fields=("status", "completed_at", "updated_at"))


def create_candidate_from_intake_item(
    *,
    item: CandidateIntakeItem,
    user: User,
    candidate_values: dict,
    source_reference: str = "",
) -> CandidateIntakeCreationResult:
    require_organization_object_access(user, item)
    created_document: CandidateDocument | None = None
    staging_storage = item.file.storage
    staging_name = ""
    try:
        with transaction.atomic():
            Organization.objects.select_for_update().get(pk=item.organization.pk)
            locked_item = (
                CandidateIntakeItem.objects.select_for_update()
                .select_related("batch__organization")
                .get(pk=item.pk)
            )
            batch = CandidateIntakeBatch.objects.select_for_update().get(
                pk=locked_item.batch_id
            )
            if batch.status != CandidateIntakeBatch.Status.OPEN:
                raise ValidationError("This intake batch is no longer open.")
            if locked_item.status != CandidateIntakeItem.Status.PENDING:
                raise ValidationError("This intake item has already been processed.")

            candidate_values = {
                key: value.strip() if isinstance(value, str) else value
                for key, value in candidate_values.items()
            }
            duplicate = CandidateDuplicateFinder(batch.organization).find(
                email=candidate_values.get("email", ""),
                phone=candidate_values.get("phone", ""),
                source_reference=source_reference,
            )
            if duplicate is not None:
                raise CandidateIntakeDuplicateError(
                    candidate=duplicate.candidate,
                    reasons=duplicate.reasons,
                )

            try:
                with locked_item.file.storage.open(
                    locked_item.file.name, "rb"
                ) as staged_file:
                    raw = staged_file.read(DEFAULT_MAX_DOCUMENT_BYTES + 1)
            except (OSError, ValueError) as error:
                raise ValidationError(
                    "The staged CV is unavailable and no candidate was created."
                ) from error
            if len(raw) > DEFAULT_MAX_DOCUMENT_BYTES:
                raise ValidationError(
                    "The staged CV exceeds the supported size and no candidate was "
                    "created."
                )
            staged_upload = SimpleUploadedFile(
                locked_item.original_filename,
                raw,
                content_type=locked_item.content_type,
            )
            validated = validate_candidate_cv_upload(uploaded_file=staged_upload)
            if (
                len(validated.raw) != locked_item.size_bytes
                or validated.sha256 != locked_item.sha256
            ):
                raise ValidationError(
                    "The staged CV failed its integrity check and no candidate was "
                    "created."
                )

            candidate = create_candidate_with_source(
                organization=batch.organization,
                user=user,
                candidate_values={
                    **candidate_values,
                    "retention_until": batch.candidate_retention_until,
                },
                source_values={
                    "source_type": CandidateSource.SourceType.DOCUMENT_UPLOAD,
                    "source_name": batch.source_name,
                    "source_reference": source_reference.strip(),
                    "lawful_basis": batch.lawful_basis,
                    "consent_status": batch.consent_status,
                    "contact_permission": batch.contact_permission,
                    "permission_notes": batch.permission_notes,
                    "retention_until": batch.source_retention_until,
                },
            )
            staged_upload.seek(0)
            created_document = upload_candidate_cv(
                candidate=candidate,
                user=user,
                uploaded_file=staged_upload,
                retention_until=batch.document_retention_until,
            )

            locked_item.status = CandidateIntakeItem.Status.CREATED
            locked_item.candidate = candidate
            locked_item.processed_by = user
            locked_item.processed_at = timezone.now()
            staging_name = _clear_private_intake_payload(locked_item)
            locked_item.full_clean()
            locked_item.save()
            _complete_batch_if_ready(batch)
            if staging_name:
                transaction.on_commit(lambda: staging_storage.delete(staging_name))
    except Exception:
        if created_document is not None and created_document.file.name:
            created_document.file.storage.delete(created_document.file.name)
        raise

    return CandidateIntakeCreationResult(
        candidate=created_document.candidate,
        document=created_document,
    )


def skip_candidate_intake_item(
    *, item: CandidateIntakeItem, user: User
) -> CandidateIntakeItem:
    require_organization_object_access(user, item)
    storage = item.file.storage
    with transaction.atomic():
        locked_item = (
            CandidateIntakeItem.objects.select_for_update()
            .select_related("batch")
            .get(pk=item.pk)
        )
        batch = CandidateIntakeBatch.objects.select_for_update().get(
            pk=locked_item.batch_id
        )
        if batch.status != CandidateIntakeBatch.Status.OPEN:
            raise ValidationError("This intake batch is no longer open.")
        if locked_item.status != CandidateIntakeItem.Status.PENDING:
            raise ValidationError("This intake item has already been processed.")
        stored_name = _clear_private_intake_payload(locked_item)
        locked_item.status = CandidateIntakeItem.Status.SKIPPED
        locked_item.processed_by = user
        locked_item.processed_at = timezone.now()
        locked_item.full_clean()
        locked_item.save()
        _complete_batch_if_ready(batch)
        if stored_name:
            transaction.on_commit(lambda: storage.delete(stored_name))
    return locked_item


def discard_candidate_intake_batch(
    *, batch: CandidateIntakeBatch, user: User
) -> CandidateIntakeBatch:
    require_organization_object_access(user, batch)
    storage_names: list[tuple[object, str]] = []
    with transaction.atomic():
        batch = CandidateIntakeBatch.objects.select_for_update().get(pk=batch.pk)
        if batch.status != CandidateIntakeBatch.Status.OPEN:
            raise ValidationError("This intake batch is no longer open.")
        pending_items = list(
            batch.items.select_for_update().filter(
                status=CandidateIntakeItem.Status.PENDING
            )
        )
        for item in pending_items:
            storage = item.file.storage
            stored_name = _clear_private_intake_payload(item)
            item.status = CandidateIntakeItem.Status.SKIPPED
            item.processed_by = user
            item.processed_at = timezone.now()
            item.full_clean()
            item.save()
            if stored_name:
                storage_names.append((storage, stored_name))
        batch.status = CandidateIntakeBatch.Status.DISCARDED
        batch.completed_at = timezone.now()
        batch.save(update_fields=("status", "completed_at", "updated_at"))
        for storage, stored_name in storage_names:
            transaction.on_commit(lambda s=storage, n=stored_name: s.delete(n))
    return batch
