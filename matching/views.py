from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from matching.evaluation import filter_candidates
from organizations.models import Organization
from vacancies.models import Vacancy


@login_required
def candidate_filter_report(request, organization_slug: str, vacancy_id: int):
    organization = get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )
    vacancy = get_object_or_404(
        Vacancy.objects.for_organization(organization).active(),
        pk=vacancy_id,
    )
    requirements = vacancy.current_requirements
    report = None
    page = None
    if requirements is not None:
        report = filter_candidates(requirements=requirements, user=request.user)
        page = Paginator(report.results, 25).get_page(request.GET.get("page"))

    return render(
        request,
        "matching/candidate_filter_report.html",
        {
            "organization": organization,
            "vacancy": vacancy,
            "requirements": requirements,
            "report": report,
            "page": page,
        },
    )
