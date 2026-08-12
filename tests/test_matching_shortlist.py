from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.urls import reverse

from accounts.models import OrganizationMembership, User
from candidates.models import Candidate
from candidates.services import delete_candidate
from matching.models import MatchRun, ShortlistEntry
from matching.scoring import ALGORITHM_VERSION, SHORTLIST_LIMIT, generate_shortlist
from matching.services import (
    assign_candidate_skill,
    create_hard_constraint_rule,
    sync_requirement_skills,
)
from organizations.models import Organization
from vacancies.models import Vacancy, VacancyRequirements
from vacancies.services import confirm_requirements_draft

pytestmark = pytest.mark.django_db


def make_workspace(*, username: str = "recruiter") -> tuple[User, Organization]:
    user = User.objects.create_user(username=username, password="test-password")
    organization = Organization.objects.create(
        name=f"{username.title()} Organization",
        slug=f"{username}-organization",
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )
    return user, organization


def make_requirements(
    *,
    organization: Organization,
    user: User,
    must_have: list[str] | None = None,
    nice_to_have: list[str] | None = None,
) -> tuple[Vacancy, VacancyRequirements]:
    vacancy = Vacancy.objects.create(
        organization=organization,
        title="Backend Engineer",
        description="Synthetic backend vacancy.",
        created_by=user,
    )
    requirements = VacancyRequirements.objects.create(
        vacancy=vacancy,
        version=1,
        source_description=vacancy.description,
        summary="Synthetic requirements",
        must_have_skills=must_have or [],
        nice_to_have_skills=nice_to_have or [],
        created_by=user,
    )
    sync_requirement_skills(requirements=requirements, user=user)
    return vacancy, requirements


def confirm(requirements: VacancyRequirements, user: User) -> VacancyRequirements:
    return confirm_requirements_draft(requirements=requirements, user=user)


def test_relevance_score_uses_visible_two_to_one_per_skill_weights() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python", "Django"],
        nice_to_have=["PostgreSQL", "Redis"],
    )
    confirm(requirements, user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Weighted Candidate",
    )
    assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="python",
        evidence="Synthetic Python evidence.",
    )
    assign_candidate_skill(candidate=candidate, user=user, label="Redis")

    run = generate_shortlist(requirements=requirements, user=user)
    entry = run.entries.get()

    assert entry.score == Decimal("50.00")
    assert entry.matched_must_have == 1
    assert entry.total_must_have == 2
    assert entry.matched_nice_to_have == 1
    assert entry.total_nice_to_have == 2
    assert entry.score_breakdown[0] == {
        "requirement_skill_id": requirements.skill_records.get(
            source_label="Python"
        ).pk,
        "skill_label": "Python",
        "importance": "must_have",
        "importance_label": "Must have",
        "matched": True,
        "candidate_label": "python",
        "evidence": "Synthetic Python evidence.",
        "awarded_points": "33.33",
        "possible_points": "33.33",
    }


def test_five_must_have_and_two_nice_to_have_skills_total_exactly_100() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python", "Django", "SQL", "Git", "Docker"],
        nice_to_have=["Redis", "AWS"],
    )
    confirm(requirements, user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="All Skills Candidate",
    )
    for label in ["Python", "Django", "SQL", "Git", "Docker", "Redis", "AWS"]:
        assign_candidate_skill(candidate=candidate, user=user, label=label)

    entry = generate_shortlist(requirements=requirements, user=user).entries.get()
    must_have_points = [
        Decimal(item["possible_points"])
        for item in entry.score_breakdown
        if item["importance"] == "must_have"
    ]
    nice_to_have_points = [
        Decimal(item["possible_points"])
        for item in entry.score_breakdown
        if item["importance"] == "nice_to_have"
    ]

    assert entry.score == Decimal("100.00")
    assert must_have_points == [
        Decimal("16.67"),
        Decimal("16.67"),
        Decimal("16.67"),
        Decimal("16.67"),
        Decimal("16.66"),
    ]
    assert nice_to_have_points == [Decimal("8.33"), Decimal("8.33")]
    assert sum(must_have_points + nice_to_have_points) == Decimal("100.00")


def test_one_must_have_match_outranks_one_nice_to_have_match() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python", "Django", "SQL", "Git", "Docker"],
        nice_to_have=["Redis", "AWS"],
    )
    confirm(requirements, user)
    must_have_candidate = Candidate.objects.create(
        organization=organization,
        full_name="Must Have Match",
    )
    nice_to_have_candidate = Candidate.objects.create(
        organization=organization,
        full_name="Nice To Have Match",
    )
    assign_candidate_skill(
        candidate=must_have_candidate,
        user=user,
        label="Python",
    )
    assign_candidate_skill(
        candidate=nice_to_have_candidate,
        user=user,
        label="Redis",
    )

    run = generate_shortlist(requirements=requirements, user=user)
    entries = list(run.entries.all())

    assert entries[0].candidate == must_have_candidate
    assert entries[0].score == Decimal("16.67")
    assert entries[1].candidate == nice_to_have_candidate
    assert entries[1].score == Decimal("8.33")


