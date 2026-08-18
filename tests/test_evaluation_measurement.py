import json
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from accounts.models import User
from audit.models import AIUsageEvent
from candidates.models import CandidateProfile
from evaluation.dataset import load_evaluation_dataset
from evaluation.measurement import (
    EvaluationMeasurementError,
    measure_evaluation_quality,
)
from evaluation.services import install_evaluation_dataset
from matching.models import MatchAssessment

pytestmark = pytest.mark.django_db


def install_workspace(*, tmp_path, username="evaluation-owner"):
    user = User.objects.create_user(username=username, password="test-password")
    dataset = load_evaluation_dataset()
    with override_settings(MEDIA_ROOT=tmp_path):
        installed = install_evaluation_dataset(
            dataset=dataset,
            user=user,
            organization_slug=f"{username}-workspace",
        )
    return user, dataset, installed


def create_assessment(*, entry, profile, user, score, version=1):
    return MatchAssessment.objects.create(
        shortlist_entry=entry,
        requirements=entry.match_run.requirements,
        candidate_profile=profile,
        version=version,
        score=score,
        traffic_light=MatchAssessment.traffic_light_for_score(score),
        summary="Synthetic assessment used only for ranking measurement.",
        matching_requirements=[
            {
                "requirement": "Synthetic evaluation requirement",
                "evidence": "Synthetic evaluation evidence",
            }
        ],
        gaps=[],
        uncertainties=[],
        review_recommendation="Inspect this synthetic assessment individually.",
        created_by=user,
    )


def candidate_code(entry):
    return entry.candidate.sources.get(
        source_reference__startswith="EVAL-001-"
    ).source_reference.removeprefix("EVAL-001-")


def create_complete_perfect_assessments(*, user, dataset, installed):
    specs = {spec.code: spec for spec in dataset.vacancies}
    for vacancy_code, run in installed.match_runs.items():
        spec = specs[vacancy_code]
        expected_positions = {
            item.candidate_code: position
            for position, item in enumerate(spec.expected_top)
        }
        for entry in run.entries.select_related("candidate").prefetch_related(
            "candidate__sources"
        ):
            code = candidate_code(entry)
            profile = CandidateProfile.objects.filter(
                candidate=entry.candidate,
                status=CandidateProfile.Status.CONFIRMED,
            ).first()
            score = (
                100 - expected_positions[code]
                if code in expected_positions
                else 10 + spec.relevance_judgments[code] * 20
            )
            create_assessment(
                entry=entry,
                profile=profile,
                user=user,
                score=score,
            )


def test_deterministic_metrics_are_reproducible_without_ai_coverage(tmp_path):
    user, dataset, installed = install_workspace(tmp_path=tmp_path)

    report = measure_evaluation_quality(
        dataset=dataset,
        organization=installed.organization,
        user=user,
    )

    assert report.dataset_sha256 == installed.dataset_sha256
    assert report.cutoff == 5
    assert report.deterministic_macro.ndcg_at_k == 1
    assert report.deterministic_macro.precision_at_k == Decimal("0.9333")
    assert report.deterministic_macro.expected_top_overlap_at_k == 1
    assert report.ai_assessed_count == 0
    assert report.ai_expected_count == 60
    assert report.ai_assisted_macro is None
    assert all(
        item.ai_assisted.status == "unavailable" and item.ai_assisted.metrics is None
        for item in report.vacancies
    )
    assert AIUsageEvent.objects.for_organization(installed.organization).count() == 0


def test_complete_current_assessments_are_measured_separately(tmp_path):
    user, dataset, installed = install_workspace(
        tmp_path=tmp_path,
        username="complete-evaluation-owner",
    )
    create_complete_perfect_assessments(
        user=user,
        dataset=dataset,
        installed=installed,
    )

    report = measure_evaluation_quality(
        dataset=dataset,
        organization=installed.organization,
        user=user,
    )

    assert report.ai_assisted_complete
    assert report.ai_assessed_count == 60
    assert report.ai_assisted_macro is not None
    assert report.ai_assisted_macro.ndcg_at_k == 1
    assert report.ai_assisted_macro.precision_at_k == Decimal("0.9333")
    assert report.ai_assisted_macro.expected_top_overlap_at_k == 1
    assert all(item.ai_assisted.status == "complete" for item in report.vacancies)
    assert AIUsageEvent.objects.for_organization(installed.organization).count() == 0


