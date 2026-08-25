import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from typing import BinaryIO

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from audit.models import AuditEvent
from audit.services import record_audit_event
from candidates.forms import CandidateCSVRowForm
from candidates.models import Candidate, CandidateDocument, CandidateSource
from organizations.models import Organization
from organizations.permissions import (
    require_organization_access,
    require_organization_admin,
    require_organization_object_access,
)

CSV_HEADERS = (
    "full_name",
    "email",
    "phone",
    "location",
    "source_reference",
    "retention_until",
)
CSV_REQUIRED_HEADERS = frozenset({"full_name"})
DEFAULT_MAX_CSV_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_CSV_ROWS = 2_000


class CandidateImportFileError(ValueError):
    """The CSV cannot be processed as an import file."""


class CandidateDeletionError(RuntimeError):
    """Private candidate content could not be safely removed."""


@dataclass(frozen=True)
class DuplicateMatch:
    candidate: Candidate
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CandidateQuickAddResult:
    candidate: Candidate
    document: CandidateDocument | None


@dataclass(frozen=True)
class CandidateImportRowResult:
    row_number: int
    status: str
    full_name: str
    details: tuple[str, ...] = ()
    candidate_id: int | None = None


@dataclass
class CandidateImportResult:
    rows: list[CandidateImportRowResult] = field(default_factory=list)

    @property
    def created_count(self) -> int:
        return sum(row.status == "created" for row in self.rows)

    @property
    def duplicate_count(self) -> int:
        return sum(row.status == "duplicate" for row in self.rows)

    @property
    def invalid_count(self) -> int:
        return sum(row.status == "invalid" for row in self.rows)

    @property
    def total_count(self) -> int:
        return len(self.rows)


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return digits if len(digits) >= 7 else ""


class CandidateDuplicateFinder:
    """Find organization-local duplicates without using names as identity."""

    def __init__(self, organization: Organization):
        self.organization = organization
        candidates = Candidate.objects.for_organization(organization).prefetch_related(
            "sources"
        )
        self.email_candidates: dict[str, set[int]] = {}
        self.phone_candidates: dict[str, set[int]] = {}
        self.reference_candidates: dict[str, set[int]] = {}
        self.candidates: dict[int, Candidate] = {}

        for candidate in candidates:
            self._index_candidate(candidate)

    @staticmethod
    def _add(index: dict[str, set[int]], key: str, candidate_id: int) -> None:
        if key:
            index.setdefault(key, set()).add(candidate_id)

    def _index_candidate(self, candidate: Candidate) -> None:
        if candidate.pk is None:
            return
        self.candidates[candidate.pk] = candidate
        self._add(self.email_candidates, normalize_email(candidate.email), candidate.pk)
        self._add(self.phone_candidates, normalize_phone(candidate.phone), candidate.pk)
        for source in candidate.sources.all():
            reference = source.source_reference.strip()
            self._add(self.reference_candidates, reference, candidate.pk)

    def find(
        self,
        *,
        email: str = "",
        phone: str = "",
        source_reference: str = "",
    ) -> DuplicateMatch | None:
        identity_matches: list[tuple[str, set[int]]] = []
        normalized_email = normalize_email(email)
        normalized_phone = normalize_phone(phone)
        normalized_reference = source_reference.strip()

        if normalized_email and normalized_email in self.email_candidates:
            identity_matches.append(
                ("email", self.email_candidates[normalized_email].copy())
            )
        if normalized_phone and normalized_phone in self.phone_candidates:
            identity_matches.append(
                ("phone", self.phone_candidates[normalized_phone].copy())
            )
        if normalized_reference and normalized_reference in self.reference_candidates:
            identity_matches.append(
                (
                    "source reference",
                    self.reference_candidates[normalized_reference].copy(),
                )
            )

        if not identity_matches:
            return None

        candidate_ids = set().union(*(matches for _, matches in identity_matches))
        if len(candidate_ids) > 1:
            reasons = tuple(label for label, _ in identity_matches)
            candidate = self.candidates[min(candidate_ids)]
            return DuplicateMatch(
                candidate=candidate,
                reasons=(
                    "conflicting identifiers match more than one existing candidate: "
                    + ", ".join(reasons),
                ),
            )

        candidate_id = candidate_ids.pop()
        reasons = tuple(
            label for label, matches in identity_matches if candidate_id in matches
        )
        return DuplicateMatch(
            candidate=self.candidates[candidate_id],
            reasons=reasons,
        )

    def remember(self, candidate: Candidate, source_reference: str = "") -> None:
        if candidate.pk is None:
            return
        self.candidates[candidate.pk] = candidate
        self._add(self.email_candidates, normalize_email(candidate.email), candidate.pk)
        self._add(self.phone_candidates, normalize_phone(candidate.phone), candidate.pk)
        self._add(
            self.reference_candidates,
            source_reference.strip(),
            candidate.pk,
        )


