from django import forms
from django.db.models import Q

from candidates.documents import (
    CandidateDocumentUploadError,
    ValidatedTextDocumentUpload,
    validate_text_document_upload,
)
from matching.models import HardConstraintRule, normalize_taxonomy_value
from matching.skill_taxonomy import canonical_skill_key, canonicalize_skill
from organizations.models import ClientCompany, Organization
from vacancies.models import Vacancy, VacancyRequirements

LIST_FIELD_NAMES = (
    "must_have_skills",
    "nice_to_have_skills",
    "language_requirements",
    "education_requirements",
    "certification_requirements",
    "hard_constraints",
    "ambiguities",
)

REQUIREMENTS_VALUE_FIELDS = (
    "summary",
    "must_have_skills",
    "nice_to_have_skills",
    "minimum_years_experience",
    "location_requirement",
    "work_mode",
    "language_requirements",
    "education_requirements",
    "certification_requirements",
    "employment_type",
    "hard_constraints",
    "ambiguities",
)

ELIGIBILITY_SELECTION_FIELDS = (
    "eligibility_required_skills",
    "eligibility_minimum_experience",
    "eligibility_location",
    "eligibility_work_mode",
    "eligibility_languages",
    "eligibility_education",
    "eligibility_certifications",
    "eligibility_employment_type",
)

REVIEW_REQUIREMENTS_FIELDS = (
    "summary",
    "must_have_skills",
    "nice_to_have_skills",
    "minimum_years_experience",
    "location_requirement",
    "work_mode",
    "employment_type",
)

REVIEW_ELIGIBILITY_FIELDS = (
    "eligibility_required_skills",
    "eligibility_minimum_experience",
    "eligibility_location",
    "eligibility_work_mode",
    "eligibility_employment_type",
)


class VacancyCreateForm(forms.Form):
    title = forms.CharField(max_length=200)
    client_company = forms.ModelChoiceField(
        label="Hiring client (optional)",
        queryset=ClientCompany.objects.none(),
        required=False,
        empty_label="No hiring client (direct employer)",
        help_text=("Only active hiring clients in this organization are shown."),
    )
    description = forms.CharField(
        required=False,
        label="Paste vacancy description",
        widget=forms.Textarea(attrs={"rows": 14}),
        help_text="Paste the vacancy here, or upload one file below—not both.",
    )
    vacancy_document = forms.FileField(
        required=False,
        label="Or upload vacancy",
        help_text="PDF, DOCX, or UTF-8 TXT; maximum 10 MB.",
        widget=forms.ClearableFileInput(
            attrs={"accept": ".pdf,.docx,.txt,application/pdf,text/plain"}
        ),
    )

    def __init__(self, *args, organization: Organization, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.validated_document: ValidatedTextDocumentUpload | None = None
        self.fields["client_company"].queryset = (
            ClientCompany.objects.for_organization(organization)
            .filter(is_active=True)
            .order_by("name")
        )

    def clean_title(self) -> str:
        return self.cleaned_data["title"].strip()

    def clean(self):
        cleaned_data = super().clean()
        description = (cleaned_data.get("description") or "").strip()
        vacancy_document = cleaned_data.get("vacancy_document")
        if bool(description) == bool(vacancy_document):
            raise forms.ValidationError(
                "Paste a vacancy description or upload one vacancy file, not both."
            )
        if vacancy_document:
            try:
                self.validated_document = validate_text_document_upload(
                    uploaded_file=vacancy_document,
                    max_extracted_characters=30_000,
                    allow_txt=True,
                )
            except CandidateDocumentUploadError as error:
                self.add_error("vacancy_document", error.public_message)
            else:
                cleaned_data["description"] = self.validated_document.extracted.text
        else:
            if len(description) > 30_000:
                self.add_error(
                    "description",
                    "The vacancy description must be 30,000 characters or fewer.",
                )
            cleaned_data["description"] = description
        return cleaned_data


class ClientCompanyChoiceField(forms.ModelChoiceField):
    def __init__(self, *args, current_inactive_id: int | None = None, **kwargs):
        self.current_inactive_id = current_inactive_id
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj: ClientCompany) -> str:
        if obj.pk == self.current_inactive_id:
            return f"{obj.name} (inactive — current vacancy only)"
        return obj.name