def test_partial_ai_coverage_never_produces_ai_quality_metrics(tmp_path):
    user, dataset, installed = install_workspace(
        tmp_path=tmp_path,
        username="partial-evaluation-owner",
    )
    entry = installed.match_runs["V01"].entries.select_related("candidate").first()
    profile = CandidateProfile.objects.filter(
        candidate=entry.candidate,
        status=CandidateProfile.Status.CONFIRMED,
    ).first()
    create_assessment(entry=entry, profile=profile, user=user, score=100)

    report = measure_evaluation_quality(
        dataset=dataset,
        organization=installed.organization,
        user=user,
    )

    by_code = {item.vacancy_code: item for item in report.vacancies}
    assert report.ai_assessed_count == 1
    assert report.ai_expected_count == 60
    assert report.ai_assisted_macro is None
    assert by_code["V01"].ai_assisted.ranked_count == 1
    assert by_code["V01"].ai_assisted.metrics is None
    assert by_code["V02"].ai_assisted.ranked_count == 0


def test_ai_order_can_score_worse_without_changing_deterministic_metrics(tmp_path):
    user, dataset, installed = install_workspace(
        tmp_path=tmp_path,
        username="separate-ranking-owner",
    )
    create_complete_perfect_assessments(
        user=user,
        dataset=dataset,
        installed=installed,
    )
    spec = next(item for item in dataset.vacancies if item.code == "V01")
    for entry in (
        installed.match_runs["V01"]
        .entries.select_related("candidate")
        .prefetch_related("candidate__sources")
    ):
        code = candidate_code(entry)
        profile = CandidateProfile.objects.filter(
            candidate=entry.candidate,
            status=CandidateProfile.Status.CONFIRMED,
        ).first()
        create_assessment(
            entry=entry,
            profile=profile,
            user=user,
            score=100 - spec.relevance_judgments[code] * 25,
            version=2,
        )

    report = measure_evaluation_quality(
        dataset=dataset,
        organization=installed.organization,
        user=user,
    )
    by_code = {item.vacancy_code: item for item in report.vacancies}

    assert by_code["V01"].deterministic.metrics.ndcg_at_k == 1
    assert by_code["V01"].ai_assisted.metrics.ndcg_at_k < 1
    assert report.deterministic_macro.ndcg_at_k == 1
    assert report.ai_assisted_macro.ndcg_at_k < 1


def test_measurement_rejects_a_stale_installed_shortlist(tmp_path):
    user, dataset, installed = install_workspace(
        tmp_path=tmp_path,
        username="stale-evaluation-owner",
    )
    candidate = next(iter(installed.candidates.values()))
    candidate.location = "Changed synthetic location"
    candidate.save()

    with pytest.raises(EvaluationMeasurementError, match="stale"):
        measure_evaluation_quality(
            dataset=dataset,
            organization=installed.organization,
            user=user,
        )


def test_measurement_command_supports_safe_json_and_strict_ai_gate(tmp_path):
    user, _dataset, installed = install_workspace(
        tmp_path=tmp_path,
        username="command-evaluation-owner",
    )
    output = StringIO()

    call_command(
        "measure_evaluation_dataset",
        username=user.username,
        organization_slug=installed.organization.slug,
        format="json",
        stdout=output,
    )
    payload = json.loads(output.getvalue())

    assert payload["dataset_id"] == "eval-001.synthetic-multirole.v1"
    assert payload["ai_assisted_macro"] is None
    assert payload["ai_assessed_count"] == 0
    assert payload["ai_expected_count"] == 60
    assert "Synthetic Candidate" not in output.getvalue()
    assert "@example" not in output.getvalue()

    with pytest.raises(CommandError, match="incomplete"):
        call_command(
            "measure_evaluation_dataset",
            username=user.username,
            organization_slug=installed.organization.slug,
            require_complete_ai=True,
            stdout=StringIO(),
        )
