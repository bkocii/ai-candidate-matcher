from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from audit.lifecycle import (
    DataLifecycleError,
    apply_retention_plan,
    build_retention_plan,
)
from organizations.models import Organization


class Command(BaseCommand):
    help = (
        "Preview policy-eligible lifecycle bundles and optionally purge them. "
        "Current and decision-bearing workflow history is never eligible."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--as-of",
            help="Evaluate at this ISO date/time (defaults to now).",
        )
        parser.add_argument(
            "--organization",
            help="Limit processing to one active organization slug.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the recalculated dependency-safe cleanup plan.",
        )
        parser.add_argument(
            "--confirm",
            help='Required with --apply; enter "PURGE ELIGIBLE DATA".',
        )

    def handle(self, *args, **options) -> None:
        as_of = self._parse_as_of(options["as_of"])
        if options["apply"] and options["confirm"] != "PURGE ELIGIBLE DATA":
            raise CommandError('--apply requires --confirm "PURGE ELIGIBLE DATA".')
        organizations = Organization.objects.filter(is_active=True).order_by("slug")
        if options["organization"]:
            organizations = organizations.filter(slug=options["organization"])
            if not organizations.exists():
                raise CommandError("No active organization has that slug.")

        total = 0
        blocked_organizations = 0
        for organization in organizations:
            plan = build_retention_plan(organization=organization, as_of=as_of)
            total += plan.purgeable_count
            self.stdout.write(
                f"{organization.slug}: eligible={plan.purgeable_count} "
                f"intake={len(plan.temporary_intake_item_ids)} "
                f"jobs={len(plan.completed_job_ids)} "
                f"shortlists={len(plan.obsolete_match_run_ids)} "
                f"outreach={len(plan.abandoned_outreach_entry_ids)} "
                f"metadata={plan.metadata_count} blocked={plan.blocked_count}"
            )
            if options["apply"]:
                try:
                    apply_retention_plan(
                        organization=organization,
                        actor=None,
                        as_of=as_of,
                    )
                except DataLifecycleError as error:
                    blocked_organizations += 1
                    self.stderr.write(f"{organization.slug}: blocked ({error})")

        mode = "purged" if options["apply"] else "eligible (dry run)"
        self.stdout.write(
            self.style.SUCCESS(
                f"{total} bundle(s) {mode}; "
                f"blocked organizations={blocked_organizations}."
            )
        )

    @staticmethod
    def _parse_as_of(value: str | None) -> datetime:
        if value is None:
            return timezone.now()
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise CommandError("--as-of must be an ISO date or date/time.") from error
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed
