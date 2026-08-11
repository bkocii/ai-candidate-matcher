from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from accounts.models import OrganizationMembership, User
from candidates.models import Candidate
from candidates.services import delete_candidate
from matching.models import MatchRun
from matching.scoring import ALGORITHM_VERSION, SHORTLIST_LIMIT, generate_shortlist
from matching.services import assign_candidate_skill, sync_requirement_skills
from matching.staleness import (
    INPUT_SNAPSHOT_VERSION,
    assess_match_run_staleness,
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


def make_confirmed_requirements(
    *, organization: Organization, user: User
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
        must_have_skills=["Python"],
        created_by=user,
    )
    sync_requirement_skills(requirements=requirements, user=user)
    return vacancy, confirm_requirements_draft(requirements=requirements, user=user)


def make_run() -> tuple[User, Organization, Vacancy, Candidate, MatchRun]:
    user, organization = make_workspace()
    vacancy, requirements = make_confirmed_requirements(
        organization=organization,
        user=user,
    )
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Synthetic Candidate",
        location="Prishtina",
        created_by=user,
    )
    assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="Python",
        evidence="Synthetic Python evidence.",
        years_experience=Decimal("4.0"),
    )
    return (
        user,
        organization,
        vacancy,
        candidate,
        generate_shortlist(
            requirements=requirements,
            user=user,
        ),
    )


def test_generated_run_records_current_input_signatures_and_is_fresh() -> None:
    user, _, _, _, run = make_run()

    staleness = assess_match_run_staleness(run=run, user=user)

    assert run.input_snapshot_version == INPUT_SNAPSHOT_VERSION
    assert len(run.requirements_input_signature) == 64
    assert len(run.candidate_input_signature) == 64
    assert staleness.is_stale is False
    assert staleness.reason_codes == ()


def test_candidate_location_change_marks_run_stale() -> None:
    user, _, _, candidate, run = make_run()
    candidate.location = "Peja"
    candidate.save(update_fields=("location", "updated_at"))

    staleness = assess_match_run_staleness(run=run, user=user)

    assert staleness.is_stale is True
    assert staleness.reason_codes == ("candidate_inputs_changed",)


def test_candidate_skill_evidence_change_marks_run_stale() -> None:
    user, _, _, candidate, run = make_run()
    skill_record = candidate.skill_records.get()
    skill_record.evidence = "Corrected synthetic evidence."
    skill_record.save(update_fields=("evidence", "updated_at"))

    staleness = assess_match_run_staleness(run=run, user=user)

    assert staleness.reason_codes == ("candidate_inputs_changed",)


def test_new_active_candidate_marks_run_stale() -> None:
    user, organization, _, _, run = make_run()
    Candidate.objects.create(
        organization=organization,
        full_name="Newly Eligible Candidate",
        created_by=user,
    )

    staleness = assess_match_run_staleness(run=run, user=user)

    assert staleness.reason_codes == ("candidate_inputs_changed",)


def test_inactive_candidate_does_not_change_active_input_snapshot() -> None:
    user, organization, _, _, run = make_run()
    Candidate.objects.create(
        organization=organization,
        full_name="Inactive Candidate",
        status=Candidate.Status.INACTIVE,
        created_by=user,
    )

    staleness = assess_match_run_staleness(run=run, user=user)

    assert staleness.is_stale is False


def test_unrelated_contact_change_does_not_mark_run_stale() -> None:
    user, _, _, candidate, run = make_run()
    candidate.email = "new-private@example.test"
    candidate.phone = "+383 44 000 000"
    candidate.save(update_fields=("email", "phone", "updated_at"))

    staleness = assess_match_run_staleness(run=run, user=user)

    assert staleness.is_stale is False


def test_candidate_deletion_marks_run_stale_and_keeps_history() -> None:
    user, _, _, candidate, run = make_run()

    delete_candidate(candidate=candidate, user=user)
    staleness = assess_match_run_staleness(run=run, user=user)

    assert staleness.reason_codes == ("candidate_inputs_changed",)
    assert MatchRun.objects.filter(pk=run.pk).exists()
    assert run.entries.count() == 0


