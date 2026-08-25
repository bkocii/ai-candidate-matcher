from django import forms

from organizations.models import OrganizationRetentionPolicy, RetentionException


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
