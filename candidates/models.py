from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from organizations.models import Organization, OrganizationScopedQuerySet


def _user_can_query_candidates(user: object) -> bool:
    return bool(
        getattr(user, "is_authenticated", False) and getattr(user, "is_active", False)
    )


class CandidateQuerySet(OrganizationScopedQuerySet):
    def not_deleted(self):
        """Candidates still available in the ordinary recruiter workspace."""
        return self.exclude(status=Candidate.Status.DELETED)


class CandidateRelatedQuerySet(models.QuerySet):
    """Organization scoping for records owned through a candidate."""

    def for_organization(self, organization: Organization):
        return self.filter(candidate__organization=organization)

    def visible_to(self, user: object):
        if not _user_can_query_candidates(user):
            return self.none()

        return self.filter(
            candidate__organization__is_active=True,
            candidate__organization__memberships__user=user,
            candidate__organization__memberships__is_active=True,
        ).distinct()


class Candidate(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        DELETION_REQUESTED = "deletion_requested", "Deletion requested"
        DELETED = "deleted", "Deleted"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="candidates",
    )
    full_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    retention_until = models.DateField(null=True, blank=True)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_candidates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CandidateQuerySet.as_manager()

    class Meta:
        ordering = ("full_name", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "active",
                        "inactive",
                        "deletion_requested",
                        "deleted",
                    ]
                ),
                name="candidate_has_valid_status",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(status="deletion_requested")
                    | models.Q(deletion_requested_at__isnull=False)
                ),
                name="candidate_deletion_request_has_timestamp",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(status="deleted") | models.Q(deleted_at__isnull=False)
                ),
                name="deleted_candidate_has_timestamp",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "status"),
                name="candidate_org_status_idx",
            )
        ]

    def __str__(self) -> str:
        return self.full_name


class CandidateSource(models.Model):
    class SourceType(models.TextChoices):
        MANUAL_ENTRY = "manual_entry", "Manual entry"
        CSV_IMPORT = "csv_import", "CSV import"
        DOCUMENT_UPLOAD = "document_upload", "Document upload"
        ATS_IMPORT = "ats_import", "ATS import"
        REFERRAL = "referral", "Referral"
        OTHER = "other", "Other"

    class LawfulBasis(models.TextChoices):
        NOT_RECORDED = "not_recorded", "Not recorded"
        CONSENT = "consent", "Consent"
        CONTRACT = "contract", "Contract"
        LEGITIMATE_INTERESTS = "legitimate_interests", "Legitimate interests"
        LEGAL_OBLIGATION = "legal_obligation", "Legal obligation"
        OTHER = "other", "Other"

    class ContactPermission(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        PERMITTED = "permitted", "Permitted"
        RESTRICTED = "restricted", "Restricted"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class ConsentStatus(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        NOT_REQUIRED = "not_required", "Not required"
        GRANTED = "granted", "Granted"
        WITHDRAWN = "withdrawn", "Withdrawn"

    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="sources",
    )
    source_type = models.CharField(max_length=30, choices=SourceType.choices)
    source_name = models.CharField(max_length=200)
    source_reference = models.CharField(max_length=500, blank=True)
    obtained_at = models.DateTimeField(null=True, blank=True)
    lawful_basis = models.CharField(
        max_length=30,
        choices=LawfulBasis.choices,
        default=LawfulBasis.NOT_RECORDED,
    )
    consent_status = models.CharField(
        max_length=20,
        choices=ConsentStatus.choices,
        default=ConsentStatus.UNKNOWN,
    )
    contact_permission = models.CharField(
        max_length=20,
        choices=ContactPermission.choices,
        default=ContactPermission.UNKNOWN,
    )
    consent_updated_at = models.DateTimeField(null=True, blank=True)
    permission_notes = models.TextField(blank=True)
    retention_until = models.DateField(null=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_candidate_sources",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CandidateRelatedQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    consent_status__in=[
                        "unknown",
                        "not_required",
                        "granted",
                        "withdrawn",
                    ]
                ),
                name="candidate_source_has_valid_consent_status",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    source_type__in=[
                        "manual_entry",
                        "csv_import",
                        "document_upload",
                        "ats_import",
                        "referral",
                        "other",
                    ]
                ),
                name="candidate_source_has_valid_type",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    lawful_basis__in=[
                        "not_recorded",
                        "consent",
                        "contract",
                        "legitimate_interests",
                        "legal_obligation",
                        "other",
                    ]
                ),
                name="candidate_source_has_valid_lawful_basis",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    contact_permission__in=[
                        "unknown",
                        "permitted",
                        "restricted",
                        "withdrawn",
                    ]
                ),
                name="candidate_source_has_valid_contact_permission",
            ),
        ]

    @property
    def organization(self) -> Organization:
        return self.candidate.organization

    def __str__(self) -> str:
        return f"{self.candidate} — {self.source_name}"


def candidate_document_upload_to(instance: "CandidateDocument", filename: str) -> str:
    """Build a non-public storage key without retaining the supplied basename."""
    suffix = Path(filename).suffix.lower()
    return (
        f"candidate_documents/{instance.candidate.organization_id}/"
        f"{instance.candidate_id}/{instance.storage_key}{suffix}"
    )


class CandidateDocument(models.Model):
    class DocumentType(models.TextChoices):
        CV = "cv", "CV or resume"
        COVER_LETTER = "cover_letter", "Cover letter"
        PORTFOLIO = "portfolio", "Portfolio"
        OTHER = "other", "Other"

    class ExtractionStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(
        max_length=30,
        choices=DocumentType.choices,
        default=DocumentType.CV,
    )
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to=candidate_document_upload_to, max_length=500)
    storage_key = models.UUIDField(default=uuid4, unique=True, editable=False)
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    sha256 = models.CharField(
        max_length=64,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"\A[0-9a-f]{64}\Z",
                message="SHA-256 must contain 64 lowercase hexadecimal characters.",
            )
        ],
    )
    extraction_status = models.CharField(
        max_length=20,
        choices=ExtractionStatus.choices,
        default=ExtractionStatus.PENDING,
    )
    extracted_text = models.TextField(blank=True)
    extracted_at = models.DateTimeField(null=True, blank=True)
    extraction_error_code = models.CharField(max_length=50, blank=True)
    retention_until = models.DateField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_candidate_documents",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CandidateRelatedQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    document_type__in=["cv", "cover_letter", "portfolio", "other"]
                ),
                name="candidate_document_has_valid_type",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    extraction_status__in=["pending", "succeeded", "failed"]
                ),
                name="candidate_document_has_valid_extraction_status",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(extraction_status="succeeded")
                    | (
                        ~models.Q(extracted_text="")
                        & models.Q(extracted_at__isnull=False)
                        & models.Q(extraction_error_code="")
                    )
                ),
                name="candidate_document_success_has_text",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(extraction_status="failed")
                    | (
                        models.Q(extracted_text="")
                        & models.Q(extracted_at__isnull=False)
                        & ~models.Q(extraction_error_code="")
                    )
                ),
                name="candidate_document_failure_has_code",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(extraction_status="pending")
                    | (
                        models.Q(extracted_text="")
                        & models.Q(extracted_at__isnull=True)
                        & models.Q(extraction_error_code="")
                    )
                ),
                name="candidate_document_pending_is_empty",
            ),
        ]
        indexes = [
            models.Index(fields=("sha256",), name="candidate_doc_sha256_idx"),
        ]

    @property
    def organization(self) -> Organization:
        return self.candidate.organization

    def __str__(self) -> str:
        return f"{self.candidate} — {self.original_filename}"
