from django.core.management.base import BaseCommand, CommandError

from operations.production import (
    ProductionReadinessError,
    run_production_readiness_checks,
)


class Command(BaseCommand):
    help = "Validate production settings, database, migrations, static, and storage."

    def handle(self, *args, **options):
        try:
            completed = run_production_readiness_checks()
        except ProductionReadinessError as error:
            raise CommandError(str(error)) from error

        for check_name in completed:
            self.stdout.write(f"OK: {check_name}.")
        self.stdout.write(self.style.SUCCESS("Production readiness checks passed."))
