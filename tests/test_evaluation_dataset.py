from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from accounts.models import OrganizationMembership, User
from audit.models import AIUsageEvent
from candidates.models import Candidate, CandidateDocument, CandidateProfile
from evaluation.dataset import canonical_dataset_json, load_evaluation_dataset
from matching.models import MatchAssessment, MatchRun, ReviewDecision
from organizations.models import Organization
from outreach.models import OutreachDraft
from vacancies.models import Vacancy

pytestmark = pytest.mark.django_db


def candidate_code(candidate: Candidate) -> str:
    reference = candidate.sources.get().source_reference
    return reference.removeprefix("EVAL-001-")


def test_eval_001_manifest_is_complete_strict_and_entirely_synthetic() -> None:
    dataset = load_evaluation_dataset()

    assert dataset.dataset_id == "eval-001.synthetic-multirole.v1"
    assert dataset.schema_version == "evaluation_dataset.v1"
    assert len(dataset.candidates) == 20
    assert len(dataset.vacancies) == 3
    assert all(
        item.full_name.startswith("Synthetic Candidate ") for item in dataset.candidates
    )
    assert all(len(vacancy.relevance_judgments) == 20 for vacancy in dataset.vacancies)
    assert {
        grade
        for vacancy in dataset.vacancies
        for grade in vacancy.relevance_judgments.values()
    } == {0, 1, 2, 3}

    serialized = canonical_dataset_json(dataset).casefold()
    for prohibited_key in (
        '"age":',
        '"gender":',
        '"ethnicity":',
        '"religion":',
        '"disability":',
        '"family_status":',
        '"photograph":',
    ):
        assert prohibited_key not in serialized


def test_command_installs_grounded_profiles_and_verified_shortlists(tmp_path) -> None:
    user = User.objects.create_user(username="eval-owner", password="test-password")
    output = StringIO()

    with override_settings(MEDIA_ROOT=tmp_path):
        call_command(
            "load_evaluation_dataset",
            username=user.username,
            organization_slug="eval-command-test",
            stdout=output,
        )

    organization = Organization.objects.get(slug="eval-command-test")
    dataset = load_evaluation_dataset()
    candidates = Candidate.objects.for_organization(organization)
    candidate_codes_by_id = {
        candidate.pk: candidate_code(candidate) for candidate in candidates
    }

    assert candidates.count() == 20
    assert Vacancy.objects.for_organization(organization).count() == 3
    assert CandidateDocument.objects.for_organization(organization).count() == 20
    assert CandidateProfile.objects.for_organization(organization).count() == 20
    assert MatchRun.objects.for_organization(organization).count() == 3
    assert OrganizationMembership.objects.filter(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    ).exists()

    for candidate in candidates.prefetch_related(
        "sources", "documents", "profile_versions"
    ):
        source = candidate.sources.get()
        document = candidate.documents.get()
        profile = candidate.profile_versions.get()
        assert source.contact_permission == source.ContactPermission.RESTRICTED
        assert source.consent_status == source.ConsentStatus.NOT_REQUIRED
        assert not candidate.email
        assert not candidate.phone
        assert profile.status == CandidateProfile.Status.CONFIRMED
        assert profile.source_document == document
        assert profile.relevant_experience_summary in document.extracted_text
        assert all(
            skill["evidence"] in document.extracted_text for skill in profile.skills
        )

    vacancy_specs = {vacancy.code: vacancy for vacancy in dataset.vacancies}
    for run in MatchRun.objects.for_organization(organization).select_related(
        "requirements__vacancy"
    ):
        spec = next(
            item for item in vacancy_specs.values() if item.title == run.vacancy.title
        )
        expected = [(item.candidate_code, item.score) for item in spec.expected_top]
        actual = [
            (candidate_codes_by_id[entry.candidate_id], entry.score)
            for entry in run.entries.order_by("rank")[: len(expected)]
        ]
        assert actual == expected
        assert run.evaluated_count == 20
        assert run.shortlisted_count == 20

    assert AIUsageEvent.objects.for_organization(organization).count() == 0
    assert MatchAssessment.objects.for_organization(organization).count() == 0
    assert ReviewDecision.objects.for_organization(organization).count() == 0
    assert OutreachDraft.objects.for_organization(organization).count() == 0
    assert "20 candidates, 3 vacancies, and 3 verified shortlists" in output.getvalue()
    assert "No AI request or outreach action was made" in output.getvalue()

    with pytest.raises(CommandError, match="never overwritten"):
        call_command(
            "load_evaluation_dataset",
            username=user.username,
            organization_slug=organization.slug,
        )
    assert Candidate.objects.for_organization(organization).count() == 20


def test_command_rejects_missing_or_inactive_owner() -> None:
    with pytest.raises(CommandError, match="No user"):
        call_command(
            "load_evaluation_dataset",
            username="missing-eval-user",
            organization_slug="missing-user-eval",
        )

    inactive = User.objects.create_user(username="inactive-eval", is_active=False)
    with pytest.raises(CommandError, match="active user"):
        call_command(
            "load_evaluation_dataset",
            username=inactive.username,
            organization_slug="inactive-user-eval",
        )
    assert not Organization.objects.filter(slug="inactive-user-eval").exists()


def test_frozen_expected_score_mismatch_rolls_back_database_and_files(
    tmp_path,
) -> None:
    from evaluation.services import (
        EvaluationDatasetMismatchError,
        install_evaluation_dataset,
    )

    user = User.objects.create_user(username="mismatch-owner")
    dataset = load_evaluation_dataset().model_copy(deep=True)
    dataset.vacancies[0].expected_top[0].score = Decimal("99.99")

    with override_settings(MEDIA_ROOT=tmp_path):
        with pytest.raises(EvaluationDatasetMismatchError, match="No evaluation"):
            install_evaluation_dataset(
                dataset=dataset,
                user=user,
                organization_slug="mismatch-eval",
            )

    assert not Organization.objects.filter(slug="mismatch-eval").exists()
    assert not any(path.is_file() for path in tmp_path.rglob("*"))
