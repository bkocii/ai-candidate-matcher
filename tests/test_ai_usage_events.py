from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from ai_gateway import (
    AIGatewayMetadata,
    AIGatewayTokenUsage,
    AIGatewayUnavailableError,
)
from audit.models import AIUsageEvent
from audit.services import (
    complete_ai_usage_failure,
    complete_ai_usage_success,
    start_ai_usage_event,
)
from candidates.ai_extraction import extract_candidate_profile
from matching.ai_assessment import assess_shortlist_entry, build_assessment_context
from matching.models import MatchAssessment
from tests.test_candidate_ai_extraction import (
    RecordingGateway as CandidateGateway,
)
from tests.test_candidate_ai_extraction import (
    make_workspace as make_candidate_workspace,
)
from tests.test_match_ai_assessment import (
    RecordingGateway as AssessmentGateway,
)
from tests.test_match_ai_assessment import make_workspace as make_assessment_workspace
from tests.test_match_ai_assessment import output_for_context
from tests.test_vacancy_ai_extraction import RecordingGateway as VacancyGateway
from tests.test_vacancy_ai_extraction import make_workspace as make_vacancy_workspace
from vacancies.ai_extraction import extract_vacancy_requirements
from vacancies.models import VacancyRequirements

pytestmark = pytest.mark.django_db


def rich_metadata() -> AIGatewayMetadata:
    return AIGatewayMetadata(
        request_id="safe-request-123",
        model="safe-model",
        duration_ms=125.5,
        retries_used=2,
        token_usage=AIGatewayTokenUsage(
            input_tokens=100,
            output_tokens=25,
            total_tokens=125,
        ),
        estimated_cost_usd=Decimal("0.001234567"),
    )


def test_usage_service_persists_only_bounded_success_metadata():
    user, organization, _, requirements = make_vacancy_workspace()
    event = start_ai_usage_event(
        organization=organization,
        actor=user,
        workflow=AIUsageEvent.Workflow.VACANCY_REQUIREMENTS,
        target_type=AIUsageEvent.ObjectType.VACANCY_REQUIREMENTS,
        target_id=requirements.pk,
    )

    completed = complete_ai_usage_success(
        event=event,
        metadata=rich_metadata(),
        result_type=AIUsageEvent.ObjectType.VACANCY_REQUIREMENTS,
        result_id=requirements.pk,
    )

    assert completed.status == AIUsageEvent.Status.SUCCEEDED
    assert completed.provider_request_id == "safe-request-123"
    assert completed.model == "safe-model"
    assert completed.duration_ms == Decimal("125.500")
    assert completed.retries_used == 2
    assert completed.input_tokens == 100
    assert completed.output_tokens == 25
    assert completed.total_tokens == 125
    assert completed.estimated_cost_usd == Decimal("0.001234567")
    assert completed.completed_at is not None
    field_names = {field.name for field in AIUsageEvent._meta.fields}
    assert not field_names.intersection(
        {
            "prompt",
            "response",
            "raw_response",
            "source_text",
            "candidate_name",
            "email",
            "phone",
            "error_message",
            "exception",
        }
    )


def test_all_three_ai_workflows_record_success_and_result_references():
    vacancy_user, vacancy_org, _, requirements = make_vacancy_workspace(
        username="vacancy"
    )
    vacancy_result = extract_vacancy_requirements(
        requirements=requirements,
        user=vacancy_user,
        gateway=VacancyGateway(),
    )

    profile_user, profile_org, _, document = make_candidate_workspace(
        username="profile"
    )
    profile_result = extract_candidate_profile(
        document=document,
        user=profile_user,
        gateway=CandidateGateway(),
    )

    assessment_user, assessment_org, _, _, profile, _, _, entry = (
        make_assessment_workspace(username="assessment")
    )
    context = build_assessment_context(entry=entry, profile=profile)
    assessment_result = assess_shortlist_entry(
        entry=entry,
        user=assessment_user,
        gateway=AssessmentGateway(output_for_context(context)),
    )

    vacancy_event = AIUsageEvent.objects.get(organization=vacancy_org)
    profile_event = AIUsageEvent.objects.get(organization=profile_org)
    assessment_event = AIUsageEvent.objects.get(organization=assessment_org)
    assert (
        vacancy_event.workflow,
        vacancy_event.target_type,
        vacancy_event.target_id,
        vacancy_event.result_type,
        vacancy_event.result_id,
    ) == (
        AIUsageEvent.Workflow.VACANCY_REQUIREMENTS,
        AIUsageEvent.ObjectType.VACANCY_REQUIREMENTS,
        requirements.pk,
        AIUsageEvent.ObjectType.VACANCY_REQUIREMENTS,
        vacancy_result.requirements.pk,
    )
    assert (
        profile_event.workflow,
        profile_event.target_type,
        profile_event.target_id,
        profile_event.result_type,
        profile_event.result_id,
    ) == (
        AIUsageEvent.Workflow.CANDIDATE_PROFILE,
        AIUsageEvent.ObjectType.CANDIDATE_DOCUMENT,
        document.pk,
        AIUsageEvent.ObjectType.CANDIDATE_PROFILE,
        profile_result.profile.pk,
    )
    assert (
        assessment_event.workflow,
        assessment_event.target_type,
        assessment_event.target_id,
        assessment_event.result_type,
        assessment_event.result_id,
    ) == (
        AIUsageEvent.Workflow.MATCH_ASSESSMENT,
        AIUsageEvent.ObjectType.SHORTLIST_ENTRY,
        entry.pk,
        AIUsageEvent.ObjectType.MATCH_ASSESSMENT,
        assessment_result.assessment.pk,
    )
    assert {vacancy_event.status, profile_event.status, assessment_event.status} == {
        AIUsageEvent.Status.SUCCEEDED
    }