def test_single_skill_category_uses_full_score_range() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(
        organization=organization,
        user=user,
        nice_to_have=["Python", "Django", "Redis"],
    )
    confirm(requirements, user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="One of Three",
    )
    assign_candidate_skill(candidate=candidate, user=user, label="Django")

    entry = generate_shortlist(requirements=requirements, user=user).entries.get()

    assert entry.score == Decimal("33.33")
    assert entry.matched_must_have == 0
    assert entry.total_must_have == 0
    assert entry.matched_nice_to_have == 1
    assert entry.total_nice_to_have == 3


def test_explicit_filter_failure_is_never_shortlisted() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python"],
    )
    create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type="location",
        source_text="Candidate must be in Prishtina.",
        expected_value="Prishtina",
        position=1,
    )
    confirm(requirements, user)
    failed = Candidate.objects.create(
        organization=organization,
        full_name="High Skill Failure",
        location="Peja",
    )
    eligible = Candidate.objects.create(
        organization=organization,
        full_name="Unknown But Eligible",
    )
    assign_candidate_skill(candidate=failed, user=user, label="Python")

    run = generate_shortlist(requirements=requirements, user=user)

    assert run.evaluated_count == 2
    assert run.eligible_count == 1
    assert list(run.entries.values_list("candidate_id", flat=True)) == [eligible.pk]


def test_shortlist_is_bounded_and_uses_stable_non_name_tie_break() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python"],
    )
    confirm(requirements, user)
    candidates = [
        Candidate.objects.create(
            organization=organization,
            full_name=f"Candidate {index:02d}",
        )
        for index in range(SHORTLIST_LIMIT + 5)
    ]

    run = generate_shortlist(requirements=requirements, user=user)

    assert run.entries.count() == SHORTLIST_LIMIT
    assert run.eligible_count == SHORTLIST_LIMIT + 5
    assert run.shortlisted_count == SHORTLIST_LIMIT
    assert list(run.entries.values_list("candidate_id", flat=True)) == [
        candidate.pk for candidate in candidates[:SHORTLIST_LIMIT]
    ]
    assert list(run.entries.values_list("rank", flat=True)) == list(
        range(1, SHORTLIST_LIMIT + 1)
    )


def test_score_orders_candidates_before_filter_tie_break() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python"],
    )
    create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type="location",
        source_text="Candidate must be in Prishtina.",
        expected_value="Prishtina",
        position=1,
    )
    confirm(requirements, user)
    passed = Candidate.objects.create(
        organization=organization,
        full_name="Passed Lower Score",
        location="Prishtina",
    )
    review = Candidate.objects.create(
        organization=organization,
        full_name="Review Higher Score",
    )
    assign_candidate_skill(candidate=review, user=user, label="Python")

    run = generate_shortlist(requirements=requirements, user=user)

    assert list(run.entries.values_list("candidate_id", "score", "filter_outcome")) == [
        (review.pk, Decimal("100.00"), "review"),
        (passed.pk, Decimal("0.00"), "passed"),
    ]


def test_passed_candidate_wins_equal_score_tie() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python"],
    )
    create_hard_constraint_rule(
        requirements=requirements,
        user=user,
        rule_type="location",
        source_text="Candidate must be in Prishtina.",
        expected_value="Prishtina",
        position=1,
    )
    confirm(requirements, user)
    review = Candidate.objects.create(
        organization=organization,
        full_name="Review",
    )
    passed = Candidate.objects.create(
        organization=organization,
        full_name="Passed",
        location="Prishtina",
    )

    run = generate_shortlist(requirements=requirements, user=user)

    assert list(run.entries.values_list("candidate_id", flat=True)) == [
        passed.pk,
        review.pk,
    ]


def test_run_records_version_algorithm_actor_and_multiple_generations() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python"],
    )
    confirm(requirements, user)
    Candidate.objects.create(organization=organization, full_name="Candidate")

    first = generate_shortlist(requirements=requirements, user=user)
    second = generate_shortlist(requirements=requirements, user=user)

    assert first.pk != second.pk
    assert first.requirements_id == requirements.pk
    assert first.algorithm_version == ALGORITHM_VERSION
    assert first.shortlist_limit == SHORTLIST_LIMIT
    assert first.created_by == user


def test_candidate_deletion_removes_persisted_score_evidence_but_keeps_run() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python"],
    )
    confirm(requirements, user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Private Candidate",
    )
    assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="Python",
        evidence="Private evidence that must be removed.",
    )
    run = generate_shortlist(requirements=requirements, user=user)

    delete_candidate(candidate=candidate, user=user)

    assert MatchRun.objects.filter(pk=run.pk).exists()
    assert run.shortlisted_count == 1
    assert not ShortlistEntry.objects.filter(match_run=run).exists()


