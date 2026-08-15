import csv
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ai_gateway import AIGatewayError
from candidates.ai_extraction import (
    confirm_candidate_profile,
    extract_candidate_profile,
)
from candidates.documents import (
    CandidateDocumentDeliveryError,
    CandidateDocumentUploadError,
    load_private_candidate_document,
    upload_candidate_cv,
)
from candidates.forms import (
    CandidateCSVImportForm,
    CandidateCVUploadForm,
    CandidateManualEntryForm,
    candidate_values_from_manual_form,
    source_values_from_import_form,
    source_values_from_manual_form,
)
from candidates.models import Candidate, CandidateDocument, CandidateProfile
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
    documents = candidate.documents.filter(deleted_at__isnull=True).prefetch_related(
        "profile_versions"
    )
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
@require_POST
def candidate_profile_extract(
    request,
    organization_slug: str,
    candidate_id: int,
    document_id: int,
):
    organization = _visible_organization(request, organization_slug)
    candidate = get_object_or_404(
        Candidate.objects.for_organization(organization).not_deleted(),
        pk=candidate_id,
    )
    document = get_object_or_404(
        CandidateDocument.objects.for_organization(organization),
        pk=document_id,
        candidate=candidate,
        deleted_at__isnull=True,
    )
    try:
        result = extract_candidate_profile(
            document=document,
            user=request.user,
        )
    except (AIGatewayError, ValidationError) as error:
        public_message = (
            "; ".join(error.messages)
            if isinstance(error, ValidationError)
            else str(error)
        )
        messages.error(request, public_message)
        return redirect(
            "candidates:candidate-detail",
            organization_slug=organization.slug,
            candidate_id=candidate.pk,
        )

    success_message = (
        "AI profile draft created after automatically correcting its source "
        "evidence. Review every excerpt before confirming it for matching."
        if result.evidence_repair_used
        else (
            "AI profile draft created. Review its evidence before confirming it "
            "for matching."
        )
    )
    messages.success(request, success_message)
    return redirect(
        "candidates:candidate-profile-detail",
        organization_slug=organization.slug,
        candidate_id=candidate.pk,
        profile_id=result.profile.pk,
    )


@login_required
def candidate_profile_detail(
    request,
    organization_slug: str,
    candidate_id: int,
    profile_id: int,
):
    organization = _visible_organization(request, organization_slug)
    candidate = get_object_or_404(
        Candidate.objects.for_organization(organization).not_deleted(),
        pk=candidate_id,
    )
    profile = get_object_or_404(
        CandidateProfile.objects.for_organization(organization).select_related(
            "source_document",
            "created_by",
            "confirmed_by",
        ),
        pk=profile_id,
        candidate=candidate,
    )
    return render(
        request,
        "candidates/candidate_profile_detail.html",
        {
            "organization": organization,
            "candidate": candidate,
            "profile": profile,
            "profile_versions": candidate.profile_versions.select_related(
                "source_document"
            ),
        },
    )


@login_required
@require_POST
def candidate_profile_confirm(
    request,
    organization_slug: str,
    candidate_id: int,
    profile_id: int,
):
    organization = _visible_organization(request, organization_slug)
    candidate = get_object_or_404(
        Candidate.objects.for_organization(organization).not_deleted(),
        pk=candidate_id,
    )
    profile = get_object_or_404(
        CandidateProfile.objects.for_organization(organization),
        pk=profile_id,
        candidate=candidate,
    )
    try:
        confirm_candidate_profile(profile=profile, user=request.user)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
    else:
        messages.success(
            request,
            "Candidate profile confirmed. Its grounded facts and skill evidence "
            "are now available to deterministic matching.",
        )
    return redirect(
        "candidates:candidate-profile-detail",
        organization_slug=organization.slug,
        candidate_id=candidate.pk,
        profile_id=profile.pk,
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
def candidate_document_download(
    request,
    organization_slug: str,
    candidate_id: int,
    document_id: int,
):
    organization = _visible_organization(request, organization_slug)
    candidate = get_object_or_404(
        Candidate.objects.for_organization(organization).not_deleted(),
        pk=candidate_id,
    )
    document = get_object_or_404(
        CandidateDocument.objects.for_organization(organization).select_related(
            "candidate"
        ),
        pk=document_id,
        candidate=candidate,
        deleted_at__isnull=True,
    )
    try:
        private_document = load_private_candidate_document(
            document=document,
            user=request.user,
        )
    except CandidateDocumentDeliveryError as error:
        messages.error(request, error.public_message)
        return redirect(
            "candidates:candidate-detail",
            organization_slug=organization.slug,
            candidate_id=candidate.pk,
        )

    response = FileResponse(
        BytesIO(private_document.content),
        as_attachment=True,
        filename=private_document.filename,
        content_type=private_document.content_type,
    )
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox"
    response["Cross-Origin-Resource-Policy"] = "same-origin"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


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
