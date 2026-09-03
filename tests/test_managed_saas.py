import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from accounts.models import OrganizationMembership, User
from audit.lifecycle import (
    cancel_organization_deletion,
    request_organization_deletion,
)
from audit.models import DataLifecycleEvent, TenantManagementEvent
from candidates.models import Candidate
from organizations.models import Organization
from organizations.permissions import (
    has_organization_access,
    is_platform_owner,
    require_platform_owner,
)
from organizations.services import (
    add_organization_member,
    provision_organization,
    set_organization_membership_active,
)

pytestmark = pytest.mark.django_db

TEMPORARY_PASSWORD = "Managed-Temp-9384!"


def managed_values(username: str, *, password: str = TEMPORARY_PASSWORD) -> dict:
    return {
        "username": username,
        "email": f"{username}@example.test",
        "first_name": "Managed",
        "last_name": "User",
        "temporary_password": password,
    }


def make_platform_owner(username: str = "platform-owner") -> User:
    return User.objects.create_user(username=username, is_platform_owner=True)


def make_organization_admin(
    username: str = "organization-admin",
) -> tuple[User, Organization, OrganizationMembership]:
    user = User.objects.create_user(username=username)
    organization = Organization.objects.create(
        name=f"{username} Workspace",
        slug=f"{username}-workspace",
    )
    membership = OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.ADMIN,
    )
    return user, organization, membership


def test_platform_owner_is_explicit_and_not_a_tenant_bypass() -> None:
    owner = make_platform_owner()
    technical_operator = User.objects.create_superuser(
        username="technical-operator",
        password=TEMPORARY_PASSWORD,
    )
    organization = Organization.objects.create(name="Private", slug="private")

    assert is_platform_owner(owner) is True
    assert owner.is_staff is False
    assert owner.is_superuser is False
    assert is_platform_owner(technical_operator) is False
    assert has_organization_access(owner, organization) is False
    assert not Organization.objects.visible_to(owner).exists()
    require_platform_owner(owner)
    with pytest.raises(PermissionDenied):
        require_platform_owner(technical_operator)


def test_platform_owner_provisions_organization_first_admin_and_audit() -> None:
    owner = make_platform_owner()

    organization, membership, created_user = provision_organization(
        platform_owner=owner,
        organization_name="Northstar Recruitment",
        administrator_values=managed_values("northstar-admin"),
    )

    assert created_user is True
    assert organization.slug == "northstar-recruitment"
    assert membership.role == OrganizationMembership.Role.ADMIN
    assert membership.is_active is True
    assert membership.user.check_password(TEMPORARY_PASSWORD)
    assert has_organization_access(owner, organization) is False
    events = list(
        TenantManagementEvent.objects.filter(
            organization_id_snapshot=organization.pk
        ).order_by("id")
    )
    assert [event.action for event in events] == [
        TenantManagementEvent.Action.ORGANIZATION_CREATED,
        TenantManagementEvent.Action.MEMBERSHIP_CREATED,
    ]
    assert events[0].subject_user_id_snapshot is None
    assert events[1].subject_user_id_snapshot == membership.user_id
    assert events[1].membership_role == OrganizationMembership.Role.ADMIN


def test_provisioning_can_link_existing_user_without_changing_password() -> None:
    owner = make_platform_owner()
    existing = User.objects.create_user(
        username="existing-admin",
        password="Existing-Password-4821!",
    )
    values = managed_values("existing-admin", password="")

    _, membership, created_user = provision_organization(
        platform_owner=owner,
        organization_name="Existing User Agency",
        administrator_values=values,
    )

    existing.refresh_from_db()
    assert created_user is False
    assert membership.user == existing
    assert existing.check_password("Existing-Password-4821!")


def test_non_platform_user_cannot_provision_an_organization() -> None:
    user = User.objects.create_user(username="ordinary-user")

    with pytest.raises(PermissionDenied):
        provision_organization(
            platform_owner=user,
            organization_name="Blocked",
            administrator_values=managed_values("blocked-admin"),
        )

    assert not Organization.objects.exists()


