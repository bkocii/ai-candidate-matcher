import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from ai_gateway.testing import FakeAIGateway
from candidates.models import CandidateSource
from candidates.services import delete_candidate, request_candidate_deletion
from matching.decisions import record_review_decision
from matching.models import ReviewDecision
from outreach.generation import generate_outreach_draft
from outreach.models import (
    OutreachDraft,
    OutreachDraftAction,
    OutreachDraftApproval,
)
from outreach.workflow import (
    approve_outreach_draft,
    assess_contact_permission,
    assess_final_approval_eligibility,
    assess_manual_action_eligibility,
    edit_outreach_draft,
    record_outreach_draft_action,
)
from tests.test_match_ai_assessment import make_workspace
from tests.test_outreach_drafts import approved_workspace, draft_output

pytestmark = pytest.mark.django_db


def add_permitted_source(*, candidate, user):
    return CandidateSource.objects.create(
        candidate=candidate,
        source_type=CandidateSource.SourceType.MANUAL_ENTRY,
        source_name="Synthetic permitted source",
        lawful_basis=CandidateSource.LawfulBasis.LEGITIMATE_INTERESTS,
        consent_status=CandidateSource.ConsentStatus.NOT_REQUIRED,
        contact_permission=CandidateSource.ContactPermission.PERMITTED,
        permission_notes="Synthetic workflow test only.",
        recorded_by=user,
    )


def workflow_workspace(*, username="recruiter", permitted=True):
    values = approved_workspace(username=username)
    user, _, candidate, _, _, _, _, _, _, decision = values
    if permitted:
        add_permitted_source(candidate=candidate, user=user)
    draft = generate_outreach_draft(
        decision=decision,
        user=user,
        gateway=FakeAIGateway(response=draft_output()),
    ).draft
    return (*values, draft)


def edit_url(organization, draft):
    return reverse(
        "outreach:outreach-draft-edit",
        args=[organization.slug, draft.pk],
    )


def approval_url(organization, draft):
    return reverse(
        "outreach:outreach-draft-approve",
        args=[organization.slug, draft.pk],
    )


def copy_url(organization, draft):
    return reverse(
        "outreach:outreach-draft-copy",
        args=[organization.slug, draft.pk],
    )


def export_url(organization, draft):
    return reverse(
        "outreach:outreach-draft-export",
        args=[organization.slug, draft.pk],
    )


def detail_url(organization, draft):
    return reverse(
        "outreach:outreach-draft-detail",
        args=[organization.slug, draft.pk],
    )


def test_recruiter_edit_appends_version_without_mutating_or_carrying_approval():
    user, _, _, _, _, _, _, _, _, _, draft = workflow_workspace()
    approval = approve_outreach_draft(
        draft=draft,
        user=user,
        notes="I verified this exact generated version.",
        contact_permission_confirmed=True,
    )

    edited = edit_outreach_draft(
        draft=draft,
        user=user,
        subject="Edited subject",
        body="Hello Private Candidate,\n\nThis is recruiter-verified text.",
    )

    draft.refresh_from_db()
    assert draft.subject != edited.subject
    assert edited.version == 2
    assert edited.parent_draft == draft
    assert edited.creation_method == OutreachDraft.CreationMethod.RECRUITER_EDITED
    assert edited.created_by == user
    assert edited.created_at is not None
    assert approval.draft == draft
    assert not OutreachDraftApproval.objects.filter(draft=edited).exists()
    with pytest.raises(ValidationError, match="latest outreach draft"):
        edit_outreach_draft(
            draft=draft,
            user=user,
            subject="Old edit",
            body="Must not save",
        )


def test_final_approval_is_exact_actor_attributed_and_immutable():
    user, _, _, _, _, _, _, _, _, _, draft = workflow_workspace()

    approval = approve_outreach_draft(
        draft=draft,
        user=user,
        notes="Contact permission and exact wording checked.",
        contact_permission_confirmed=True,
    )

    assert approval.draft == draft
    assert approval.approved_by == user
    assert approval.approved_at is not None
    assert approval.contact_permission_confirmed is True
    approval.notes = "Changed"
    with pytest.raises(ValidationError, match="immutable"):
        approval.save()
    with pytest.raises(ValidationError, match="already has final approval"):
        approve_outreach_draft(
            draft=draft,
            user=user,
            notes="Duplicate",
            contact_permission_confirmed=True,
        )


