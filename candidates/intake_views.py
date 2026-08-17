from dataclasses import dataclass

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from candidates.bulk_intake import (
    CandidateIntakeDuplicateError,
    create_candidate_from_intake_item,
    create_candidate_intake_batch,
    discard_candidate_intake_batch,
    skip_candidate_intake_item,
    upload_candidate_intake_cv,
)
from candidates.documents import CandidateDocumentUploadError
from candidates.forms import (
    CandidateIntakeBatchForm,
    CandidateIntakeReviewForm,
    CandidateIntakeUploadForm,
)
from candidates.models import CandidateIntakeBatch, CandidateIntakeItem
from candidates.services import CandidateDuplicateFinder
from operations.models import BackgroundJob
from operations.services import queue_candidate_profile_documents
from organizations.models import Organization

REVIEW_FLAG_LABELS = {
    "name_missing": "Name needs entry",
    "name_from_filename": "Name came from filename",
    "email_missing": "Email not found",
    "multiple_emails": "Multiple emails found",
    "phone_missing": "Phone not found",
    "multiple_phones": "Multiple phone numbers found",
    "location_missing": "Location not found",
}


@dataclass
class IntakeReviewRow:
    item: CandidateIntakeItem
    form: CandidateIntakeReviewForm
    duplicate: object | None
    flag_labels: tuple[str, ...]


def _organization(request, slug: str) -> Organization:
    return get_object_or_404(
        Organization.objects.visible_to(request.user),
        slug=slug,
    )


def _batch(organization: Organization, batch_id: int) -> CandidateIntakeBatch:
    return get_object_or_404(
        CandidateIntakeBatch.objects.for_organization(organization).select_related(
            "created_by"
        ),
        pk=batch_id,
    )


def _initial_for_item(item: CandidateIntakeItem) -> dict:
    return {
        "full_name": item.proposed_full_name,
        "email": item.proposed_email,
        "phone": item.proposed_phone,
        "location": item.proposed_location,
        "source_reference": item.proposed_source_reference,
    }


def _current_form_values(form: CandidateIntakeReviewForm, item) -> dict:
    if form.is_bound:
        return {
            field: form.data.get(form.add_prefix(field), "").strip()
            for field in (
                "email",
                "phone",
                "source_reference",
            )
        }
    return {
        "email": item.proposed_email,
        "phone": item.proposed_phone,
        "source_reference": item.proposed_source_reference,
    }


def _review_rows(
    *,
    batch: CandidateIntakeBatch,
    bound_forms: dict[int, CandidateIntakeReviewForm] | None = None,
) -> list[IntakeReviewRow]:
    finder = CandidateDuplicateFinder(batch.organization)
    rows: list[IntakeReviewRow] = []
    pending_items = batch.items.filter(
        status=CandidateIntakeItem.Status.PENDING
    ).order_by("id")
    for item in pending_items:
        form = (bound_forms or {}).get(item.pk)
        if form is None:
            form = CandidateIntakeReviewForm(
                prefix=f"item-{item.pk}",
                initial=_initial_for_item(item),
            )
        values = _current_form_values(form, item)
        duplicate = finder.find(**values)
        rows.append(
            IntakeReviewRow(
                item=item,
                form=form,
                duplicate=duplicate,
                flag_labels=tuple(
                    REVIEW_FLAG_LABELS.get(flag, "Needs review")
                    for flag in item.review_flags
                ),
            )
        )
    return rows


def _render_batch(
    request,
    *,
    organization: Organization,
    batch: CandidateIntakeBatch,
    upload_form: CandidateIntakeUploadForm | None = None,
    bound_forms: dict[int, CandidateIntakeReviewForm] | None = None,
    queued_job: BackgroundJob | None = None,
):
    batch.refresh_from_db()
    items = batch.items.select_related("candidate", "processed_by")
    pending_count = items.filter(status=CandidateIntakeItem.Status.PENDING).count()
    created_items = items.filter(status=CandidateIntakeItem.Status.CREATED)
    skipped_count = items.filter(status=CandidateIntakeItem.Status.SKIPPED).count()
    return render(
        request,
        "candidates/candidate_intake_detail.html",
        {
            "organization": organization,
            "batch": batch,
            "upload_form": upload_form or CandidateIntakeUploadForm(),
            "review_rows": _review_rows(batch=batch, bound_forms=bound_forms),
            "pending_count": pending_count,
            "created_items": created_items,
            "created_count": created_items.count(),
            "skipped_count": skipped_count,
            "queued_job": queued_job,
        },
    )


@login_required
def candidate_intake_list(request, organization_slug: str):
    organization = _organization(request, organization_slug)
    batches = (
        CandidateIntakeBatch.objects.for_organization(organization)
        .select_related("created_by")
        .annotate(
            item_count=Count("items"),
            pending_count=Count(
                "items",
                filter=Q(items__status=CandidateIntakeItem.Status.PENDING),
            ),
            created_count=Count(
                "items",
                filter=Q(items__status=CandidateIntakeItem.Status.CREATED),
            ),
        )
    )
    page = Paginator(batches, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "candidates/candidate_intake_list.html",
        {"organization": organization, "page": page},
    )


@login_required
def candidate_intake_create(request, organization_slug: str):
    organization = _organization(request, organization_slug)
    form = CandidateIntakeBatchForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        batch = create_candidate_intake_batch(
            organization=organization,
            user=request.user,
            values=form.cleaned_data,
        )
        messages.success(
            request,
            "Intake batch created. Upload CVs for local identity review.",
        )
        return redirect(
            "candidates:candidate-intake-detail",
            organization.slug,
            batch.pk,
        )
    return render(
        request,
        "candidates/candidate_intake_form.html",
        {"organization": organization, "form": form},
    )