class VacancyEditForm(forms.Form):
    title = forms.CharField(max_length=200)
    client_company = ClientCompanyChoiceField(
        label="Hiring client (optional)",
        queryset=ClientCompany.objects.none(),
        required=False,
        empty_label="No hiring client (direct employer)",
        help_text=(
            "Choose an active client. A current inactive client can be retained "
            "for this historical vacancy only."
        ),
    )

    def __init__(
        self,
        *args,
        organization: Organization,
        vacancy: Vacancy,
        **kwargs,
    ) -> None:
        if kwargs.get("initial") is None:
            kwargs["initial"] = {
                "title": vacancy.title,
                "client_company": vacancy.client_company,
            }
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.vacancy = vacancy
        current_inactive_id = (
            vacancy.client_company_id
            if vacancy.client_company_id and not vacancy.client_company.is_active
            else None
        )
        queryset = ClientCompany.objects.for_organization(organization).filter(
            Q(is_active=True) | Q(pk=current_inactive_id)
        )
        field = self.fields["client_company"]
        field.queryset = queryset.order_by("name")
        field.current_inactive_id = current_inactive_id

    def clean_title(self) -> str:
        return self.cleaned_data["title"].strip()

    def clean_client_company(self) -> ClientCompany | None:
        company = self.cleaned_data["client_company"]
        if (
            company is not None
            and not company.is_active
            and company.pk != self.vacancy.client_company_id
        ):
            raise forms.ValidationError("Select an active client company.")
        return company


class VacancyRequirementsForm(forms.Form):
    summary = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="A concise recruiter-written summary of the role requirements.",
    )
    must_have_skills = forms.CharField(
        required=False,
        label="Must-have skills",
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Enter one skill per line.",
    )
    nice_to_have_skills = forms.CharField(
        required=False,
        label="Nice-to-have skills",
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Enter one skill per line.",
    )
    minimum_years_experience = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=4,
        decimal_places=1,
        label="Minimum years of experience",
    )
    location_requirement = forms.CharField(required=False, max_length=200)
    work_mode = forms.ChoiceField(choices=VacancyRequirements.WorkMode.choices)
    language_requirements = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Enter one language requirement per line.",
    )
    education_requirements = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Enter one education requirement per line.",
    )
    certification_requirements = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Enter one certification requirement per line.",
    )
    employment_type = forms.ChoiceField(
        choices=VacancyRequirements.EmploymentType.choices
    )
    hard_constraints = forms.CharField(
        required=False,
        label="Other requirements",
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text=(
            "Notes only; these do not affect candidate filtering. Add an eligibility "
            "rule below for a requirement that should filter candidates. Do not "
            "enter protected characteristics."
        ),
    )
    ambiguities = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Enter one unanswered question or ambiguity per line.",
    )
    eligibility_required_skills = forms.MultipleChoiceField(
        required=False,
        label="Required for eligibility",
        widget=forms.CheckboxSelectMultiple,
    )
    eligibility_minimum_experience = forms.BooleanField(
        required=False,
        label="Required for eligibility",
    )
    eligibility_location = forms.BooleanField(
        required=False,
        label="Required for eligibility",
    )
    eligibility_work_mode = forms.BooleanField(
        required=False,
        label="Required for eligibility",
    )
    eligibility_languages = forms.MultipleChoiceField(
        required=False,
        label="Required for eligibility",
        widget=forms.CheckboxSelectMultiple,
    )
    eligibility_education = forms.MultipleChoiceField(
        required=False,
        label="Required for eligibility",
        widget=forms.CheckboxSelectMultiple,
    )
    eligibility_certifications = forms.MultipleChoiceField(
        required=False,
        label="Required for eligibility",
        widget=forms.CheckboxSelectMultiple,
    )
    eligibility_employment_type = forms.BooleanField(
        required=False,
        label="Required for eligibility",
    )

    def __init__(
        self,
        *args,
        requirements: VacancyRequirements | None = None,
        **kwargs,
    ) -> None:
        if requirements is not None and "initial" not in kwargs:
            kwargs["initial"] = {
                **requirements_form_initial(requirements),
                **eligibility_form_initial(requirements),
            }
        super().__init__(*args, **kwargs)
        self.requirements = requirements
        list_values = {
            field_name: self._list_values(field_name)
            for field_name in (
                "must_have_skills",
                "nice_to_have_skills",
                "language_requirements",
                "education_requirements",
                "certification_requirements",
            )
        }
        choice_fields = {
            "eligibility_required_skills": "must_have_skills",
            "eligibility_languages": "language_requirements",
            "eligibility_education": "education_requirements",
            "eligibility_certifications": "certification_requirements",
        }
        for eligibility_field, value_field in choice_fields.items():
            values = list_values[value_field]
            self.fields[eligibility_field].choices = [
                (value, value) for value in values
            ]

        self.must_have_skill_previews = _skill_previews(list_values["must_have_skills"])
        self.nice_to_have_skill_previews = _skill_previews(
            list_values["nice_to_have_skills"]
        )

    def _list_values(self, field_name: str) -> list[str]:
        if self.is_bound:
            return _parse_line_list(self.data.get(field_name, ""))
        if self.requirements is None:
            return []
        return list(getattr(self.requirements, field_name))

    def clean(self):
        cleaned_data = super().clean()
        for field_name in LIST_FIELD_NAMES:
            value = cleaned_data.get(field_name)
            if isinstance(value, str):
                cleaned_data[field_name] = _parse_line_list(value)

        for field_name in ("summary", "location_requirement"):
            value = cleaned_data.get(field_name)
            if isinstance(value, str):
                cleaned_data[field_name] = value.strip()

        required_values = (
            (
                "eligibility_minimum_experience",
                cleaned_data.get("minimum_years_experience") is not None,
                "Enter minimum years before making it required for eligibility.",
            ),
            (
                "eligibility_location",
                bool(cleaned_data.get("location_requirement")),
                "Enter a location before making it required for eligibility.",
            ),
            (
                "eligibility_work_mode",
                cleaned_data.get("work_mode")
                not in {None, VacancyRequirements.WorkMode.UNKNOWN},
                "Select a work mode before making it required for eligibility.",
            ),
            (
                "eligibility_employment_type",
                cleaned_data.get("employment_type")
                not in {None, VacancyRequirements.EmploymentType.UNKNOWN},
                "Select an employment type before making it required for eligibility.",
            ),
        )
        for field_name, has_value, message in required_values:
            if cleaned_data.get(field_name) and not has_value:
                self.add_error(field_name, message)
        return cleaned_data


