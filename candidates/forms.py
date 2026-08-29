from django import forms

from candidates.models import (
    Candidate,
    CandidateIntakeBatch,
    CandidateProfile,
    CandidateSource,
)
from candidates.privacy import (
    CONSENT_HELP_TEXT,
    CONSENT_STATUS_LABELS,
    CONTACT_PERMISSION_HELP_TEXT,
    CONTACT_PERMISSION_LABELS,
    LAWFUL_BASIS_HELP_TEXT,
    LAWFUL_BASIS_LABELS,
    RETENTION_HELP_TEXT,
    SOURCE_NAME_HELP_TEXT,
    SOURCE_REFERENCE_HELP_TEXT,
    form_choices,
)

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
        label="Delete or review on",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text=RETENTION_HELP_TEXT,
    )


class CandidateEditForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ("full_name", "email", "phone", "location", "retention_until")
        widgets = {"retention_until": forms.DateInput(attrs={"type": "date"})}
        labels = {"retention_until": "Delete or review on"}
        help_texts = {"retention_until": RETENTION_HELP_TEXT}


class CandidateSourceEditForm(forms.ModelForm):
    class Meta:
        model = CandidateSource
        fields = (
            "source_name",
            "source_reference",
            "lawful_basis",
            "consent_status",
            "contact_permission",
            "permission_notes",
            "retention_until",
        )
        widgets = {
            "permission_notes": forms.Textarea(attrs={"rows": 3}),
            "retention_until": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "lawful_basis": "Reason for storing data",
            "consent_status": "Consent",
            "contact_permission": "Allowed contact",
            "permission_notes": "Privacy and contact notes",
            "retention_until": "Delete or review on",
        }
        help_texts = {
            "source_name": SOURCE_NAME_HELP_TEXT,
            "source_reference": SOURCE_REFERENCE_HELP_TEXT,
            "lawful_basis": LAWFUL_BASIS_HELP_TEXT,
            "consent_status": CONSENT_HELP_TEXT,
            "contact_permission": CONTACT_PERMISSION_HELP_TEXT,
            "retention_until": RETENTION_HELP_TEXT,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["lawful_basis"].choices = form_choices(
            CandidateSource.LawfulBasis.choices, LAWFUL_BASIS_LABELS
        )
        self.fields["consent_status"].choices = form_choices(
            CandidateSource.ConsentStatus.choices, CONSENT_STATUS_LABELS
        )
        self.fields["contact_permission"].choices = form_choices(
            CandidateSource.ContactPermission.choices, CONTACT_PERMISSION_LABELS
        )


class CandidateProfileCorrectionForm(forms.Form):
    relevant_experience_summary = forms.CharField(
        label="Relevant experience summary",
        required=False,
        max_length=2_000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    relevant_experience_summary_evidence = forms.CharField(
        label="Summary CV evidence",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Keep this as a short verbatim excerpt from the CV.",
    )
    location = forms.CharField(required=False, max_length=200)
    location_evidence = forms.CharField(
        label="Location CV evidence",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Required when a location is recorded.",
    )
    work_mode_preference = forms.ChoiceField(
        label="Work mode preference",
        choices=CandidateProfile.WorkMode.choices,
    )
    work_mode_preference_evidence = forms.CharField(
        label="Work mode CV evidence",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    availability = forms.CharField(required=False, max_length=300)
    availability_evidence = forms.CharField(
        label="Availability CV evidence",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    retained_skills = forms.MultipleChoiceField(
        label="Supported skills to retain",
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text=(
            "Uncheck a skill that was misclassified. New skills require a new "
            "evidence-reviewed extraction."
        ),
    )
    ambiguities = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Enter one unresolved ambiguity per line, or leave blank.",
    )

    def __init__(self, *args, profile: CandidateProfile, **kwargs):
        self.profile = profile
        initial = {
            "relevant_experience_summary": profile.relevant_experience_summary,
            "relevant_experience_summary_evidence": profile.fact_evidence.get(
                "relevant_experience_summary", ""
            ),
            "location": profile.location,
            "location_evidence": profile.fact_evidence.get("location", ""),
            "work_mode_preference": profile.work_mode_preference,
            "work_mode_preference_evidence": profile.fact_evidence.get(
                "work_mode_preference", ""
            ),
            "availability": profile.availability,
            "availability_evidence": profile.fact_evidence.get("availability", ""),
            "retained_skills": [str(index) for index in range(len(profile.skills))],
            "ambiguities": "\n".join(profile.ambiguities),
        }
        initial.update(kwargs.pop("initial", {}))
        super().__init__(*args, initial=initial, **kwargs)
        self.fields["retained_skills"].choices = tuple(
            (str(index), f"{skill['name']} — {skill['evidence']}")
            for index, skill in enumerate(profile.skills)
        )

    def clean_ambiguities(self):
        value = self.cleaned_data["ambiguities"]
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        if len(lines) > 40:
            raise forms.ValidationError("Record no more than 40 ambiguities.")
        if any(len(line) > 500 for line in lines):
            raise forms.ValidationError(
                "Each ambiguity must contain no more than 500 characters."
            )
        if len({line.casefold() for line in lines}) != len(lines):
            raise forms.ValidationError("Remove duplicate ambiguity lines.")
        return lines


class CandidateManualEntryForm(forms.Form):
    full_name = forms.CharField(max_length=200)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=50, required=False)
    location = forms.CharField(max_length=200, required=False)
    cv_file = forms.FileField(
        required=False,
        label="CV file (optional)",
        help_text=(
            "Add a PDF or DOCX now, up to 10 MB, or upload one from the candidate "
            "record later."
        ),
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
    candidate_retention_until = forms.DateField(
        label="Candidate — delete or review on",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text=RETENTION_HELP_TEXT,
    )
    source_name = forms.CharField(
        max_length=200,
        initial="Manual recruiter entry",
        help_text=SOURCE_NAME_HELP_TEXT,
    )
    source_reference = forms.CharField(
        max_length=500,
        required=False,
        help_text=SOURCE_REFERENCE_HELP_TEXT,
    )
    lawful_basis = forms.ChoiceField(
        label="Reason for storing data",
        choices=form_choices(CandidateSource.LawfulBasis.choices, LAWFUL_BASIS_LABELS),
        initial=CandidateSource.LawfulBasis.NOT_RECORDED,
        help_text=LAWFUL_BASIS_HELP_TEXT,
    )
    consent_status = forms.ChoiceField(
        label="Consent",
        choices=form_choices(
            CandidateSource.ConsentStatus.choices, CONSENT_STATUS_LABELS
        ),
        initial=CandidateSource.ConsentStatus.UNKNOWN,
        help_text=CONSENT_HELP_TEXT,
    )
    contact_permission = forms.ChoiceField(
        label="Allowed contact",
        choices=form_choices(
            CandidateSource.ContactPermission.choices, CONTACT_PERMISSION_LABELS
        ),
        initial=CandidateSource.ContactPermission.UNKNOWN,
        help_text=CONTACT_PERMISSION_HELP_TEXT,
    )
    permission_notes = forms.CharField(
        label="Privacy and contact notes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    source_retention_until = forms.DateField(
        label="Source — delete or review on",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text=RETENTION_HELP_TEXT,
    )
    document_retention_until = forms.DateField(
        label="CV — delete or review on",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text=RETENTION_HELP_TEXT,
    )


class CandidateCSVImportForm(forms.Form):
    csv_file = forms.FileField(
        label="CSV file",
        help_text="UTF-8, comma-separated, up to 2 MB and 2,000 data rows.",
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}),
    )
    source_name = forms.CharField(
        max_length=200,
        help_text=SOURCE_NAME_HELP_TEXT,
    )
    lawful_basis = forms.ChoiceField(
        label="Reason for storing data",
        choices=form_choices(CandidateSource.LawfulBasis.choices, LAWFUL_BASIS_LABELS),
        initial=CandidateSource.LawfulBasis.NOT_RECORDED,
        help_text=LAWFUL_BASIS_HELP_TEXT,
    )
    consent_status = forms.ChoiceField(
        label="Consent",
        choices=form_choices(
            CandidateSource.ConsentStatus.choices, CONSENT_STATUS_LABELS
        ),
        initial=CandidateSource.ConsentStatus.UNKNOWN,
        help_text=CONSENT_HELP_TEXT,
    )
    contact_permission = forms.ChoiceField(
        label="Allowed contact",
        choices=form_choices(
            CandidateSource.ContactPermission.choices, CONTACT_PERMISSION_LABELS
        ),
        initial=CandidateSource.ContactPermission.UNKNOWN,
        help_text=CONTACT_PERMISSION_HELP_TEXT,
    )
    permission_notes = forms.CharField(
        label="Privacy and contact notes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Applied to every source record created by this import.",
    )
    source_retention_until = forms.DateField(
        label="Source — delete or review on",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text=RETENTION_HELP_TEXT,
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
            "source_name": SOURCE_NAME_HELP_TEXT,
            "lawful_basis": LAWFUL_BASIS_HELP_TEXT,
            "consent_status": CONSENT_HELP_TEXT,
            "contact_permission": CONTACT_PERMISSION_HELP_TEXT,
            "candidate_retention_until": RETENTION_HELP_TEXT,
            "source_retention_until": RETENTION_HELP_TEXT,
            "document_retention_until": RETENTION_HELP_TEXT,
        }
        labels = {
            "lawful_basis": "Reason for storing data",
            "consent_status": "Consent",
            "contact_permission": "Allowed contact",
            "permission_notes": "Privacy and contact notes",
            "candidate_retention_until": "Candidate — delete or review on",
            "source_retention_until": "Source — delete or review on",
            "document_retention_until": "CV — delete or review on",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["lawful_basis"].choices = form_choices(
            CandidateSource.LawfulBasis.choices, LAWFUL_BASIS_LABELS
        )
        self.fields["consent_status"].choices = form_choices(
            CandidateSource.ConsentStatus.choices, CONSENT_STATUS_LABELS
        )
        self.fields["contact_permission"].choices = form_choices(
            CandidateSource.ContactPermission.choices, CONTACT_PERMISSION_LABELS
        )


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


class CandidateIntakeCSVMappingForm(forms.Form):
    csv_file = forms.FileField(
        label="Candidate CSV",
        help_text=(
            "UTF-8 CSV with exact cv_filename and full_name columns. Optional "
            "columns: email, phone, location, and source_reference."
        ),
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}),
    )


class CandidateIntakeCSVRowForm(forms.Form):
    cv_filename = forms.CharField(max_length=255)
    full_name = forms.CharField(max_length=200)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=50, required=False)
    location = forms.CharField(max_length=200, required=False)
    source_reference = forms.CharField(max_length=500, required=False)

    def clean(self):
        cleaned_data = super().clean()
        for field_name in (
            "cv_filename",
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


class CandidateIntakeReviewForm(forms.Form):
    selected = forms.BooleanField(required=False)
    full_name = forms.CharField(max_length=200, required=False)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=50, required=False)
    location = forms.CharField(max_length=200, required=False)
    source_reference = forms.CharField(
        max_length=500,
        required=False,
        help_text=SOURCE_REFERENCE_HELP_TEXT,
    )

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