@login_required
def candidate_intake_detail(request, organization_slug: str, batch_id: int):
    organization = _organization(request, organization_slug)
    batch = _batch(organization, batch_id)
    queued_job = None
    requested_job = request.GET.get("job")
    if requested_job and requested_job.isdigit():
        queued_job = (
            BackgroundJob.objects.for_organization(organization)
            .filter(pk=int(requested_job))
            .first()
        )
    return _render_batch(
        request,
        organization=organization,
        batch=batch,
        queued_job=queued_job,
    )


@login_required
@require_POST
def candidate_intake_upload(request, organization_slug: str, batch_id: int):
    organization = _organization(request, organization_slug)
    batch = _batch(organization, batch_id)
    form = CandidateIntakeUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return _render_batch(
            request,
            organization=organization,
            batch=batch,
            upload_form=form,
        )

    created = 0
    failures = 0
    for position, uploaded_file in enumerate(form.cleaned_data["cv_files"], start=1):
        try:
            upload_candidate_intake_cv(
                batch=batch,
                user=request.user,
                uploaded_file=uploaded_file,
            )
        except CandidateDocumentUploadError as error:
            failures += 1
            messages.error(request, f"File {position}: {error.public_message}")
        except ValidationError as error:
            failures += 1
            messages.error(request, f"File {position}: {'; '.join(error.messages)}")
        else:
            created += 1
    if created:
        messages.success(
            request,
            f"Added {created} CV(s) to the review queue.",
        )
    if failures:
        messages.error(
            request,
            f"{failures} file(s) were rejected without storing private bytes.",
        )
    return redirect(
        "candidates:candidate-intake-detail",
        organization.slug,
        batch.pk,
    )


@login_required
@require_POST
def candidate_intake_create_selected(request, organization_slug: str, batch_id: int):
    organization = _organization(request, organization_slug)
    batch = _batch(organization, batch_id)
    pending_items = list(
        batch.items.filter(status=CandidateIntakeItem.Status.PENDING).order_by("id")
    )
    bound_forms: dict[int, CandidateIntakeReviewForm] = {}
    selected: list[tuple[CandidateIntakeItem, CandidateIntakeReviewForm]] = []
    for item in pending_items:
        selected_key = f"item-{item.pk}-selected"
        if selected_key not in request.POST:
            continue
        form = CandidateIntakeReviewForm(request.POST, prefix=f"item-{item.pk}")
        bound_forms[item.pk] = form
        if form.is_valid() and form.cleaned_data["selected"]:
            selected.append((item, form))

    if not selected and not any(form.errors for form in bound_forms.values()):
        messages.error(request, "Select at least one reviewed CV to create.")
        return redirect(
            "candidates:candidate-intake-detail",
            organization.slug,
            batch.pk,
        )

    document_ids: list[int] = []
    created_count = 0
    for item, form in selected:
        values = form.cleaned_data
        try:
            result = create_candidate_from_intake_item(
                item=item,
                user=request.user,
                candidate_values={
                    "full_name": values["full_name"],
                    "email": values["email"],
                    "phone": values["phone"],
                    "location": values["location"],
                },
                source_reference=values["source_reference"],
            )
        except CandidateIntakeDuplicateError as error:
            form.add_error(None, error.messages[0])
        except (CandidateDocumentUploadError, ValidationError) as error:
            public_message = (
                error.public_message
                if isinstance(error, CandidateDocumentUploadError)
                else "; ".join(error.messages)
            )
            form.add_error(None, public_message)
        else:
            created_count += 1
            document_ids.append(result.document.pk)
            bound_forms.pop(item.pk, None)

    queued_job = None
    if document_ids and request.POST.get("queue_profiles") == "on":
        try:
            queued = queue_candidate_profile_documents(
                organization=organization,
                user=request.user,
                document_ids=document_ids,
            )
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            queued_job = queued.job
    if created_count:
        messages.success(
            request,
            f"Created {created_count} candidate(s) with private CVs and provenance.",
        )

    if any(form.errors for form in bound_forms.values()):
        return _render_batch(
            request,
            organization=organization,
            batch=batch,
            bound_forms=bound_forms,
            queued_job=queued_job,
        )

    detail_url = reverse(
        "candidates:candidate-intake-detail",
        args=[organization.slug, batch.pk],
    )
    if queued_job is not None:
        detail_url = f"{detail_url}?job={queued_job.pk}"
    return redirect(detail_url)


@login_required
@require_POST
def candidate_intake_skip(request, organization_slug: str, batch_id: int, item_id: int):
    organization = _organization(request, organization_slug)
    batch = _batch(organization, batch_id)
    item = get_object_or_404(
        CandidateIntakeItem.objects.for_organization(organization),
        pk=item_id,
        batch=batch,
    )
    try:
        skip_candidate_intake_item(item=item, user=request.user)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
    else:
        messages.success(
            request,
            "Pending intake CV discarded and private data cleared.",
        )
    return redirect(
        "candidates:candidate-intake-detail",
        organization.slug,
        batch.pk,
    )


@login_required
@require_POST
def candidate_intake_discard(request, organization_slug: str, batch_id: int):
    organization = _organization(request, organization_slug)
    batch = _batch(organization, batch_id)
    try:
        discard_candidate_intake_batch(batch=batch, user=request.user)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
    else:
        messages.success(
            request,
            "Intake closed. Every remaining temporary CV and identity proposal was "
            "cleared.",
        )
    return redirect(
        "candidates:candidate-intake-detail",
        organization.slug,
        batch.pk,
    )
