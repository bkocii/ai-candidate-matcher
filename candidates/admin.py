from django.contrib import admin

from candidates.models import Candidate, CandidateDocument, CandidateSource


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
        "created_at",
    )
    list_filter = ("status", "organization")
    search_fields = ("full_name", "email", "phone")
    autocomplete_fields = ("organization", "created_by")
    inlines = (CandidateSourceInline,)


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