def test_platform_create_route_and_content_boundary(client) -> None:
    owner = make_platform_owner()
    client.force_login(owner)

    landing = client.get(reverse("organizations:dashboard"))
    assert landing.status_code == 302
    assert landing.url == reverse("organizations:platform-organization-list")

    response = client.post(
        reverse("organizations:platform-organization-create"),
        {
            "organization_name": "Managed Agency",
            "username": "managed-admin",
            "email": "managed-admin@example.test",
            "first_name": "Managed",
            "last_name": "Admin",
            "temporary_password": TEMPORARY_PASSWORD,
            "temporary_password_confirmation": TEMPORARY_PASSWORD,
        },
    )

    organization = Organization.objects.get(slug="managed-agency")
    assert response.status_code == 302
    assert response.url == reverse(
        "organizations:platform-organization-detail", args=[organization.pk]
    )
    candidate = Candidate.objects.create(
        organization=organization,
        full_name="Private Candidate Name",
    )
    detail = client.get(response.url)
    assert "Private Candidate Name" not in detail.content.decode()
    assert (
        client.get(
            reverse(
                "candidates:candidate-detail",
                args=[organization.slug, candidate.pk],
            )
        ).status_code
        == 404
    )


def test_platform_organization_list_surfaces_health_counts_and_filters(client) -> None:
    owner = make_platform_owner()
    _, healthy, _ = make_organization_admin("healthy-admin")
    recruiter = User.objects.create_user(username="healthy-recruiter")
    OrganizationMembership.objects.create(
        user=recruiter,
        organization=healthy,
        role=OrganizationMembership.Role.RECRUITER,
    )
    removed = User.objects.create_user(username="removed-member")
    OrganizationMembership.objects.create(
        user=removed,
        organization=healthy,
        role=OrganizationMembership.Role.RECRUITER,
        is_active=False,
    )
    orphaned = Organization.objects.create(name="Orphaned Agency", slug="orphaned")
    suspended = Organization.objects.create(
        name="Suspended Agency", slug="suspended", is_active=False
    )
    client.force_login(owner)

    response = client.get(reverse("organizations:platform-organization-list"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Needs administrator" in content
    assert "Active members" in content
    assert "Total memberships" in content
    assert response.context["organization_summary"] == {
        "active": 2,
        "suspended": 1,
        "needs_administrator": 1,
    }
    healthy_item = next(
        item for item in response.context["managed_organizations"] if item == healthy
    )
    assert healthy_item.administrator_count == 1
    assert healthy_item.active_membership_count == 2
    assert healthy_item.total_membership_count == 3
    filtered = client.get(
        reverse("organizations:platform-organization-list"),
        {"q": "orphan", "status": "needs_administrator"},
    )
    filtered_content = filtered.content.decode()
    assert orphaned.name in filtered_content
    assert healthy.name not in filtered_content
    assert suspended.name not in filtered_content
    assert "Add administrator" in filtered_content


def test_platform_organization_list_paginates_and_preserves_filters(client) -> None:
    owner = make_platform_owner()
    Organization.objects.bulk_create(
        [
            Organization(name=f"Agency {number:02d}", slug=f"agency-{number:02d}")
            for number in range(26)
        ]
    )
    client.force_login(owner)

    response = client.get(
        reverse("organizations:platform-organization-list"),
        {"q": "Agency", "status": "needs_administrator"},
    )
    content = response.content.decode()

    assert response.context["managed_organizations"].paginator.per_page == 25
    assert "Page 1 of 2" in content
    assert "q=Agency&amp;status=needs_administrator&amp;page=2" in content


@pytest.mark.parametrize("username", ["ordinary", "technical-superuser"])
def test_platform_routes_reject_non_platform_accounts(client, username: str) -> None:
    if username == "technical-superuser":
        user = User.objects.create_superuser(
            username=username,
            password=TEMPORARY_PASSWORD,
        )
    else:
        user = User.objects.create_user(username=username)
    client.force_login(user)

    assert (
        client.get(reverse("organizations:platform-organization-list")).status_code
        == 403
    )


def test_organization_admin_creates_and_scopes_recruiter_access() -> None:
    admin, organization, _ = make_organization_admin()

    membership, created_user = add_organization_member(
        organization=organization,
        actor=admin,
        role=OrganizationMembership.Role.RECRUITER,
        values=managed_values("new-recruiter"),
    )

    assert created_user is True
    assert membership.user.check_password(TEMPORARY_PASSWORD)
    assert has_organization_access(membership.user, organization) is True
    event = TenantManagementEvent.objects.get(
        action=TenantManagementEvent.Action.MEMBERSHIP_CREATED
    )
    assert event.actor == admin
    assert event.membership_role == OrganizationMembership.Role.RECRUITER


def test_existing_user_can_join_second_workspace_without_account_change() -> None:
    first_admin, first, _ = make_organization_admin("first-admin")
    second_admin, second, _ = make_organization_admin("second-admin")
    recruiter = User.objects.create_user(
        username="multi-workspace",
        password="Existing-Password-5732!",
    )
    add_organization_member(
        organization=first,
        actor=first_admin,
        role=OrganizationMembership.Role.RECRUITER,
        values=managed_values("multi-workspace", password=""),
    )

    membership, created_user = add_organization_member(
        organization=second,
        actor=second_admin,
        role=OrganizationMembership.Role.RECRUITER,
        values=managed_values("multi-workspace", password=""),
    )

    recruiter.refresh_from_db()
    assert created_user is False
    assert membership.user == recruiter
    assert recruiter.check_password("Existing-Password-5732!")
    assert Organization.objects.visible_to(recruiter).count() == 2


def test_recruiter_cannot_manage_team_and_admin_cannot_create_admin() -> None:
    admin, organization, _ = make_organization_admin()
    recruiter = User.objects.create_user(username="recruiter")
    OrganizationMembership.objects.create(
        user=recruiter,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )

    with pytest.raises(PermissionDenied):
        add_organization_member(
            organization=organization,
            actor=recruiter,
            role=OrganizationMembership.Role.RECRUITER,
            values=managed_values("blocked-recruiter"),
        )
    with pytest.raises(PermissionDenied):
        add_organization_member(
            organization=organization,
            actor=admin,
            role=OrganizationMembership.Role.ADMIN,
            values=managed_values("blocked-admin"),
        )


def test_deactivating_membership_removes_only_that_workspace_access() -> None:
    first_admin, first, _ = make_organization_admin("first-admin")
    second_admin, second, _ = make_organization_admin("second-admin")
    recruiter = User.objects.create_user(username="shared-recruiter")
    first_membership = OrganizationMembership.objects.create(
        user=recruiter,
        organization=first,
        role=OrganizationMembership.Role.RECRUITER,
    )
    OrganizationMembership.objects.create(
        user=recruiter,
        organization=second,
        role=OrganizationMembership.Role.RECRUITER,
    )

    set_organization_membership_active(
        membership=first_membership,
        actor=first_admin,
        is_active=False,
    )

    recruiter.refresh_from_db()
    assert recruiter.is_active is True
    assert has_organization_access(recruiter, first) is False
    assert has_organization_access(recruiter, second) is True
    assert TenantManagementEvent.objects.filter(
        action=TenantManagementEvent.Action.MEMBERSHIP_DEACTIVATED,
        subject_user_id_snapshot=recruiter.pk,
    ).exists()


def test_platform_owner_manages_admins_but_cannot_remove_last_active_admin() -> None:
    owner = make_platform_owner()
    _, organization, first_admin_membership = make_organization_admin()

    with pytest.raises(ValidationError, match="another active administrator"):
        set_organization_membership_active(
            membership=first_admin_membership,
            actor=owner,
            is_active=False,
        )

    second_admin, _ = add_organization_member(
        organization=organization,
        actor=owner,
        role=OrganizationMembership.Role.ADMIN,
        values=managed_values("second-organization-admin"),
    )
    set_organization_membership_active(
        membership=first_admin_membership,
        actor=owner,
        is_active=False,
    )
    first_admin_membership.refresh_from_db()
    assert first_admin_membership.is_active is False
    assert second_admin.is_active is True


def test_platform_administrator_access_change_requires_identity_confirmation(
    client,
) -> None:
    owner = make_platform_owner()
    user, organization, membership = make_organization_admin("first-admin")
    second_membership, _ = add_organization_member(
        organization=organization,
        actor=owner,
        role=OrganizationMembership.Role.ADMIN,
        values=managed_values("second-admin"),
    )
    user.email = "first-admin@example.test"
    user.save(update_fields=("email",))
    client.force_login(owner)
    url = reverse(
        "organizations:platform-administrator-status",
        args=[organization.pk, membership.pk],
    )

    review = client.get(url)
    content = review.content.decode()

    assert review.status_code == 200
    assert "Remove administrator access?" in content
    assert "first-admin@example.test" in content
    assert organization.name in content
    assert "Active administrators remaining" in content
    assert ">1<" in content
    membership.refresh_from_db()
    assert membership.is_active is True

    changed = client.post(url, {"is_active": "false"})
    assert changed.status_code == 302
    membership.refresh_from_db()
    assert membership.is_active is False
    second_membership.refresh_from_db()
    assert second_membership.is_active is True


def test_platform_administrator_confirmation_blocks_last_active_admin(client) -> None:
    owner = make_platform_owner()
    _, organization, membership = make_organization_admin()
    client.force_login(owner)
    url = reverse(
        "organizations:platform-administrator-status",
        args=[organization.pk, membership.pk],
    )

    review = client.get(url)
    content = review.content.decode()

    assert review.status_code == 200
    assert "This access cannot be removed" in content
    assert "Remove administrator access</button>" not in content

    rejected = client.post(url, {"is_active": "false"})
    assert rejected.status_code == 302
    membership.refresh_from_db()
    assert membership.is_active is True


def test_platform_owner_membership_is_explained_as_separate_access(client) -> None:
    owner = make_platform_owner()
    organization = Organization.objects.create(name="Support Tenant", slug="support")
    membership = OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrganizationMembership.Role.ADMIN,
    )
    client.force_login(owner)

    detail = client.get(
        reverse("organizations:platform-organization-detail", args=[organization.pk])
    )
    assert (
        "Platform owner with separate workspace membership" in detail.content.decode()
    )

    review = client.get(
        reverse(
            "organizations:platform-administrator-status",
            args=[organization.pk, membership.pk],
        )
    )
    assert "Platform-management capability remains unchanged" in review.content.decode()


def test_team_routes_are_admin_only_and_manage_recruiters(client) -> None:
    admin, organization, _ = make_organization_admin()
    recruiter = User.objects.create_user(username="existing-recruiter")
    membership = OrganizationMembership.objects.create(
        user=recruiter,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )
    list_url = reverse("organizations:member-list", args=[organization.slug])

    client.force_login(recruiter)
    assert client.get(list_url).status_code == 403
    client.force_login(admin)
    assert client.get(list_url).status_code == 200
    response = client.post(
        reverse(
            "organizations:recruiter-status",
            args=[organization.slug, membership.pk],
        ),
        {"is_active": "false"},
    )
    assert response.status_code == 302
    membership.refresh_from_db()
    assert membership.is_active is False


def test_workspace_switch_navigation_uses_only_active_memberships(client) -> None:
    user = User.objects.create_user(username="workspace-switcher")
    first = Organization.objects.create(name="First", slug="first")
    second = Organization.objects.create(name="Second", slug="second")
    hidden = Organization.objects.create(name="Hidden", slug="hidden")
    for organization, active in ((first, True), (second, True), (hidden, False)):
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrganizationMembership.Role.RECRUITER,
            is_active=active,
        )
    client.force_login(user)

    dashboard = client.get(
        reverse("organizations:organization-dashboard", args=[first.slug])
    )
    selection = client.get(reverse("organizations:dashboard"))

    assert "Switch workspace" in dashboard.content.decode()
    assert selection.status_code == 200
    assert "First" in selection.content.decode()
    assert "Second" in selection.content.decode()
    assert "Hidden" not in selection.content.decode()


