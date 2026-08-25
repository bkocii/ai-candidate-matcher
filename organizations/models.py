from django.conf import settings
from django.db import models


def _user_can_query_organizations(user: object) -> bool:
    return bool(
        getattr(user, "is_authenticated", False) and getattr(user, "is_active", False)
    )


class OrganizationQuerySet(models.QuerySet):
    def visible_to(self, user: object):
        """Return active organizations available through an active membership."""
        if not _user_can_query_organizations(user):
            return self.none()

        return self.filter(
            is_active=True,
            memberships__user=user,
            memberships__is_active=True,
        ).distinct()


class Organization(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    is_active = models.BooleanField(default=True)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    deletion_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_organization_deletions",
    )
    purge_after = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrganizationQuerySet.as_manager()

    class Meta:
        ordering = ("name",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        deletion_requested_at__isnull=True,
                        purge_after__isnull=True,
                    )
                    | models.Q(
                        deletion_requested_at__isnull=False,
                        purge_after__isnull=False,
                        is_active=False,
                    )
                ),
                name="organization_deletion_state_consistent",
            )
        ]

    def __str__(self) -> str:
        return self.name


class OrganizationScopedQuerySet(models.QuerySet):
    def for_organization(self, organization: Organization):
        """Restrict organization-owned records to one explicit tenant boundary."""
        return self.filter(organization=organization)

    def visible_to(self, user: object):
        """Return records belonging to the user's active organizations."""
        if not _user_can_query_organizations(user):
            return self.none()

        return self.filter(
            organization__is_active=True,
            organization__memberships__user=user,
            organization__memberships__is_active=True,
        ).distinct()


class ClientCompany(models.Model):
    """An agency client; direct employers can leave this concept unused."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="client_companies",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "slug"),
                name="unique_client_company_slug_per_organization",
            )
        ]

    def __str__(self) -> str:
        return self.name


class OrganizationRetentionPolicy(models.Model):
    """Tenant-owned lifecycle limits with conservative operational defaults."""

    DEFAULT_TEMPORARY_INTAKE_DAYS = 7
    DEFAULT_COMPLETED_JOB_DAYS = 90
    DEFAULT_UNCOMMITTED_WORKFLOW_DAYS = 180
    DEFAULT_METADATA_DAYS = 365
    DEFAULT_ORGANIZATION_RECOVERY_DAYS = 30

    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="retention_policy",
    )
    policy_version = models.PositiveIntegerField(default=1)
    temporary_intake_days = models.PositiveIntegerField(
        default=DEFAULT_TEMPORARY_INTAKE_DAYS
    )
    completed_job_days = models.PositiveIntegerField(default=DEFAULT_COMPLETED_JOB_DAYS)
    uncommitted_workflow_days = models.PositiveIntegerField(
        default=DEFAULT_UNCOMMITTED_WORKFLOW_DAYS
    )
    metadata_days = models.PositiveIntegerField(default=DEFAULT_METADATA_DAYS)
    organization_recovery_days = models.PositiveIntegerField(
        default=DEFAULT_ORGANIZATION_RECOVERY_DAYS
    )
    legal_hold = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_organization_retention_policies",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(policy_version__gte=1),
                name="retention_policy_version_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(temporary_intake_days__gte=1)
                    & models.Q(temporary_intake_days__lte=3650)
                    & models.Q(completed_job_days__gte=1)
                    & models.Q(completed_job_days__lte=3650)
                    & models.Q(uncommitted_workflow_days__gte=1)
                    & models.Q(uncommitted_workflow_days__lte=3650)
                    & models.Q(metadata_days__gte=1)
                    & models.Q(metadata_days__lte=3650)
                    & models.Q(organization_recovery_days__gte=1)
                    & models.Q(organization_recovery_days__lte=365)
                ),
                name="retention_policy_days_bounded",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.organization} retention policy v{self.policy_version}"


class RetentionException(models.Model):
    """Explicit, tenant-scoped block on one lifecycle group or object."""

    class Scope(models.TextChoices):
        TEMPORARY_INTAKE = "temporary_intake", "Temporary intake"
        COMPLETED_JOBS = "completed_jobs", "Completed jobs"
        MATCH_RUNS = "match_runs", "Obsolete shortlist bundles"
        OUTREACH = "outreach", "Abandoned outreach chains"
        METADATA = "metadata", "Usage and audit metadata"
        ORGANIZATION = "organization", "Organization deletion"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="retention_exceptions",
    )
    scope = models.CharField(max_length=30, choices=Scope.choices)
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    reason = models.CharField(max_length=500)
    expires_at = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_retention_exceptions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("scope", "object_id", "id")
        indexes = [
            models.Index(
                fields=("organization", "scope", "is_active"),
                name="retention_exc_org_scope_idx",
            )
        ]

    def __str__(self) -> str:
        target = f" #{self.object_id}" if self.object_id else ""
        return f"{self.get_scope_display()}{target}"
