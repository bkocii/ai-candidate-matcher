import csv
import io
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from django.db import transaction

from accounts.models import User
from candidates.forms import CandidateIntakeCSVRowForm
from candidates.models import CandidateIntakeBatch, CandidateIntakeItem
from organizations.permissions import require_organization_object_access

INTAKE_CSV_HEADERS = (
    "cv_filename",
    "full_name",
    "email",
    "phone",
    "location",
    "source_reference",
)
INTAKE_CSV_REQUIRED_HEADERS = frozenset({"cv_filename", "full_name"})
MAX_INTAKE_CSV_BYTES = 2 * 1024 * 1024
MAX_INTAKE_CSV_ROWS = 2_000


class CandidateIntakeCSVError(ValueError):
    """The CSV cannot be safely mapped to pending intake CVs."""


@dataclass(frozen=True)
class CandidateIntakeMappingRow:
    row_number: int
    cv_filename: str
    status: str
    details: tuple[str, ...] = ()


@dataclass
class CandidateIntakeMappingResult:
    rows: list[CandidateIntakeMappingRow] = field(default_factory=list)

    @property
    def mapped_count(self) -> int:
        return sum(row.status == "mapped" for row in self.rows)

    @property
    def unresolved_count(self) -> int:
        return sum(row.status == "unresolved" for row in self.rows)

    @property
    def invalid_count(self) -> int:
        return sum(row.status == "invalid" for row in self.rows)


def _decode_csv(uploaded_file) -> str:
    raw = uploaded_file.read(MAX_INTAKE_CSV_BYTES + 1)
    if len(raw) > MAX_INTAKE_CSV_BYTES:
        raise CandidateIntakeCSVError("The CSV exceeds the 2 MB limit.")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CandidateIntakeCSVError("The CSV must use UTF-8 encoding.") from error


def _validate_headers(fieldnames: list[str] | None) -> tuple[str, ...]:
    if not fieldnames:
        raise CandidateIntakeCSVError("The CSV is empty or has no header row.")
    headers = tuple(header.strip() for header in fieldnames)
    if any(not header for header in headers):
        raise CandidateIntakeCSVError("CSV column names cannot be blank.")
    if len(set(headers)) != len(headers):
        raise CandidateIntakeCSVError("The CSV contains duplicate column headers.")
    missing = INTAKE_CSV_REQUIRED_HEADERS.difference(headers)
    if missing:
        raise CandidateIntakeCSVError(
            "Missing required column(s): " + ", ".join(sorted(missing)) + "."
        )
    unsupported = set(headers).difference(INTAKE_CSV_HEADERS)
    if unsupported:
        raise CandidateIntakeCSVError(
            "Unsupported column(s): " + ", ".join(sorted(unsupported)) + "."
        )
    return headers


def apply_candidate_intake_csv(
    *, batch: CandidateIntakeBatch, user: User, uploaded_file
) -> CandidateIntakeMappingResult:
    """Apply only exact, one-to-one filename mappings to pending intake CVs."""
    require_organization_object_access(user, batch)
    if batch.status != CandidateIntakeBatch.Status.OPEN:
        raise CandidateIntakeCSVError("This intake batch is no longer open.")

    text = _decode_csv(uploaded_file)
    reader = csv.DictReader(io.StringIO(text, newline=""))
    headers = _validate_headers(reader.fieldnames)
    raw_rows = list(reader)
    if len(raw_rows) > MAX_INTAKE_CSV_ROWS:
        raise CandidateIntakeCSVError(
            f"The CSV exceeds the {MAX_INTAKE_CSV_ROWS:,}-row limit."
        )

    parsed_rows: list[tuple[int, CandidateIntakeCSVRowForm]] = []
    filename_counts: Counter[str] = Counter()
    for row_number, row in enumerate(raw_rows, start=2):
        normalized_row = {header: (row.get(header) or "") for header in headers}
        form = CandidateIntakeCSVRowForm(normalized_row)
        parsed_rows.append((row_number, form))
        filename_counts[normalized_row.get("cv_filename", "").strip()] += 1

    pending_by_filename: dict[str, list[CandidateIntakeItem]] = defaultdict(list)
    for item in batch.items.filter(status=CandidateIntakeItem.Status.PENDING):
        pending_by_filename[item.original_filename].append(item)

    result = CandidateIntakeMappingResult()
    updates: list[tuple[CandidateIntakeItem, dict]] = []
    for row_number, form in parsed_rows:
        if not form.is_valid():
            details = tuple(
                message for messages in form.errors.values() for message in messages
            )
            result.rows.append(
                CandidateIntakeMappingRow(
                    row_number=row_number,
                    cv_filename=form.data.get("cv_filename", "").strip(),
                    status="invalid",
                    details=details,
                )
            )
            continue

        values = form.cleaned_data
        filename = values["cv_filename"]
        if filename_counts[filename] > 1:
            result.rows.append(
                CandidateIntakeMappingRow(
                    row_number=row_number,
                    cv_filename=filename,
                    status="unresolved",
                    details=("The CSV contains this cv_filename more than once.",),
                )
            )
            continue
        matched_items = pending_by_filename.get(filename, [])
        if not matched_items:
            result.rows.append(
                CandidateIntakeMappingRow(
                    row_number=row_number,
                    cv_filename=filename,
                    status="unresolved",
                    details=("No pending CV has this exact filename.",),
                )
            )
            continue
        if len(matched_items) > 1:
            result.rows.append(
                CandidateIntakeMappingRow(
                    row_number=row_number,
                    cv_filename=filename,
                    status="unresolved",
                    details=(
                        "More than one pending CV has this exact filename; rename "
                        "the files and upload them again.",
                    ),
                )
            )
            continue
        updates.append((matched_items[0], values))
        result.rows.append(
            CandidateIntakeMappingRow(
                row_number=row_number,
                cv_filename=filename,
                status="mapped",
            )
        )

    with transaction.atomic():
        locked_batch = CandidateIntakeBatch.objects.select_for_update().get(pk=batch.pk)
        if locked_batch.status != CandidateIntakeBatch.Status.OPEN:
            raise CandidateIntakeCSVError("This intake batch is no longer open.")
        for item, values in updates:
            locked_item = CandidateIntakeItem.objects.select_for_update().get(
                pk=item.pk
            )
            if locked_item.status != CandidateIntakeItem.Status.PENDING:
                raise CandidateIntakeCSVError(
                    "An intake item changed while the CSV was being applied. Try again."
                )
            locked_item.proposed_full_name = values["full_name"]
            locked_item.proposed_email = values["email"]
            locked_item.proposed_phone = values["phone"]
            locked_item.proposed_location = values["location"]
            locked_item.proposed_source_reference = values["source_reference"]
            locked_item.review_flags = []
            locked_item.full_clean()
            locked_item.save(
                update_fields=(
                    "proposed_full_name",
                    "proposed_email",
                    "proposed_phone",
                    "proposed_location",
                    "proposed_source_reference",
                    "review_flags",
                    "updated_at",
                )
            )
    return result