def create_candidate_with_source(
    *,
    organization: Organization,
    user: User,
    candidate_values: dict,
    source_values: dict,
) -> Candidate:
    require_organization_access(user, organization)
    with transaction.atomic():
        candidate = Candidate(
            organization=organization,
            created_by=user,
            **candidate_values,
        )
        candidate.full_clean()
        candidate.save()

        source = CandidateSource(
            candidate=candidate,
            recorded_by=user,
            **source_values,
        )
        source.full_clean()
        source.save()

    return candidate


@transaction.atomic
def create_candidate_quick_add(
    *,
    organization: Organization,
    user: User,
    candidate_values: dict,
    source_values: dict,
    cv_file=None,
    document_retention_until=None,
) -> CandidateQuickAddResult:
    """Create a minimal candidate and optionally attach one validated CV."""
    candidate = create_candidate_with_source(
        organization=organization,
        user=user,
        candidate_values=candidate_values,
        source_values=source_values,
    )
    document = None
    if cv_file is not None:
        from candidates.documents import upload_candidate_cv

        document = upload_candidate_cv(
            candidate=candidate,
            user=user,
            uploaded_file=cv_file,
            retention_until=document_retention_until,
        )
    return CandidateQuickAddResult(candidate=candidate, document=document)


def _request_candidate_deletion(
    *,
    candidate: Candidate,
    actor: User | None,
    action: str,
) -> Candidate:
    candidate = Candidate.objects.select_for_update().get(pk=candidate.pk)
    if candidate.status == Candidate.Status.DELETED:
        raise ValidationError("This candidate has already been deleted.")
    if candidate.status == Candidate.Status.DELETION_REQUESTED:
        raise ValidationError("Candidate deletion has already been requested.")
    if candidate.status not in {Candidate.Status.ACTIVE, Candidate.Status.INACTIVE}:
        raise ValidationError("This candidate cannot enter deletion review.")

    candidate.status_before_deletion_request = candidate.status
    candidate.status = Candidate.Status.DELETION_REQUESTED
    candidate.deletion_requested_at = timezone.now()
    candidate.deletion_requested_by = actor
    candidate.save(
        update_fields=(
            "status_before_deletion_request",
            "status",
            "deletion_requested_at",
            "deletion_requested_by",
            "updated_at",
        )
    )
    record_audit_event(
        organization=candidate.organization,
        actor=actor,
        action=action,
        object_type=AuditEvent.ObjectType.CANDIDATE,
        object_id=candidate.pk,
        system=actor is None,
    )
    return candidate


@transaction.atomic
def request_candidate_deletion(*, candidate: Candidate, user: User) -> Candidate:
    """Freeze a candidate for explicit later deletion review."""
    require_organization_object_access(user, candidate)
    return _request_candidate_deletion(
        candidate=candidate,
        actor=user,
        action=AuditEvent.Action.CANDIDATE_DELETION_REQUESTED,
    )


@transaction.atomic
def flag_candidate_for_expired_retention(
    *,
    candidate: Candidate,
    as_of: date,
) -> Candidate:
    """System flag for an expired candidate-level retention date; never purge."""
    candidate = Candidate.objects.select_for_update().get(pk=candidate.pk)
    if candidate.retention_until is None or candidate.retention_until > as_of:
        raise ValidationError("Candidate retention has not expired.")
    return _request_candidate_deletion(
        candidate=candidate,
        actor=None,
        action=AuditEvent.Action.CANDIDATE_RETENTION_FLAGGED,
    )


