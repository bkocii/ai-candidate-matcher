import re
import unicodedata
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from candidates.models import Candidate, CandidateDocument, CandidateProfile
from organizations.models import (
    Organization,
    OrganizationScopedQuerySet,
)
from vacancies.models import VacancyRequirements

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_taxonomy_value(value: str) -> str:
    """Return a conservative identity key without merging meaningful punctuation."""
    if not isinstance(value, str):
        raise ValidationError("Enter a text value.")
    normalized = _WHITESPACE_RE.sub(
        " ", unicodedata.normalize("NFKC", value).strip()
    ).casefold()
    if not normalized:
        raise ValidationError("Enter a non-blank value.")
    return normalized


def _user_can_query_matching_data(user: object) -> bool:
    return bool(
        getattr(user, "is_authenticated", False) and getattr(user, "is_active", False)
    )


def _requirements_are_confirmed(requirements_id: int | None) -> bool:
    if requirements_id is None:
        return False
    return VacancyRequirements.objects.filter(
        pk=requirements_id,
        status=VacancyRequirements.Status.CONFIRMED,
    ).exists()


class CandidateOwnedQuerySet(models.QuerySet):
    def for_organization(self, organization: Organization):
        return self.filter(candidate__organization=organization)

    def visible_to(self, user: object):
        if not _user_can_query_matching_data(user):
            return self.none()
        return self.filter(
            candidate__organization__is_active=True,
            candidate__organization__memberships__user=user,
            candidate__organization__memberships__is_active=True,
        ).distinct()


class RequirementsOwnedQuerySet(models.QuerySet):
    def for_organization(self, organization: Organization):
        return self.filter(requirements__vacancy__organization=organization)

    def visible_to(self, user: object):
        if not _user_can_query_matching_data(user):
            return self.none()
        return self.filter(
            requirements__vacancy__organization__is_active=True,
            requirements__vacancy__organization__memberships__user=user,
            requirements__vacancy__organization__memberships__is_active=True,
        ).distinct()

    def _reject_confirmed_mutation(self) -> None:
        if self.filter(
            requirements__status=VacancyRequirements.Status.CONFIRMED
        ).exists():
            raise ValidationError(
                "Confirmed matching definitions are immutable; create a new version."
            )

    def update(self, **kwargs):
        self._reject_confirmed_mutation()
        return super().update(**kwargs)

    def delete(self):
        self._reject_confirmed_mutation()
        return super().delete()


class MatchRunQuerySet(models.QuerySet):
    def for_organization(self, organization: Organization):
        return self.filter(requirements__vacancy__organization=organization)

    def visible_to(self, user: object):
        if not _user_can_query_matching_data(user):
            return self.none()
        return self.filter(
            requirements__vacancy__organization__is_active=True,
            requirements__vacancy__organization__memberships__user=user,
            requirements__vacancy__organization__memberships__is_active=True,
        ).distinct()


class ShortlistEntryQuerySet(models.QuerySet):
    def for_organization(self, organization: Organization):
        return self.filter(match_run__requirements__vacancy__organization=organization)

    def visible_to(self, user: object):
        if not _user_can_query_matching_data(user):
            return self.none()
        return self.filter(
            match_run__requirements__vacancy__organization__is_active=True,
            match_run__requirements__vacancy__organization__memberships__user=user,
            match_run__requirements__vacancy__organization__memberships__is_active=True,
        ).distinct()


