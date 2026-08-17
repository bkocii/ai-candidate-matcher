from django import forms

from candidates.models import CandidateIntakeBatch, CandidateSource

MAX_INTAKE_FILES_PER_UPLOAD = 10
MAX_INTAKE_UPLOAD_BYTES = 10 * 1024 * 1024


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        return [single_clean(data, initial)]


class CandidateCVUploadForm(forms.Form):
    cv_file = forms.FileField(
        label="CV file",
        help_text="PDF or DOCX, up to 10 MB. Scanned-image PDFs are not supported.",
        widget=forms.ClearableFileInput(
            attrs={
                "accept": (
                    ".pdf,.docx,application/pdf,"
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                )
            }
        ),
    )
    retention_until = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Optional date for reviewing or removing this stored document.",
    )


class CandidateManualEntryForm(forms.Form):
    full_name = forms.CharField(max_length=200)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=50, required=False)
    location = forms.CharField(max_length=200, required=False)
    candidate_retention_until = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Optional date for reviewing or removing the candidate record.",
    )
    source_name = forms.CharField(
        max_length=200,
        initial="Manual recruiter entry",
        help_text="Where this candidate record came from.",
    )
    source_reference = forms.CharField(
        max_length=500,
        required=False,
        help_text="Optional stable ID or reference from the original source.",
    )
    lawful_basis = forms.ChoiceField(
        choices=CandidateSource.LawfulBasis.choices,
        initial=CandidateSource.LawfulBasis.NOT_RECORDED,
    )
    consent_status = forms.ChoiceField(
        choices=CandidateSource.ConsentStatus.choices,
        initial=CandidateSource.ConsentStatus.UNKNOWN,
    )
    contact_permission = forms.ChoiceField(
        choices=CandidateSource.ContactPermission.choices,
        initial=CandidateSource.ContactPermission.UNKNOWN,
    )
    permission_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    source_retention_until = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Optional retention date for this provenance record.",
    )


class CandidateCSVImportForm(forms.Form):
    csv_file = forms.FileField(
        label="CSV file",
        help_text="UTF-8, comma-separated, up to 2 MB and 2,000 data rows.",
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}),
    )
    source_name = forms.CharField(
        max_length=200,
        help_text="Applied to every candidate created by this import.",
    )
    lawful_basis = forms.ChoiceField(
        choices=CandidateSource.LawfulBasis.choices,
        initial=CandidateSource.LawfulBasis.NOT_RECORDED,
    )
    consent_status = forms.ChoiceField(
        choices=CandidateSource.ConsentStatus.choices,
        initial=CandidateSource.ConsentStatus.UNKNOWN,
    )
    contact_permission = forms.ChoiceField(
        choices=CandidateSource.ContactPermission.choices,
        initial=CandidateSource.ContactPermission.UNKNOWN,
    )
    permission_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Applied to every source record created by this import.",
    )
    source_retention_until = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )


class CandidateIntakeBatchForm(forms.ModelForm):
    class Meta:
        model = CandidateIntakeBatch
        fields = (
            "source_name",
            "lawful_basis",
            "consent_status",
            "contact_permission",
            "permission_notes",
            "candidate_retention_until",
            "source_retention_until",
            "document_retention_until",
        )
        widgets = {
            "permission_notes": forms.Textarea(attrs={"rows": 3}),
            "candidate_retention_until": forms.DateInput(attrs={"type": "date"}),
            "source_retention_until": forms.DateInput(attrs={"type": "date"}),
            "document_retention_until": forms.DateInput(attrs={"type": "date"}),
        }
        help_texts = {
            "source_name": "Where every CV in this batch was obtained.",
            "candidate_retention_until": (
                "Optional review/removal date applied to created candidates."
            ),
            "source_retention_until": (
                "Optional retention date applied to each provenance record."
            ),
            "document_retention_until": (
                "Optional retention date applied to each accepted CV."
            ),
        }


