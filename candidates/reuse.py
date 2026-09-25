from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import User
from candidates.models import (
    Candidate,
    CandidateSource,
    CandidateVacancyConsideration,
)
from organizations.permissions import require_organization_object_access
from outreach.workflow import assess_contact_permission
from vacancies.models import Vacancy


@dataclass(frozen=True)
class CandidatePoolReuseEligibility:
    can_add: bool
    reason: str = ""
    source: CandidateSource | None = None


def assess_candidate_pool_reuse(
    *,
    candidate: Candidate,
    vacancy: Vacancy,
) -> CandidatePoolReuseEligibility:
    """Check whether one existing candidate can be deliberately reused."""
    if candidate.organization_id != vacancy.organization_id:
        return CandidatePoolReuseEligibility(False, "Candidate is unavailable.")
    if vacancy.deleted_at is not None or vacancy.status != Vacancy.Status.OPEN:
        return CandidatePoolReuseEligibility(False, "The vacancy is not open.")
    if vacancy.current_requirements is None:
        return CandidatePoolReuseEligibility(
            False,
            "Confirm vacancy requirements before adding candidates.",
        )
    if candidate.status != Candidate.Status.ACTIVE:
        return CandidatePoolReuseEligibility(False, "Candidate is not active.")
    if CandidateVacancyConsideration.objects.filter(
        candidate=candidate,
        vacancy=vacancy,
    ).exists():
        return CandidatePoolReuseEligibility(
            False,
            "Candidate is already associated with this vacancy.",
        )

    contact = assess_contact_permission(candidate=candidate)
    if not contact.can_proceed:
        return CandidatePoolReuseEligibility(False, contact.reason)

    source = next(
        (
            source
            for source in candidate.sources.all()
            if source.contact_permission == CandidateSource.ContactPermission.PERMITTED
            and source.lawful_basis != CandidateSource.LawfulBasis.NOT_RECORDED
            and not (
                source.lawful_basis == CandidateSource.LawfulBasis.CONSENT
                and source.consent_status != CandidateSource.ConsentStatus.GRANTED
            )
        ),
        None,
    )
    if source is None:
        return CandidatePoolReuseEligibility(
            False,
            "No source permits contact about future roles.",
        )
    return CandidatePoolReuseEligibility(True, source=source)


@transaction.atomic
def add_candidates_from_pool(
    *,
    vacancy: Vacancy,
    user: User,
    candidate_ids: list[int],
) -> list[CandidateVacancyConsideration]:
    """Add explicitly selected, permission-eligible candidates to one vacancy."""
    require_organization_object_access(user, vacancy)
    selected_ids = list(dict.fromkeys(candidate_ids))
    if not selected_ids:
        raise ValidationError("Select at least one candidate.")

    vacancy = (
        Vacancy.objects.select_for_update()
        .for_organization(vacancy.organization)
        .active()
        .get(pk=vacancy.pk)
    )
    candidates = list(
        Candidate.objects.select_for_update()
        .for_organization(vacancy.organization)
        .filter(pk__in=selected_ids)
        .order_by("full_name", "id")
    )
    if len(candidates) != len(selected_ids):
        raise ValidationError("One or more selected candidates are unavailable.")

    created: list[CandidateVacancyConsideration] = []
    for candidate in candidates:
        list(CandidateSource.objects.select_for_update().filter(candidate=candidate))
        eligibility = assess_candidate_pool_reuse(
            candidate=candidate,
            vacancy=vacancy,
        )
        if not eligibility.can_add or eligibility.source is None:
            raise ValidationError(f"{candidate.full_name}: {eligibility.reason}")
        consideration = CandidateVacancyConsideration(
            candidate=candidate,
            vacancy=vacancy,
            source=eligibility.source,
            contact_scope=(CandidateVacancyConsideration.ContactScope.CURRENT_VACANCY),
            origin=CandidateVacancyConsideration.Origin.CANDIDATE_POOL,
            created_by=user,
        )
        consideration.save()
        created.append(consideration)
    return created