def test_only_current_confirmed_requirements_can_generate_shortlist() -> None:
    user, organization = make_workspace()
    vacancy, old_requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python"],
    )
    confirm(old_requirements, user)
    newer = VacancyRequirements.objects.create(
        vacancy=vacancy,
        version=2,
        source_description=vacancy.description,
        summary="New current version",
        must_have_skills=["Django"],
        created_by=user,
    )
    sync_requirement_skills(requirements=newer, user=user)
    confirm(newer, user)

    with pytest.raises(ValidationError, match="current confirmed requirements"):
        generate_shortlist(requirements=old_requirements, user=user)


def test_generation_repeats_tenant_permission_boundary() -> None:
    owner, organization = make_workspace(username="owner")
    outsider, _ = make_workspace(username="outsider")
    _, requirements = make_requirements(
        organization=organization,
        user=owner,
        must_have=["Python"],
    )
    confirm(requirements, owner)

    with pytest.raises(PermissionDenied):
        generate_shortlist(requirements=requirements, user=outsider)


def test_shortlist_model_rejects_cross_organization_candidate() -> None:
    user, organization = make_workspace()
    other_user, other = make_workspace(username="other")
    _, requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python"],
    )
    confirm(requirements, user)
    run = MatchRun.objects.create(
        requirements=requirements,
        algorithm_version=ALGORITHM_VERSION,
        shortlist_limit=SHORTLIST_LIMIT,
        evaluated_count=1,
        eligible_count=1,
        created_by=user,
    )
    other_candidate = Candidate.objects.create(
        organization=other,
        full_name="Other Candidate",
        created_by=other_user,
    )

    with pytest.raises(ValidationError, match="match-run organization"):
        ShortlistEntry.objects.create(
            match_run=run,
            candidate=other_candidate,
            rank=1,
            score=Decimal("0"),
            filter_outcome="review",
        )


def test_database_constraints_protect_rank_and_score() -> None:
    user, organization = make_workspace()
    _, requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python"],
    )
    confirm(requirements, user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Candidate",
    )
    run = generate_shortlist(requirements=requirements, user=user)

    with pytest.raises(IntegrityError):
        ShortlistEntry.objects.filter(match_run=run, candidate=candidate).update(
            score=Decimal("101")
        )


def test_generate_route_is_post_only_and_redirects_to_report(client) -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python"],
        nice_to_have=["Redis"],
    )
    confirm(requirements, user)
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Visible Candidate",
        email="private@example.test",
    )
    assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="Python",
        evidence="Inspectable evidence only.",
    )
    url = reverse(
        "matching:shortlist-generate",
        args=[organization.slug, vacancy.pk],
    )
    client.force_login(user)

    get_response = client.get(url)
    post_response = client.post(url, follow=True)
    content = post_response.content.decode()

    assert get_response.status_code == 405
    assert post_response.status_code == 200
    assert "Visible Candidate" in content
    assert "66.67" in content
    assert "Inspectable evidence only." in content
    assert "Requirements version 1" in content
    assert "private@example.test" not in content
    assert "does not automatically reject" in content


def test_shortlist_pages_hide_other_organizations(client) -> None:
    owner, organization = make_workspace(username="owner")
    outsider, other = make_workspace(username="outsider")
    vacancy, requirements = make_requirements(
        organization=organization,
        user=owner,
        must_have=["Python"],
    )
    confirm(requirements, owner)
    Candidate.objects.create(organization=organization, full_name="Candidate")
    run = generate_shortlist(requirements=requirements, user=owner)
    client.force_login(outsider)

    generate_response = client.post(
        reverse(
            "matching:shortlist-generate",
            args=[organization.slug, vacancy.pk],
        )
    )
    detail_response = client.get(
        reverse(
            "matching:shortlist-detail",
            args=[organization.slug, vacancy.pk, run.pk],
        )
    )
    mismatched_response = client.get(
        reverse(
            "matching:shortlist-detail",
            args=[other.slug, vacancy.pk, run.pk],
        )
    )

    assert generate_response.status_code == 404
    assert detail_response.status_code == 404
    assert mismatched_response.status_code == 404


def test_filter_and_vacancy_pages_link_to_latest_shortlist(client) -> None:
    user, organization = make_workspace()
    vacancy, requirements = make_requirements(
        organization=organization,
        user=user,
        must_have=["Python"],
    )
    confirm(requirements, user)
    Candidate.objects.create(organization=organization, full_name="Candidate")
    run = generate_shortlist(requirements=requirements, user=user)
    expected_path = reverse(
        "matching:shortlist-detail",
        args=[organization.slug, vacancy.pk, run.pk],
    )
    client.force_login(user)

    filter_response = client.get(
        reverse(
            "matching:candidate-filter-report",
            args=[organization.slug, vacancy.pk],
        )
    )
    vacancy_response = client.get(
        reverse(
            "vacancies:vacancy-detail",
            args=[organization.slug, vacancy.pk],
        )
    )

    assert expected_path in filter_response.content.decode()
    assert expected_path in vacancy_response.content.decode()
