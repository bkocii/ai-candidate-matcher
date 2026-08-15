from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from ai_gateway import AIGatewayUnavailableError
from ai_gateway.testing import FakeAIGateway
from candidates.models import Candidate, CandidateDocument, CandidateProfile
from matching.scoring import generate_shortlist
from matching.services import assign_candidate_skill
from operations.models import BackgroundJob, BackgroundTask
from operations.services import (
    process_next_background_task,
    queue_candidate_profile_batch,
    queue_shortlist_assessment_batch,
    retry_background_job,
)
from tests.test_candidate_ai_extraction import (
    extracted_output,
)
from tests.test_candidate_ai_extraction import (
    make_workspace as make_profile_workspace,
)
from tests.test_candidate_ai_extraction import (
    metadata as profile_metadata,
)
from tests.test_match_ai_assessment import (
    ConfiguredAssessmentGateway,
)
from tests.test_match_ai_assessment import (
    make_workspace as make_match_workspace,
)

pytestmark = pytest.mark.django_db


def profile_gateway():
    return FakeAIGateway(
        response=extracted_output(),
        metadata=profile_metadata(),
    )


def test_profile_batch_is_idempotent_and_creates_reviewable_draft():
    user, organization, _, document = make_profile_workspace()

    first = queue_candidate_profile_batch(organization=organization, user=user)
    duplicate = queue_candidate_profile_batch(organization=organization, user=user)

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.job == first.job
    assert first.job.tasks.count() == 1

    gateway = profile_gateway()
    task = process_next_background_task(job_id=first.job.pk, gateway=gateway)

    profile = CandidateProfile.objects.get(source_document=document)
    first.job.refresh_from_db()
    assert task.status == BackgroundTask.Status.SUCCEEDED
    assert task.outcome == BackgroundTask.Outcome.CREATED
    assert profile.status == CandidateProfile.Status.DRAFT
    assert profile.confirmed_by is None
    assert first.job.status == BackgroundJob.Status.SUCCEEDED
    assert len(gateway.calls) == 1
    assert (
        queue_candidate_profile_batch(
            organization=organization,
            user=user,
        ).job
        == first.job
    )


def test_profile_batch_reuses_profiled_source_and_queues_new_corrected_cv_only():
    user, organization, candidate, old_document = make_profile_workspace()
    old_profile = CandidateProfile.objects.create(
        candidate=candidate,
        source_document=old_document,
        version=1,
        source_document_sha256=old_document.sha256,
        source_text_sha256="b" * 64,
        ambiguities=["Recruiter review required"],
        created_by=user,
    )
    corrected = CandidateDocument.objects.create(
        candidate=candidate,
        document_type=CandidateDocument.DocumentType.CV,
        original_filename="corrected-cv.pdf",
        file="candidate_documents/corrected-cv.pdf",
        content_type="application/pdf",
        size_bytes=2_000,
        sha256="c" * 64,
        extraction_status=CandidateDocument.ExtractionStatus.SUCCEEDED,
        extracted_text=old_document.extracted_text,
        extracted_at=timezone.now(),
        uploaded_by=user,
    )

    queued = queue_candidate_profile_batch(organization=organization, user=user)

    task = queued.job.tasks.get()
    assert task.target_id == corrected.pk
    assert task.target_id != old_profile.source_document_id


def _add_skill_only_candidate(*, user, organization):
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Second Synthetic Candidate",
        location="Prishtina",
        created_by=user,
    )
    assign_candidate_skill(
        candidate=candidate,
        user=user,
        label="Python",
        evidence="Python: five years",
        years_experience=5,
    )
    return candidate


