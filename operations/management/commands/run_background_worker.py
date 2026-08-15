import time

from django.core.management.base import BaseCommand, CommandError

from operations.models import BackgroundJob
from operations.services import process_next_background_task


class Command(BaseCommand):
    help = "Process durable AI Candidate Matcher background tasks."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument(
            "--once",
            action="store_true",
            help="Process at most one available task and exit.",
        )
        mode.add_argument(
            "--burst",
            action="store_true",
            help="Process available tasks until the queue is empty and exit.",
        )
        parser.add_argument("--job", type=int, help="Limit work to one job ID.")
        parser.add_argument(
            "--poll-interval",
            type=float,
            default=2.0,
            help="Seconds between empty-queue polls in continuous mode.",
        )

    def handle(self, *args, **options):
        job_id = options["job"]
        if job_id is not None and not BackgroundJob.objects.filter(pk=job_id).exists():
            raise CommandError("The requested job does not exist.")
        if options["poll_interval"] <= 0:
            raise CommandError("--poll-interval must be greater than zero.")
        processed = 0
        while True:
            task = process_next_background_task(job_id=job_id)
            if task is not None:
                processed += 1
                self.stdout.write(f"Processed task {task.pk}: {task.status}.")
                if options["once"]:
                    break
                continue
            if options["once"] or options["burst"]:
                break
            time.sleep(options["poll_interval"])
        self.stdout.write(self.style.SUCCESS(f"Processed {processed} task(s)."))
