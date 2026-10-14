"""Content-free profile evidence failure codes for durable jobs."""

import re

from candidates.ai_extraction import CandidateProfileEvidenceError

AREA_LABELS = {
    "skill": "skill item",
    "employment": "employment-history item",
    "language": "language item",
    "education": "education item",
    "certification": "certification item",
    "summary": "relevant-experience summary",
    "role": "role family",
    "seniority": "seniority",
    "location": "location",
    "work_mode": "work-mode preference",
    "employment_type": "employment-type preferences",
    "availability": "availability",
}


def profile_evidence_failure_code(error: CandidateProfileEvidenceError) -> str:
    issue = error.issues[0]
    for area, label in AREA_LABELS.items():
        if issue.label == label:
            index = 0
        else:
            match = re.fullmatch(re.escape(label) + r" ([1-9][0-9]{0,2})", issue.label)
            if not match:
                continue
            index = int(match[1])
        reason = "source" if issue.reason == "evidence_not_in_source" else "fact"
        return f"profile_evidence:{reason}:{area}:{index}"
    return "profile_evidence"


def profile_evidence_failure_label(code: str) -> str:
    if code == "profile_evidence":
        area = "profile evidence"
        explanation = "The AI output could not be verified against the CV."
    else:
        match = re.fullmatch(
            r"profile_evidence:(source|fact):([a-z_]+):([0-9]{1,3})", code
        )
        if not match or match[2] not in AREA_LABELS:
            return ""
        area = AREA_LABELS[match[2]]
        if int(match[3]):
            area += f" {int(match[3])}"
        explanation = (
            "The AI's quoted evidence was not found in the source CV."
            if match[1] == "source"
            else "The AI's claimed fact was not supported by its quoted evidence."
        )
    return (
        f"Profile extraction failed verification ({area}). {explanation} "
        "No profile was saved. Inspect the original CV or retry extraction. "
        "Repeated failure requires support; editing the CV is not required."
    )
