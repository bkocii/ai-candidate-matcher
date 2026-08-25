"""Recruiter-facing privacy wording over stable candidate-source values."""

LAWFUL_BASIS_LABELS = {
    "not_recorded": "Not recorded",
    "consent": "Consent",
    "contract": "Contract",
    "legitimate_interests": "Legitimate interests",
    "legal_obligation": "Legal obligation",
    "other": "Other organization-approved reason",
}

CONSENT_STATUS_LABELS = {
    "unknown": "Not recorded",
    "not_required": "Not required",
    "granted": "Given",
    "withdrawn": "Withdrawn",
}

CONTACT_PERMISSION_LABELS = {
    "unknown": "Not confirmed",
    "permitted": "Future roles allowed",
    "restricted": "Application only",
    "withdrawn": "Do not contact",
}

SOURCE_NAME_HELP_TEXT = "Where this candidate record came from."
SOURCE_REFERENCE_HELP_TEXT = "Optional stable ID or reference from the original source."
LAWFUL_BASIS_HELP_TEXT = (
    "Choose the organization-approved reason for storing and processing this "
    "candidate record. This records your organization's assertion; it is not "
    "legal certification."
)
CONSENT_HELP_TEXT = (
    "Consent is separate from allowed contact. Select Given only when consent "
    "has actually been recorded."
)
CONTACT_PERMISSION_HELP_TEXT = (
    "Future roles allowed permits this app's outreach workflow. Application "
    "only, Do not contact, and Not confirmed block final outreach approval."
)
RETENTION_HELP_TEXT = (
    "Set the date when this data should be deleted or reviewed. Leave it blank "
    "until an organization retention policy or documented exception supplies a date."
)


def _display(value: str, labels: dict[str, str]) -> str:
    return labels.get(value, value.replace("_", " ").title())


def lawful_basis_display(value: str) -> str:
    return _display(value, LAWFUL_BASIS_LABELS)


def consent_status_display(value: str) -> str:
    return _display(value, CONSENT_STATUS_LABELS)


def contact_permission_display(value: str) -> str:
    return _display(value, CONTACT_PERMISSION_LABELS)


def form_choices(model_choices, labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple((value, labels[value]) for value, _ in model_choices)
