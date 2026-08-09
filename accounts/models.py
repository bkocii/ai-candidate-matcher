from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Application user, kept deliberately small for the foundation sprint."""


class OrganizationMembership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        RECRUITER = "recruiter", "Recruiter"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("organization__name", "user__username")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "organization"),
                name="unique_user_organization_membership",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=["admin", "recruiter"]),
                name="membership_has_valid_role",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} — {self.organization} ({self.get_role_display()})"

    @property
    def is_administrator(self) -> bool:
        return self.is_active and self.role == self.Role.ADMIN
