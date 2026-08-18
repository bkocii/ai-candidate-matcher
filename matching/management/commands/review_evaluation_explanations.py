import json
from dataclasses import asdict

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from evaluation.dataset import load_evaluation_dataset
from evaluation.explanation_review import (
    ExplanationReviewReport,
    review_evaluation_explanations,
)
from organizations.models import Organization


def _report_text(report: ExplanationReviewReport) -> str:
    lines = [
        f"Dataset: {report.dataset_id}",
        f"Dataset SHA-256: {report.dataset_sha256}",
        f"Organization: {report.organization_slug}",
        (
            f"Coverage: {report.reviewed_count}/{report.expected_count} "
            "current assessments"
        ),
        f"Status: {report.status}",
        f"Clean: {report.clean_count}",
        f"Flagged: {report.flagged_count}",
    ]
    for code, count in report.issue_counts.items():
        lines.append(f"Issue {code}: {count}")
    for review in report.assessments:
        if review.issues:
            codes = ", ".join(
                f"{issue.code}@{issue.location}" for issue in review.issues
            )
            lines.append(
                f"{review.vacancy_code}/{review.candidate_code} "
                f"assessment v{review.assessment_version}: {codes}"
            )
    lines.append(
        "Stored provider-authored explanations were reviewed read-only; no AI "
        "request was made and no score, assessment, decision, or outreach changed."
    )
    return "\n".join(lines)


class Command(BaseCommand):
    help = (
        "Review current EVAL-001 assessment explanations for evidence and "
        "protected-attribute safety without making an AI request."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--username", required=True)
        parser.add_argument(
            "--organization-slug",
            default="synthetic-eval-001",
        )
        parser.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
        )
        parser.add_argument("--require-complete", action="store_true")
        parser.add_argument("--require-clean", action="store_true")

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
            report = review_evaluation_explanations(
                dataset=load_evaluation_dataset(),
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
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        else:
            self.stdout.write(_report_text(report))

        if options["require_complete"] and not report.is_complete:
            raise CommandError(
                "Explanation review is incomplete; generate current assessments "
                "for every evaluation shortlist entry."
            )
        if options["require_clean"] and not report.is_clean:
            raise CommandError(
                "Explanation review is not clean; complete coverage and resolve all "
                "flagged explanations."
            )
