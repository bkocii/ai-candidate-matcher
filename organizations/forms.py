from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.text import slugify

from accounts.models import User
from candidates.models import CandidateIntakeItem
from matching.models import MatchRun
from operations.models import BackgroundJob
from organizations.models import (
    ClientCompany,
    Organization,
    OrganizationRetentionPolicy,
    RetentionException,
)
from outreach.models import OutreachDraft


class ManagedMembershipForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        validators=(UnicodeUsernameValidator(),),
        help_text=(
            "Enter an existing username to add its account, or a new username "
            "to create an account."
        ),
    )
    email = forms.EmailField(
        required=False,
        help_text="Required only when creating a new account.",
    )
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    temporary_password = forms.CharField(
        required=False,
        strip=False,
        widget=forms.PasswordInput,
        help_text=(
            "Required only for a new account. Share it securely and ask the "
            "user to change it after signing in."
        ),
    )
    temporary_password_confirmation = forms.CharField(
        required=False,
        strip=False,
        widget=forms.PasswordInput,
        label="Confirm temporary password",
    )

    def clean_username(self) -> str:
        return self.cleaned_data["username"].strip()

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username", "")
        if not username:
            return cleaned_data
        existing = User.objects.filter(username__iexact=username).first()
        password = cleaned_data.get("temporary_password", "")
        confirmation = cleaned_data.get("temporary_password_confirmation", "")
        if existing is not None:
            if not existing.is_active:
                self.add_error("username", "The existing user account is inactive.")
            if password or confirmation:
                self.add_error(
                    "temporary_password",
                    "Leave password fields blank when adding an existing account.",
                )
            return cleaned_data

        if not cleaned_data.get("email"):
            self.add_error("email", "Email is required for a new account.")
        if not password:
            self.add_error("temporary_password", "A temporary password is required.")
        elif password != confirmation:
            self.add_error(
                "temporary_password_confirmation", "The passwords do not match."
            )
        else:
            proposed_user = User(
                username=username,
                email=cleaned_data.get("email", ""),
                first_name=cleaned_data.get("first_name", ""),
                last_name=cleaned_data.get("last_name", ""),
            )
            try:
                password_validation.validate_password(password, proposed_user)
            except ValidationError as error:
                self.add_error("temporary_password", error)
        return cleaned_data

    def managed_user_values(self) -> dict:
        return {
            "username": self.cleaned_data["username"],
            "email": self.cleaned_data.get("email", ""),
            "first_name": self.cleaned_data.get("first_name", ""),
            "last_name": self.cleaned_data.get("last_name", ""),
            "temporary_password": self.cleaned_data.get("temporary_password", ""),
        }


class ExistingManagedMembershipForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        validators=(UnicodeUsernameValidator(),),
        label="Existing username",
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
        help_text="Enter the exact username, then verify the matched identity.",
    )

    def clean_username(self) -> str:
        username = self.cleaned_data["username"].strip()
        user = User.objects.filter(username__iexact=username).first()
        if user is None:
            raise ValidationError("No account matches this username.")
        if not user.is_active:
            raise ValidationError("This user account is inactive.")
        self.existing_user = user
        return user.username

    def managed_user_values(self) -> dict:
        return {
            "username": self.cleaned_data["username"],
            "email": "",
            "first_name": "",
            "last_name": "",
            "temporary_password": "",
        }


