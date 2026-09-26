from django import forms

from matching.models import HardConstraintRule, RequirementSkill, ReviewDecision
from vacancies.models import VacancyRequirements


class HardConstraintRuleForm(forms.Form):
    rule_type = forms.ChoiceField(
        choices=HardConstraintRule.RuleType.choices,
        label="Eligibility criterion",
    )
    source_text = forms.CharField(
        required=False,
        label="Why is this required?",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=(
            "Use explicit wording from the vacancy or the recruiter's confirmed "
            "interpretation."
        ),
    )
    skill = forms.ChoiceField(
        required=False,
        label="Required skill",
    )
    numeric_value = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=5,
        decimal_places=1,
        label="Minimum years",
    )
    expected_value = forms.CharField(
        required=False,
        max_length=200,
        label="Required value",
        help_text="Examples: Prishtina, Remote, English B2, Full time.",
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
        self.must_have_by_label = {
            record.source_label.casefold(): record for record in must_have
        }
        self.fields["skill"].choices = [("", "Select a saved must-have skill")] + [
            (record.source_label, record.source_label) for record in must_have
        ]

    @staticmethod
    def _initial_from_rule(rule: HardConstraintRule) -> dict:
        return {
            "rule_type": rule.rule_type,
            "source_text": rule.source_text,
            "skill": (
                rule.requirements.skill_records.filter(
                    skill_id=rule.skill_id,
                    importance=RequirementSkill.Importance.MUST_HAVE,
                )
                .values_list("source_label", flat=True)
                .first()
                or ""
            ),
            "numeric_value": rule.numeric_value,
            "expected_value": rule.expected_value,
        }

    def clean_source_text(self) -> str:
        source_text = self.cleaned_data["source_text"].strip()
        if not source_text:
            raise forms.ValidationError("Explain why this criterion is required.")
        return source_text

    def clean(self):
        cleaned_data = super().clean()
        rule_type = cleaned_data.get("rule_type")
        skill_label = cleaned_data.get("skill", "")
        numeric_value = cleaned_data.get("numeric_value")
        expected_value = cleaned_data.get("expected_value", "").strip()

        cleaned_data["skill_label"] = ""
        cleaned_data["numeric_value"] = None
        cleaned_data["expected_value"] = ""

        if rule_type == HardConstraintRule.RuleType.REQUIRED_SKILL:
            record = self.must_have_by_label.get(skill_label.casefold())
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
    DEFAULT_APPROVAL_NOTE = "Reviewed the current assessment and supporting evidence."

    decision = forms.ChoiceField(
        choices=ReviewDecision.Decision.choices,
        widget=forms.RadioSelect,
        label="Recruiter decision",
    )
    notes = forms.CharField(
        required=False,
        max_length=2_000,
        label="Reason or follow-up note",
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text=(
            "Optional for approval. Required when rejecting or revisiting later. "
            "These notes stay internal and are never copied into candidate emails."
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        decision = cleaned_data.get("decision")
        notes = cleaned_data.get("notes", "").strip()
        if decision == ReviewDecision.Decision.APPROVED and not notes:
            cleaned_data["notes"] = self.DEFAULT_APPROVAL_NOTE
        elif (
            decision
            in {
                ReviewDecision.Decision.REJECTED,
                ReviewDecision.Decision.REVISIT,
            }
            and not notes
        ):
            self.add_error("notes", "Add a short reason for this decision.")
        else:
            cleaned_data["notes"] = notes
        return cleaned_data
