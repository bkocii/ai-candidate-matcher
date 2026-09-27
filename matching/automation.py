from accounts.models import User
from candidates.models import Candidate
from matching.models import MatchRun
from matching.scoring import generate_shortlist
from organizations.permissions import require_organization_object_access
from vacancies.models import Vacancy


def refresh_vacancy_shortlist(*, vacancy: Vacancy, user: User) -> MatchRun | None:
    """Generate the current deterministic shortlist when a vacancy is match-ready."""
    require_organization_object_access(user, vacancy)
    vacancy = Vacancy.objects.get(pk=vacancy.pk)
    if vacancy.status != Vacancy.Status.OPEN or vacancy.current_requirements is None:
        return None
    return generate_shortlist(requirements=vacancy.current_requirements, user=user)


def refresh_candidate_shortlists(
    *, candidate: Candidate, user: User
) -> tuple[MatchRun, ...]:
    """Refresh each open vacancy that currently considers this candidate."""
    require_organization_object_access(user, candidate)
    vacancy_ids = (
        candidate.vacancy_considerations.filter(
            vacancy__status=Vacancy.Status.OPEN,
            vacancy__deleted_at__isnull=True,
        )
        .order_by("vacancy_id")
        .values_list("vacancy_id", flat=True)
        .distinct()
    )
    refreshed: list[MatchRun] = []
    for vacancy in Vacancy.objects.filter(pk__in=vacancy_ids).order_by("pk"):
        run = refresh_vacancy_shortlist(vacancy=vacancy, user=user)
        if run is not None:
            refreshed.append(run)
    return tuple(refreshed)