@pytest.mark.parametrize(
    ("contact_permission", "consent_status", "expected"),
    [
        (
            CandidateSource.ContactPermission.UNKNOWN,
            CandidateSource.ConsentStatus.NOT_REQUIRED,
            "explicitly permit contact",
        ),
        (
            CandidateSource.ContactPermission.RESTRICTED,
            CandidateSource.ConsentStatus.NOT_REQUIRED,
            "restricted",
        ),
        (
            CandidateSource.ContactPermission.WITHDRAWN,
            CandidateSource.ConsentStatus.NOT_REQUIRED,
            "withdrawn",
        ),
        (
            CandidateSource.ContactPermission.PERMITTED,
            CandidateSource.ConsentStatus.WITHDRAWN,
            "consent is recorded as withdrawn",
        ),
    ],
)
def test_final_approval_requires_safe_recorded_contact_permission(
    contact_permission,
    consent_status,
    expected,
):
    user, _, candidate, _, _, _, _, _, _, _, draft = workflow_workspace(permitted=False)
    CandidateSource.objects.create(
        candidate=candidate,
        source_type=CandidateSource.SourceType.MANUAL_ENTRY,
        source_name="Synthetic blocked source",
        lawful_basis=CandidateSource.LawfulBasis.NOT_RECORDED,
        consent_status=consent_status,
        contact_permission=contact_permission,
        recorded_by=user,
    )

    eligibility = assess_final_approval_eligibility(draft=draft, user=user)

    assert eligibility.can_proceed is False
    assert expected in eligibility.reason
    with pytest.raises(ValidationError, match=expected):
        approve_outreach_draft(
            draft=draft,
            user=user,
            notes="Should not approve.",
            contact_permission_confirmed=True,
        )


def test_approval_requires_recruiter_attestation_and_notes():
    user, _, _, _, _, _, _, _, _, _, draft = workflow_workspace()

    with pytest.raises(ValidationError, match="final approval notes"):
        approve_outreach_draft(
            draft=draft,
            user=user,
            notes="   ",
            contact_permission_confirmed=True,
        )
    with pytest.raises(ValidationError, match="Confirm contact permission"):
        approve_outreach_draft(
            draft=draft,
            user=user,
            notes="Checked",
            contact_permission_confirmed=False,
        )
    assert not OutreachDraftApproval.objects.exists()


def test_copy_and_export_actions_require_exact_current_final_approval():
    user, _, _, _, _, _, _, _, _, _, draft = workflow_workspace()
    with pytest.raises(ValidationError, match="Approve this exact draft"):
        record_outreach_draft_action(
            draft=draft,
            user=user,
            action_type=OutreachDraftAction.ActionType.COPY,
        )
    approve_outreach_draft(
        draft=draft,
        user=user,
        notes="Exact text checked.",
        contact_permission_confirmed=True,
    )

    copied = record_outreach_draft_action(
        draft=draft,
        user=user,
        action_type=OutreachDraftAction.ActionType.COPY,
    )
    exported = record_outreach_draft_action(
        draft=draft,
        user=user,
        action_type=OutreachDraftAction.ActionType.EXPORT,
    )

    assert [copied.action_type, exported.action_type] == ["copy", "export"]
    assert copied.actor == user
    assert copied.created_at is not None
    copied.action_type = OutreachDraftAction.ActionType.EXPORT
    with pytest.raises(ValidationError, match="immutable"):
        copied.save()
    with pytest.raises(ValidationError, match="supported outreach draft action"):
        record_outreach_draft_action(
            draft=draft,
            user=user,
            action_type="send",
        )


def test_new_version_or_changed_source_boundary_blocks_prior_approved_actions():
    user, _, candidate, _, _, _, _, _, assessment, _, draft = workflow_workspace()
    approve_outreach_draft(
        draft=draft,
        user=user,
        notes="Exact text checked.",
        contact_permission_confirmed=True,
    )
    edited = edit_outreach_draft(
        draft=draft,
        user=user,
        subject="New latest version",
        body="New exact body requiring approval.",
    )

    old_eligibility = assess_manual_action_eligibility(draft=draft, user=user)
    new_eligibility = assess_manual_action_eligibility(draft=edited, user=user)
    assert old_eligibility.can_proceed is False
    assert "latest outreach draft" in old_eligibility.reason
    assert new_eligibility.can_proceed is False
    assert "Approve this exact draft" in new_eligibility.reason

    approve_outreach_draft(
        draft=edited,
        user=user,
        notes="New exact text checked.",
        contact_permission_confirmed=True,
    )
    record_review_decision(
        assessment=assessment,
        user=user,
        decision=ReviewDecision.Decision.REVISIT,
        notes="The candidate decision changed before manual outreach use.",
    )
    corrected = assess_manual_action_eligibility(draft=edited, user=user)
    assert corrected.can_proceed is False
    assert "latest recruiter decision" in corrected.reason

    candidate.sources.update(
        contact_permission=CandidateSource.ContactPermission.WITHDRAWN
    )
    permission = assess_contact_permission(candidate=candidate)
    assert permission.can_proceed is False
    assert "withdrawn" in permission.reason


