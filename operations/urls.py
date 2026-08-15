from django.urls import path

from operations import views

app_name = "operations"

urlpatterns = [
    path(
        "organizations/<slug:organization_slug>/jobs/",
        views.job_list,
        name="job-list",
    ),
    path(
        "organizations/<slug:organization_slug>/jobs/<int:job_id>/",
        views.job_detail,
        name="job-detail",
    ),
    path(
        "organizations/<slug:organization_slug>/jobs/<int:job_id>/retry/",
        views.job_retry,
        name="job-retry",
    ),
    path(
        "organizations/<slug:organization_slug>/candidate-profile-jobs/queue/",
        views.candidate_profile_batch_queue,
        name="candidate-profile-batch-queue",
    ),
    path(
        "organizations/<slug:organization_slug>/vacancies/<int:vacancy_id>/"
        "shortlists/<int:match_run_id>/assessment-jobs/queue/",
        views.shortlist_assessment_batch_queue,
        name="shortlist-assessment-batch-queue",
    ),
]
