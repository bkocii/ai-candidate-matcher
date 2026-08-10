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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrganizationQuerySet.as_manager()

    class Meta:
        ordering = ("name",)

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
