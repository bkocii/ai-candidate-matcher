import hashlib

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError

from accounts.models import User
from audit.models import AuditEvent
from audit.services import record_audit_event
from candidates.ai_extraction import (
    CandidateProfileExtraction,
    redact_candidate_contact_data,
    validate_profile_evidence,
)
from candidates.models import (
    Candidate,
    CandidateDocument,
    CandidateProfile,
    CandidateSource,
)
from candidates.services import CandidateDuplicateFinder
from organizations.permissions import require_organization_object_access


def _ensure_candidate_editable(candidate: Candidate) -> None:
    if candidate.status in {
        Candidate.Status.DELETION_REQUESTED,
        Candidate.Status.DELETED,
    }:
        raise ValidationError("Candidate data cannot be edited during deletion.")


@transaction.atomic
def update_candidate_record(
    *, candidate: Candidate, user: User, values: dict
) -> Candidate:
    require_organization_object_access(user, candidate)
    candidate = Candidate.objects.select_for_update().get(pk=candidate.pk)
    _ensure_candidate_editable(candidate)
    duplicate = CandidateDuplicateFinder(
        candidate.organization,
        exclude_candidate_id=candidate.pk,
    ).find(email=values.get("email", ""), phone=values.get("phone", ""))
    if duplicate is not None:
        raise ValidationError(
            "Possible duplicate of "
            f"{duplicate.candidate.full_name} (matched by "
            f"{', '.join(duplicate.reasons)}). No changes were saved."
        )
    for field, value in values.items():
        setattr(candidate, field, value)
    candidate.full_clean()
    candidate.save()
    record_audit_event(
        organization=candidate.organization,
        actor=user,
        action=AuditEvent.Action.CANDIDATE_UPDATED,
        object_type=AuditEvent.ObjectType.CANDIDATE,
        object_id=candidate.pk,
    )
    return candidate


@transaction.atomic
def update_candidate_source(
    *, source: CandidateSource, user: User, values: dict
) -> CandidateSource:
    require_organization_object_access(user, source)
    source = (
        CandidateSource.objects.select_for_update()
        .select_related("candidate__organization")
        .get(pk=source.pk)
    )
    _ensure_candidate_editable(source.candidate)
    duplicate = CandidateDuplicateFinder(
        source.organization,
        exclude_candidate_id=source.candidate_id,
    ).find(source_reference=values.get("source_reference", ""))
    if duplicate is not None:
        raise ValidationError(
            "This source reference belongs to another candidate. No changes were saved."
        )
    previous_consent = source.consent_status
    for field, value in values.items():
        setattr(source, field, value)
    if source.consent_status != previous_consent:
        source.consent_updated_at = timezone.now()
    source.full_clean()
    source.save()
    record_audit_event(
        organization=source.organization,
        actor=user,
        action=AuditEvent.Action.CANDIDATE_SOURCE_UPDATED,
        object_type=AuditEvent.ObjectType.CANDIDATE_SOURCE,
        object_id=source.pk,
    )
    return source


def _profile_output(
    *, profile: CandidateProfile, values: dict
) -> CandidateProfileExtraction:
    retained_indices = {int(value) for value in values["retained_skills"]}
    payload = {
        "relevant_experience_summary": values["relevant_experience_summary"],
        "relevant_experience_summary_evidence": values[
            "relevant_experience_summary_evidence"
        ],
        "skills": [
            skill
            for index, skill in enumerate(profile.skills)
            if index in retained_indices
        ],
        "employment_history": profile.employment_history,
        "location": values["location"],
        "location_evidence": values["location_evidence"],
        "work_mode_preference": values["work_mode_preference"],
        "work_mode_preference_evidence": values["work_mode_preference_evidence"],
        "languages": profile.languages,
        "education": profile.education,
        "certifications": profile.certifications,
        "employment_type_preferences": profile.employment_type_preferences,
        "employment_type_preferences_evidence": profile.fact_evidence.get(
            "employment_type_preferences", ""
        ),
        "availability": values["availability"],
        "availability_evidence": values["availability_evidence"],
        "ambiguities": values["ambiguities"],
        "excluded_sensitive_content_detected": (
            profile.excluded_sensitive_content_detected
        ),
    }
    try:
        return CandidateProfileExtraction.model_validate(payload)
    except PydanticValidationError as error:
        raise ValidationError(
            "The corrected profile is incomplete or invalid. Check each fact and "
            "its CV evidence."
        ) from error


@transaction.atomic
def create_corrected_profile_version(
    *, profile: CandidateProfile, user: User, values: dict
) -> CandidateProfile:
    require_organization_object_access(user, profile)
    profile = (
        CandidateProfile.objects.select_for_update()
        .select_related("candidate__organization", "source_document")
        .get(pk=profile.pk)
    )
    candidate = Candidate.objects.select_for_update().get(pk=profile.candidate_id)
    _ensure_candidate_editable(candidate)
    document = CandidateDocument.objects.select_for_update().get(
        pk=profile.source_document_id
    )
    source_text_sha256 = hashlib.sha256(document.extracted_text.encode()).hexdigest()
    if (
        document.deleted_at is not None
        or document.extraction_status != CandidateDocument.ExtractionStatus.SUCCEEDED
        or document.sha256 != profile.source_document_sha256
        or source_text_sha256 != profile.source_text_sha256
    ):
        raise ValidationError(
            "The source CV changed after this profile was created. Extract a new "
            "profile instead."
        )
    output = _profile_output(profile=profile, values=values)
    sanitized_source = redact_candidate_contact_data(
        candidate=candidate,
        text=document.extracted_text,
    ).strip()
    validate_profile_evidence(output=output, sanitized_source=sanitized_source)
    next_version = (
        candidate.profile_versions.aggregate(latest=Max("version"))["latest"] or 0
    ) + 1
    corrected = CandidateProfile.objects.create(
        candidate=candidate,
        source_document=document,
        version=next_version,
        schema_version=profile.schema_version,
        source_document_sha256=document.sha256,
        source_text_sha256=source_text_sha256,
        created_by=user,
        **output.as_profile_values(),
    )
    record_audit_event(
        organization=candidate.organization,
        actor=user,
        action=AuditEvent.Action.CANDIDATE_PROFILE_CORRECTED,
        object_type=AuditEvent.ObjectType.CANDIDATE_PROFILE,
        object_id=corrected.pk,
    )
    return corrected