class VacancyRequirementsReviewForm(VacancyRequirementsForm):
    """Compact routine editor for matching essentials and eligibility."""

    def __init__(self, *args, requirements: VacancyRequirements, **kwargs) -> None:
        super().__init__(*args, requirements=requirements, **kwargs)
        retained = set(REVIEW_REQUIREMENTS_FIELDS + REVIEW_ELIGIBILITY_FIELDS)
        for field_name in tuple(self.fields):
            if field_name not in retained:
                self.fields.pop(field_name)


def _parse_line_list(value: str) -> list[str]:
    """Normalize a recruiter-friendly one-item-per-line field."""
    items = []
    seen = set()
    for line in value.splitlines():
        item = line.strip()
        key = item.casefold()
        if item and key not in seen:
            items.append(item)
            seen.add(key)
    return items


def requirements_form_initial(requirements: VacancyRequirements) -> dict:
    initial = {
        "summary": requirements.summary,
        "minimum_years_experience": requirements.minimum_years_experience,
        "location_requirement": requirements.location_requirement,
        "work_mode": requirements.work_mode,
        "employment_type": requirements.employment_type,
    }
    for field_name in LIST_FIELD_NAMES:
        initial[field_name] = "\n".join(getattr(requirements, field_name))
    return initial


def _skill_previews(values: list[str]) -> list[dict[str, str | bool]]:
    previews = []
    for source_label in values:
        canonical = canonicalize_skill(source_label)
        previews.append(
            {
                "source_label": source_label,
                "canonical_name": canonical.display_name,
                "is_alias": canonical_skill_key(source_label)
                != normalize_taxonomy_value(source_label),
            }
        )
    return previews


