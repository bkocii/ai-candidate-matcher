from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

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
    OrganizationRetentionPolicyForm,
    RequestOrganizationDeletionForm,
    RetentionExceptionForm,
)
from organizations.models import ClientCompany, Organization, RetentionException
from organizations.permissions import (
    can_administer_organization,
    can_recover_organization,
    require_organization_admin,
)
from vacancies.models import Vacancy


@login_required
def dashboard_home(request):
    """Resolve the user's organization or offer an explicit organization choice."""
    organizations = list(Organization.objects.visible_to(request.user))

    recoverable = organizations_available_for_recovery(request.user)
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


@login_required
def retention_dashboard(request, organization_slug: str):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    require_organization_admin(request.user, organization)
    policy = get_retention_policy(organization)
    policy_form = OrganizationRetentionPolicyForm(instance=policy, prefix="policy")
    exception_form = RetentionExceptionForm(prefix="exception")
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
            exception_form = RetentionExceptionForm(request.POST, prefix="exception")
            if exception_form.is_valid():
                exception = exception_form.save(commit=False)
                exception.organization = organization
                exception.created_by = request.user
                exception.full_clean()
                exception.save()
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
    form = RequestOrganizationDeletionForm(request.POST or None)
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
        {"organization": organization, "form": form},
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
