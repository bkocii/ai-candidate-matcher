from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models

from matching.models import ReviewDecision, ShortlistEntry
from organizations.models import Organization


def _user_can_query_outreach(user: object) -> bool:
    return bool(
        getattr(user, "is_authenticated", False) and getattr(user, "is_active", False)
    )


class OutreachDraftQuerySet(models.QuerySet):
    def for_organization(self, organization: Organization):
        return self.filter(
            shortlist_entry__match_run__requirements__vacancy__organization=(
                organization
            )
        )

    def visible_to(self, user: object):
        if not _user_can_query_outreach(user):
            return self.none()
        return self.filter(
            shortlist_entry__match_run__requirements__vacancy__organization__is_active=(
                True
            ),
            shortlist_entry__match_run__requirements__vacancy__organization__memberships__user=(
                user
            ),
            shortlist_entry__match_run__requirements__vacancy__organization__memberships__is_active=(
                True
            ),
        ).distinct()


class OutreachDraft(models.Model):
    """Immutable generated draft tied to one exact human approval."""

    shortlist_entry = models.ForeignKey(
        ShortlistEntry,
        on_delete=models.CASCADE,
        related_name="outreach_drafts",
    )
    review_decision = models.ForeignKey(
        ReviewDecision,
        on_delete=models.CASCADE,
        related_name="outreach_drafts",
    )
    version = models.PositiveIntegerField()
    schema_version = models.CharField(max_length=50)
    subject = models.CharField(max_length=200)
    body = models.TextField(validators=[MaxLengthValidator(5_000)])
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_outreach_drafts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OutreachDraftQuerySet.as_manager()

    class Meta:
        ordering = ("-version", "-created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("shortlist_entry", "version"),
                name="unique_outreach_draft_version_per_entry",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1),
                name="outreach_draft_version_positive",
            ),
        ]

    @property
    def organization(self) -> Organization:
        return self.shortlist_entry.organization

    def _snapshot_changed(self) -> bool:
        if not self.pk:
            return False
        persisted = type(self).objects.get(pk=self.pk)
        fields = (
            "shortlist_entry_id",
            "review_decision_id",
            "version",
            "schema_version",
            "subject",
            "body",
            "created_by_id",
        )
        return any(
            getattr(self, field_name) != getattr(persisted, field_name)
            for field_name in fields
        )

    def clean(self) -> None:
        super().clean()
        if (
            self.shortlist_entry_id
            and self.review_decision_id
            and self.review_decision.shortlist_entry_id != self.shortlist_entry_id
        ):
            raise ValidationError(
                {"review_decision": "Use a decision for this shortlist entry."}
            )
        if self.review_decision_id and (
            self.review_decision.decision != ReviewDecision.Decision.APPROVED
        ):
            raise ValidationError(
                {"review_decision": "Outreach drafts require an approved decision."}
            )
        self.subject = self.subject.strip()
        self.body = self.body.strip()
        if not self.subject:
            raise ValidationError({"subject": "Enter a non-blank subject."})
        if not self.body:
            raise ValidationError({"body": "Enter a non-blank message body."})

    def save(self, *args, **kwargs) -> None:
        if self._snapshot_changed():
            raise ValidationError(
                "Generated outreach drafts are immutable; generate a new version."
            )
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.shortlist_entry} — outreach draft v{self.version}"
