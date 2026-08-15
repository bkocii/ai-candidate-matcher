import re

from django import forms

_UNSAFE_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean_plain_text(value: str) -> str:
    value = value.strip()
    if _UNSAFE_CONTROL_RE.search(value):
        raise forms.ValidationError("Remove unsupported control characters.")
    return value


class OutreachDraftEditForm(forms.Form):
    subject = forms.CharField(
        max_length=200,
        help_text="Use only organization-verified facts and wording.",
    )
    body = forms.CharField(
        max_length=5_000,
        widget=forms.Textarea(attrs={"rows": 14}),
        help_text=(
            "Plain text only. Saving creates a new immutable version that needs "
            "its own final approval."
        ),
    )

    def clean_subject(self) -> str:
        return _clean_plain_text(self.cleaned_data["subject"])

    def clean_body(self) -> str:
        return _clean_plain_text(self.cleaned_data["body"])


class OutreachDraftApprovalForm(forms.Form):
    notes = forms.CharField(
        max_length=2_000,
        label="Final approval notes",
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Record what you checked before approving this exact draft.",
    )
    contact_permission_confirmed = forms.BooleanField(
        label=(
            "I verified the candidate's recorded contact permission and approve "
            "this exact subject and body."
        ),
    )

    def clean_notes(self) -> str:
        notes = _clean_plain_text(self.cleaned_data["notes"])
        if not notes:
            raise forms.ValidationError("Record final approval notes.")
        return notes
