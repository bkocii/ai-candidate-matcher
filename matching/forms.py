from django import forms

from matching.models import HardConstraintRule, RequirementSkill, ReviewDecision
from vacancies.models import VacancyRequirements


class HardConstraintRuleForm(forms.Form):
    rule_type = forms.ChoiceField(
        choices=HardConstraintRule.RuleType.choices,
        label="Rule type",
    )
    source_text = forms.CharField(
        label="Exact source wording",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=(
            "Copy the explicit wording from the vacancy or record the recruiter's "
            "confirmed interpretation."
        ),
    )
    skill = forms.ChoiceField(
        required=False,
        label="Required must-have skill",
        help_text="Used only for a Required skill rule.",
    )
    numeric_value = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=5,
        decimal_places=1,
        label="Minimum years",
        help_text="Used only for a Minimum years of experience rule.",
    )
    expected_value = forms.CharField(
        required=False,
        max_length=200,
        label="Required value",
        help_text=(
            "Used for location, work mode, language, education, certification, "
            "or employment type. Examples: Prishtina, Remote, English B2, Full time."
        ),
    )

    def __init__(
        self,
        *args,
        requirements: VacancyRequirements,
        rule: HardConstraintRule | None = None,
        **kwargs,
    ) -> None:
        self.requirements = requirements
        self.rule = rule
        if rule is not None and "initial" not in kwargs:
            kwargs["initial"] = self._initial_from_rule(rule)
        super().__init__(*args, **kwargs)
        must_have = requirements.skill_records.filter(
            importance=RequirementSkill.Importance.MUST_HAVE
        ).select_related("skill")
        self.must_have_by_id = {str(record.skill_id): record for record in must_have}
        self.fields["skill"].choices = [("", "Select a saved must-have skill")] + [
            (skill_id, record.source_label)
            for skill_id, record in self.must_have_by_id.items()
        ]

    @staticmethod
    def _initial_from_rule(rule: HardConstraintRule) -> dict:
        return {
            "rule_type": rule.rule_type,
            "source_text": rule.source_text,
            "skill": str(rule.skill_id or ""),
            "numeric_value": rule.numeric_value,
            "expected_value": rule.expected_value,
        }

    def clean_source_text(self) -> str:
        return self.cleaned_data["source_text"].strip()

    def clean(self):
        cleaned_data = super().clean()
        rule_type = cleaned_data.get("rule_type")
        skill_id = cleaned_data.get("skill", "")
        numeric_value = cleaned_data.get("numeric_value")
        expected_value = cleaned_data.get("expected_value", "").strip()

        cleaned_data["skill_label"] = ""
        cleaned_data["numeric_value"] = None
        cleaned_data["expected_value"] = ""

        if rule_type == HardConstraintRule.RuleType.REQUIRED_SKILL:
            record = self.must_have_by_id.get(skill_id)
            if record is None:
                self.add_error("skill", "Select a saved must-have skill.")
            else:
                cleaned_data["skill_label"] = record.source_label
        elif rule_type == HardConstraintRule.RuleType.MINIMUM_EXPERIENCE:
            if numeric_value is None:
                self.add_error("numeric_value", "Enter the minimum years.")
            else:
                cleaned_data["numeric_value"] = numeric_value
        elif rule_type in HardConstraintRule.TEXT_RULE_TYPES:
            if not expected_value:
                self.add_error("expected_value", "Enter the required value.")
            else:
                cleaned_data["expected_value"] = self._clean_controlled_value(
                    rule_type,
                    expected_value,
                )
        return cleaned_data

    def _clean_controlled_value(self, rule_type: str, value: str) -> str:
        choices = None
        label = "value"
        if rule_type == HardConstraintRule.RuleType.WORK_MODE:
            choices = tuple(
                choice
                for choice in VacancyRequirements.WorkMode.choices
                if choice[0] != VacancyRequirements.WorkMode.UNKNOWN
            )
            label = "work mode"
        elif rule_type == HardConstraintRule.RuleType.EMPLOYMENT_TYPE:
            choices = tuple(
                choice
                for choice in VacancyRequirements.EmploymentType.choices
                if choice[0] != VacancyRequirements.EmploymentType.UNKNOWN
            )
            label = "employment type"

        if choices is None:
            return " ".join(value.split())

        normalized = " ".join(value.split()).casefold()
        lookup = {
            candidate.casefold(): candidate for candidate, _candidate_label in choices
        }
        lookup.update(
            {
                candidate_label.casefold(): candidate
                for candidate, candidate_label in choices
            }
        )
        if normalized not in lookup:
            self.add_error(
                "expected_value",
                f"Select a supported {label}: "
                + ", ".join(choice_label for _choice, choice_label in choices),
            )
            return ""
        return lookup[normalized]


def hard_constraint_values_from_form(form: HardConstraintRuleForm) -> dict:
    return {
        "rule_type": form.cleaned_data["rule_type"],
        "source_text": form.cleaned_data["source_text"],
        "skill_label": form.cleaned_data["skill_label"],
        "numeric_value": form.cleaned_data["numeric_value"],
        "expected_value": form.cleaned_data["expected_value"],
    }


class ReviewDecisionForm(forms.Form):
    decision = forms.ChoiceField(
        choices=ReviewDecision.Decision.choices,
        widget=forms.RadioSelect,
        label="Recruiter decision",
    )
    notes = forms.CharField(
        max_length=2_000,
        label="Recruiter notes",
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text=(
            "Record the evidence considered, follow-up needed, or reason for this "
            "individual decision."
        ),
    )

    def clean_notes(self) -> str:
        notes = self.cleaned_data["notes"].strip()
        if not notes:
            raise forms.ValidationError("Record recruiter notes for the decision.")
        return notes