def test_shortlist_batch_isolates_failures_and_explicit_retry_resumes_work():
    user, organization, _, _, _, _, original_run, _ = make_match_workspace()
    _add_skill_only_candidate(
        user=user,
        organization=organization,
    )
    run = generate_shortlist(requirements=original_run.requirements, user=user)
    queued = queue_shortlist_assessment_batch(run=run, user=user)
    duplicate = queue_shortlist_assessment_batch(run=run, user=user)
    assert duplicate.job == queued.job
    assert duplicate.created is False
    assert queued.job.total_count == 2

    failed = process_next_background_task(
        job_id=queued.job.pk,
        gateway=FakeAIGateway(error=AIGatewayUnavailableError()),
    )
    skipped = process_next_background_task(
        job_id=queued.job.pk,
        gateway=ConfiguredAssessmentGateway(),
    )

    queued.job.refresh_from_db()
    assert failed.status == BackgroundTask.Status.FAILED
    assert failed.failure_code == "ai_service_unavailable"
    assert skipped.status == BackgroundTask.Status.SKIPPED
    assert skipped.failure_code == "confirmed_profile_required"
    assert queued.job.status == BackgroundJob.Status.COMPLETED_WITH_ERRORS
    assert queued.job.failed_count == 1
    assert queued.job.skipped_count == 1

    assert retry_background_job(job=queued.job, user=user) == 2
    retried = process_next_background_task(
        job_id=queued.job.pk,
        gateway=ConfiguredAssessmentGateway(),
    )
    assert retried.status == BackgroundTask.Status.SUCCEEDED
    assert retried.attempt_count == 2


def test_shortlist_batch_creates_assessment_without_a_candidate_decision():
    user, _, _, _, profile, _, run, entry = make_match_workspace()
    queued = queue_shortlist_assessment_batch(run=run, user=user)

    task = process_next_background_task(
        job_id=queued.job.pk,
        gateway=ConfiguredAssessmentGateway(),
    )

    assessment = entry.assessments.get()
    queued.job.refresh_from_db()
    assert task.status == BackgroundTask.Status.SUCCEEDED
    assert task.result_id == assessment.pk
    assert assessment.candidate_profile == profile
    assert not entry.review_decisions.exists()
    assert queued.job.status == BackgroundJob.Status.SUCCEEDED


def test_expired_task_reuses_saved_profile_without_another_ai_call():
    user, organization, candidate, document = make_profile_workspace()
    queued = queue_candidate_profile_batch(organization=organization, user=user)
    profile = CandidateProfile.objects.create(
        candidate=candidate,
        source_document=document,
        version=1,
        source_document_sha256=document.sha256,
        source_text_sha256="d" * 64,
        ambiguities=["Recruiter review required"],
        created_by=user,
    )
    task = queued.job.tasks.get()
    task.status = BackgroundTask.Status.RUNNING
    task.lease_expires_at = timezone.now() - timedelta(minutes=1)
    task.save(update_fields=("status", "lease_expires_at", "updated_at"))
    gateway = FakeAIGateway(error=AssertionError("AI must not be called"))

    resumed = process_next_background_task(job_id=queued.job.pk, gateway=gateway)

    assert resumed.status == BackgroundTask.Status.SUCCEEDED
    assert resumed.outcome == BackgroundTask.Outcome.REUSED
    assert resumed.result_id == profile.pk
    assert gateway.calls == []


def test_job_routes_are_tenant_scoped_and_show_batch_controls(client):
    user, organization, _, _ = make_profile_workspace()
    other_user, other_organization, _, _ = make_profile_workspace(
        username="other-recruiter"
    )
    job = queue_candidate_profile_batch(organization=organization, user=user).job
    client.force_login(user)

    candidate_page = client.get(
        reverse("candidates:candidate-list", args=[organization.slug])
    )
    job_page = client.get(
        reverse("operations:job-detail", args=[organization.slug, job.pk])
    )
    hidden = client.get(
        reverse("operations:job-detail", args=[other_organization.slug, job.pk])
    )

    assert candidate_page.status_code == 200
    assert b"Queue pending profile extraction" in candidate_page.content
    assert job_page.status_code == 200
    assert b"Profile confirmation" in job_page.content
    assert hidden.status_code == 404
    assert other_user != user


def test_worker_burst_reports_only_safe_task_identifiers(monkeypatch, capsys):
    user, organization, _, _ = make_profile_workspace()
    queued = queue_candidate_profile_batch(organization=organization, user=user)
    task = queued.job.tasks.get()

    def fake_process(*, job_id=None, gateway=None):
        if fake_process.called:
            return None
        fake_process.called = True
        task.status = BackgroundTask.Status.SUCCEEDED
        return task

    fake_process.called = False
    monkeypatch.setattr(
        "operations.management.commands.run_background_worker."
        "process_next_background_task",
        fake_process,
    )

    call_command("run_background_worker", "--burst", "--job", str(queued.job.pk))
    output = capsys.readouterr().out
    assert f"Processed task {task.pk}: succeeded." in output
    assert "arta@example.test" not in output
    assert "Arta Krasniqi" not in output
