from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from organizations.models import (
    ClientCompany,
    Organization,
    OrganizationScopedQuerySet,
)


def validate_string_list(value: object) -> None:
    """Require JSON list fields to contain only non-blank strings."""
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValidationError("Enter a list containing only non-blank strings.")


class VacancyQuerySet(OrganizationScopedQuerySet):
    pass


class VacancyRequirementsQuerySet(models.QuerySet):
    """Organization scoping for requirement versions owned through a vacancy."""

    def for_organization(self, organization: Organization):
        return self.filter(vacancy__organization=organization)

    def visible_to(self, user: object):
        if not (
            getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
        ):
            return self.none()

        return self.filter(
            vacancy__organization__is_active=True,
            vacancy__organization__memberships__user=user,
            vacancy__organization__memberships__is_active=True,
        ).distinct()


class Vacancy(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        PAUSED = "paused", "Paused"
        CLOSED = "closed", "Closed"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="vacancies",
    )
    client_company = models.ForeignKey(
        ClientCompany,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vacancies",
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_vacancies",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = VacancyQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["draft", "open", "paused", "closed"]),
                name="vacancy_has_valid_status",
            )
        ]
        indexes = [
            models.Index(
                fields=("organization", "status"),
                name="vacancy_org_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.organization_id
            and self.client_company_id
            and self.client_company.organization_id != self.organization_id
        ):
            raise ValidationError(
                {
                    "client_company": (
                        "The client company must belong to the vacancy organization."
                    )
                }
            )

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def current_requirements(self):
        return self.requirement_versions.filter(
            status=VacancyRequirements.Status.CONFIRMED
        ).first()

    def __str__(self) -> str:
        return self.title


class VacancyRequirements(models.Model):
    """A recruiter-reviewable, versioned snapshot of vacancy requirements."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CONFIRMED = "confirmed", "Confirmed"

    class CreationMethod(models.TextChoices):
        MANUAL = "manual", "Manual"
        AI_ASSISTED = "ai_assisted", "AI assisted"
        IMPORTED = "imported", "Imported"

    class EmploymentType(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        FULL_TIME = "full_time", "Full time"
        PART_TIME = "part_time", "Part time"
        CONTRACT = "contract", "Contract"
        TEMPORARY = "temporary", "Temporary"
        INTERNSHIP = "internship", "Internship"
        OTHER = "other", "Other"

    class WorkMode(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        ON_SITE = "on_site", "On site"
        HYBRID = "hybrid", "Hybrid"
        REMOTE = "remote", "Remote"
        FLEXIBLE = "flexible", "Flexible"

    vacancy = models.ForeignKey(
        Vacancy,
        on_delete=models.CASCADE,
        related_name="requirement_versions",
    )
    version = models.PositiveIntegerField(default=1)
    schema_version = models.CharField(
        max_length=50,
        default="vacancy_requirements.v1",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    creation_method = models.CharField(
        max_length=20,
        choices=CreationMethod.choices,
        default=CreationMethod.MANUAL,
    )
    source_description = models.TextField()
    summary = models.TextField(blank=True)
    must_have_skills = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_string_list],
    )
    nice_to_have_skills = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_string_list],
    )
    minimum_years_experience = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    location_requirement = models.CharField(max_length=200, blank=True)
    work_mode = models.CharField(
        max_length=20,
        choices=WorkMode.choices,
        default=WorkMode.UNKNOWN,
    )
    language_requirements = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_string_list],
    )
    education_requirements = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_string_list],
    )
    certification_requirements = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_string_list],
    )
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.UNKNOWN,
    )
    hard_constraints = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_string_list],
    )
    ambiguities = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_string_list],
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_vacancy_requirement_versions",
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="confirmed_vacancy_requirement_versions",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = VacancyRequirementsQuerySet.as_manager()

    class Meta:
        ordering = ("-version", "-created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("vacancy", "version"),
                name="unique_requirement_version_per_vacancy",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1),
                name="vacancy_requirement_version_is_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["draft", "confirmed"]),
                name="vacancy_requirement_has_valid_status",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    creation_method__in=["manual", "ai_assisted", "imported"]
                ),
                name="vacancy_requirement_has_valid_creation_method",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    employment_type__in=[
                        "unknown",
                        "full_time",
                        "part_time",
                        "contract",
                        "temporary",
                        "internship",
                        "other",
                    ]
                ),
                name="vacancy_requirement_has_valid_employment_type",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    work_mode__in=[
                        "unknown",
                        "on_site",
                        "hybrid",
                        "remote",
                        "flexible",
                    ]
                ),
                name="vacancy_requirement_has_valid_work_mode",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="draft",
                        confirmed_by__isnull=True,
                        confirmed_at__isnull=True,
                    )
                    | models.Q(
                        status="confirmed",
                        confirmed_by__isnull=False,
                        confirmed_at__isnull=False,
                    )
                ),
                name="vacancy_requirement_confirmation_is_consistent",
            ),
        ]

    @property
    def organization(self) -> Organization:
        return self.vacancy.organization

    def _confirmed_snapshot_changed(self) -> bool:
        if not self.pk:
            return False

        persisted = type(self).objects.get(pk=self.pk)
        if persisted.status != self.Status.CONFIRMED:
            return False

        immutable_fields = (
            "vacancy_id",
            "version",
            "schema_version",
            "status",
            "creation_method",
            "source_description",
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
            "created_by_id",
            "confirmed_by_id",
            "confirmed_at",
        )
        return any(
            getattr(self, field) != getattr(persisted, field)
            for field in immutable_fields
        )

    def save(self, *args, **kwargs) -> None:
        if self._confirmed_snapshot_changed():
            raise ValidationError(
                "Confirmed vacancy requirements are immutable; create a new version."
            )
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.vacancy} — requirements v{self.version}"
