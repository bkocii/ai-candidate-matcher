import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from candidates.documents import CandidateDocumentUploadError, upload_candidate_cv
from candidates.forms import (
    CandidateCSVImportForm,
    CandidateCVUploadForm,
    CandidateManualEntryForm,
    candidate_values_from_manual_form,
    source_values_from_import_form,
    source_values_from_manual_form,
)
from candidates.models import Candidate
from candidates.services import (
    CSV_HEADERS,
    CandidateDeletionError,
    CandidateDuplicateFinder,
    CandidateImportFileError,
    create_candidate_with_source,
    delete_candidate,
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
    candidates = (
        Candidate.objects.for_organization(organization)
        .not_deleted()
        .order_by("full_name", "id")
    )
    page = Paginator(candidates, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "candidates/candidate_list.html",
        {"organization": organization, "page": page},
    )


@login_required
def candidate_detail(request, organization_slug: str, candidate_id: int):
    organization = _visible_organization(request, organization_slug)
    candidate = get_object_or_404(
        Candidate.objects.for_organization(organization).not_deleted(),
        pk=candidate_id,
    )
    documents = candidate.documents.filter(deleted_at__isnull=True)
    return render(
        request,
        "candidates/candidate_detail.html",
        {
            "organization": organization,
            "candidate": candidate,
            "documents": documents,
        },
    )


@login_required
def candidate_cv_upload(request, organization_slug: str, candidate_id: int):
    organization = _visible_organization(request, organization_slug)
    candidate = get_object_or_404(
        Candidate.objects.for_organization(organization).not_deleted(),
        pk=candidate_id,
    )
    form = CandidateCVUploadForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        try:
            document = upload_candidate_cv(
                candidate=candidate,
                user=request.user,
                uploaded_file=form.cleaned_data["cv_file"],
                retention_until=form.cleaned_data["retention_until"],
            )
        except CandidateDocumentUploadError as error:
            form.add_error("cv_file", error.public_message)
        else:
            messages.success(
                request,
                f"Uploaded and extracted {document.original_filename}.",
            )
            return redirect(
                "candidates:candidate-detail",
                organization_slug=organization.slug,
                candidate_id=candidate.pk,
            )

    return render(
        request,
        "candidates/candidate_cv_upload.html",
        {
            "organization": organization,
            "candidate": candidate,
            "form": form,
        },
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
def candidate_delete(request, organization_slug: str, candidate_id: int):
    organization = _visible_organization(request, organization_slug)
    candidate = get_object_or_404(
        Candidate.objects.for_organization(organization).not_deleted(),
        pk=candidate_id,
    )
    if request.method == "POST":
        candidate_name = candidate.full_name
        try:
            delete_candidate(candidate=candidate, user=request.user)
        except CandidateDeletionError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, f'Deleted candidate "{candidate_name}".')
            return redirect(
                "candidates:candidate-list",
                organization_slug=organization.slug,
            )

    return render(
        request,
        "candidates/candidate_confirm_delete.html",
        {"organization": organization, "candidate": candidate},
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
