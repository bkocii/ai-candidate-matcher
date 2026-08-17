from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from evaluation.dataset import load_evaluation_dataset
from evaluation.services import install_evaluation_dataset


class Command(BaseCommand):
    help = (
        "Create the isolated EVAL-001 synthetic candidate/vacancy workspace and "
        "verify its expected deterministic rankings."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--username",
            required=True,
            help="Existing active user who will own and inspect the fixtures.",
        )
        parser.add_argument(
            "--organization-slug",
            default="synthetic-eval-001",
            help=(
                "New organization slug for the isolated fixtures. Existing "
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
        except (OSError, ValueError) as error:
            raise CommandError("The packaged evaluation dataset is invalid.") from error
        try:
            installed = install_evaluation_dataset(
                dataset=dataset,
                user=user,
                organization_slug=options["organization_slug"],
            )
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error

        self.stdout.write(
            self.style.SUCCESS(
                f"Installed {dataset.dataset_id} in "
                f"{installed.organization.slug}: "
                f"{len(installed.candidates)} candidates, "
                f"{len(installed.vacancies)} vacancies, and "
                f"{len(installed.match_runs)} verified shortlists. "
                "No AI request or outreach action was made."
            )
        )
