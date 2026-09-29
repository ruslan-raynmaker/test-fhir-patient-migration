import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .fhir.client import FHIRClient, FHIRError
from .fhir.mappers import map_observation, map_patient
from .models import ImportRun, Observation, Patient

logger = logging.getLogger(__name__)

MAX_CONSECUTIVE_FAILURES = 3

OBSERVATION_UPDATE_FIELDS = [
    "patient", "status", "category", "code", "code_system", "display", "effective_at",
    "value_number", "value_unit", "value_text", "components",
]


def run_import(client=None, patient_limit=20, max_observations=200, only_with_observations=False, since=None):
    client = client or FHIRClient()
    run = ImportRun.objects.create(checkpoint=since or "")
    logger.info("import run %s started (patient_limit=%s, since=%s)", run.pk, patient_limit, since)

    params = {"_count": settings.FHIR_PAGE_SIZE, "_sort": "_lastUpdated"}
    if only_with_observations:
        params["_has:Observation:patient:status"] = "final"
    if since:
        params["_lastUpdated"] = f"ge{since}"

    consecutive_failures = 0
    try:
        for resource in client.search("Patient", params, limit=patient_limit):
            fhir_id = resource.get("id")
            try:
                obs_count = _import_patient(client, resource, max_observations)
            except Exception as exc:
                logger.exception("patient %s failed", fhir_id)
                run.failures.append({"fhir_id": fhir_id, "error": f"{exc.__class__.__name__}: {exc}"})
                run.save(update_fields=["failures"])
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    raise FHIRError(f"{consecutive_failures} patients failed in a row, aborting")
                continue

            consecutive_failures = 0
            run.patients_imported += 1
            run.observations_imported += obs_count
            run.checkpoint = (resource.get("meta") or {}).get("lastUpdated") or run.checkpoint
            run.save(update_fields=["patients_imported", "observations_imported", "checkpoint"])
            logger.info("patient %s imported with %s observations", fhir_id, obs_count)
    except FHIRError as exc:
        run.status = ImportRun.Status.FAILED
        run.error = str(exc)
        logger.error("import run %s failed: %s", run.pk, exc)
    else:
        run.status = ImportRun.Status.PARTIAL if run.failures else ImportRun.Status.COMPLETED

    run.finished_at = timezone.now()
    run.save()
    logger.info(
        "import run %s finished: status=%s patients=%s observations=%s failures=%s",
        run.pk, run.status, run.patients_imported, run.observations_imported, len(run.failures),
    )
    return run


def _import_patient(client, resource, max_observations):
    patient_data = map_patient(resource)
    fhir_id = patient_data.pop("fhir_id")

    obs_params = {"subject": f"Patient/{fhir_id}", "_count": settings.FHIR_PAGE_SIZE}
    observations = [
        map_observation(obs)
        for obs in client.search("Observation", obs_params, limit=max_observations)
    ]

    with transaction.atomic():
        patient, _ = Patient.objects.update_or_create(fhir_id=fhir_id, defaults=patient_data)
        Observation.objects.bulk_create(
            [Observation(patient=patient, **data) for data in observations],
            update_conflicts=True,
            unique_fields=["fhir_id"],
            update_fields=OBSERVATION_UPDATE_FIELDS,
        )
    return len(observations)
