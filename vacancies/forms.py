from django import forms
from django.db.models import Q

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


class VacancyCreateForm(forms.Form):
    title = forms.CharField(max_length=200)
    client_company = forms.ModelChoiceField(
        queryset=ClientCompany.objects.none(),
        required=False,
        empty_label="Direct employer / no client company",
        help_text=(
            "Optional. Only active client companies in this organization are shown."
        ),
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 14}),
        help_text="Paste the complete vacancy or job description.",
    )

    def __init__(self, *args, organization: Organization, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["client_company"].queryset = (
            ClientCompany.objects.for_organization(organization)
            .filter(is_active=True)
            .order_by("name")
        )

    def clean_title(self) -> str:
        return self.cleaned_data["title"].strip()

    def clean_description(self) -> str:
        return self.cleaned_data["description"].strip()


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
        queryset=ClientCompany.objects.none(),
        required=False,
        empty_label="Direct employer / no client company",
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
        label="Hard-constraint notes (not executable)",
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text=(
            "Optional notes only. Use the typed-rule editor below for constraints "
            "that deterministic filtering must evaluate. Do not enter protected "
            "characteristics."
        ),
    )
    ambiguities = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Enter one unanswered question or ambiguity per line.",
    )

    def __init__(
        self,
        *args,
        requirements: VacancyRequirements | None = None,
        **kwargs,
    ) -> None:
        if requirements is not None and "initial" not in kwargs:
            kwargs["initial"] = requirements_form_initial(requirements)
        super().__init__(*args, **kwargs)

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
        return cleaned_data


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


def vacancy_values_from_form(form: VacancyCreateForm) -> dict:
    return {
        "title": form.cleaned_data["title"],
        "client_company": form.cleaned_data["client_company"],
        "description": form.cleaned_data["description"],
    }


def vacancy_edit_values_from_form(form: VacancyEditForm) -> dict:
    return {
        "title": form.cleaned_data["title"],
        "client_company": form.cleaned_data["client_company"],
    }


def requirements_values_from_form(form: VacancyRequirementsForm) -> dict:
    return {field_name: form.cleaned_data[field_name] for field_name in form.fields}
