import re
import unicodedata
from dataclasses import dataclass

ROLE_FAMILY_CHOICES = (
    ("unknown", "Not determined"),
    ("backend", "Backend engineering"),
    ("frontend", "Frontend engineering"),
    ("full_stack", "Full-stack engineering"),
    ("mobile", "Mobile engineering"),
    ("devops", "DevOps / platform / SRE"),
    ("data", "Data / machine learning"),
    ("qa", "Quality assurance / testing"),
    ("security", "Security engineering"),
    ("product", "Product management"),
    ("design", "Product / UX design"),
    ("other", "Other supported role"),
)
SENIORITY_CHOICES = (
    ("unknown", "Not determined"),
    ("junior", "Junior"),
    ("mid", "Mid-level"),
    ("senior", "Senior"),
    ("lead", "Lead / principal"),
    ("manager", "Manager / head"),
    ("executive", "Executive"),
)

ROLE_FAMILY_VALUES = frozenset(value for value, _ in ROLE_FAMILY_CHOICES)
SENIORITY_VALUES = frozenset(value for value, _ in SENIORITY_CHOICES)
ROLE_FAMILY_LABELS = dict(ROLE_FAMILY_CHOICES)
SENIORITY_LABELS = dict(SENIORITY_CHOICES)

_ROLE_PATTERNS = (
    ("full_stack", r"\bfull[\s-]?stack\b"),
    ("mobile", r"\b(?:mobile|android|ios|flutter|react\s+native)\b"),
    (
        "devops",
        r"\b(?:devops|site\s+reliability|sre|platform\s+engineer|cloud\s+engineer)\b",
    ),
    (
        "data",
        r"\b(?:data\s+(?:engineer|scientist|analyst)|machine\s+learning|ml\s+engineer|ai\s+engineer)\b",
    ),
    (
        "qa",
        r"\b(?:quality\s+assurance|qa|test\s+automation|automation\s+(?:engineer|tester)|software\s+tester)\b",
    ),
    ("security", r"\b(?:security|cybersecurity|application\s+security)\b"),
    ("product", r"\b(?:product\s+(?:manager|owner)|product\s+management)\b"),
    (
        "design",
        r"\b(?:product\s+designer|ux\s+designer|ui\s+designer|user\s+experience)\b",
    ),
    (
        "frontend",
        r"\b(?:front[\s-]?end|frontend|react\s+developer|angular\s+developer|vue\s+developer|ui\s+developer)\b",
    ),
    (
        "backend",
        r"\b(?:back[\s-]?end|backend|(?:django|python|java|api)\s+(?:developer|engineer))\b",
    ),
)
_SENIORITY_PATTERNS = (
    ("executive", r"\b(?:chief|cto|cio|ciso|vp|vice\s+president)\b"),
    ("manager", r"\b(?:manager|head\s+of|engineering\s+manager)\b"),
    ("lead", r"\b(?:lead|principal|staff|architect)\b"),
    ("senior", r"\b(?:senior|sr\.?|experienced)\b"),
    ("junior", r"\b(?:junior|jr\.?|entry[\s-]?level|graduate|intern)\b"),
    ("mid", r"\b(?:mid[\s-]?(?:level)?|intermediate)\b"),
)


def _normalized_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().replace("_", " ")


def normalize_role_family(value: str) -> str:
    """Map only reviewed role wording to one controlled family."""
    normalized = _normalized_text(value)
    if normalized.strip() in ROLE_FAMILY_VALUES:
        return normalized.strip()
    for family, pattern in _ROLE_PATTERNS:
        if re.search(pattern, normalized):
            return family
    return "unknown"


def normalize_seniority(value: str) -> str:
    """Map only explicit seniority wording to one controlled level."""
    normalized = _normalized_text(value)
    if normalized.strip() in SENIORITY_VALUES:
        return normalized.strip()
    for seniority, pattern in _SENIORITY_PATTERNS:
        if re.search(pattern, normalized):
            return seniority
    return "unknown"


@dataclass(frozen=True)
class DiscoverySignal:
    signal: str
    status: str
    requirement_value: str
    candidate_value: str
    requirement_label: str
    candidate_label: str
    requirement_evidence: str
    candidate_evidence: str

    def as_snapshot(self) -> dict[str, str]:
        return {
            "signal": self.signal,
            "status": self.status,
            "requirement_value": self.requirement_value,
            "candidate_value": self.candidate_value,
            "requirement_label": self.requirement_label,
            "candidate_label": self.candidate_label,
            "requirement_evidence": self.requirement_evidence,
            "candidate_evidence": self.candidate_evidence,
        }


def compare_discovery_value(
    *,
    signal: str,
    requirement_value: str,
    candidate_value: str,
    requirement_evidence: str,
    candidate_evidence: str,
) -> DiscoverySignal:
    labels = ROLE_FAMILY_LABELS if signal == "role_family" else SENIORITY_LABELS
    status = "unknown"
    if requirement_value != "unknown" and candidate_value != "unknown":
        status = "matched" if requirement_value == candidate_value else "different"
    return DiscoverySignal(
        signal=signal,
        status=status,
        requirement_value=requirement_value,
        candidate_value=candidate_value,
        requirement_label=labels.get(requirement_value, requirement_value),
        candidate_label=labels.get(candidate_value, candidate_value),
        requirement_evidence=requirement_evidence,
        candidate_evidence=candidate_evidence,
    )
