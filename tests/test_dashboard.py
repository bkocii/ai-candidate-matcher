import re

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.urls import reverse

from accounts.models import OrganizationMembership, User
from candidates.models import Candidate
from config.middleware import AuthenticatedHTMLNoStoreMiddleware
from organizations.models import ClientCompany, Organization

pytestmark = pytest.mark.django_db


def add_membership(
    user: User,
    organization: Organization,
    *,
    role: str = OrganizationMembership.Role.RECRUITER,
    is_active: bool = True,
) -> OrganizationMembership:
    return OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=role,
        is_active=is_active,
    )


def test_dashboard_requires_authentication(client) -> None:
    response = client.get(reverse("organizations:dashboard"))

    assert response.status_code == 302
    assert response.url == f"{reverse('accounts:login')}?next=/"


def test_single_visible_organization_redirects_to_its_dashboard(client) -> None:
    user = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_membership(user, organization)
    client.force_login(user)

    response = client.get(reverse("organizations:dashboard"))

    assert response.status_code == 302
    assert response.url == reverse(
        "organizations:organization-dashboard",
        kwargs={"organization_slug": organization.slug},
    )


def test_multiple_visible_organizations_show_a_selection_page(client) -> None:
    user = User.objects.create_user(username="multi-organization-recruiter")
    first = Organization.objects.create(name="First Agency", slug="first-agency")
    second = Organization.objects.create(name="Second Agency", slug="second-agency")
    hidden = Organization.objects.create(name="Hidden Agency", slug="hidden-agency")
    add_membership(user, first)
    add_membership(user, second)
    add_membership(user, hidden, is_active=False)
    client.force_login(user)

    response = client.get(reverse("organizations:dashboard"))

    assert response.status_code == 200
    assert list(response.context["organizations"]) == [first, second]
    assert "First Agency" in response.content.decode()
    assert "Second Agency" in response.content.decode()
    assert "Hidden Agency" not in response.content.decode()


def test_user_without_active_membership_gets_safe_access_page(client) -> None:
    user = User.objects.create_user(username="unassigned")
    Organization.objects.create(name="Private Agency", slug="private-agency")
    client.force_login(user)

    response = client.get(reverse("organizations:dashboard"))

    assert response.status_code == 403
    assert "No active organization membership" in response.content.decode()
    assert "Private Agency" not in response.content.decode()


def test_dashboard_is_scoped_to_the_requested_organization(client) -> None:
    user = User.objects.create_user(username="organization-admin")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    other = Organization.objects.create(name="Other Agency", slug="other-agency")
    add_membership(user, organization, role=OrganizationMembership.Role.ADMIN)
    ClientCompany.objects.create(
        organization=organization,
        name="Active Client",
        slug="active-client",
    )
    ClientCompany.objects.create(
        organization=organization,
        name="Inactive Client",
        slug="inactive-client",
        is_active=False,
    )
    ClientCompany.objects.create(
        organization=other,
        name="Other Client",
        slug="other-client",
    )
    Candidate.objects.create(
        organization=organization,
        full_name="Active Candidate",
    )
    Candidate.objects.create(
        organization=organization,
        full_name="Inactive Candidate",
        status=Candidate.Status.INACTIVE,
    )
    Candidate.objects.create(
        organization=other,
        full_name="Other Candidate",
    )
    client.force_login(user)

    response = client.get(
        reverse(
            "organizations:organization-dashboard",
            kwargs={"organization_slug": organization.slug},
        )
    )

    assert response.status_code == 200
    assert response.context["organization"] == organization
    assert response.context["active_client_count"] == 1
    assert response.context["active_candidate_count"] == 1
    assert response.context["membership"].role == OrganizationMembership.Role.ADMIN
    assert "Northstar" in response.content.decode()
    assert "Administrator" in response.content.decode()
    assert (
        reverse(
            "candidates:candidate-list",
            kwargs={"organization_slug": organization.slug},
        )
        in response.content.decode()
    )


def test_dashboard_hides_another_organizations_existence(client) -> None:
    user = User.objects.create_user(username="first-recruiter")
    first = Organization.objects.create(name="First", slug="first")
    second = Organization.objects.create(name="Second", slug="second")
    add_membership(user, first)
    client.force_login(user)

    response = client.get(
        reverse(
            "organizations:organization-dashboard",
            kwargs={"organization_slug": second.slug},
        )
    )

    assert response.status_code == 404
    assert "Second" not in response.content.decode()


