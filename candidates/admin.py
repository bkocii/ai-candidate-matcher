from django.contrib import admin

from candidates.models import (
    Candidate,
    CandidateDocument,
    CandidateIntakeBatch,
    CandidateIntakeItem,
    CandidateProfile,
    CandidateSource,
)


class CandidateSourceInline(admin.TabularInline):
    model = CandidateSource
    extra = 0
    fields = (
        "source_type",
        "source_name",
        "lawful_basis",
        "consent_status",
        "contact_permission",
        "retention_until",
    )


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "organization",
        "email",
        "status",
        "retention_until",
        "deletion_requested_at",
        "created_at",
    )
    list_filter = ("status", "organization")
    search_fields = ("full_name", "email", "phone")
    autocomplete_fields = ("organization", "created_by")
    inlines = (CandidateSourceInline,)

    def has_delete_permission(self, request, obj=None):
        """Require the staged application deletion workflow."""
        return False


@admin.register(CandidateSource)
class CandidateSourceAdmin(admin.ModelAdmin):
    list_display = (
        "candidate",
        "source_type",
        "source_name",
        "lawful_basis",
        "consent_status",
        "contact_permission",
        "created_at",
    )
    list_filter = (
        "source_type",
        "lawful_basis",
        "consent_status",
        "contact_permission",
    )
    search_fields = (
        "candidate__full_name",
        "source_name",
        "source_reference",
    )
    autocomplete_fields = ("candidate", "recorded_by")


@admin.register(CandidateDocument)
class CandidateDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "original_filename",
        "candidate",
        "document_type",
        "content_type",
        "size_bytes",
        "created_at",
    )
    list_filter = ("document_type", "content_type")
    search_fields = ("original_filename", "candidate__full_name", "sha256")
    autocomplete_fields = ("candidate", "uploaded_by")
    exclude = ("file",)
    readonly_fields = (
        "storage_key",
        "content_type",
        "size_bytes",
        "sha256",
        "extraction_status",
        "extracted_text",
        "extracted_at",
        "extraction_error_code",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        """Require the validated recruiter upload service for new documents."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Stored bytes must be removed through the application workflow."""
        return False


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = (
        "candidate",
        "version",
        "status",
        "source_document",
        "created_at",
        "confirmed_at",
    )
    list_filter = ("status", "work_mode_preference")
    search_fields = ("candidate__full_name", "source_document__original_filename")
    autocomplete_fields = (
        "candidate",
        "source_document",
        "created_by",
        "confirmed_by",
    )
    readonly_fields = (
        "candidate",
        "source_document",
        "version",
        "schema_version",
        "status",
        "source_document_sha256",
        "source_text_sha256",
        "relevant_experience_summary",
        "skills",
        "employment_history",
        "location",
        "work_mode_preference",
        "languages",
        "education",
        "certifications",
        "employment_type_preferences",
        "availability",
        "fact_evidence",
        "ambiguities",
        "excluded_sensitive_content_detected",
        "created_by",
        "confirmed_by",
        "confirmed_at",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CandidateIntakeBatch)
class CandidateIntakeBatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "source_name",
        "status",
        "created_by",
        "created_at",
        "completed_at",
    )
    list_filter = ("status", "organization")
    search_fields = ("source_name",)
    readonly_fields = (
        "organization",
        "source_name",
        "lawful_basis",
        "consent_status",
        "contact_permission",
        "permission_notes",
        "candidate_retention_until",
        "source_retention_until",
        "document_retention_until",
        "status",
        "created_by",
        "completed_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CandidateIntakeItem)
class CandidateIntakeItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "batch",
        "status",
        "candidate",
        "accepted_document",
        "uploaded_by",
        "processed_by",
        "created_at",
    )
    list_filter = ("status", "batch__organization")
    search_fields = ("candidate__full_name",)
    readonly_fields = (
        "batch",
        "status",
        "candidate",
        "accepted_document",
        "uploaded_by",
        "processed_by",
        "processed_at",
        "created_at",
        "updated_at",
    )
    exclude = (
        "file",
        "original_filename",
        "storage_key",
        "content_type",
        "size_bytes",
        "sha256",
        "extracted_text",
        "proposed_full_name",
        "proposed_email",
        "proposed_phone",
        "proposed_location",
        "proposed_source_reference",
        "review_flags",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
