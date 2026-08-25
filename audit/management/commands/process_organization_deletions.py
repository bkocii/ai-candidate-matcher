from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from audit.lifecycle import DataLifecycleError, purge_organization
from organizations.models import Organization


class Command(BaseCommand):
    help = (
        "Preview organizations past their recovery deadline and optionally purge "
        "their complete tenant dependency tree and private files."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--as-of", help="Evaluate at this ISO date/time.")
        parser.add_argument("--organization", help="Limit to one organization slug.")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument(
            "--confirm", help='Required with --apply; enter "PURGE ORGANIZATIONS".'
        )

    def handle(self, *args, **options) -> None:
        as_of = self._parse_as_of(options["as_of"])
        if options["apply"] and options["confirm"] != "PURGE ORGANIZATIONS":
            raise CommandError('--apply requires --confirm "PURGE ORGANIZATIONS".')
        organizations = Organization.objects.filter(
            is_active=False,
            deletion_requested_at__isnull=False,
            purge_after__lte=as_of,
        ).order_by("id")
        if options["organization"]:
            organizations = organizations.filter(slug=options["organization"])

        eligible_ids = list(organizations.values_list("id", flat=True))
        self.stdout.write(f"Eligible organizations: {len(eligible_ids)}")
        if not options["apply"]:
            self.stdout.write(self.style.SUCCESS("Dry run only; no data was purged."))
            return
        purged = 0
        blocked = 0
        for organization_id in eligible_ids:
            organization = Organization.objects.get(pk=organization_id)
            try:
                purge_organization(organization=organization, as_of=as_of)
            except DataLifecycleError as error:
                blocked += 1
                self.stderr.write(f"Organization #{organization_id}: blocked ({error})")
            else:
                purged += 1
        self.stdout.write(self.style.SUCCESS(f"Purged: {purged}; blocked: {blocked}."))

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