def test_managed_user_can_replace_temporary_password(client) -> None:
    user = User.objects.create_user(
        username="temporary-password-user",
        password=TEMPORARY_PASSWORD,
    )
    client.force_login(user)
    new_password = "Replacement-Password-7462!"

    response = client.post(
        reverse("accounts:password-change"),
        {
            "old_password": TEMPORARY_PASSWORD,
            "new_password1": new_password,
            "new_password2": new_password,
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("accounts:password-change-done")
    user.refresh_from_db()
    assert user.check_password(new_password)
    assert client.get(reverse("accounts:password-change-done")).status_code == 200


def test_platform_owner_can_suspend_and_recover_without_tenant_membership() -> None:
    owner = make_platform_owner()
    _, organization, _ = make_organization_admin()

    request_organization_deletion(organization=organization, user=owner)
    organization.refresh_from_db()
    assert organization.is_active is False
    assert has_organization_access(owner, organization) is False
    assert DataLifecycleEvent.objects.filter(
        organization_id_snapshot=organization.pk,
        action=DataLifecycleEvent.Action.ORGANIZATION_DELETION_REQUESTED,
        actor=owner,
    ).exists()

    cancel_organization_deletion(organization=organization, user=owner)
    organization.refresh_from_db()
    assert organization.is_active is True
    assert DataLifecycleEvent.objects.filter(
        organization_id_snapshot=organization.pk,
        action=DataLifecycleEvent.Action.ORGANIZATION_DELETION_CANCELLED,
        actor=owner,
    ).exists()


def test_tenant_management_events_are_immutable() -> None:
    owner = make_platform_owner()
    organization, _, _ = provision_organization(
        platform_owner=owner,
        organization_name="Audited",
        administrator_values=managed_values("audited-admin"),
    )
    event = TenantManagementEvent.objects.filter(
        organization_id_snapshot=organization.pk
    ).first()

    event.membership_role = OrganizationMembership.Role.RECRUITER
    with pytest.raises(ValidationError, match="immutable"):
        event.save()
    with pytest.raises(ValidationError, match="immutable"):
        TenantManagementEvent.objects.filter(pk=event.pk).delete()
