from accounts.models import User
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
