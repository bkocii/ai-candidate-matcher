from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone

from audit.models import AIUsageEvent, AuditEvent
from candidates.models import Candidate, CandidateDocument, CandidateSource
from matching.models import (
    CandidateSkill,
    MatchAssessment,
    ReviewDecision,
    ShortlistEntry,
)
from organizations.models import Organization
from organizations.permissions import require_organization_admin
from outreach.models import OutreachDraftAction, OutreachDraftApproval

ALL_AUDIT_CATEGORIES = "all"
AUDIT_CATEGORY_OPTIONS = (
    (ALL_AUDIT_CATEGORIES, "All activity"),
    ("ai", "AI processing"),
    ("intake", "Candidate intake"),
    ("assessment", "Match assessments"),
    ("decision", "Recruiter decisions"),
    ("outreach", "Outreach review"),
)
AUDIT_STATUS_OPTIONS = (
    ("all", "All results"),
    ("succeeded", "Succeeded"),
    ("failed", "Failed"),
    ("pending", "Pending"),
    ("recorded", "Recorded decisions and actions"),
)
AUDIT_PERIOD_OPTIONS = (
    ("30", "Past 30 days"),
    ("7", "Past 7 days"),
    ("90", "Past 90 days"),
    ("all", "All recorded time"),
)


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
    candidates_missing_retention: tuple[Candidate, ...]
    sources_missing_retention: tuple[CandidateSource, ...]
    documents_missing_retention: tuple[CandidateDocument, ...]
    minimization_issues: tuple[DataMinimizationIssue, ...]

    @property
    def candidates_without_retention(self) -> int:
        return len(self.candidates_missing_retention)

    @property
    def sources_without_retention(self) -> int:
        return len(self.sources_missing_retention)

    @property
    def documents_without_retention(self) -> int:
        return len(self.documents_missing_retention)

    @property
    def records_due_count(self) -> int:
        return (
            len(self.overdue_candidates)
            + len(self.overdue_sources)
            + len(self.overdue_documents)
        )

    @property
    def missing_dates_count(self) -> int:
        return (
            self.candidates_without_retention
            + self.sources_without_retention
            + self.documents_without_retention
        )

    @property
    def needs_attention_count(self) -> int:
        return (
            len(self.pending_deletions)
            + self.records_due_count
            + self.missing_dates_count
            + len(self.minimization_issues)
        )


@dataclass(frozen=True)
class AuditHistory:
    privacy_events: tuple[AuditEvent, ...]
    ai_usage_events: tuple[AIUsageEvent, ...]
    csv_import_records: tuple[CandidateSource, ...]
    assessments: tuple[MatchAssessment, ...]
    review_decisions: tuple[ReviewDecision, ...]
    outreach_approvals: tuple[OutreachDraftApproval, ...]
    outreach_actions: tuple[OutreachDraftAction, ...]
    workflow_entries: tuple["WorkflowAuditEntry", ...]
    selected_category: str
    selected_status: str
    selected_period: str


@dataclass(frozen=True)
class WorkflowAuditEntry:
    occurred_at: object
    category: str
    activity: str
    result: str
    status_group: str
    actor_name: str
    reference: str


def normalize_audit_category(value: str | None) -> str:
    valid = {item[0] for item in AUDIT_CATEGORY_OPTIONS}
    return value if value in valid else ALL_AUDIT_CATEGORIES


def _normalize_option(value: str | None, options, default: str) -> str:
    return value if value in {item[0] for item in options} else default


def build_retention_and_minimization_report(
    *,
    organization: Organization,
    user,
    as_of: date,
) -> RetentionAndMinimizationReport:
    require_organization_admin(user, organization)
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
        candidates_missing_retention=tuple(
            operational_candidates.filter(retention_until__isnull=True).order_by("id")
        ),
        sources_missing_retention=tuple(
            sources.filter(retention_until__isnull=True)
            .select_related("candidate")
            .order_by("id")
        ),
        documents_missing_retention=tuple(
            documents.filter(retention_until__isnull=True)
            .select_related("candidate")
            .order_by("id")
        ),
        minimization_issues=tuple(issues),
    )


