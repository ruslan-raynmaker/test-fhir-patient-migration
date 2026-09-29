from django.core.management.base import BaseCommand, CommandError

from clinical.importer import run_import
from clinical.models import ImportRun


class Command(BaseCommand):
    help = "Import patients and their observations from the FHIR server"

    def add_arguments(self, parser):
        parser.add_argument("--patients", type=int, default=20, help="how many patients to import")
        parser.add_argument(
            "--max-observations", type=int, default=200,
            help="cap of observations per patient, 0 = no cap",
        )
        parser.add_argument(
            "--only-with-observations", action="store_true",
            help="only patients that have at least one final observation (nicer for a demo)",
        )
        parser.add_argument("--resume", action="store_true", help="continue the last run that did not complete")

    def handle(self, *args, **options):
        since = None
        if options["resume"]:
            last = ImportRun.objects.order_by("-pk").first()
            unfinished = [ImportRun.Status.RUNNING, ImportRun.Status.FAILED]
            if not last or last.status not in unfinished or not last.checkpoint:
                raise CommandError("nothing to resume, last run finished")
            since = last.checkpoint
            self.stdout.write(f"resuming run #{last.pk} from {since}")

        run = run_import(
            patient_limit=options["patients"],
            max_observations=options["max_observations"] or None,
            only_with_observations=options["only_with_observations"],
            since=since,
        )

        summary = (
            f"run #{run.pk} {run.status}: {run.patients_imported} patients, "
            f"{run.observations_imported} observations, {len(run.failures)} failed"
        )
        for failure in run.failures:
            self.stderr.write(f"  patient {failure['fhir_id']}: {failure['error']}")

        if run.status == ImportRun.Status.FAILED:
            raise CommandError(f"{summary}\n{run.error}")
        self.stdout.write(self.style.SUCCESS(summary))
