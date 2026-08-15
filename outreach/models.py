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


class OutreachDraftRelatedQuerySet(models.QuerySet):
    def for_organization(self, organization: Organization):
        return self.filter(
            draft__shortlist_entry__match_run__requirements__vacancy__organization=(
                organization
            )
        )

    def visible_to(self, user: object):
        if not _user_can_query_outreach(user):
            return self.none()
        return self.filter(
            draft__shortlist_entry__match_run__requirements__vacancy__organization__is_active=(
                True
            ),
            draft__shortlist_entry__match_run__requirements__vacancy__organization__memberships__user=(
                user
            ),
            draft__shortlist_entry__match_run__requirements__vacancy__organization__memberships__is_active=(
                True
            ),
        ).distinct()


class OutreachDraft(models.Model):
    """Immutable generated or recruiter-edited outreach content snapshot."""

    class CreationMethod(models.TextChoices):
        AI_GENERATED = "ai_generated", "AI generated"
        RECRUITER_EDITED = "recruiter_edited", "Recruiter edited"

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
    creation_method = models.CharField(
        max_length=30,
        choices=CreationMethod.choices,
        default=CreationMethod.AI_GENERATED,
    )
    parent_draft = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="revisions",
    )
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
            models.CheckConstraint(
                condition=models.Q(
                    creation_method__in=["ai_generated", "recruiter_edited"]
                ),
                name="outreach_draft_valid_creation_method",
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
            "creation_method",
            "parent_draft_id",
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
        if self.parent_draft_id:
            if self.parent_draft.shortlist_entry_id != self.shortlist_entry_id:
                raise ValidationError(
                    {"parent_draft": "Use a prior draft for this shortlist entry."}
                )
            if self.parent_draft.version >= self.version:
                raise ValidationError(
                    {"parent_draft": "The parent draft must be an earlier version."}
                )
        if (
            self.creation_method == self.CreationMethod.RECRUITER_EDITED
            and not self.parent_draft_id
        ):
            raise ValidationError(
                {"parent_draft": "Recruiter-edited drafts require a parent version."}
            )
        if (
            self.creation_method == self.CreationMethod.AI_GENERATED
            and self.parent_draft_id
        ):
            raise ValidationError(
                {"parent_draft": "AI-generated drafts do not use a parent version."}
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
                "Outreach drafts are immutable; create a new version."
            )
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.shortlist_entry} — outreach draft v{self.version}"


class OutreachDraftApproval(models.Model):
    """Immutable human approval of the exact content in one draft version."""

    draft = models.OneToOneField(
        OutreachDraft,
        on_delete=models.CASCADE,
        related_name="final_approval",
    )
    notes = models.TextField(validators=[MaxLengthValidator(2_000)])
    contact_permission_confirmed = models.BooleanField()
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approved_outreach_drafts",
    )
    approved_at = models.DateTimeField(auto_now_add=True)

    objects = OutreachDraftRelatedQuerySet.as_manager()

    class Meta:
        ordering = ("-approved_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(contact_permission_confirmed=True),
                name="outreach_approval_confirms_contact_permission",
            )
        ]

    @property
    def organization(self) -> Organization:
        return self.draft.organization

    def _snapshot_changed(self) -> bool:
        if not self.pk:
            return False
        persisted = type(self).objects.get(pk=self.pk)
        fields = (
            "draft_id",
            "notes",
            "contact_permission_confirmed",
            "approved_by_id",
        )
        return any(
            getattr(self, field_name) != getattr(persisted, field_name)
            for field_name in fields
        )

    def clean(self) -> None:
        super().clean()
        self.notes = self.notes.strip()
        if not self.notes:
            raise ValidationError({"notes": "Record final approval notes."})
        if not self.contact_permission_confirmed:
            raise ValidationError(
                {
                    "contact_permission_confirmed": (
                        "Confirm contact permission before final approval."
                    )
                }
            )

    def save(self, *args, **kwargs) -> None:
        if self._snapshot_changed():
            raise ValidationError(
                "Final outreach approvals are immutable; approve a new draft version."
            )
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Final approval — {self.draft}"


class OutreachDraftAction(models.Model):
    """Immutable record of a manual copy or export of an approved draft."""

    class ActionType(models.TextChoices):
        COPY = "copy", "Copy"
        EXPORT = "export", "Export"

    draft = models.ForeignKey(
        OutreachDraft,
        on_delete=models.CASCADE,
        related_name="manual_actions",
    )
    action_type = models.CharField(max_length=20, choices=ActionType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="outreach_draft_actions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OutreachDraftRelatedQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(action_type__in=["copy", "export"]),
                name="outreach_action_valid_type",
            )
        ]

    @property
    def organization(self) -> Organization:
        return self.draft.organization

    def _snapshot_changed(self) -> bool:
        if not self.pk:
            return False
        persisted = type(self).objects.get(pk=self.pk)
        return any(
            getattr(self, field_name) != getattr(persisted, field_name)
            for field_name in ("draft_id", "action_type", "actor_id")
        )

    def clean(self) -> None:
        super().clean()
        if (
            self.draft_id
            and not OutreachDraftApproval.objects.filter(
                draft_id=self.draft_id
            ).exists()
        ):
            raise ValidationError(
                {"draft": "Only a finally approved draft can be copied or exported."}
            )

    def save(self, *args, **kwargs) -> None:
        if self._snapshot_changed():
            raise ValidationError("Outreach copy/export history is immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.get_action_type_display()} — {self.draft}"
