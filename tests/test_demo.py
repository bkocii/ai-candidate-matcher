from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.urls import reverse

from accounts.models import User
from audit.models import AIUsageEvent
from candidates.models import (
    Candidate,
    CandidateDocument,
    CandidateProfile,
    CandidateSource,
)
from evaluation.dataset import load_evaluation_dataset
from evaluation.demo import prepare_demo
from evaluation.explanation_review import review_evaluation_explanations
from matching.models import MatchAssessment, MatchRun, ReviewDecision
from organizations.models import Organization
from outreach.models import OutreachDraft, OutreachDraftAction, OutreachDraftApproval
from vacancies.models import Vacancy

pytestmark = pytest.mark.django_db


def prepare_demo_command(*, tmp_path, username="demo-owner", slug="demo-test"):
    user = User.objects.create_user(
        username=username,
        password="test-password",
        email=f"{username}@example.test",
    )
    output = StringIO()
    with override_settings(MEDIA_ROOT=tmp_path):
        call_command(
            "prepare_demo",
            username=user.username,
            organization_slug=slug,
            stdout=output,
        )
    return user, Organization.objects.get(slug=slug), output.getvalue()


def test_command_prepares_provider_free_reviewable_demo(tmp_path):
    user, organization, output = prepare_demo_command(tmp_path=tmp_path)

    assert organization.name == "Synthetic Demo — AI Candidate Matcher"
    assert Candidate.objects.for_organization(organization).count() == 20
    assert CandidateDocument.objects.for_organization(organization).count() == 20
    assert CandidateProfile.objects.for_organization(organization).count() == 20
    assert Vacancy.objects.for_organization(organization).count() == 3
    assert MatchRun.objects.for_organization(organization).count() == 3
    assert MatchAssessment.objects.for_organization(organization).count() == 20
    decisions = ReviewDecision.objects.for_organization(organization)
    assert decisions.count() == 3
    assert set(decisions.values_list("decision", flat=True)) == {
        ReviewDecision.Decision.APPROVED,
        ReviewDecision.Decision.REJECTED,
        ReviewDecision.Decision.REVISIT,
    }
    assert OutreachDraft.objects.for_organization(organization).count() == 1
    assert not OutreachDraftApproval.objects.for_organization(organization).exists()
    assert not OutreachDraftAction.objects.for_organization(organization).exists()
    assert AIUsageEvent.objects.for_organization(organization).count() == 21
    assert all(
        source.contact_permission == CandidateSource.ContactPermission.RESTRICTED
        for source in CandidateSource.objects.for_organization(organization)
    )
    assessed_vacancies = set(
        MatchAssessment.objects.for_organization(organization).values_list(
            "requirements__vacancy__title",
            flat=True,
        )
    )
    assert assessed_vacancies == {"Synthetic Senior Django Backend Engineer"}
    explanation_report = review_evaluation_explanations(
        dataset=load_evaluation_dataset(),
        organization=organization,
        user=user,
    )
    assert explanation_report.reviewed_count == 20
    assert explanation_report.clean_count == 20
    assert explanation_report.flagged_count == 0

    assert "20 current assessments" in output
    assert "3 individual decisions" in output
    assert "unapproved outreach draft" in output
    assert "No provider or network request was made" in output
    assert "contact remains restricted" in output
    assert "Synthetic Candidate" not in output
    assert "Recorded synthetic skills" not in output
    assert user.email not in output


def test_demo_pages_are_real_tenant_scoped_workflow_views(client, tmp_path):
    user, organization, _output = prepare_demo_command(
        tmp_path=tmp_path,
        username="demo-page-owner",
        slug="demo-pages",
    )
    run = (
        MatchRun.objects.for_organization(organization)
        .filter(requirements__vacancy__title="Synthetic Senior Django Backend Engineer")
        .get()
    )
    approved = ReviewDecision.objects.for_organization(organization).get(
        decision=ReviewDecision.Decision.APPROVED
    )
    draft = OutreachDraft.objects.for_organization(organization).get()
    client.force_login(user)

    routes_and_text = (
        (
            reverse("organizations:organization-dashboard", args=[organization.slug]),
            "Synthetic Demo",
        ),
        (
            reverse(
                "matching:shortlist-detail",
                args=[organization.slug, run.requirements.vacancy_id, run.pk],
            ),
            "Deterministic shortlist",
        ),
        (
            reverse("matching:assessment-review-queue", args=[organization.slug])
            + "?scope=all",
            "Assessment review queue",
        ),
        (
            reverse(
                "matching:assessment-review-detail",
                args=[organization.slug, approved.assessment_id],
            ),
            "Human-controlled decision",
        ),
        (
            reverse(
                "outreach:outreach-draft-detail",
                args=[organization.slug, draft.pk],
            ),
            "Final approval is unavailable",
        ),
    )
    for route, expected_text in routes_and_text:
        response = client.get(route)
        assert response.status_code == 200
        assert expected_text in response.content.decode()


def test_demo_refuses_overwrite_and_invalid_owners(tmp_path):
    user, organization, _output = prepare_demo_command(tmp_path=tmp_path)

    with override_settings(MEDIA_ROOT=tmp_path):
        with pytest.raises(CommandError, match="never overwritten"):
            call_command(
                "prepare_demo",
                username=user.username,
                organization_slug=organization.slug,
            )
    assert Candidate.objects.for_organization(organization).count() == 20

    with pytest.raises(CommandError, match="No user"):
        call_command(
            "prepare_demo",
            username="missing-demo-user",
            organization_slug="missing-demo",
        )
    inactive = User.objects.create_user(username="inactive-demo", is_active=False)
    with pytest.raises(CommandError, match="active user"):
        call_command(
            "prepare_demo",
            username=inactive.username,
            organization_slug="inactive-demo",
        )
    assert not Organization.objects.filter(slug="inactive-demo").exists()


def test_demo_failure_rolls_back_database_and_private_fixture_files(
    monkeypatch,
    tmp_path,
):
    user = User.objects.create_user(username="failed-demo-owner")

    def fail_assessment(*args, **kwargs):
        raise RuntimeError("synthetic demo failure")

    monkeypatch.setattr("evaluation.demo.assess_shortlist_entry", fail_assessment)
    with override_settings(MEDIA_ROOT=tmp_path):
        with pytest.raises(RuntimeError, match="synthetic demo failure"):
            prepare_demo(
                dataset=load_evaluation_dataset(),
                user=user,
                organization_slug="failed-demo",
            )

    assert not Organization.objects.filter(slug="failed-demo").exists()
    assert not any(path.is_file() for path in tmp_path.rglob("*"))
