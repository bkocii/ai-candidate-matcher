from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import OrganizationMembership
from candidates.models import Candidate
from organizations.models import ClientCompany, Organization
from vacancies.models import Vacancy


@login_required
def dashboard_home(request):
    """Resolve the user's organization or offer an explicit organization choice."""
    organizations = list(Organization.objects.visible_to(request.user))

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
        },
    )
