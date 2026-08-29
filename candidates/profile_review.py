import re
import unicodedata
from dataclasses import dataclass

from candidates.models import Candidate, CandidateProfile


@dataclass(frozen=True)
class CandidateProfileConflict:
    field: str
    candidate_value: str
    profile_value: str

    @property
    def message(self) -> str:
        return (
            f"Candidate {self.field} and CV profile {self.field} do not match. "
            "Review and correct the trusted record before confirmation."
        )


def _normalized_comparison_value(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"\w+", normalized, flags=re.UNICODE))


def candidate_profile_conflicts(
    *, candidate: Candidate, profile: CandidateProfile
) -> tuple[CandidateProfileConflict, ...]:
    """Return deterministic conflicts between recruiter and CV-derived facts."""
    conflicts: list[CandidateProfileConflict] = []
    comparisons = (("location", candidate.location, profile.location),)
    for field, candidate_value, profile_value in comparisons:
        candidate_normalized = _normalized_comparison_value(candidate_value)
        profile_normalized = _normalized_comparison_value(profile_value)
        if (
            candidate_normalized
            and profile_normalized
            and candidate_normalized != profile_normalized
        ):
            conflicts.append(
                CandidateProfileConflict(
                    field=field,
                    candidate_value=candidate_value,
                    profile_value=profile_value,
                )
            )
    return tuple(conflicts)
