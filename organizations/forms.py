from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError

from accounts.models import User
from organizations.models import (
    ClientCompany,
    OrganizationRetentionPolicy,
    RetentionException,
)


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


class ClientCompanyForm(forms.ModelForm):
    website = forms.URLField(
        required=False,
        assume_scheme="https",
        help_text="Optional. Used only as organization-owned reference metadata.",
    )

    class Meta:
        model = ClientCompany
        fields = ("name", "website")
        labels = {"name": "Client company name"}

    def clean_name(self) -> str:
        return self.cleaned_data["name"].strip()


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
            "uncommitted_workflow_days": "Uncommitted workflow history after (days)",
            "metadata_days": "Usage and audit metadata after (days)",
            "organization_recovery_days": "Organization recovery window (days)",
            "legal_hold": "Pause all scheduled deletion (legal hold)",
        }
        help_texts = {
            "legal_hold": (
                "Blocks automatic cleanup and organization purge until removed."
            )
        }


class RetentionExceptionForm(forms.ModelForm):
    class Meta:
        model = RetentionException
        fields = ("scope", "object_id", "reason", "expires_at")
        widgets = {"expires_at": forms.DateInput(attrs={"type": "date"})}
        help_texts = {
            "object_id": "Leave blank to pause this entire retention group.",
            "reason": "Do not copy candidate, CV, decision, or outreach content here.",
        }


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
    confirmation = forms.CharField(
        label='Type "DELETE ORGANIZATION" to confirm suspension',
        max_length=30,
    )

    def clean_confirmation(self) -> str:
        value = self.cleaned_data["confirmation"].strip()
        if value != "DELETE ORGANIZATION":
            raise forms.ValidationError("Enter the exact confirmation phrase.")
        return value