class NewManagedMembershipForm(ManagedMembershipForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = "Create a unique username for this account."
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["email"].required = True
        self.fields[
            "email"
        ].help_text = "Used to identify and contact this administrator."
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["first_name"].widget.attrs["autocomplete"] = "given-name"
        self.fields["last_name"].widget.attrs["autocomplete"] = "family-name"
        self.fields["temporary_password"].widget.attrs["autocomplete"] = "new-password"
        self.fields["temporary_password_confirmation"].widget.attrs["autocomplete"] = (
            "new-password"
        )

    def clean_username(self) -> str:
        username = super().clean_username()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError(
                "This account already exists. Use Add existing account instead."
            )
        return username


class OrganizationProvisionForm(ManagedMembershipForm):
    field_order = (
        "organization_name",
        "username",
        "email",
        "first_name",
        "last_name",
        "temporary_password",
        "temporary_password_confirmation",
    )
    organization_name = forms.CharField(max_length=200, label="Organization name")

    def clean_organization_name(self) -> str:
        return self.cleaned_data["organization_name"].strip()


class OrganizationProvisionFieldsMixin:
    def clean_organization_name(self) -> str:
        return self.cleaned_data["organization_name"].strip()

    def clean_organization_slug(self) -> str:
        slug = self.cleaned_data["organization_slug"].strip().lower()
        if not slug:
            slug = slugify(self.cleaned_data.get("organization_name", ""))[:200]
        if Organization.objects.filter(slug=slug).exists():
            raise ValidationError("This workspace URL is already in use.")
        return slug


class ExistingOrganizationProvisionForm(
    OrganizationProvisionFieldsMixin, ExistingManagedMembershipForm
):
    organization_name = forms.CharField(max_length=200, label="Organization name")
    organization_slug = forms.SlugField(
        max_length=200,
        required=False,
        label="Workspace URL",
        help_text="Stable identifier used in organization URLs.",
    )
    field_order = ("organization_name", "organization_slug", "username")


class NewOrganizationProvisionForm(
    OrganizationProvisionFieldsMixin, NewManagedMembershipForm
):
    organization_name = forms.CharField(max_length=200, label="Organization name")
    organization_slug = forms.SlugField(
        max_length=200,
        required=False,
        label="Workspace URL",
        help_text="Stable identifier used in organization URLs.",
    )
    field_order = (
        "organization_name",
        "organization_slug",
        "username",
        "email",
        "first_name",
        "last_name",
        "temporary_password",
        "temporary_password_confirmation",
    )


class ClientCompanyForm(forms.ModelForm):
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"inputmode": "url", "placeholder": "company.com"}
        ),
        help_text="Optional. Helps your team identify the hiring client.",
    )

    class Meta:
        model = ClientCompany
        fields = ("name", "website")
        labels = {"name": "Hiring client name"}

    def clean_name(self) -> str:
        return self.cleaned_data["name"].strip()

    def clean_website(self) -> str:
        website = self.cleaned_data["website"].strip()
        if not website:
            return ""
        if "://" not in website:
            website = f"https://{website}"
        URLValidator(schemes=("http", "https"))(website)
        return website


class OrganizationRetentionPolicyForm(forms.ModelForm):
    class Meta:
        model = OrganizationRetentionPolicy
        fields = (
            "temporary_intake_days",
            "completed_job_days",
            "uncommitted_workflow_days",
            "metadata_days",
            "organization_recovery_days",
            "legal_hold",
        )
        labels = {
            "temporary_intake_days": "Abandoned intake after (days)",
            "completed_job_days": "Completed job history after (days)",
            "uncommitted_workflow_days": (
                "Unused shortlists and abandoned outreach after (days)"
            ),
            "metadata_days": "AI usage and audit history after (days)",
            "organization_recovery_days": "Organization recovery window (days)",
            "legal_hold": "Pause all scheduled deletion (legal hold)",
        }
        help_texts = {
            "legal_hold": (
                "Blocks automatic cleanup and organization purge until removed."
            )
        }


