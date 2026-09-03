from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import OrganizationMembership
from audit.lifecycle import (
    DataLifecycleError,
    apply_retention_plan,
    build_retention_plan,
    cancel_organization_deletion,
    get_retention_policy,
    organizations_available_for_recovery,
    request_organization_deletion,
    update_retention_policy,
)
from candidates.models import Candidate
from organizations.forms import (
    ApplyRetentionForm,
    ClientCompanyForm,
    ExistingManagedMembershipForm,
    ManagedMembershipForm,
    NewManagedMembershipForm,
    OrganizationProvisionForm,
    OrganizationRetentionPolicyForm,
    RequestOrganizationDeletionForm,
    RetentionExceptionForm,
)
from organizations.models import ClientCompany, Organization, RetentionException
from organizations.permissions import (
    can_administer_organization,
    can_recover_organization,
    is_platform_owner,
    require_organization_admin,
    require_platform_owner,
)
from organizations.services import (
    add_organization_member,
    create_client_company,
    provision_organization,
    set_client_company_active,
    set_organization_membership_active,
    update_client_company,
)
from vacancies.models import Vacancy


@login_required
def dashboard_home(request):
    """Resolve the user's organization or offer an explicit organization choice."""
    organizations = list(Organization.objects.visible_to(request.user))

    recoverable = organizations_available_for_recovery(request.user)
    if not organizations and is_platform_owner(request.user):
        return redirect("organizations:platform-organization-list")
    if not organizations and recoverable.exists():
        return redirect("organizations:organization-recovery")
    if not organizations:
        return render(request, "organizations/no_access.html", status=403)

    if len(organizations) == 1:
        return redirect(
            "organizations:organization-dashboard",
            organization_slug=organizations[0].slug,
        )

    return render(
        request,
        "organizations/select_organization.html",
        {"organizations": organizations},
    )


@login_required
def organization_dashboard(request, organization_slug: str):
    """Show foundation data for one organization visible to the current user."""
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    membership = get_object_or_404(
        OrganizationMembership,
        user=request.user,
        organization=organization,
        is_active=True,
    )
    active_clients = ClientCompany.objects.for_organization(organization).filter(
        is_active=True
    )
    active_candidates = Candidate.objects.for_organization(organization).filter(
        status=Candidate.Status.ACTIVE
    )
    open_vacancies = (
        Vacancy.objects.for_organization(organization)
        .active()
        .filter(status=Vacancy.Status.OPEN)
    )

    return render(
        request,
        "organizations/dashboard.html",
        {
            "organization": organization,
            "membership": membership,
            "active_client_count": active_clients.count(),
            "active_candidate_count": active_candidates.count(),
            "open_vacancy_count": open_vacancies.count(),
            "can_administer": can_administer_organization(request.user, organization),
        },
    )


def _visible_organization(request, organization_slug: str) -> Organization:
    return get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )


