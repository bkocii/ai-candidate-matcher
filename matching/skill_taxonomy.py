from dataclasses import dataclass

from matching.models import normalize_taxonomy_value


@dataclass(frozen=True)
class CanonicalSkill:
    """A controlled deterministic skill identity and its display label."""

    key: str
    display_name: str


# Keep this deliberately small and reviewable. These entries express only
# unambiguous technology/role wording seen in recruiter-controlled vacancy or CV
# text. Adding an alias changes deterministic matching policy and requires tests
# plus an algorithm-version bump.
_CONTROLLED_SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": (
        "Python developer",
        "Python development",
        "Python development experience",
        "Python programmer",
        "Python programming",
        "Python-development",
    ),
    "Django": (
        "Django developer",
        "Django development",
        "Django-development",
    ),
}


def _build_alias_index() -> tuple[dict[str, str], dict[str, str]]:
    aliases: dict[str, str] = {}
    display_names: dict[str, str] = {}
    for display_name, source_aliases in _CONTROLLED_SKILL_ALIASES.items():
        canonical_key = normalize_taxonomy_value(display_name)
        display_names[canonical_key] = display_name
        for alias in (display_name, *source_aliases):
            normalized_alias = normalize_taxonomy_value(alias)
            existing = aliases.get(normalized_alias)
            if existing is not None and existing != canonical_key:
                raise RuntimeError("A controlled skill alias has multiple identities.")
            aliases[normalized_alias] = canonical_key
    return aliases, display_names


_ALIAS_TO_CANONICAL_KEY, _CANONICAL_DISPLAY_NAMES = _build_alias_index()


def canonicalize_skill(value: str) -> CanonicalSkill:
    """Return a safe canonical key while retaining unknown skills as distinct."""
    normalized_value = normalize_taxonomy_value(value)
    canonical_key = _ALIAS_TO_CANONICAL_KEY.get(normalized_value, normalized_value)
    display_name = _CANONICAL_DISPLAY_NAMES.get(canonical_key)
    if display_name is None:
        display_name = " ".join(value.split())
    return CanonicalSkill(key=canonical_key, display_name=display_name)


def canonical_skill_key(value: str) -> str:
    return canonicalize_skill(value).key