class RetentionExceptionForm(forms.Form):
    target = forms.ChoiceField(label="What should be protected?")
    reason = forms.CharField(
        max_length=500,
        help_text=(
            "Use a short operational reason. Do not include candidate, CV, "
            "decision, or outreach content."
        ),
    )
    expires_at = forms.DateField(
        required=False,
        label="Expiry date",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Optional. Leave blank when the exception has no planned expiry.",
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["target"].choices = self._target_choices()

    @staticmethod
    def _value(scope: str, object_id: int | None = None) -> str:
        return f"{scope}:{object_id or ''}"

    def _target_choices(self):
        groups = []
        intake_choices = [
            (self._value(RetentionException.Scope.TEMPORARY_INTAKE), "Entire group")
        ]
        intake_choices.extend(
            (
                self._value(RetentionException.Scope.TEMPORARY_INTAKE, item.pk),
                f"Intake item #{item.pk} — {item.get_status_display()}",
            )
            for item in CandidateIntakeItem.objects.for_organization(self.organization)[
                :100
            ]
        )
        groups.append(("Temporary candidate intake", intake_choices))

        job_choices = [
            (self._value(RetentionException.Scope.COMPLETED_JOBS), "Entire group")
        ]
        job_choices.extend(
            (
                self._value(RetentionException.Scope.COMPLETED_JOBS, job.pk),
                f"Processing job #{job.pk} — {job.get_status_display()}",
            )
            for job in BackgroundJob.objects.for_organization(self.organization).filter(
                status__in=[
                    BackgroundJob.Status.SUCCEEDED,
                    BackgroundJob.Status.COMPLETED_WITH_ERRORS,
                ]
            )[:100]
        )
        groups.append(("Completed processing activity", job_choices))

        shortlist_choices = [
            (self._value(RetentionException.Scope.MATCH_RUNS), "Entire group")
        ]
        shortlist_choices.extend(
            (
                self._value(RetentionException.Scope.MATCH_RUNS, run.pk),
                f"Shortlist #{run.pk}",
            )
            for run in MatchRun.objects.for_organization(self.organization)[:100]
        )
        groups.append(("Older shortlists", shortlist_choices))

        outreach_choices = [
            (self._value(RetentionException.Scope.OUTREACH), "Entire group")
        ]
        outreach_entry_ids = (
            OutreachDraft.objects.for_organization(self.organization)
            .values_list("shortlist_entry_id", flat=True)
            .distinct()[:100]
        )
        outreach_choices.extend(
            (
                self._value(RetentionException.Scope.OUTREACH, entry_id),
                f"Outreach chain for shortlist entry #{entry_id}",
            )
            for entry_id in outreach_entry_ids
        )
        groups.append(("Unapproved outreach", outreach_choices))
        groups.append(
            (
                "Operational records",
                [
                    (
                        self._value(RetentionException.Scope.METADATA),
                        "All AI usage and audit history",
                    )
                ],
            )
        )
        groups.append(
            (
                "Organization deletion",
                [
                    (
                        self._value(RetentionException.Scope.ORGANIZATION),
                        f"{self.organization.name} organization deletion",
                    )
                ],
            )
        )
        return [("", "Choose what to protect"), *groups]

    def save(self, *, user) -> RetentionException:
        scope, raw_object_id = self.cleaned_data["target"].split(":", 1)
        exception = RetentionException(
            organization=self.organization,
            scope=scope,
            object_id=int(raw_object_id) if raw_object_id else None,
            reason=self.cleaned_data["reason"].strip(),
            expires_at=self.cleaned_data["expires_at"],
            created_by=user,
        )
        exception.full_clean()
        exception.save()
        return exception


class ApplyRetentionForm(forms.Form):
    confirmation = forms.CharField(
        label='Type "PURGE ELIGIBLE DATA" to confirm',
        max_length=30,
    )

    def clean_confirmation(self) -> str:
        value = self.cleaned_data["confirmation"].strip()
        if value != "PURGE ELIGIBLE DATA":
            raise forms.ValidationError("Enter the exact confirmation phrase.")
        return value


class RequestOrganizationDeletionForm(forms.Form):
    confirmation = forms.CharField(max_length=240)

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.confirmation_phrase = f"SUSPEND {organization.name.upper()}"
        self.fields[
            "confirmation"
        ].label = f'Type "{self.confirmation_phrase}" to confirm'
        self.fields["confirmation"].widget.attrs.update(
            {
                "autocomplete": "off",
                "spellcheck": "false",
            }
        )

    def clean_confirmation(self) -> str:
        value = self.cleaned_data["confirmation"].strip()
        if value != self.confirmation_phrase:
            raise forms.ValidationError("Enter the exact confirmation phrase.")
        return value
