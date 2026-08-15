from dataclasses import dataclass
from datetime import date

from audit.models import AIUsageEvent, AuditEvent
from candidates.models import Candidate, CandidateDocument, CandidateSource
from matching.models import (
    CandidateSkill,
    MatchAssessment,
    ReviewDecision,
    ShortlistEntry,
)
from organizations.models import Organization
from organizations.permissions import require_organization_access
from outreach.models import OutreachDraftAction, OutreachDraftApproval


@dataclass(frozen=True)
class DataMinimizationIssue:
    code: str
    object_type: str
    object_id: int


@dataclass(frozen=True)
class RetentionAndMinimizationReport:
    as_of: date
    pending_deletions: tuple[Candidate, ...]
    overdue_candidates: tuple[Candidate, ...]
    overdue_sources: tuple[CandidateSource, ...]
    overdue_documents: tuple[CandidateDocument, ...]
    candidates_without_retention: int
    sources_without_retention: int
    documents_without_retention: int
    minimization_issues: tuple[DataMinimizationIssue, ...]


@dataclass(frozen=True)
class AuditHistory:
    privacy_events: tuple[AuditEvent, ...]
    ai_usage_events: tuple[AIUsageEvent, ...]
    csv_import_records: tuple[CandidateSource, ...]
    assessments: tuple[MatchAssessment, ...]
    review_decisions: tuple[ReviewDecision, ...]
    outreach_approvals: tuple[OutreachDraftApproval, ...]
    outreach_actions: tuple[OutreachDraftAction, ...]


def build_retention_and_minimization_report(
    *,
    organization: Organization,
    user,
    as_of: date,
) -> RetentionAndMinimizationReport:
    require_organization_access(user, organization)
    candidates = Candidate.objects.for_organization(organization)
    operational_candidates = candidates.filter(
        status__in=[Candidate.Status.ACTIVE, Candidate.Status.INACTIVE]
    )
    sources = CandidateSource.objects.for_organization(organization).exclude(
        candidate__status=Candidate.Status.DELETED
    )
    documents = CandidateDocument.objects.for_organization(organization).filter(
        candidate__status__in=[
            Candidate.Status.ACTIVE,
            Candidate.Status.INACTIVE,
            Candidate.Status.DELETION_REQUESTED,
        ],
        deleted_at__isnull=True,
    )

    pending_deletions = tuple(
        candidates.filter(status=Candidate.Status.DELETION_REQUESTED)
        .select_related("deletion_requested_by")
        .order_by("deletion_requested_at", "id")
    )
    overdue_candidates = tuple(
        operational_candidates.filter(retention_until__lte=as_of).order_by(
            "retention_until", "id"
        )
    )
    overdue_sources = tuple(
        sources.filter(retention_until__lte=as_of)
        .select_related("candidate")
        .order_by("retention_until", "id")
    )
    overdue_documents = tuple(
        documents.filter(retention_until__lte=as_of)
        .select_related("candidate")
        .order_by("retention_until", "id")
    )

    issues: list[DataMinimizationIssue] = []
    deleted_candidates = tuple(candidates.filter(status=Candidate.Status.DELETED))
    for candidate in deleted_candidates:
        if (
            candidate.full_name != f"Deleted candidate #{candidate.pk}"
            or candidate.email
            or candidate.phone
            or candidate.location
            or candidate.retention_until is not None
            or candidate.deletion_requested_by_id is not None
            or candidate.status_before_deletion_request
        ):
            issues.append(
                DataMinimizationIssue(
                    code="deleted_candidate_retains_identity",
                    object_type="candidate",
                    object_id=candidate.pk,
                )
            )

    deleted_ids = [candidate.pk for candidate in deleted_candidates]
    related_checks = (
        (
            "deleted_candidate_retains_source",
            CandidateSource.objects.filter(candidate_id__in=deleted_ids),
        ),
        (
            "deleted_candidate_retains_document",
            CandidateDocument.objects.filter(candidate_id__in=deleted_ids),
        ),
        (
            "deleted_candidate_retains_skill",
            CandidateSkill.objects.filter(candidate_id__in=deleted_ids),
        ),
        (
            "deleted_candidate_retains_shortlist_entry",
            ShortlistEntry.objects.filter(candidate_id__in=deleted_ids),
        ),
    )
    for code, queryset in related_checks:
        for candidate_id in queryset.values_list("candidate_id", flat=True).distinct():
            issues.append(
                DataMinimizationIssue(
                    code=code,
                    object_type="candidate",
                    object_id=candidate_id,
                )
            )

    return RetentionAndMinimizationReport(
        as_of=as_of,
        pending_deletions=pending_deletions,
        overdue_candidates=overdue_candidates,
        overdue_sources=overdue_sources,
        overdue_documents=overdue_documents,
        candidates_without_retention=operational_candidates.filter(
            retention_until__isnull=True
        ).count(),
        sources_without_retention=sources.filter(retention_until__isnull=True).count(),
        documents_without_retention=documents.filter(
            retention_until__isnull=True
        ).count(),
        minimization_issues=tuple(issues),
    )


def build_audit_history(
    *,
    organization: Organization,
    user,
    limit: int = 50,
) -> AuditHistory:
    require_organization_access(user, organization)
    bounded_limit = min(max(limit, 1), 100)
    return AuditHistory(
        privacy_events=tuple(
            AuditEvent.objects.for_organization(organization).select_related("actor")[
                :bounded_limit
            ]
        ),
        ai_usage_events=tuple(
            AIUsageEvent.objects.for_organization(organization).select_related("actor")[
                :bounded_limit
            ]
        ),
        csv_import_records=tuple(
            CandidateSource.objects.for_organization(organization)
            .filter(source_type=CandidateSource.SourceType.CSV_IMPORT)
            .select_related("recorded_by")[:bounded_limit]
        ),
        assessments=tuple(
            MatchAssessment.objects.for_organization(organization).select_related(
                "created_by"
            )[:bounded_limit]
        ),
        review_decisions=tuple(
            ReviewDecision.objects.for_organization(organization).select_related(
                "created_by"
            )[:bounded_limit]
        ),
        outreach_approvals=tuple(
            OutreachDraftApproval.objects.for_organization(organization).select_related(
                "approved_by", "draft"
            )[:bounded_limit]
        ),
        outreach_actions=tuple(
            OutreachDraftAction.objects.for_organization(organization).select_related(
                "actor", "draft"
            )[:bounded_limit]
        ),
    )
