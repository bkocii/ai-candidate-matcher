import copy
import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from accounts.models import User
from audit.models import AIUsageEvent
from candidates.models import CandidateProfile
from evaluation.dataset import load_evaluation_dataset
from evaluation.explanation_review import review_evaluation_explanations
from evaluation.services import install_evaluation_dataset
from matching.ai_assessment import (
    MATCH_ASSESSMENT_SCHEMA_VERSION,
    MatchAssessmentOutput,
    _assessment_values,
    build_assessment_context,
)
from matching.explanation_safety import normalize_explanation_text
from matching.models import MatchAssessment

pytestmark = pytest.mark.django_db


def install_workspace(*, tmp_path, username="explanation-owner"):
    user = User.objects.create_user(username=username, password="test-password")
    dataset = load_evaluation_dataset()
    with override_settings(MEDIA_ROOT=tmp_path):
        installed = install_evaluation_dataset(
            dataset=dataset,
            user=user,
            organization_slug=f"{username}-workspace",
        )
    return user, dataset, installed


def candidate_code(entry):
    return entry.candidate.sources.get(
        source_reference__startswith="EVAL-001-"
    ).source_reference.removeprefix("EVAL-001-")


def _tokens(value):
    return set(normalize_explanation_text(value).replace(",", " ").split())


def create_safe_assessment(*, entry, user):
    profile = (
        CandidateProfile.objects.filter(
            candidate=entry.candidate,
            status=CandidateProfile.Status.CONFIRMED,
        )
        .order_by("-version", "-id")
        .first()
    )
    context = build_assessment_context(entry=entry, profile=profile)
    findings = []
    for requirement in context.requirements:
        requirement_tokens = _tokens(requirement.label) | _tokens(requirement.evidence)
        matching_evidence = next(
            (
                item
                for item in context.candidate_evidence
                if requirement_tokens & (_tokens(item.label) | _tokens(item.evidence))
            ),
            None,
        )
        findings.append(
            {
                "requirement_id": requirement.identifier,
                "outcome": "match" if matching_evidence else "uncertain",
                "candidate_evidence_ids": (
                    [matching_evidence.identifier] if matching_evidence else []
                ),
                "explanation": (
                    "The linked evidence supports this match."
                    if matching_evidence
                    else "The supplied evidence does not resolve this requirement."
                ),
            }
        )
    output = MatchAssessmentOutput.model_validate(
        {
            "score": 50,
            "summary": "Review the linked requirement findings.",
            "requirement_assessments": findings,
            "review_recommendation": "Verify every uncertain requirement.",
        }
    )
    return MatchAssessment.objects.create(
        shortlist_entry=entry,
        requirements=entry.match_run.requirements,
        candidate_profile=profile,
        version=1,
        schema_version=MATCH_ASSESSMENT_SCHEMA_VERSION,
        created_by=user,
        **_assessment_values(output=output, context=context),
    )


def create_complete_assessments(*, installed, user):
    for run in installed.match_runs.values():
        for entry in run.entries.select_related("candidate", "match_run__requirements"):
            create_safe_assessment(entry=entry, user=user)


def test_complete_current_explanations_can_be_reviewed_cleanly(tmp_path):
    user, dataset, installed = install_workspace(tmp_path=tmp_path)
    create_complete_assessments(installed=installed, user=user)

    report = review_evaluation_explanations(
        dataset=dataset,
        organization=installed.organization,
        user=user,
    )

    assert report.status == "complete"
    assert report.reviewed_count == report.expected_count == 60
    assert report.clean_count == 60
    assert report.flagged_count == 0
    assert report.issue_counts == {}
    assert report.is_clean
    assert AIUsageEvent.objects.for_organization(installed.organization).count() == 0


def test_review_flags_protected_unsupported_and_snapshot_content(tmp_path):
    user, dataset, installed = install_workspace(
        tmp_path=tmp_path,
        username="flagged-explanation-owner",
    )
    entry = (
        installed.match_runs["V01"]
        .entries.select_related("candidate", "match_run__requirements")
        .prefetch_related("candidate__sources")
        .first()
    )
    assessment = create_safe_assessment(entry=entry, user=user)
    findings = copy.deepcopy(assessment.matching_requirements)
    assert findings
    findings[0]["requirement_label"] = "Tampered requirement label"
    MatchAssessment.objects.filter(pk=assessment.pk).update(
        summary="The candidate's age indicates 99 years of experience.",
        review_recommendation='Verify the claimed "Unsupported Fixture Phrase".',
        matching_requirements=findings,
    )

    report = review_evaluation_explanations(
        dataset=dataset,
        organization=installed.organization,
        user=user,
    )

    assert report.status == "unavailable"
    assert report.reviewed_count == 1
    codes = report.issue_counts
    assert codes["protected_attribute_language"] == 1
    assert codes["unsupported_measured_claim"] == 1
    assert codes["unsupported_quoted_claim"] == 1
    assert codes["invalid_requirement_snapshot"] == 1
    assert candidate_code(entry) in {
        item.candidate_code for item in report.assessments if item.issues
    }


def test_review_flags_a_match_whose_citation_does_not_support_requirement(tmp_path):
    user, dataset, installed = install_workspace(
        tmp_path=tmp_path,
        username="mismatch-explanation-owner",
    )
    entry = (
        installed.match_runs["V01"]
        .entries.select_related("candidate", "match_run__requirements")
        .first()
    )
    assessment = create_safe_assessment(entry=entry, user=user)
    context = build_assessment_context(
        entry=entry,
        profile=assessment.candidate_profile,
    )
    findings = copy.deepcopy(assessment.matching_requirements)
    target = findings[0]
    requirement = next(
        item
        for item in context.requirements
        if item.identifier == target["requirement_id"]
    )
    requirement_tokens = _tokens(requirement.label) | _tokens(requirement.evidence)
    unrelated = next(
        item
        for item in context.candidate_evidence
        if not requirement_tokens & (_tokens(item.label) | _tokens(item.evidence))
    )
    target["candidate_evidence"] = [
        {
            "id": unrelated.identifier,
            "label": unrelated.label,
            "evidence": unrelated.evidence,
        }
    ]
    MatchAssessment.objects.filter(pk=assessment.pk).update(
        matching_requirements=findings
    )

    report = review_evaluation_explanations(
        dataset=dataset,
        organization=installed.organization,
        user=user,
    )

    assert report.issue_counts["match_without_lexical_support"] == 1


def test_review_command_is_content_minimized_and_supports_strict_gates(tmp_path):
    user, _dataset, installed = install_workspace(
        tmp_path=tmp_path,
        username="explanation-command-owner",
    )
    output = StringIO()

    call_command(
        "review_evaluation_explanations",
        username=user.username,
        organization_slug=installed.organization.slug,
        format="json",
        stdout=output,
    )
    payload = json.loads(output.getvalue())

    assert payload["status"] == "unavailable"
    assert payload["reviewed_count"] == 0
    assert payload["expected_count"] == 60
    assert "Synthetic Candidate" not in output.getvalue()
    assert "Recorded synthetic skills" not in output.getvalue()
    assert AIUsageEvent.objects.for_organization(installed.organization).count() == 0

    with pytest.raises(CommandError, match="incomplete"):
        call_command(
            "review_evaluation_explanations",
            username=user.username,
            organization_slug=installed.organization.slug,
            require_complete=True,
            stdout=StringIO(),
        )
    with pytest.raises(CommandError, match="not clean"):
        call_command(
            "review_evaluation_explanations",
            username=user.username,
            organization_slug=installed.organization.slug,
            require_clean=True,
            stdout=StringIO(),
        )
