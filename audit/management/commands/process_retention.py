from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from candidates.models import Candidate
from candidates.services import flag_candidate_for_expired_retention
from organizations.models import Organization


class Command(BaseCommand):
    help = (
        "Report expired candidate retention dates and optionally freeze those "
        "candidates for explicit deletion review. This command never purges data."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--as-of",
            help="Evaluate retention through this ISO date (defaults to today).",
        )
        parser.add_argument(
            "--organization",
            help="Limit processing to one active organization slug.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Create staged candidate deletion requests; never purge data.",
        )

    def handle(self, *args, **options) -> None:
        as_of = self._parse_as_of(options["as_of"])
        organizations = Organization.objects.filter(is_active=True).order_by("slug")
        requested_slug = options["organization"]
        if requested_slug:
            organizations = organizations.filter(slug=requested_slug)
            if not organizations.exists():
                raise CommandError("No active organization has that slug.")

        total = 0
        for organization in organizations:
            expired_candidates = list(
                Candidate.objects.for_organization(organization)
                .filter(
                    status__in=[Candidate.Status.ACTIVE, Candidate.Status.INACTIVE],
                    retention_until__lte=as_of,
                )
                .order_by("id")
            )
            count = len(expired_candidates)
            total += count
            if options["apply"]:
                for candidate in expired_candidates:
                    flag_candidate_for_expired_retention(
                        candidate=candidate,
                        as_of=as_of,
                    )
            self.stdout.write(f"{organization.slug}: {count} candidate(s) due")

        mode = "flagged for review" if options["apply"] else "found (dry run)"
        self.stdout.write(
            self.style.SUCCESS(
                f"{total} candidate(s) {mode} as of {as_of.isoformat()}. "
                "No data was purged."
            )
        )

    @staticmethod
    def _parse_as_of(value: str | None) -> date:
        if value is None:
            return timezone.localdate()
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise CommandError("--as-of must use YYYY-MM-DD.") from error
