from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from accounts.models import User
from organizations.models import Organization
from organizations.permissions import (
    require_organization_access,
    require_organization_object_access,
)
from vacancies.models import Vacancy, VacancyRequirements

REQUIREMENTS_COPY_FIELDS = (
    "summary",
    "must_have_skills",
    "nice_to_have_skills",
    "minimum_years_experience",
    "location_requirement",
    "work_mode",
    "language_requirements",
    "education_requirements",
    "certification_requirements",
    "employment_type",
    "hard_constraints",
    "ambiguities",
)


@transaction.atomic
def create_vacancy_with_requirements(
    *,
    organization: Organization,
    user: User,
    vacancy_values: dict,
) -> Vacancy:
    """Create a vacancy and its first manual requirements draft atomically."""
    require_organization_access(user, organization)
    client_company = vacancy_values.get("client_company")
    if client_company and client_company.organization_id != organization.pk:
        raise ValidationError(
            {"client_company": "The client company is not in this organization."}
        )

    vacancy = Vacancy.objects.create(
        organization=organization,
        created_by=user,
        **vacancy_values,
    )
    VacancyRequirements.objects.create(
        vacancy=vacancy,
        version=1,
        source_description=vacancy.description,
        creation_method=VacancyRequirements.CreationMethod.MANUAL,
        created_by=user,
    )
    return vacancy


@transaction.atomic
def update_requirements_draft(
    *,
    requirements: VacancyRequirements,
    user: User,
    values: dict,
) -> VacancyRequirements:
    require_organization_object_access(user, requirements)
    requirements = VacancyRequirements.objects.select_for_update().get(
        pk=requirements.pk
    )
    if requirements.status != VacancyRequirements.Status.DRAFT:
        raise ValidationError(
            "Confirmed requirements cannot be edited; create a new version."
        )

    for field_name in REQUIREMENTS_COPY_FIELDS:
        setattr(requirements, field_name, values[field_name])
    requirements.save()
    return requirements


def _has_meaningful_requirements(requirements: VacancyRequirements) -> bool:
    if requirements.summary or requirements.minimum_years_experience is not None:
        return True
    if requirements.location_requirement:
        return True
    if requirements.work_mode != VacancyRequirements.WorkMode.UNKNOWN:
        return True
    if requirements.employment_type != VacancyRequirements.EmploymentType.UNKNOWN:
        return True
    return any(
        getattr(requirements, field_name)
        for field_name in REQUIREMENTS_COPY_FIELDS
        if field_name
        not in {
            "summary",
            "minimum_years_experience",
            "location_requirement",
            "work_mode",
            "employment_type",
        }
    )


@transaction.atomic
def confirm_requirements_draft(
    *,
    requirements: VacancyRequirements,
    user: User,
) -> VacancyRequirements:
    require_organization_object_access(user, requirements)
    requirements = VacancyRequirements.objects.select_for_update().get(
        pk=requirements.pk
    )
    if requirements.status != VacancyRequirements.Status.DRAFT:
        raise ValidationError("This requirements version is already confirmed.")
    if not _has_meaningful_requirements(requirements):
        raise ValidationError(
            "Add at least one structured requirement before confirming this version."
        )

    requirements.status = VacancyRequirements.Status.CONFIRMED
    requirements.confirmed_by = user
    requirements.confirmed_at = timezone.now()
    requirements.save()
    return requirements


@transaction.atomic
def create_next_requirements_draft(
    *,
    vacancy: Vacancy,
    user: User,
) -> tuple[VacancyRequirements, bool]:
    """Return an existing draft or copy the current snapshot into a new draft."""
    require_organization_object_access(user, vacancy)
    vacancy = Vacancy.objects.select_for_update().get(pk=vacancy.pk)
    existing_draft = vacancy.requirement_versions.filter(
        status=VacancyRequirements.Status.DRAFT
    ).first()
    if existing_draft:
        return existing_draft, False

    base = vacancy.current_requirements
    max_version = vacancy.requirement_versions.aggregate(Max("version"))["version__max"]
    values = {
        field_name: getattr(base, field_name) if base else []
        for field_name in REQUIREMENTS_COPY_FIELDS
    }
    if base is None:
        values.update(
            {
                "summary": "",
                "minimum_years_experience": None,
                "location_requirement": "",
                "work_mode": VacancyRequirements.WorkMode.UNKNOWN,
                "employment_type": VacancyRequirements.EmploymentType.UNKNOWN,
            }
        )

    draft = VacancyRequirements.objects.create(
        vacancy=vacancy,
        version=(max_version or 0) + 1,
        source_description=base.source_description if base else vacancy.description,
        creation_method=VacancyRequirements.CreationMethod.MANUAL,
        created_by=user,
        **values,
    )
    return draft, True