def eligibility_form_initial(requirements: VacancyRequirements) -> dict:
    rules = tuple(
        requirements.hard_constraint_rules.select_related("skill").order_by(
            "position", "id"
        )
    )

    def has_text_rule(rule_type: str, value: str) -> bool:
        if not value:
            return False
        normalized = normalize_taxonomy_value(value)
        return any(
            rule.rule_type == rule_type and rule.normalized_expected_value == normalized
            for rule in rules
        )

    selected_skills = []
    for label in requirements.must_have_skills:
        key = canonical_skill_key(label)
        if any(
            rule.rule_type == HardConstraintRule.RuleType.REQUIRED_SKILL
            and rule.skill_id
            and canonical_skill_key(rule.skill.name) == key
            for rule in rules
        ):
            selected_skills.append(label)

    return {
        "eligibility_required_skills": selected_skills,
        "eligibility_minimum_experience": any(
            rule.rule_type == HardConstraintRule.RuleType.MINIMUM_EXPERIENCE
            and rule.numeric_value == requirements.minimum_years_experience
            for rule in rules
        ),
        "eligibility_location": has_text_rule(
            HardConstraintRule.RuleType.LOCATION,
            requirements.location_requirement,
        ),
        "eligibility_work_mode": has_text_rule(
            HardConstraintRule.RuleType.WORK_MODE,
            requirements.work_mode,
        ),
        "eligibility_languages": [
            value
            for value in requirements.language_requirements
            if has_text_rule(HardConstraintRule.RuleType.LANGUAGE, value)
        ],
        "eligibility_education": [
            value
            for value in requirements.education_requirements
            if has_text_rule(HardConstraintRule.RuleType.EDUCATION, value)
        ],
        "eligibility_certifications": [
            value
            for value in requirements.certification_requirements
            if has_text_rule(HardConstraintRule.RuleType.CERTIFICATION, value)
        ],
        "eligibility_employment_type": has_text_rule(
            HardConstraintRule.RuleType.EMPLOYMENT_TYPE,
            requirements.employment_type,
        ),
    }


def vacancy_values_from_form(form: VacancyCreateForm) -> dict:
    return {
        "title": form.cleaned_data["title"],
        "client_company": form.cleaned_data["client_company"],
        "description": form.cleaned_data["description"],
    }


def vacancy_source_provenance_from_form(form: VacancyCreateForm) -> dict:
    validated = form.validated_document
    if validated is None:
        return {}
    return {
        "source_original_filename": validated.original_filename,
        "source_content_type": validated.extracted.content_type,
        "source_sha256": validated.sha256,
    }


def vacancy_edit_values_from_form(form: VacancyEditForm) -> dict:
    return {
        "title": form.cleaned_data["title"],
        "client_company": form.cleaned_data["client_company"],
    }


def requirements_values_from_form(form: VacancyRequirementsForm) -> dict:
    return {
        field_name: form.cleaned_data[field_name]
        for field_name in REQUIREMENTS_VALUE_FIELDS
    }


def review_requirements_values_from_form(
    *,
    requirements: VacancyRequirements,
    form: VacancyRequirementsReviewForm,
) -> dict:
    values = {
        field_name: getattr(requirements, field_name)
        for field_name in REQUIREMENTS_VALUE_FIELDS
    }
    values.update(
        {
            field_name: form.cleaned_data[field_name]
            for field_name in REVIEW_REQUIREMENTS_FIELDS
        }
    )
    return values


def eligibility_values_from_form(form: VacancyRequirementsForm) -> dict:
    return {
        field_name.removeprefix("eligibility_"): form.cleaned_data[field_name]
        for field_name in ELIGIBILITY_SELECTION_FIELDS
    }


def review_eligibility_values_from_form(
    *,
    requirements: VacancyRequirements,
    form: VacancyRequirementsReviewForm,
) -> dict:
    values = eligibility_form_initial(requirements)
    values.update(
        {
            field_name: form.cleaned_data[field_name]
            for field_name in REVIEW_ELIGIBILITY_FIELDS
        }
    )
    return {
        field_name.removeprefix("eligibility_"): values[field_name]
        for field_name in ELIGIBILITY_SELECTION_FIELDS
    }