def test_gateway_failure_records_allowlisted_code_without_private_detail():
    user, organization, _, requirements = make_vacancy_workspace()
    private_detail = "private provider payload"
    error = AIGatewayUnavailableError()
    error.private_detail = private_detail

    with pytest.raises(AIGatewayUnavailableError):
        extract_vacancy_requirements(
            requirements=requirements,
            user=user,
            gateway=VacancyGateway(error=error),
        )

    event = AIUsageEvent.objects.get(organization=organization)
    assert event.status == AIUsageEvent.Status.FAILED
    assert event.failure_stage == AIUsageEvent.FailureStage.GATEWAY
    assert event.failure_code == "ai_service_unavailable"
    assert event.provider_request_id == ""
    assert event.model == ""
    assert private_detail not in repr(event.__dict__)
    requirements.refresh_from_db()
    assert requirements.creation_method == VacancyRequirements.CreationMethod.MANUAL


def test_rejected_completed_output_records_application_failure_with_metadata():
    user, organization, _, _, profile, _, _, entry = make_assessment_workspace()
    context = build_assessment_context(entry=entry, profile=profile)
    unsafe = output_for_context(context).model_copy(
        update={"review_recommendation": "We recommend hiring the candidate."}
    )

    with pytest.raises(ValidationError, match="recruitment decision"):
        assess_shortlist_entry(
            entry=entry,
            user=user,
            gateway=AssessmentGateway(unsafe),
        )

    event = AIUsageEvent.objects.get(organization=organization)
    assert event.status == AIUsageEvent.Status.FAILED
    assert event.failure_stage == AIUsageEvent.FailureStage.APPLICATION
    assert event.failure_code == "ai_application_validation"
    assert event.provider_request_id == "assessment-request-123"
    assert event.model == "test-model"
    assert event.result_id is None
    assert not MatchAssessment.objects.exists()


def test_precondition_failure_before_request_creates_no_usage_event():
    user, _, _, requirements = make_vacancy_workspace()
    requirements.status = VacancyRequirements.Status.CONFIRMED
    requirements.confirmed_by = user
    requirements.confirmed_at = timezone.now()
    requirements.save()
    gateway = VacancyGateway()

    with pytest.raises(ValidationError, match="only for an editable"):
        extract_vacancy_requirements(
            requirements=requirements,
            user=user,
            gateway=gateway,
        )

    assert gateway.calls == []
    assert not AIUsageEvent.objects.exists()


def test_usage_events_are_tenant_scoped_and_completed_records_are_immutable():
    owner, organization, _, requirements = make_vacancy_workspace(username="owner")
    outsider, other, *_ = make_vacancy_workspace(username="outsider")
    event = start_ai_usage_event(
        organization=organization,
        actor=owner,
        workflow=AIUsageEvent.Workflow.VACANCY_REQUIREMENTS,
        target_type=AIUsageEvent.ObjectType.VACANCY_REQUIREMENTS,
        target_id=requirements.pk,
    )
    event = complete_ai_usage_failure(
        event=event,
        error=AIGatewayUnavailableError(),
    )

    assert list(AIUsageEvent.objects.visible_to(owner)) == [event]
    assert not AIUsageEvent.objects.visible_to(outsider).exists()
    with pytest.raises(PermissionDenied):
        start_ai_usage_event(
            organization=organization,
            actor=outsider,
            workflow=AIUsageEvent.Workflow.VACANCY_REQUIREMENTS,
            target_type=AIUsageEvent.ObjectType.VACANCY_REQUIREMENTS,
            target_id=requirements.pk,
        )
    assert other != organization

    event.failure_code = "ai_request_failed"
    with pytest.raises(ValidationError, match="immutable"):
        event.save()


def test_database_rejects_inconsistent_completed_failure():
    user, organization, _, requirements = make_vacancy_workspace()
    event = AIUsageEvent.objects.create(
        organization=organization,
        actor=user,
        workflow=AIUsageEvent.Workflow.VACANCY_REQUIREMENTS,
        target_type=AIUsageEvent.ObjectType.VACANCY_REQUIREMENTS,
        target_id=requirements.pk,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        AIUsageEvent.objects.filter(pk=event.pk).update(
            status=AIUsageEvent.Status.FAILED,
            completed_at=timezone.now(),
        )


def test_actor_deletion_preserves_nonidentifying_usage_history():
    user, organization, _, requirements = make_vacancy_workspace()
    extract_vacancy_requirements(
        requirements=requirements,
        user=user,
        gateway=VacancyGateway(),
    )

    user.delete()

    event = AIUsageEvent.objects.get(organization=organization)
    assert event.actor is None
    assert event.target_id == requirements.pk
    assert event.status == AIUsageEvent.Status.SUCCEEDED