class CandidateIntakeUploadForm(forms.Form):
    cv_files = MultipleFileField(
        label="CV files",
        help_text=(
            "Select up to 10 PDF/DOCX files per upload. The combined request and "
            "each file must remain within 10 MB; repeat uploads can add up to 50 "
            "items to the batch."
        ),
        widget=MultipleFileInput(
            attrs={
                "accept": (
                    ".pdf,.docx,application/pdf,"
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                )
            }
        ),
    )

    def clean_cv_files(self):
        files = self.cleaned_data["cv_files"]
        if len(files) > MAX_INTAKE_FILES_PER_UPLOAD:
            raise forms.ValidationError(
                f"Select no more than {MAX_INTAKE_FILES_PER_UPLOAD} files at once."
            )
        total_bytes = sum(getattr(uploaded, "size", 0) for uploaded in files)
        if total_bytes > MAX_INTAKE_UPLOAD_BYTES:
            raise forms.ValidationError(
                "The combined upload exceeds the 10 MB request limit. Upload "
                "fewer files and repeat."
            )
        return files


class CandidateIntakeReviewForm(forms.Form):
    selected = forms.BooleanField(required=False)
    full_name = forms.CharField(max_length=200, required=False)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=50, required=False)
    location = forms.CharField(max_length=200, required=False)
    source_reference = forms.CharField(max_length=500, required=False)

    def clean(self):
        cleaned_data = super().clean()
        for field_name in (
            "full_name",
            "email",
            "phone",
            "location",
            "source_reference",
        ):
            value = cleaned_data.get(field_name)
            if isinstance(value, str):
                cleaned_data[field_name] = value.strip()
        if cleaned_data.get("selected") and not cleaned_data.get("full_name"):
            self.add_error("full_name", "A full name is required before creation.")
        return cleaned_data


class CandidateCSVRowForm(forms.Form):
    full_name = forms.CharField(max_length=200)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=50, required=False)
    location = forms.CharField(max_length=200, required=False)
    source_reference = forms.CharField(max_length=500, required=False)
    retention_until = forms.DateField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        for field_name in (
            "full_name",
            "email",
            "phone",
            "location",
            "source_reference",
        ):
            value = cleaned_data.get(field_name)
            if isinstance(value, str):
                cleaned_data[field_name] = value.strip()
        return cleaned_data


def candidate_values_from_manual_form(form: CandidateManualEntryForm) -> dict:
    return {
        "full_name": form.cleaned_data["full_name"].strip(),
        "email": form.cleaned_data["email"].strip(),
        "phone": form.cleaned_data["phone"].strip(),
        "location": form.cleaned_data["location"].strip(),
        "retention_until": form.cleaned_data["candidate_retention_until"],
    }


def source_values_from_manual_form(form: CandidateManualEntryForm) -> dict:
    return {
        "source_type": CandidateSource.SourceType.MANUAL_ENTRY,
        "source_name": form.cleaned_data["source_name"].strip(),
        "source_reference": form.cleaned_data["source_reference"].strip(),
        "lawful_basis": form.cleaned_data["lawful_basis"],
        "consent_status": form.cleaned_data["consent_status"],
        "contact_permission": form.cleaned_data["contact_permission"],
        "permission_notes": form.cleaned_data["permission_notes"].strip(),
        "retention_until": form.cleaned_data["source_retention_until"],
    }


def source_values_from_import_form(form: CandidateCSVImportForm) -> dict:
    return {
        "source_type": CandidateSource.SourceType.CSV_IMPORT,
        "source_name": form.cleaned_data["source_name"].strip(),
        "lawful_basis": form.cleaned_data["lawful_basis"],
        "consent_status": form.cleaned_data["consent_status"],
        "contact_permission": form.cleaned_data["contact_permission"],
        "permission_notes": form.cleaned_data["permission_notes"].strip(),
        "retention_until": form.cleaned_data["source_retention_until"],
    }