class Skill(models.Model):
    """An organization-owned canonical skill identity."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="skills",
    )
    name = models.CharField(max_length=120)
    normalized_name = models.CharField(max_length=120, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_skills",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "normalized_name"),
                name="unique_normalized_skill_per_organization",
            )
        ]

    def clean(self) -> None:
        super().clean()
        normalized = normalize_taxonomy_value(self.name)
        if len(normalized) > 120:
            raise ValidationError({"name": "The normalized skill is too long."})
        self.name = _WHITESPACE_RE.sub(
            " ", unicodedata.normalize("NFKC", self.name).strip()
        )
        self.normalized_name = normalized

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class CandidateSkill(models.Model):
    """A candidate skill assertion with recruiter-inspectable evidence."""

    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="skill_records",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="candidate_records",
    )
    source_label = models.CharField(max_length=120)
    evidence = models.TextField(blank=True)
    years_experience = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    source_document = models.ForeignKey(
        CandidateDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="skill_records",
    )
    source_profile = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="published_skill_records",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_candidate_skills",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CandidateOwnedQuerySet.as_manager()

    class Meta:
        ordering = ("skill__name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("candidate", "skill"),
                name="unique_skill_per_candidate",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(years_experience__isnull=True)
                    | models.Q(years_experience__gte=0)
                ),
                name="candidate_skill_years_is_nonnegative",
            ),
        ]

    @property
    def organization(self) -> Organization:
        return self.candidate.organization

    def clean(self) -> None:
        super().clean()
        self.source_label = _WHITESPACE_RE.sub(" ", self.source_label.strip())
        if not self.source_label:
            raise ValidationError({"source_label": "Enter the source skill wording."})
        if (
            self.candidate_id
            and self.skill_id
            and self.candidate.organization_id != self.skill.organization_id
        ):
            raise ValidationError(
                {"skill": "The skill must belong to the candidate organization."}
            )
        if (
            self.candidate_id
            and self.source_document_id
            and self.source_document.candidate_id != self.candidate_id
        ):
            raise ValidationError(
                {"source_document": "The document must belong to this candidate."}
            )
        if (
            self.candidate_id
            and self.source_profile_id
            and self.source_profile.candidate_id != self.candidate_id
        ):
            raise ValidationError(
                {"source_profile": "The profile must belong to this candidate."}
            )
        if (
            self.source_document_id
            and self.source_profile_id
            and self.source_profile.source_document_id != self.source_document_id
        ):
            raise ValidationError(
                {
                    "source_profile": (
                        "The profile and skill evidence must use the same document."
                    )
                }
            )
        if self.candidate_id and self.candidate.status == Candidate.Status.DELETED:
            raise ValidationError("Deleted candidates cannot receive skill records.")

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.candidate} — {self.skill}"


class RequirementSkill(models.Model):
    """A normalized skill linked to one immutable requirements snapshot."""

    class Importance(models.TextChoices):
        MUST_HAVE = "must_have", "Must have"
        NICE_TO_HAVE = "nice_to_have", "Nice to have"

    requirements = models.ForeignKey(
        VacancyRequirements,
        on_delete=models.CASCADE,
        related_name="skill_records",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="requirement_records",
    )
    importance = models.CharField(max_length=20, choices=Importance.choices)
    source_label = models.CharField(max_length=120)
    position = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = RequirementsOwnedQuerySet.as_manager()

    class Meta:
        ordering = ("importance", "position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("requirements", "skill"),
                name="unique_skill_per_requirements_version",
            ),
            models.UniqueConstraint(
                fields=("requirements", "importance", "position"),
                name="unique_skill_position_per_requirement_group",
            ),
            models.CheckConstraint(
                condition=models.Q(importance__in=["must_have", "nice_to_have"]),
                name="requirement_skill_has_valid_importance",
            ),
            models.CheckConstraint(
                condition=models.Q(position__gte=1),
                name="requirement_skill_position_is_positive",
            ),
        ]

    @property
    def organization(self) -> Organization:
        return self.requirements.organization

    def clean(self) -> None:
        super().clean()
        self.source_label = _WHITESPACE_RE.sub(" ", self.source_label.strip())
        if not self.source_label:
            raise ValidationError({"source_label": "Enter the source skill wording."})
        if (
            self.requirements_id
            and self.skill_id
            and self.requirements.vacancy.organization_id != self.skill.organization_id
        ):
            raise ValidationError(
                {"skill": "The skill must belong to the vacancy organization."}
            )
        if _requirements_are_confirmed(self.requirements_id):
            raise ValidationError(
                "Confirmed requirements skill links are immutable; "
                "create a new version."
            )

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if _requirements_are_confirmed(self.requirements_id):
            raise ValidationError(
                "Confirmed requirements skill links are immutable; "
                "create a new version."
            )
        return super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.requirements} — {self.skill}"


class HardConstraintRule(models.Model):
    """A typed, recruiter-confirmed rule for later deterministic evaluation."""

    class RuleType(models.TextChoices):
        REQUIRED_SKILL = "required_skill", "Required skill"
        MINIMUM_EXPERIENCE = "minimum_experience", "Minimum years of experience"
        LOCATION = "location", "Location"
        WORK_MODE = "work_mode", "Work mode"
        LANGUAGE = "language", "Language"
        EDUCATION = "education", "Education"
        CERTIFICATION = "certification", "Certification"
        EMPLOYMENT_TYPE = "employment_type", "Employment type"

    class Operator(models.TextChoices):
        HAS_SKILL = "has_skill", "Has skill"
        AT_LEAST = "at_least", "At least"
        EQUALS = "equals", "Equals"

    class UnknownOutcome(models.TextChoices):
        KEEP_FOR_REVIEW = "keep_for_review", "Keep for recruiter review"

    requirements = models.ForeignKey(
        VacancyRequirements,
        on_delete=models.CASCADE,
        related_name="hard_constraint_rules",
    )
    rule_type = models.CharField(max_length=30, choices=RuleType.choices)
    operator = models.CharField(max_length=20, choices=Operator.choices)
    source_text = models.TextField()
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="hard_constraint_rules",
    )
    expected_value = models.CharField(max_length=200, blank=True)
    normalized_expected_value = models.CharField(
        max_length=200,
        blank=True,
        editable=False,
    )
    numeric_value = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    unknown_outcome = models.CharField(
        max_length=30,
        choices=UnknownOutcome.choices,
        default=UnknownOutcome.KEEP_FOR_REVIEW,
        editable=False,
    )
    position = models.PositiveIntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_hard_constraint_rules",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = RequirementsOwnedQuerySet.as_manager()

    TEXT_RULE_TYPES = (
        RuleType.LOCATION,
        RuleType.WORK_MODE,
        RuleType.LANGUAGE,
        RuleType.EDUCATION,
        RuleType.CERTIFICATION,
        RuleType.EMPLOYMENT_TYPE,
    )

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("requirements", "position"),
                name="unique_hard_constraint_position_per_version",
            ),
            models.CheckConstraint(
                condition=models.Q(position__gte=1),
                name="hard_constraint_position_is_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    rule_type__in=[
                        "required_skill",
                        "minimum_experience",
                        "location",
                        "work_mode",
                        "language",
                        "education",
                        "certification",
                        "employment_type",
                    ]
                ),
                name="hard_constraint_has_valid_type",
            ),
            models.CheckConstraint(
                condition=models.Q(operator__in=["has_skill", "at_least", "equals"]),
                name="hard_constraint_has_valid_operator",
            ),
            models.CheckConstraint(
                condition=models.Q(unknown_outcome="keep_for_review"),
                name="hard_constraint_unknown_keeps_candidate",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        rule_type="required_skill",
                        operator="has_skill",
                        skill__isnull=False,
                        expected_value="",
                        normalized_expected_value="",
                        numeric_value__isnull=True,
                    )
                    | models.Q(
                        rule_type="minimum_experience",
                        operator="at_least",
                        skill__isnull=True,
                        expected_value="",
                        normalized_expected_value="",
                        numeric_value__isnull=False,
                    )
                    | (
                        models.Q(
                            rule_type__in=[
                                "location",
                                "work_mode",
                                "language",
                                "education",
                                "certification",
                                "employment_type",
                            ],
                            operator="equals",
                            skill__isnull=True,
                            numeric_value__isnull=True,
                        )
                        & ~models.Q(expected_value="")
                        & ~models.Q(normalized_expected_value="")
                    )
                ),
                name="hard_constraint_payload_matches_type",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(numeric_value__isnull=True)
                    | models.Q(numeric_value__gte=0)
                ),
                name="hard_constraint_numeric_is_nonnegative",
            ),
        ]

    @property
    def organization(self) -> Organization:
        return self.requirements.organization

    @property
    def expected_display(self) -> str:
        if self.skill_id:
            return self.skill.name
        if self.numeric_value is not None:
            return f"{self.numeric_value} years"
        return self.expected_value

    def clean(self) -> None:
        super().clean()
        self.source_text = self.source_text.strip()
        if not self.source_text:
            raise ValidationError(
                {"source_text": "Record the explicit source wording."}
            )
        if _requirements_are_confirmed(self.requirements_id):
            raise ValidationError(
                "Confirmed hard-constraint rules are immutable; create a new version."
            )
        if (
            self.requirements_id
            and self.skill_id
            and self.requirements.vacancy.organization_id != self.skill.organization_id
        ):
            raise ValidationError(
                {"skill": "The skill must belong to the vacancy organization."}
            )

        if self.rule_type == self.RuleType.REQUIRED_SKILL:
            if self.operator != self.Operator.HAS_SKILL or not self.skill_id:
                raise ValidationError(
                    "A required-skill rule must use the has-skill operator and a skill."
                )
            if self.expected_value or self.numeric_value is not None:
                raise ValidationError("A required-skill rule accepts only a skill.")
            self.normalized_expected_value = ""
        elif self.rule_type == self.RuleType.MINIMUM_EXPERIENCE:
            if self.operator != self.Operator.AT_LEAST or self.numeric_value is None:
                raise ValidationError(
                    "A minimum-experience rule must use at-least and a number."
                )
            if self.skill_id or self.expected_value:
                raise ValidationError(
                    "A minimum-experience rule accepts only a numeric value."
                )
            self.normalized_expected_value = ""
        elif self.rule_type in self.TEXT_RULE_TYPES:
            if self.operator != self.Operator.EQUALS or not self.expected_value.strip():
                raise ValidationError(
                    "This rule must use equals and a non-blank expected value."
                )
            if self.skill_id or self.numeric_value is not None:
                raise ValidationError("This rule accepts only a text value.")
            self.expected_value = _WHITESPACE_RE.sub(
                " ", unicodedata.normalize("NFKC", self.expected_value).strip()
            )
            self.normalized_expected_value = normalize_taxonomy_value(
                self.expected_value
            )
            if len(self.normalized_expected_value) > 200:
                raise ValidationError(
                    {"expected_value": "The normalized expected value is too long."}
                )
            if (
                self.rule_type == self.RuleType.WORK_MODE
                and self.normalized_expected_value
                not in VacancyRequirements.WorkMode.values
            ):
                raise ValidationError(
                    {"expected_value": "Select a supported work-mode value."}
                )
            if (
                self.rule_type == self.RuleType.EMPLOYMENT_TYPE
                and self.normalized_expected_value
                not in VacancyRequirements.EmploymentType.values
            ):
                raise ValidationError(
                    {"expected_value": "Select a supported employment-type value."}
                )
        else:
            raise ValidationError({"rule_type": "Select a supported rule type."})

        if self.unknown_outcome != self.UnknownOutcome.KEEP_FOR_REVIEW:
            raise ValidationError(
                {"unknown_outcome": "Unknown facts must stay eligible for review."}
            )
        if (
            self.rule_type == self.RuleType.REQUIRED_SKILL
            and self.requirements_id
            and self.skill_id
            and not RequirementSkill.objects.filter(
                requirements_id=self.requirements_id,
                skill_id=self.skill_id,
                importance=RequirementSkill.Importance.MUST_HAVE,
            ).exists()
        ):
            raise ValidationError(
                {"skill": "A required-skill rule must reference a must-have skill."}
            )

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if _requirements_are_confirmed(self.requirements_id):
            raise ValidationError(
                "Confirmed hard-constraint rules are immutable; create a new version."
            )
        return super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.requirements} — rule {self.position}"


class MatchRun(models.Model):
    """One version-labelled deterministic shortlist generation event."""

    requirements = models.ForeignKey(
        VacancyRequirements,
        on_delete=models.PROTECT,
        related_name="match_runs",
    )
    algorithm_version = models.CharField(max_length=50)
    input_snapshot_version = models.CharField(
        max_length=50,
        default="deterministic_match_inputs.v1",
    )
    requirements_input_signature = models.CharField(max_length=64, blank=True)
    candidate_input_signature = models.CharField(max_length=64, blank=True)
    shortlist_limit = models.PositiveIntegerField()
    evaluated_count = models.PositiveIntegerField()
    eligible_count = models.PositiveIntegerField()
    shortlisted_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_match_runs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = MatchRunQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(shortlist_limit__gte=1),
                name="match_run_limit_is_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(eligible_count__lte=models.F("evaluated_count")),
                name="match_run_eligible_not_above_evaluated",
            ),
            models.CheckConstraint(
                condition=models.Q(shortlisted_count__lte=models.F("eligible_count")),
                name="match_run_shortlisted_not_above_eligible",
            ),
            models.CheckConstraint(
                condition=models.Q(shortlisted_count__lte=models.F("shortlist_limit")),
                name="match_run_shortlisted_not_above_limit",
            ),
        ]

    @property
    def organization(self) -> Organization:
        return self.requirements.organization

    @property
    def vacancy(self):
        return self.requirements.vacancy

    def clean(self) -> None:
        super().clean()
        if self.requirements_id and not _requirements_are_confirmed(
            self.requirements_id
        ):
            raise ValidationError(
                {"requirements": "A match run requires confirmed requirements."}
            )
        if (
            self.eligible_count is not None
            and self.evaluated_count is not None
            and self.eligible_count > self.evaluated_count
        ):
            raise ValidationError(
                {"eligible_count": "Eligible count cannot exceed evaluated count."}
            )
        if (
            self.shortlisted_count is not None
            and self.eligible_count is not None
            and self.shortlisted_count > self.eligible_count
        ):
            raise ValidationError(
                {"shortlisted_count": "Shortlisted count cannot exceed eligible count."}
            )
        if (
            self.shortlisted_count is not None
            and self.shortlist_limit is not None
            and self.shortlisted_count > self.shortlist_limit
        ):
            raise ValidationError(
                {"shortlisted_count": "Shortlisted count cannot exceed the limit."}
            )

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"{self.requirements.vacancy} — shortlist run {self.pk or 'new'} "
            f"(requirements v{self.requirements.version})"
        )


class ShortlistEntry(models.Model):
    """A ranked candidate and its inspectable deterministic skill score."""

    class FilterOutcome(models.TextChoices):
        PASSED = "passed", "Passed"
        REVIEW = "review", "Needs review"

    match_run = models.ForeignKey(
        MatchRun,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.PROTECT,
        related_name="shortlist_entries",
    )
    rank = models.PositiveIntegerField()
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    filter_outcome = models.CharField(max_length=20, choices=FilterOutcome.choices)
    matched_must_have = models.PositiveIntegerField(default=0)
    total_must_have = models.PositiveIntegerField(default=0)
    matched_nice_to_have = models.PositiveIntegerField(default=0)
    total_nice_to_have = models.PositiveIntegerField(default=0)
    score_breakdown = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ShortlistEntryQuerySet.as_manager()

    class Meta:
        ordering = ("rank", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("match_run", "candidate"),
                name="unique_candidate_per_match_run",
            ),
            models.UniqueConstraint(
                fields=("match_run", "rank"),
                name="unique_rank_per_match_run",
            ),
            models.CheckConstraint(
                condition=models.Q(rank__gte=1),
                name="shortlist_entry_rank_is_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(score__gte=0) & models.Q(score__lte=100),
                name="shortlist_entry_score_in_range",
            ),
            models.CheckConstraint(
                condition=models.Q(filter_outcome__in=["passed", "review"]),
                name="shortlist_entry_has_eligible_filter_outcome",
            ),
            models.CheckConstraint(
                condition=models.Q(matched_must_have__lte=models.F("total_must_have")),
                name="shortlist_must_match_not_above_total",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    matched_nice_to_have__lte=models.F("total_nice_to_have")
                ),
                name="shortlist_nice_match_not_above_total",
            ),
        ]

    @property
    def organization(self) -> Organization:
        return self.match_run.organization

    def clean(self) -> None:
        super().clean()
        if (
            self.match_run_id
            and self.candidate_id
            and self.match_run.organization.pk != self.candidate.organization_id
        ):
            raise ValidationError(
                {
                    "candidate": (
                        "The candidate must belong to the match-run organization."
                    )
                }
            )
        if self.matched_must_have > self.total_must_have:
            raise ValidationError("Matched must-have skills cannot exceed the total.")
        if self.matched_nice_to_have > self.total_nice_to_have:
            raise ValidationError(
                "Matched nice-to-have skills cannot exceed the total."
            )
        if not isinstance(self.score_breakdown, list):
            raise ValidationError({"score_breakdown": "Enter a list."})

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"#{self.rank} {self.candidate} — {self.score}"