def build_audit_history(
    *,
    organization: Organization,
    user,
    limit: int = 50,
    category: str | None = None,
    status: str | None = None,
    period: str | None = None,
    now=None,
) -> AuditHistory:
    require_organization_admin(user, organization)
    bounded_limit = min(max(limit, 1), 100)
    selected_category = normalize_audit_category(category)
    selected_status = _normalize_option(status, AUDIT_STATUS_OPTIONS, "all")
    selected_period = _normalize_option(period, AUDIT_PERIOD_OPTIONS, "30")
    current_time = now or timezone.now()
    privacy_events = tuple(
        AuditEvent.objects.for_organization(organization).select_related("actor")[
            :bounded_limit
        ]
    )
    ai_usage_events = tuple(
        AIUsageEvent.objects.for_organization(organization).select_related("actor")[
            :bounded_limit
        ]
    )
    csv_import_records = tuple(
        CandidateSource.objects.for_organization(organization)
        .filter(source_type=CandidateSource.SourceType.CSV_IMPORT)
        .select_related("recorded_by")[:bounded_limit]
    )
    assessments = tuple(
        MatchAssessment.objects.for_organization(organization).select_related(
            "created_by"
        )[:bounded_limit]
    )
    review_decisions = tuple(
        ReviewDecision.objects.for_organization(organization).select_related(
            "created_by"
        )[:bounded_limit]
    )
    outreach_approvals = tuple(
        OutreachDraftApproval.objects.for_organization(organization).select_related(
            "approved_by", "draft"
        )[:bounded_limit]
    )
    outreach_actions = tuple(
        OutreachDraftAction.objects.for_organization(organization).select_related(
            "actor", "draft"
        )[:bounded_limit]
    )
    entries = [
        WorkflowAuditEntry(
            occurred_at=event.started_at,
            category="ai",
            activity=f"{event.get_workflow_display()} AI processing",
            result=event.get_status_display(),
            status_group=event.status,
            actor_name=event.actor.username if event.actor else "Deleted actor",
            reference=f"AI attempt #{event.pk}",
        )
        for event in ai_usage_events
    ]
    entries.extend(
        WorkflowAuditEntry(
            occurred_at=source.created_at,
            category="intake",
            activity="Candidate added from CSV",
            result="Recorded",
            status_group="recorded",
            actor_name=(
                source.recorded_by.username if source.recorded_by else "Deleted actor"
            ),
            reference=f"Candidate #{source.candidate_id}",
        )
        for source in csv_import_records
    )
    entries.extend(
        WorkflowAuditEntry(
            occurred_at=assessment.created_at,
            category="assessment",
            activity="Match assessment created",
            result=f"Version {assessment.version}",
            status_group="recorded",
            actor_name=assessment.created_by.username,
            reference=f"Assessment #{assessment.pk}",
        )
        for assessment in assessments
    )
    entries.extend(
        WorkflowAuditEntry(
            occurred_at=decision.created_at,
            category="decision",
            activity="Recruiter decision recorded",
            result=decision.get_decision_display(),
            status_group="recorded",
            actor_name=decision.created_by.username,
            reference=f"Decision #{decision.pk} · version {decision.version}",
        )
        for decision in review_decisions
    )
    entries.extend(
        WorkflowAuditEntry(
            occurred_at=approval.approved_at,
            category="outreach",
            activity="Outreach draft approved",
            result="Approved",
            status_group="recorded",
            actor_name=approval.approved_by.username,
            reference=f"Draft #{approval.draft_id} · version {approval.draft.version}",
        )
        for approval in outreach_approvals
    )
    entries.extend(
        WorkflowAuditEntry(
            occurred_at=action.created_at,
            category="outreach",
            activity="Outreach draft handed off",
            result=action.get_action_type_display(),
            status_group="recorded",
            actor_name=action.actor.username,
            reference=f"Draft #{action.draft_id}",
        )
        for action in outreach_actions
    )
    if selected_category != ALL_AUDIT_CATEGORIES:
        entries = [entry for entry in entries if entry.category == selected_category]
    if selected_status != "all":
        entries = [entry for entry in entries if entry.status_group == selected_status]
    if selected_period != "all":
        cutoff = current_time - timedelta(days=int(selected_period))
        entries = [entry for entry in entries if entry.occurred_at >= cutoff]
    entries.sort(key=lambda entry: entry.occurred_at, reverse=True)
    return AuditHistory(
        privacy_events=privacy_events,
        ai_usage_events=ai_usage_events,
        csv_import_records=csv_import_records,
        assessments=assessments,
        review_decisions=review_decisions,
        outreach_approvals=outreach_approvals,
        outreach_actions=outreach_actions,
        workflow_entries=tuple(entries[:bounded_limit]),
        selected_category=selected_category,
        selected_status=selected_status,
        selected_period=selected_period,
    )
