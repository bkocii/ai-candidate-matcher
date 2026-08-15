from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from candidates.models import CandidateDocument, CandidateProfile
from matching.models import MatchAssessment, MatchRun, ShortlistEntry
from operations.models import BackgroundJob, BackgroundTask
from operations.services import (
    queue_candidate_profile_batch,
    queue_shortlist_assessment_batch,
    retry_background_job,
)
from organizations.models import Organization
from vacancies.models import Vacancy

FAILURE_LABELS = {
    "ai_request_failed": "AI request could not be completed",
    "ai_configuration_error": "AI service is not configured",
    "ai_service_unavailable": "AI service is temporarily unavailable",
    "ai_invalid_response": "AI response did not pass validation",
    "authorization_failed": "Recruiter access is no longer active",
    "application_validation": "Inputs changed or did not pass safety validation",
    "confirmed_profile_required": "Confirmed candidate profile required",
    "target_unavailable": "Target record is no longer available",
    "unexpected_processing_error": "Unexpected processing failure",
}


def _organization(request, slug: str) -> Organization:
    return get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=slug,
    )


@login_required
@require_POST
def candidate_profile_batch_queue(request, organization_slug: str):
    organization = _organization(request, organization_slug)
    try:
        result = queue_candidate_profile_batch(
            organization=organization,
            user=request.user,
        )
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
        return redirect("candidates:candidate-list", organization.slug)
    messages.success(
        request,
        (
            "Profile extraction job queued. Drafts still require evidence review and "
            "individual confirmation."
            if result.created
            else "The same profile extraction job is already available."
        ),
    )
    return redirect("operations:job-detail", organization.slug, result.job.pk)


@login_required
@require_POST
def shortlist_assessment_batch_queue(
    request,
    organization_slug: str,
    vacancy_id: int,
    match_run_id: int,
):
    organization = _organization(request, organization_slug)
    vacancy = get_object_or_404(
        Vacancy.objects.for_organization(organization).active(),
        pk=vacancy_id,
    )
    run = get_object_or_404(
        MatchRun.objects.for_organization(organization),
        pk=match_run_id,
        requirements__vacancy=vacancy,
    )
    try:
        result = queue_shortlist_assessment_batch(run=run, user=request.user)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
        return redirect(
            "matching:shortlist-detail",
            organization.slug,
            vacancy.pk,
            run.pk,
        )
    messages.success(
        request,
        (
            "Whole-shortlist assessment job queued. Final decisions remain individual."
            if result.created
            else "The assessment job for this shortlist is already available."
        ),
    )
    return redirect("operations:job-detail", organization.slug, result.job.pk)


@login_required
def job_list(request, organization_slug: str):
    organization = _organization(request, organization_slug)
    jobs = BackgroundJob.objects.for_organization(organization).select_related(
        "created_by"
    )
    page = Paginator(jobs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "operations/job_list.html",
        {"organization": organization, "page": page},
    )


def _present_task(task: BackgroundTask, organization: Organization) -> None:
    task.target_label = f"Target {task.target_id}"
    task.target_url = ""
    task.result_url = ""
    if task.target_type == BackgroundTask.TargetType.CANDIDATE_DOCUMENT:
        document = (
            CandidateDocument.objects.for_organization(organization)
            .select_related("candidate")
            .filter(pk=task.target_id)
            .first()
        )
        if document is not None:
            task.target_label = document.candidate.full_name
            task.target_url = reverse(
                "candidates:candidate-detail",
                args=[organization.slug, document.candidate_id],
            )
    else:
        entry = (
            ShortlistEntry.objects.for_organization(organization)
            .select_related("candidate")
            .filter(pk=task.target_id)
            .first()
        )
        if entry is not None:
            task.target_label = entry.candidate.full_name
            task.target_url = reverse(
                "candidates:candidate-detail",
                args=[organization.slug, entry.candidate_id],
            )
    if task.result_type == BackgroundTask.ResultType.CANDIDATE_PROFILE:
        profile = (
            CandidateProfile.objects.for_organization(organization)
            .filter(pk=task.result_id)
            .first()
        )
        if profile is not None:
            task.result_url = reverse(
                "candidates:candidate-profile-detail",
                args=[organization.slug, profile.candidate_id, profile.pk],
            )
    elif task.result_type == BackgroundTask.ResultType.MATCH_ASSESSMENT:
        assessment = (
            MatchAssessment.objects.for_organization(organization)
            .filter(pk=task.result_id)
            .first()
        )
        if assessment is not None:
            task.result_url = reverse(
                "matching:assessment-review-detail",
                args=[organization.slug, assessment.pk],
            )
    task.failure_label = FAILURE_LABELS.get(
        task.failure_code,
        "Processing exception requires review",
    )


@login_required
def job_detail(request, organization_slug: str, job_id: int):
    organization = _organization(request, organization_slug)
    job = get_object_or_404(
        BackgroundJob.objects.for_organization(organization).select_related(
            "created_by"
        ),
        pk=job_id,
    )
    tasks = list(job.tasks.all())
    for task in tasks:
        _present_task(task, organization)
    return render(
        request,
        "operations/job_detail.html",
        {"organization": organization, "job": job, "tasks": tasks},
    )


@login_required
@require_POST
def job_retry(request, organization_slug: str, job_id: int):
    organization = _organization(request, organization_slug)
    job = get_object_or_404(
        BackgroundJob.objects.for_organization(organization),
        pk=job_id,
    )
    count = retry_background_job(job=job, user=request.user)
    if count:
        messages.success(request, f"Requeued {count} exception target(s).")
    else:
        messages.error(request, "This job has no failed or skipped targets to retry.")
    return redirect("operations:job-detail", organization.slug, job.pk)