@transaction.atomic
def cancel_candidate_deletion(*, candidate: Candidate, user: User) -> Candidate:
    """Allow an organization administrator to restore a pending candidate."""
    require_organization_admin(user, candidate.organization)
    candidate = Candidate.objects.select_for_update().get(pk=candidate.pk)
    if candidate.status != Candidate.Status.DELETION_REQUESTED:
        raise ValidationError("This candidate has no pending deletion request.")

    restored_status = candidate.status_before_deletion_request
    if restored_status not in {Candidate.Status.ACTIVE, Candidate.Status.INACTIVE}:
        raise ValidationError("The candidate's prior status cannot be restored.")
    candidate.status = restored_status
    candidate.status_before_deletion_request = ""
    candidate.deletion_requested_at = None
    candidate.deletion_requested_by = None
    candidate.save(
        update_fields=(
            "status",
            "status_before_deletion_request",
            "deletion_requested_at",
            "deletion_requested_by",
            "updated_at",
        )
    )
    record_audit_event(
        organization=candidate.organization,
        actor=user,
        action=AuditEvent.Action.CANDIDATE_DELETION_CANCELLED,
        object_type=AuditEvent.ObjectType.CANDIDATE,
        object_id=candidate.pk,
    )
    return candidate


@transaction.atomic
def delete_candidate(*, candidate: Candidate, user: User) -> Candidate:
    """Execute a reviewed purge while retaining a minimized tombstone and event."""
    require_organization_object_access(user, candidate)
    candidate = Candidate.objects.select_for_update().get(pk=candidate.pk)
    if candidate.status == Candidate.Status.DELETED:
        raise ValidationError("This candidate has already been deleted.")
    if candidate.status != Candidate.Status.DELETION_REQUESTED:
        raise ValidationError("Request candidate deletion before executing the purge.")

    documents = list(
        CandidateDocument.objects.select_for_update().filter(candidate=candidate)
    )
    try:
        for document in documents:
            stored_name = document.file.name
            if stored_name:
                document.file.storage.delete(stored_name)
    except Exception as error:
        raise CandidateDeletionError(
            "The private documents could not be removed. "
            "No candidate record was deleted."
        ) from error

    CandidateDocument.objects.filter(candidate=candidate).delete()
    CandidateSource.objects.filter(candidate=candidate).delete()
    from matching.models import CandidateSkill, ShortlistEntry

    CandidateSkill.objects.filter(candidate=candidate).delete()
    ShortlistEntry.objects.filter(candidate=candidate).delete()

    deleted_at = timezone.now()
    candidate.full_name = f"Deleted candidate #{candidate.pk}"
    candidate.email = ""
    candidate.phone = ""
    candidate.location = ""
    candidate.status = Candidate.Status.DELETED
    candidate.retention_until = None
    candidate.deletion_requested_at = candidate.deletion_requested_at or deleted_at
    candidate.deletion_requested_by = None
    candidate.status_before_deletion_request = ""
    candidate.deleted_at = deleted_at
    candidate.save(
        update_fields=(
            "full_name",
            "email",
            "phone",
            "location",
            "status",
            "retention_until",
            "deletion_requested_at",
            "deletion_requested_by",
            "status_before_deletion_request",
            "deleted_at",
            "updated_at",
        )
    )
    record_audit_event(
        organization=candidate.organization,
        actor=user,
        action=AuditEvent.Action.CANDIDATE_DELETED,
        object_type=AuditEvent.ObjectType.CANDIDATE,
        object_id=candidate.pk,
    )
    return candidate


def _read_csv_text(uploaded_file: BinaryIO, max_bytes: int) -> str:
    raw = uploaded_file.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise CandidateImportFileError(
            f"The CSV exceeds the {max_bytes // (1024 * 1024)} MB limit."
        )
    if b"\x00" in raw:
        raise CandidateImportFileError("The CSV contains unsupported null bytes.")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CandidateImportFileError("The CSV must use UTF-8 encoding.") from error


