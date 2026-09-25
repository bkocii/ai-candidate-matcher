from accounts.models import User
from candidates.models import (
    Candidate,
    CandidateSource,
    CandidateVacancyConsideration,
)
from vacancies.models import Vacancy


def associate_candidate_with_vacancy(
    *,
    candidate: Candidate,
    vacancy: Vacancy,
    user: User,
) -> CandidateVacancyConsideration:
    """Create minimal explicit application context for matching tests."""
    source = CandidateSource.objects.create(
        candidate=candidate,
        source_type=CandidateSource.SourceType.OTHER,
        source_name=f"Test application for {vacancy.title}",
        lawful_basis=CandidateSource.LawfulBasis.LEGITIMATE_INTERESTS,
        consent_status=CandidateSource.ConsentStatus.NOT_REQUIRED,
        contact_permission=CandidateSource.ContactPermission.RESTRICTED,
        recorded_by=user,
    )
    return CandidateVacancyConsideration.objects.create(
        candidate=candidate,
        vacancy=vacancy,
        source=source,
        created_by=user,
    )


def associate_organization_candidates_with_vacancy(
    *,
    vacancy: Vacancy,
    user: User,
) -> None:
    """Associate every current organization candidate for matching test setup."""
    candidates = Candidate.objects.for_organization(vacancy.organization).exclude(
        vacancy_considerations__vacancy=vacancy
    )
    for candidate in candidates:
        associate_candidate_with_vacancy(
            candidate=candidate,
            vacancy=vacancy,
            user=user,
        )