def test_inactive_organization_is_not_available_from_dashboard(client) -> None:
    user = User.objects.create_user(username="inactive-organization-member")
    organization = Organization.objects.create(
        name="Inactive Agency",
        slug="inactive-agency",
        is_active=False,
    )
    add_membership(user, organization)
    client.force_login(user)

    response = client.get(
        reverse(
            "organizations:organization-dashboard",
            kwargs={"organization_slug": organization.slug},
        )
    )

    assert response.status_code == 404


def test_navigation_exposes_django_admin_only_to_staff(client) -> None:
    recruiter = User.objects.create_user(username="recruiter")
    organization = Organization.objects.create(name="Northstar", slug="northstar")
    add_membership(recruiter, organization)
    dashboard_url = reverse(
        "organizations:organization-dashboard",
        kwargs={"organization_slug": organization.slug},
    )

    client.force_login(recruiter)
    response = client.get(dashboard_url)
    assert "Django admin" not in response.content.decode()

    recruiter.is_staff = True
    recruiter.save(update_fields=["is_staff"])
    response = client.get(dashboard_url)
    assert "Django admin" in response.content.decode()


def test_logout_requires_post_and_returns_to_login(client) -> None:
    user = User.objects.create_user(username="signed-in-user")
    client.force_login(user)
    logout_url = reverse("accounts:logout")

    assert client.get(logout_url).status_code == 405

    response = client.post(logout_url)

    assert response.status_code == 302
    assert response.url == reverse("accounts:login")
    assert response["Cache-Control"] == "no-store, private, max-age=0"
    assert response["Pragma"] == "no-cache"
    assert response["Expires"] == "0"


def test_login_links_to_password_recovery(client) -> None:
    response = client.get(reverse("accounts:login"))

    assert response.status_code == 200
    assert reverse("accounts:password-reset") in response.content.decode()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_password_reset_does_not_disclose_unknown_email(client) -> None:
    response = client.post(
        reverse("accounts:password-reset"),
        {"email": "unknown@example.test"},
        follow=True,
    )

    assert response.status_code == 200
    assert "If an active account matches" in response.content.decode()
    assert mail.outbox == []


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_password_reset_link_sets_password_and_clears_first_login_gate(client) -> None:
    user = User.objects.create_user(
        username="reset-user",
        email="reset@example.test",
        password="TemporaryPass123!",
        must_change_password=True,
    )

    response = client.post(reverse("accounts:password-reset"), {"email": user.email})

    assert response.status_code == 302
    assert len(mail.outbox) == 1
    reset_path = re.search(
        r"https?://[^/]+(/accounts/password/reset/[^\s]+)", mail.outbox[0].body
    )
    assert reset_path is not None

    response = client.get(reset_path.group(1))
    assert response.status_code == 302
    response = client.post(
        response.url,
        {
            "new_password1": "NewPrivatePass456!",
            "new_password2": "NewPrivatePass456!",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("accounts:password-reset-complete")
    user.refresh_from_db()
    assert user.must_change_password is False
    assert client.login(username=user.username, password="NewPrivatePass456!") is True


def test_authenticated_html_responses_cannot_be_restored_from_cache(client) -> None:
    user = User.objects.create_user(username="private-page-user")
    organization = Organization.objects.create(name="Private", slug="private")
    add_membership(user, organization)
    client.force_login(user)

    response = client.get(
        reverse(
            "organizations:organization-dashboard",
            kwargs={"organization_slug": organization.slug},
        )
    )

    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store, private, max-age=0"
    assert response["Pragma"] == "no-cache"
    assert response["Expires"] == "0"


def test_anonymous_html_response_keeps_its_existing_cache_policy() -> None:
    request = RequestFactory().get("/public/")
    request.user = AnonymousUser()
    middleware = AuthenticatedHTMLNoStoreMiddleware(
        lambda request: HttpResponse(
            "Public",
            headers={"Cache-Control": "public, max-age=300"},
        )
    )

    response = middleware(request)

    assert response["Cache-Control"] == "public, max-age=300"
    assert "Pragma" not in response
    assert "Expires" not in response


def test_authenticated_non_html_response_keeps_its_existing_cache_policy() -> None:
    request = RequestFactory().get("/static/css/app.css")
    request.user = type("AuthenticatedUser", (), {"is_authenticated": True})()
    middleware = AuthenticatedHTMLNoStoreMiddleware(
        lambda request: HttpResponse(
            "body { color: inherit; }",
            content_type="text/css",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    )

    response = middleware(request)

    assert response["Cache-Control"] == "public, max-age=3600"
    assert "Pragma" not in response
    assert "Expires" not in response