def _validate_headers(fieldnames: list[str] | None) -> tuple[str, ...]:
    if not fieldnames:
        raise CandidateImportFileError("The CSV is empty or has no header row.")
    cleaned = tuple(header.strip() for header in fieldnames)
    if len(cleaned) != len(set(cleaned)):
        raise CandidateImportFileError("The CSV contains duplicate column headers.")

    missing = CSV_REQUIRED_HEADERS.difference(cleaned)
    if missing:
        raise CandidateImportFileError(
            "Missing required column: " + ", ".join(sorted(missing)) + "."
        )

    unsupported = set(cleaned).difference(CSV_HEADERS)
    if unsupported:
        raise CandidateImportFileError(
            "Unsupported column(s): " + ", ".join(sorted(unsupported)) + "."
        )
    return cleaned


def _form_error_details(form: CandidateCSVRowForm) -> tuple[str, ...]:
    details = []
    for field_name, errors in form.errors.items():
        label = "Row" if field_name == "__all__" else field_name.replace("_", " ")
        details.extend(f"{label}: {error}" for error in errors)
    return tuple(details)


def import_candidate_csv(
    *,
    uploaded_file: BinaryIO,
    organization: Organization,
    user: User,
    source_defaults: dict,
    max_bytes: int = DEFAULT_MAX_CSV_BYTES,
    max_rows: int = DEFAULT_MAX_CSV_ROWS,
) -> CandidateImportResult:
    require_organization_access(user, organization)
    text = _read_csv_text(uploaded_file, max_bytes)
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    try:
        headers = _validate_headers(reader.fieldnames)
    except csv.Error as error:
        raise CandidateImportFileError(f"The CSV is malformed: {error}.") from error
    reader.fieldnames = list(headers)
    parsed_rows: list[tuple[int, dict[str, str]]] = []
    try:
        for row_number, raw_row in enumerate(reader, start=2):
            if row_number - 1 > max_rows:
                raise CandidateImportFileError(
                    f"The CSV exceeds the {max_rows:,}-row limit."
                )
            if None in raw_row:
                raise CandidateImportFileError(
                    f"Row {row_number} has more values than the header row."
                )

            row = {header: (raw_row.get(header) or "") for header in headers}
            if not any(value.strip() for value in row.values()):
                continue
            parsed_rows.append((row_number, row))
    except csv.Error as error:
        raise CandidateImportFileError(f"The CSV is malformed: {error}.") from error

    finder = CandidateDuplicateFinder(organization)
    result = CandidateImportResult()
    for row_number, row in parsed_rows:
        display_name = row.get("full_name", "").strip() or "Unnamed row"
        form = CandidateCSVRowForm(row)
        if not form.is_valid():
            result.rows.append(
                CandidateImportRowResult(
                    row_number=row_number,
                    status="invalid",
                    full_name=display_name,
                    details=_form_error_details(form),
                )
            )
            continue

        values = form.cleaned_data
        duplicate = finder.find(
            email=values["email"],
            phone=values["phone"],
            source_reference=values["source_reference"],
        )
        if duplicate:
            result.rows.append(
                CandidateImportRowResult(
                    row_number=row_number,
                    status="duplicate",
                    full_name=values["full_name"],
                    details=duplicate.reasons,
                    candidate_id=duplicate.candidate.pk,
                )
            )
            continue

        candidate_values = {
            "full_name": values["full_name"],
            "email": values["email"],
            "phone": values["phone"],
            "location": values["location"],
            "retention_until": values["retention_until"],
        }
        source_values = {
            **source_defaults,
            "source_reference": values["source_reference"],
        }
        try:
            candidate = create_candidate_with_source(
                organization=organization,
                user=user,
                candidate_values=candidate_values,
                source_values=source_values,
            )
        except ValidationError as error:
            result.rows.append(
                CandidateImportRowResult(
                    row_number=row_number,
                    status="invalid",
                    full_name=values["full_name"],
                    details=tuple(error.messages),
                )
            )
            continue

        finder.remember(candidate, values["source_reference"])
        result.rows.append(
            CandidateImportRowResult(
                row_number=row_number,
                status="created",
                full_name=candidate.full_name,
                candidate_id=candidate.pk,
            )
        )

    return result