def _safe_return_url(request) -> str:
    value = (
        request.POST.get("next")
        if request.method == "POST"
        else request.GET.get("next")
    )
    if value and url_has_allowed_host_and_scheme(
        value,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return value
    return ""


def _with_selected_company(url: str, company: ClientCompany) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["client_company"] = str(company.pk)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


@login_required
def organization_settings(request, organization_slug: str):
    organization = _visible_organization(request, organization_slug)
    require_organization_admin(request.user, organization)
    return render(
        request,
        "organizations/organization_settings.html",
        {"organization": organization},
    )


@login_required
def organization_member_list(request, organization_slug: str):
    organization = _visible_organization(request, organization_slug)
    require_organization_admin(request.user, organization)
    memberships = OrganizationMembership.objects.filter(
        organization=organization
    ).select_related("user")
    return render(
        request,
        "organizations/member_list.html",
        {"organization": organization, "memberships": memberships},
    )


@login_required
def recruiter_create(request, organization_slug: str):
    organization = _visible_organization(request, organization_slug)
    require_organization_admin(request.user, organization)
    form = ManagedMembershipForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            membership, created_user = add_organization_member(
                organization=organization,
                actor=request.user,
                role=OrganizationMembership.Role.RECRUITER,
                values=form.managed_user_values(),
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            action = "created" if created_user else "added"
            messages.success(
                request,
                f'Recruiter account "{membership.user.username}" {action}.',
            )
            return redirect("organizations:member-list", organization.slug)
    return render(
        request,
        "organizations/member_form.html",
        {
            "organization": organization,
            "form": form,
            "heading": "Add recruiter",
            "submit_label": "Add recruiter",
        },
    )


@login_required
@require_POST
def recruiter_status(request, organization_slug: str, membership_id: int):
    organization = _visible_organization(request, organization_slug)
    require_organization_admin(request.user, organization)
    membership = get_object_or_404(
        OrganizationMembership.objects.select_related("user", "organization"),
        pk=membership_id,
        organization=organization,
        role=OrganizationMembership.Role.RECRUITER,
    )
    requested_state = request.POST.get("is_active")
    if requested_state not in {"true", "false"}:
        messages.error(request, "Select a valid recruiter access state.")
    else:
        try:
            membership = set_organization_membership_active(
                membership=membership,
                actor=request.user,
                is_active=requested_state == "true",
            )
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            state = "restored" if membership.is_active else "removed"
            messages.success(
                request,
                f'Recruiter access for "{membership.user.username}" {state}.',
            )
    return redirect("organizations:member-list", organization.slug)


@login_required
def platform_organization_list(request):
    require_platform_owner(request.user)
    organizations = (
        Organization.objects.all()
        .annotate(
            active_membership_count=Count(
                "memberships",
                filter=Q(memberships__is_active=True),
                distinct=True,
            ),
            total_membership_count=Count("memberships", distinct=True),
            administrator_count=Count(
                "memberships",
                filter=(
                    Q(memberships__role=OrganizationMembership.Role.ADMIN)
                    & Q(memberships__is_active=True)
                ),
                distinct=True,
            ),
        )
        .order_by("name", "slug")
    )
    summary = {
        "active": organizations.filter(is_active=True).count(),
        "suspended": organizations.filter(is_active=False).count(),
        "needs_administrator": organizations.filter(
            is_active=True, administrator_count=0
        ).count(),
    }
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all")
    if query:
        organizations = organizations.filter(
            Q(name__icontains=query) | Q(slug__icontains=query)
        )
    if status == "active":
        organizations = organizations.filter(is_active=True)
    elif status == "suspended":
        organizations = organizations.filter(is_active=False)
    elif status == "needs_administrator":
        organizations = organizations.filter(is_active=True, administrator_count=0)
    elif status != "all":
        status = "all"

    page = Paginator(organizations, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "organizations/platform_organization_list.html",
        {
            "managed_organizations": page,
            "organization_summary": summary,
            "organization_query": query,
            "organization_status": status,
        },
    )


@login_required
def platform_organization_create(request):
    require_platform_owner(request.user)
    form = OrganizationProvisionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            organization, membership, created_user = provision_organization(
                platform_owner=request.user,
                organization_name=form.cleaned_data["organization_name"],
                administrator_values=form.managed_user_values(),
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            account_action = "created" if created_user else "linked"
            messages.success(
                request,
                f"{organization.name} created and administrator "
                f'"{membership.user.username}" {account_action}.',
            )
            return redirect(
                "organizations:platform-organization-detail", organization.pk
            )
    return render(
        request,
        "organizations/platform_organization_form.html",
        {"form": form},
    )


def _platform_organization(request, organization_id: int) -> Organization:
    require_platform_owner(request.user)
    return get_object_or_404(Organization, pk=organization_id)


@login_required
def platform_organization_detail(request, organization_id: int):
    managed_organization = _platform_organization(request, organization_id)
    administrators = OrganizationMembership.objects.filter(
        organization=managed_organization,
        role=OrganizationMembership.Role.ADMIN,
    ).select_related("user")
    return render(
        request,
        "organizations/platform_organization_detail.html",
        {
            "managed_organization": managed_organization,
            "administrators": administrators,
        },
    )


@login_required
def platform_administrator_create(request, organization_id: int):
    managed_organization = _platform_organization(request, organization_id)
    default_mode = (
        "new" if request.method == "POST" and request.POST.get("email") else "existing"
    )
    mode = request.POST.get("account_mode") or request.GET.get("mode", default_mode)
    if mode not in {"existing", "new"}:
        mode = "existing"
    form_class = (
        ExistingManagedMembershipForm
        if mode == "existing"
        else NewManagedMembershipForm
    )
    form = form_class(request.POST or None)
    matched_user = None
    if request.method == "GET" and mode == "existing" and request.GET.get("username"):
        form = form_class({"username": request.GET["username"]})
        if form.is_valid():
            matched_user = form.existing_user
    if request.method == "POST" and form.is_valid():
        try:
            membership, created_user = add_organization_member(
                organization=managed_organization,
                actor=request.user,
                role=OrganizationMembership.Role.ADMIN,
                values=form.managed_user_values(),
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            action = "created" if created_user else "granted access"
            messages.success(
                request,
                f'Administrator "{membership.user.username}" {action}.',
            )
            return redirect(
                "organizations:platform-organization-detail",
                managed_organization.pk,
            )
    return render(
        request,
        "organizations/platform_administrator_form.html",
        {
            "managed_organization": managed_organization,
            "form": form,
            "account_mode": mode,
            "matched_user": matched_user,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def platform_administrator_status(request, organization_id: int, membership_id: int):
    managed_organization = _platform_organization(request, organization_id)
    membership = get_object_or_404(
        OrganizationMembership.objects.select_related("organization", "user"),
        pk=membership_id,
        organization=managed_organization,
        role=OrganizationMembership.Role.ADMIN,
    )
    requested_state = (
        request.POST.get("is_active")
        if request.method == "POST"
        else ("false" if membership.is_active else "true")
    )
    active_administrators_remaining = (
        OrganizationMembership.objects.filter(
            organization=managed_organization,
            role=OrganizationMembership.Role.ADMIN,
            is_active=True,
        )
        .exclude(pk=membership.pk)
        .count()
    )
    if request.method == "GET":
        return render(
            request,
            "organizations/platform_administrator_status_confirm.html",
            {
                "managed_organization": managed_organization,
                "membership": membership,
                "requested_state": requested_state,
                "active_administrators_remaining": active_administrators_remaining,
                "removal_blocked": (
                    requested_state == "false" and active_administrators_remaining == 0
                ),
            },
        )
    if requested_state not in {"true", "false"}:
        messages.error(request, "Select a valid administrator access state.")
    else:
        try:
            membership = set_organization_membership_active(
                membership=membership,
                actor=request.user,
                is_active=requested_state == "true",
            )
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            state = "restored" if membership.is_active else "removed"
            messages.success(
                request,
                f'Administrator access for "{membership.user.username}" {state}.',
            )
    return redirect(
        "organizations:platform-organization-detail", managed_organization.pk
    )


@login_required
def platform_organization_delete_request(request, organization_id: int):
    managed_organization = _platform_organization(request, organization_id)
    if managed_organization.deletion_requested_at is not None:
        messages.error(request, "Organization deletion is already scheduled.")
        return redirect(
            "organizations:platform-organization-detail", managed_organization.pk
        )
    form = RequestOrganizationDeletionForm(
        request.POST or None,
        organization=managed_organization,
    )
    if request.method == "POST" and form.is_valid():
        request_organization_deletion(
            organization=managed_organization,
            user=request.user,
        )
        messages.warning(
            request,
            "Organization access is suspended until recovery or scheduled purge.",
        )
        return redirect(
            "organizations:platform-organization-detail", managed_organization.pk
        )
    return render(
        request,
        "organizations/platform_organization_confirm_delete.html",
        {"managed_organization": managed_organization, "form": form},
    )


@login_required
@require_POST
def platform_organization_recover(request, organization_id: int):
    managed_organization = _platform_organization(request, organization_id)
    try:
        cancel_organization_deletion(
            organization=managed_organization,
            user=request.user,
        )
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
    else:
        messages.success(request, "Organization access restored.")
    return redirect(
        "organizations:platform-organization-detail", managed_organization.pk
    )


@login_required
def client_company_list(request, organization_slug: str):
    organization = _visible_organization(request, organization_slug)
    require_organization_admin(request.user, organization)
    companies = (
        ClientCompany.objects.for_organization(organization)
        .annotate(vacancy_count=Count("vacancies"))
        .order_by("name", "id")
    )
    return render(
        request,
        "organizations/client_company_list.html",
        {"organization": organization, "companies": companies},
    )


@login_required
def client_company_create(request, organization_slug: str):
    organization = _visible_organization(request, organization_slug)
    require_organization_admin(request.user, organization)
    return_url = _safe_return_url(request)
    form = ClientCompanyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        company = create_client_company(
            organization=organization,
            user=request.user,
            values=form.cleaned_data,
        )
        messages.success(request, f'Client company "{company.name}" added.')
        if return_url:
            return redirect(_with_selected_company(return_url, company))
        return redirect("organizations:client-company-list", organization.slug)
    return render(
        request,
        "organizations/client_company_form.html",
        {
            "organization": organization,
            "form": form,
            "return_url": return_url,
            "heading": "Add client company",
            "submit_label": "Add client company",
        },
    )


@login_required
def client_company_edit(request, organization_slug: str, company_id: int):
    organization = _visible_organization(request, organization_slug)
    require_organization_admin(request.user, organization)
    company = get_object_or_404(
        ClientCompany.objects.for_organization(organization), pk=company_id
    )
    form = ClientCompanyForm(request.POST or None, instance=company)
    if request.method == "POST" and form.is_valid():
        company = update_client_company(
            company=company,
            user=request.user,
            values=form.cleaned_data,
        )
        messages.success(request, f'Client company "{company.name}" updated.')
        return redirect("organizations:client-company-list", organization.slug)
    return render(
        request,
        "organizations/client_company_form.html",
        {
            "organization": organization,
            "company": company,
            "form": form,
            "heading": "Edit client company",
            "submit_label": "Save client company",
        },
    )


@login_required
@require_POST
def client_company_status(request, organization_slug: str, company_id: int):
    organization = _visible_organization(request, organization_slug)
    require_organization_admin(request.user, organization)
    company = get_object_or_404(
        ClientCompany.objects.for_organization(organization), pk=company_id
    )
    requested_state = request.POST.get("is_active")
    if requested_state not in {"true", "false"}:
        messages.error(request, "Select a valid client-company status.")
    else:
        try:
            company = set_client_company_active(
                company=company,
                user=request.user,
                is_active=requested_state == "true",
            )
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            state = "activated" if company.is_active else "deactivated"
            messages.success(request, f'Client company "{company.name}" {state}.')
    return redirect("organizations:client-company-list", organization.slug)


@login_required
def retention_dashboard(request, organization_slug: str):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    require_organization_admin(request.user, organization)
    policy = get_retention_policy(organization)
    policy_form = OrganizationRetentionPolicyForm(instance=policy, prefix="policy")
    exception_form = RetentionExceptionForm(
        organization=organization, prefix="exception"
    )
    apply_form = ApplyRetentionForm(prefix="apply")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update_policy":
            policy_form = OrganizationRetentionPolicyForm(
                request.POST, instance=policy, prefix="policy"
            )
            if policy_form.is_valid():
                policy = update_retention_policy(
                    organization=organization,
                    user=request.user,
                    values=policy_form.cleaned_data,
                )
                messages.success(request, "Retention policy updated.")
                return redirect("organizations:retention-dashboard", organization.slug)
        elif action == "add_exception":
            exception_form = RetentionExceptionForm(
                request.POST,
                organization=organization,
                prefix="exception",
            )
            if exception_form.is_valid():
                exception_form.save(user=request.user)
                messages.success(request, "Retention exception added.")
                return redirect("organizations:retention-dashboard", organization.slug)
        elif action == "deactivate_exception":
            exception = get_object_or_404(
                RetentionException,
                organization=organization,
                pk=request.POST.get("exception_id"),
                is_active=True,
            )
            exception.is_active = False
            exception.save(update_fields=("is_active",))
            messages.success(request, "Retention exception removed.")
            return redirect("organizations:retention-dashboard", organization.slug)
        elif action == "apply_cleanup":
            apply_form = ApplyRetentionForm(request.POST, prefix="apply")
            if apply_form.is_valid():
                try:
                    result = apply_retention_plan(
                        organization=organization,
                        actor=request.user,
                    )
                except DataLifecycleError as error:
                    apply_form.add_error(None, str(error))
                else:
                    messages.success(
                        request,
                        "Lifecycle cleanup completed: "
                        f"{result.total} record bundle(s).",
                    )
                    return redirect(
                        "organizations:retention-dashboard", organization.slug
                    )

    return render(
        request,
        "organizations/retention_dashboard.html",
        {
            "organization": organization,
            "policy": policy,
            "plan": build_retention_plan(organization=organization),
            "policy_form": policy_form,
            "exception_form": exception_form,
            "apply_form": apply_form,
            "exceptions": organization.retention_exceptions.filter(
                is_active=True
            ).select_related("created_by"),
        },
    )


@login_required
def organization_delete_request(request, organization_slug: str):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    require_organization_admin(request.user, organization)
    policy = get_retention_policy(organization)
    projected_purge_after = timezone.now() + timedelta(
        days=policy.organization_recovery_days
    )
    organization_exception_active = (
        organization.retention_exceptions.filter(
            is_active=True,
            scope=RetentionException.Scope.ORGANIZATION,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.localdate()))
        .exists()
    )
    form = RequestOrganizationDeletionForm(
        request.POST or None,
        organization=organization,
    )
    if request.method == "POST" and form.is_valid():
        request_organization_deletion(organization=organization, user=request.user)
        messages.warning(
            request,
            "Organization access is suspended. Recover it before the purge date "
            "if needed.",
        )
        return redirect("organizations:organization-recovery")
    return render(
        request,
        "organizations/organization_confirm_delete.html",
        {
            "organization": organization,
            "form": form,
            "policy": policy,
            "projected_purge_after": projected_purge_after,
            "organization_exception_active": organization_exception_active,
        },
    )


@login_required
def organization_recovery(request):
    return render(
        request,
        "organizations/organization_recovery.html",
        {"organizations": organizations_available_for_recovery(request.user)},
    )


@login_required
def organization_recover(request, organization_id: int):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organization = get_object_or_404(
        Organization,
        pk=organization_id,
        is_active=False,
        deletion_requested_at__isnull=False,
    )
    if not can_recover_organization(request.user, organization):
        return get_object_or_404(Organization.objects.none())
    try:
        cancel_organization_deletion(organization=organization, user=request.user)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
        return redirect("organizations:organization-recovery")
    messages.success(request, "Organization access restored.")
    return redirect("organizations:organization-dashboard", organization.slug)