def test_new_confirmed_requirements_version_marks_old_run_stale() -> None:
    user, _, vacancy, _, run = make_run()
    newer = VacancyRequirements.objects.create(
        vacancy=vacancy,
        version=2,
        source_description=vacancy.description,
        summary="Corrected requirements",
        must_have_skills=["Django"],
        created_by=user,
    )
    sync_requirement_skills(requirements=newer, user=user)
    confirm_requirements_draft(requirements=newer, user=user)

    staleness = assess_match_run_staleness(run=run, user=user)

    assert staleness.reason_codes == ("vacancy_requirements_changed",)


def test_vacancy_and_filter_pages_keep_stale_history_discoverable(client) -> None:
    user, organization, vacancy, _, run = make_run()
    newer = VacancyRequirements.objects.create(
        vacancy=vacancy,
        version=2,
        source_description=vacancy.description,
        summary="Corrected requirements",
        must_have_skills=["Django"],
        created_by=user,
    )
    sync_requirement_skills(requirements=newer, user=user)
    confirm_requirements_draft(requirements=newer, user=user)
    expected_path = reverse(
        "matching:shortlist-detail",
        args=[organization.slug, vacancy.pk, run.pk],
    )
    client.force_login(user)

    vacancy_response = client.get(
        reverse(
            "vacancies:vacancy-detail",
            args=[organization.slug, vacancy.pk],
        )
    )
    filter_response = client.get(
        reverse(
            "matching:candidate-filter-report",
            args=[organization.slug, vacancy.pk],
        )
    )

    assert expected_path in vacancy_response.content.decode()
    assert "Latest shortlist (stale)" in vacancy_response.content.decode()
    assert expected_path in filter_response.content.decode()
    assert "View latest shortlist (stale)" in filter_response.content.decode()


def test_legacy_run_without_signatures_is_explicitly_stale() -> None:
    user, organization = make_workspace()
    _, requirements = make_confirmed_requirements(
        organization=organization,
        user=user,
    )
    run = MatchRun.objects.create(
        requirements=requirements,
        algorithm_version=ALGORITHM_VERSION,
        input_snapshot_version=INPUT_SNAPSHOT_VERSION,
        requirements_input_signature="",
        candidate_input_signature="",
        shortlist_limit=SHORTLIST_LIMIT,
        evaluated_count=0,
        eligible_count=0,
        created_by=user,
    )

    staleness = assess_match_run_staleness(run=run, user=user)

    assert staleness.reason_codes == ("input_snapshot_unavailable",)


def test_staleness_service_repeats_tenant_permission_boundary() -> None:
    owner, _, _, _, run = make_run()
    outsider, _ = make_workspace(username="outsider")

    with pytest.raises(PermissionDenied):
        assess_match_run_staleness(run=run, user=outsider)

    assert owner != outsider


def test_shortlist_page_labels_stale_run_and_preserves_saved_score(client) -> None:
    user, organization, vacancy, candidate, run = make_run()
    original_score = run.entries.get().score
    candidate.location = "Peja"
    candidate.save(update_fields=("location", "updated_at"))
    client.force_login(user)

    response = client.get(
        reverse(
            "matching:shortlist-detail",
            args=[organization.slug, vacancy.pk, run.pk],
        )
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "This shortlist is stale" in content
    assert "candidate matching evidence changed" in content
    assert "Generate current shortlist" in content
    assert run.entries.get().score == original_score


def test_regeneration_keeps_old_run_stale_and_creates_fresh_history(client) -> None:
    user, organization, vacancy, candidate, old_run = make_run()
    candidate.location = "Peja"
    candidate.save(update_fields=("location", "updated_at"))
    client.force_login(user)

    response = client.post(
        reverse(
            "matching:shortlist-generate",
            args=[organization.slug, vacancy.pk],
        ),
        follow=True,
    )
    new_run = MatchRun.objects.exclude(pk=old_run.pk).get()

    assert response.status_code == 200
    assert "Current result" in response.content.decode()
    assert assess_match_run_staleness(run=old_run, user=user).is_stale is True
    assert assess_match_run_staleness(run=new_run, user=user).is_stale is False
