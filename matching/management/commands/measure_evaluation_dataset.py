import json
from dataclasses import asdict
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from evaluation.dataset import load_evaluation_dataset
from evaluation.measurement import EvaluationQualityReport, measure_evaluation_quality
from organizations.models import Organization


def _json_default(value: object) -> str:
    if isinstance(value, Decimal):
        return format(value, ".4f")
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _metrics_text(metrics) -> str:
    return (
        f"nDCG@5 {metrics.ndcg_at_k:.4f} | "
        f"precision@5 {metrics.precision_at_k:.4f} | "
        f"expected-top overlap@5 {metrics.expected_top_overlap_at_k:.4f}"
    )


def _report_text(report: EvaluationQualityReport) -> str:
    lines = [
        f"Dataset: {report.dataset_id}",
        f"Dataset SHA-256: {report.dataset_sha256}",
        f"Organization: {report.organization_slug}",
        f"Cutoff: {report.cutoff}",
    ]
    for item in report.vacancies:
        lines.append(
            f"{item.vacancy_code} deterministic: "
            f"{_metrics_text(item.deterministic.metrics)}"
        )
        if item.ai_assisted.metrics is None:
            lines.append(
                f"{item.vacancy_code} AI-assisted: unavailable "
                f"({item.ai_assisted.ranked_count}/"
                f"{item.ai_assisted.expected_count} current assessments)"
            )
        else:
            lines.append(
                f"{item.vacancy_code} AI-assisted: "
                f"{_metrics_text(item.ai_assisted.metrics)}"
            )
    lines.append(f"Deterministic macro: {_metrics_text(report.deterministic_macro)}")
    lines.append(
        f"AI coverage: {report.ai_assessed_count}/{report.ai_expected_count} "
        "current assessments"
    )
    if report.ai_assisted_macro is None:
        lines.append("AI-assisted macro: unavailable until coverage is complete")
    else:
        lines.append(f"AI-assisted macro: {_metrics_text(report.ai_assisted_macro)}")
    lines.append(
        "Deterministic and AI-assisted rankings were measured separately; "
        "no scores were blended and no AI request was made."
    )
    return "\n".join(lines)


class Command(BaseCommand):
    help = (
        "Measure deterministic and current AI-assisted ranking quality separately "
        "for an installed EVAL-001 workspace."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--username",
            required=True,
            help="Existing active member of the evaluation organization.",
        )
        parser.add_argument(
            "--organization-slug",
            default="synthetic-eval-001",
            help="Installed EVAL-001 organization slug.",
        )
        parser.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
            help="Stable human-readable or machine-readable report format.",
        )
        parser.add_argument(
            "--require-complete-ai",
            action="store_true",
            help=(
                "Fail after reporting when current AI-assessment coverage is "
                "incomplete."
            ),
        )

    def handle(self, *args, **options) -> None:
        try:
            user = User.objects.get(username=options["username"])
        except User.DoesNotExist as error:
            raise CommandError("No user has that username.") from error
        try:
            organization = Organization.objects.visible_to(user).get(
                slug=options["organization_slug"]
            )
        except Organization.DoesNotExist as error:
            raise CommandError(
                "No accessible active organization has that slug."
            ) from error
        try:
            dataset = load_evaluation_dataset()
            report = measure_evaluation_quality(
                dataset=dataset,
                organization=organization,
                user=user,
            )
        except (OSError, ValueError) as error:
            raise CommandError("The packaged evaluation dataset is invalid.") from error
        except (PermissionDenied, ValidationError) as error:
            messages = getattr(error, "messages", None)
            message = "; ".join(messages) if messages else str(error)
            raise CommandError(message) from error

        if options["format"] == "json":
            self.stdout.write(
                json.dumps(
                    asdict(report),
                    default=_json_default,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        else:
            self.stdout.write(_report_text(report))

        if options["require_complete_ai"] and not report.ai_assisted_complete:
            raise CommandError(
                "AI-assisted measurement is incomplete; generate current assessments "
                "for every evaluation shortlist entry."
            )