def test_recruiter_edit_approve_copy_and_export_routes(client):
    user, organization, candidate, _, _, _, _, _, _, _, draft = workflow_workspace()
    client.force_login(user)

    edit_get = client.get(edit_url(organization, draft))
    edit_post = client.post(
        edit_url(organization, draft),
        {
            "subject": "Recruiter-edited role conversation",
            "body": (
                f"Hello {candidate.full_name},\n\nWould you be open to a conversation?"
            ),
        },
        follow=True,
    )
    edited = OutreachDraft.objects.get(version=2)
    approve_get = client.get(approval_url(organization, edited))
    approve_post = client.post(
        approval_url(organization, edited),
        {
            "notes": "I checked the exact text and contact permission.",
            "contact_permission_confirmed": "on",
        },
        follow=True,
    )
    copy_get = client.get(copy_url(organization, edited))
    copy_post = client.post(copy_url(organization, edited))
    export_get = client.get(export_url(organization, edited))
    export_post = client.post(export_url(organization, edited))

    assert edit_get.status_code == 200
    assert "Saving does not overwrite this version" in edit_get.content.decode()
    assert edit_post.status_code == 200
    assert "draft version 2 was saved for final review" in edit_post.content.decode()
    assert approve_get.status_code == 405
    assert approve_post.status_code == 200
    assert "received final approval. Nothing was sent" in approve_post.content.decode()
    assert "Copy approved draft" in approve_post.content.decode()
    assert copy_get.status_code == 405
    assert copy_post.status_code == 200
    assert copy_post.json() == {
        "recorded": True,
        "copy_text": (
            "Subject: Recruiter-edited role conversation\n\n"
            f"Hello {candidate.full_name},\n\nWould you be open to a conversation?"
        ),
    }
    assert copy_post["Cache-Control"] == "private, no-store"
    assert export_get.status_code == 405
    assert export_post.status_code == 200
    assert export_post["Content-Type"].startswith("text/plain")
    assert export_post["Cache-Control"] == "private, no-store"
    assert candidate.full_name not in export_post["Content-Disposition"]
    assert "outreach-draft-" in export_post["Content-Disposition"]
    exported_text = export_post.content.decode()
    assert "Subject: Recruiter-edited role conversation" in exported_text
    assert f"Hello {candidate.full_name}" in exported_text
    assert list(
        OutreachDraftAction.objects.order_by("created_at").values_list(
            "action_type", flat=True
        )
    ) == ["copy", "export"]
    assert detail_url(organization, edited) in approve_post.redirect_chain[-1][0]


def test_copy_endpoint_returns_no_text_after_permission_is_withdrawn(client):
    user, organization, candidate, _, _, _, _, _, _, _, draft = workflow_workspace()
    approve_outreach_draft(
        draft=draft,
        user=user,
        notes="Exact text and permission checked.",
        contact_permission_confirmed=True,
    )
    candidate.sources.update(
        contact_permission=CandidateSource.ContactPermission.WITHDRAWN
    )
    client.force_login(user)

    response = client.post(copy_url(organization, draft))

    assert response.status_code == 400
    assert "withdrawn" in response.json()["error"]
    assert "copy_text" not in response.json()
    assert response["Cache-Control"] == "private, no-store"
    assert not OutreachDraftAction.objects.exists()


def test_cross_organization_workflow_routes_and_services_are_hidden(client):
    owner, organization, _, _, _, _, _, _, _, _, draft = workflow_workspace(
        username="owner"
    )
    outsider, other, *_ = make_workspace(username="outsider")
    client.force_login(outsider)

    assert client.get(edit_url(organization, draft)).status_code == 404
    assert client.post(approval_url(organization, draft)).status_code == 404
    assert client.post(copy_url(other, draft)).status_code == 404
    assert client.post(export_url(organization, draft)).status_code == 404
    with pytest.raises(PermissionDenied):
        edit_outreach_draft(
            draft=draft,
            user=outsider,
            subject="Hidden",
            body="Hidden",
        )
    assert owner != outsider
    assert OutreachDraft.objects.count() == 1
    assert not OutreachDraftApproval.objects.exists()
    assert not OutreachDraftAction.objects.exists()


def test_candidate_deletion_removes_approval_and_manual_action_history(
    settings,
    tmp_path,
):
    settings.MEDIA_ROOT = tmp_path
    user, _, candidate, _, _, _, _, _, _, _, draft = workflow_workspace()
    approve_outreach_draft(
        draft=draft,
        user=user,
        notes="Synthetic deletion test approval.",
        contact_permission_confirmed=True,
    )
    record_outreach_draft_action(
        draft=draft,
        user=user,
        action_type=OutreachDraftAction.ActionType.EXPORT,
    )

    request_candidate_deletion(candidate=candidate, user=user)
    delete_candidate(candidate=candidate, user=user)

    assert not OutreachDraft.objects.exists()
    assert not OutreachDraftApproval.objects.exists()
    assert not OutreachDraftAction.objects.exists()
