from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

from accounts.models import User
from evaluation.dataset import load_evaluation_dataset
from evaluation.demo import DEMO_VACANCY_CODE, prepare_demo


class Command(BaseCommand):
    help = (
        "Create an isolated provider-free synthetic product demo with assessments, "
        "individual decisions, and one unapproved outreach draft."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--username",
            required=True,
            help="Existing active user who will own and inspect the demo.",
        )
        parser.add_argument(
            "--organization-slug",
            default="synthetic-demo-001",
            help=(
                "New organization slug for the isolated demo. Existing "
                "organizations are never replaced."
            ),
        )

    def handle(self, *args, **options) -> None:
        try:
            user = User.objects.get(username=options["username"])
        except User.DoesNotExist as error:
            raise CommandError("No user has that username.") from error

        try:
            dataset = load_evaluation_dataset()
            prepared = prepare_demo(
                dataset=dataset,
                user=user,
                organization_slug=options["organization_slug"],
            )
        except (OSError, ValueError) as error:
            raise CommandError("The packaged synthetic dataset is invalid.") from error
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error

        installed = prepared.installed
        organization = installed.organization
        run = installed.match_runs[DEMO_VACANCY_CODE]
        approved_assessment = prepared.decisions[0].assessment
        self.stdout.write(
            self.style.SUCCESS(
                f"Prepared provider-free synthetic demo in {organization.slug}: "
                f"{len(installed.candidates)} candidates, "
                f"{len(installed.vacancies)} vacancies, "
                f"{len(installed.match_runs)} deterministic shortlists, "
                f"{len(prepared.assessments)} current assessments, "
                f"{len(prepared.decisions)} individual decisions, and one "
                "unapproved outreach draft."
            )
        )
        self.stdout.write(
            "No provider or network request was made. No final outreach approval, "
            "copy, export, or send occurred. Synthetic source contact remains "
            "restricted."
        )
        routes = (
            (
                "Dashboard",
                reverse(
                    "organizations:organization-dashboard",
                    args=[organization.slug],
                ),
            ),
            (
                "Shortlist",
                reverse(
                    "matching:shortlist-detail",
                    args=[organization.slug, run.requirements.vacancy_id, run.pk],
                ),
            ),
            (
                "Review queue",
                reverse(
                    "matching:assessment-review-queue",
                    args=[organization.slug],
                )
                + "?scope=all",
            ),
            (
                "Approved assessment",
                reverse(
                    "matching:assessment-review-detail",
                    args=[organization.slug, approved_assessment.pk],
                ),
            ),
            (
                "Unapproved outreach draft",
                reverse(
                    "outreach:outreach-draft-detail",
                    args=[organization.slug, prepared.outreach_draft.pk],
                ),
            ),
        )
        for label, route in routes:
            self.stdout.write(f"{label}: {route}")
