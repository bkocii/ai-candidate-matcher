import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from candidates.forms import (
    CandidateCSVImportForm,
    CandidateManualEntryForm,
    candidate_values_from_manual_form,
    source_values_from_import_form,
    source_values_from_manual_form,
)
from candidates.models import Candidate
from candidates.services import (
    CSV_HEADERS,
    CandidateDuplicateFinder,
    CandidateImportFileError,
    create_candidate_with_source,
    import_candidate_csv,
)
from organizations.models import Organization


def _visible_organization(request, organization_slug: str) -> Organization:
    return get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=organization_slug,
    )


@login_required
def candidate_list(request, organization_slug: str):
    organization = _visible_organization(request, organization_slug)
    candidates = Candidate.objects.for_organization(organization).order_by(
        "full_name", "id"
    )
    page = Paginator(candidates, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "candidates/candidate_list.html",
        {"organization": organization, "page": page},
    )


@login_required
def candidate_create(request, organization_slug: str):
    organization = _visible_organization(request, organization_slug)
    form = CandidateManualEntryForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        candidate_values = candidate_values_from_manual_form(form)
        source_values = source_values_from_manual_form(form)
        duplicate = CandidateDuplicateFinder(organization).find(
            email=candidate_values["email"],
            phone=candidate_values["phone"],
            source_reference=source_values["source_reference"],
        )
        if duplicate:
            reasons = ", ".join(duplicate.reasons)
            form.add_error(
                None,
                f"Possible duplicate of {duplicate.candidate.full_name} "
                f"(matched by {reasons}). No record was created.",
            )
        else:
            candidate = create_candidate_with_source(
                organization=organization,
                user=request.user,
                candidate_values=candidate_values,
                source_values=source_values,
            )
            messages.success(request, f"Created candidate {candidate.full_name}.")
            return redirect(
                "candidates:candidate-list",
                organization_slug=organization.slug,
            )

    return render(
        request,
        "candidates/candidate_form.html",
        {"organization": organization, "form": form},
    )


@login_required
def candidate_import(request, organization_slug: str):
    organization = _visible_organization(request, organization_slug)
    form = CandidateCSVImportForm(request.POST or None, request.FILES or None)
    result = None

    if request.method == "POST" and form.is_valid():
        try:
            result = import_candidate_csv(
                uploaded_file=form.cleaned_data["csv_file"],
                organization=organization,
                user=request.user,
                source_defaults=source_values_from_import_form(form),
            )
        except CandidateImportFileError as error:
            form.add_error("csv_file", str(error))

    return render(
        request,
        "candidates/candidate_import.html",
        {"organization": organization, "form": form, "result": result},
    )


@login_required
def candidate_import_template(request, organization_slug: str):
    _visible_organization(request, organization_slug)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        'attachment; filename="candidate-import-template.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(CSV_HEADERS)
    return response
