import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from clinical.fhir.client import FHIRUnavailable
from clinical.importer import run_import
from clinical.models import ImportRun, Observation, Patient

pytestmark = pytest.mark.django_db


class FakeClient:
    def __init__(self, patients, observations=None, broken_patients=(), crash_after=None):
        self.patients = patients
        self.observations = observations or {}
        self.broken_patients = set(broken_patients)
        self.crash_after = crash_after
        self.calls = []

    def search(self, resource_type, params=None, limit=None):
        self.calls.append((resource_type, dict(params or {})))
        if resource_type == "Patient":
            for i, resource in enumerate(self.patients[:limit]):
                if i == self.crash_after:
                    raise RuntimeError("process died")
                yield resource
            return
        patient_id = params["subject"].split("/")[1]
        if patient_id in self.broken_patients:
            raise FHIRUnavailable("giving up after 5 attempts: HTTP 503")
        yield from self.observations.get(patient_id, [])


def patient(pid, family="Doe", updated=None):
    resource = {"resourceType": "Patient", "id": pid, "name": [{"family": family, "given": ["Jane"]}]}
    if updated:
        resource["meta"] = {"lastUpdated": updated}
    return resource


def observation(oid, value=1):
    return {
        "resourceType": "Observation",
        "id": oid,
        "status": "final",
        "code": {"text": "Heart rate"},
        "valueQuantity": {"value": value, "unit": "bpm"},
    }


def test_import_saves_patients_with_observations():
    client = FakeClient(
        patients=[patient("p1"), patient("p2")],
        observations={"p1": [observation("o1"), observation("o2")]},
    )

    run = run_import(client=client)

    assert run.status == ImportRun.Status.COMPLETED
    assert (run.patients_imported, run.observations_imported) == (2, 2)
    assert Patient.objects.get(fhir_id="p1").observations.count() == 2
    assert Patient.objects.get(fhir_id="p2").observations.count() == 0


def test_rerun_updates_instead_of_duplicating():
    run_import(client=FakeClient([patient("p1")], {"p1": [observation("o1", value=70)]}))
    run_import(client=FakeClient([patient("p1", family="Smith")], {"p1": [observation("o1", value=95)]}))

    assert Patient.objects.count() == 1
    assert Observation.objects.count() == 1
    assert Patient.objects.get().family_name == "Smith"
    assert Observation.objects.get().value_number == 95


def test_failing_patient_is_skipped_and_reported():
    client = FakeClient(
        patients=[patient("p1"), patient("bad"), patient("p3")],
        observations={"p1": [observation("o1")], "p3": [observation("o3")]},
        broken_patients=["bad"],
    )

    run = run_import(client=client)

    assert run.status == ImportRun.Status.PARTIAL
    assert run.patients_imported == 2
    assert [f["fhir_id"] for f in run.failures] == ["bad"]
    assert not Patient.objects.filter(fhir_id="bad").exists()


def test_run_aborts_when_server_looks_down():
    ids = ["a", "b", "c", "d", "e"]
    client = FakeClient(patients=[patient(i) for i in ids], broken_patients=ids)

    run = run_import(client=client)

    assert run.status == ImportRun.Status.FAILED
    assert len(run.failures) == 3
    assert Patient.objects.count() == 0


def test_crash_mid_run_keeps_progress_in_db():
    client = FakeClient(
        patients=[patient("p1", updated="2024-01-01T00:00:00Z"), patient("p2", updated="2024-01-02T00:00:00Z"), patient("p3")],
        observations={"p1": [observation("o1")], "p2": [observation("o2")]},
        crash_after=2,
    )

    with pytest.raises(RuntimeError):
        run_import(client=client)

    run = ImportRun.objects.get()
    assert run.status == ImportRun.Status.RUNNING
    assert (run.patients_imported, run.observations_imported) == (2, 2)
    assert run.checkpoint == "2024-01-02T00:00:00Z"


def test_since_is_passed_to_patient_search():
    client = FakeClient(patients=[patient("p1")])

    run = run_import(client=client, since="2024-01-02T00:00:00Z")

    resource_type, params = client.calls[0]
    assert resource_type == "Patient"
    assert params["_lastUpdated"] == "ge2024-01-02T00:00:00Z"
    assert params["_sort"] == "_lastUpdated"
    assert run.checkpoint == "2024-01-02T00:00:00Z"


def test_resume_flag_continues_last_unfinished_run(monkeypatch):
    ImportRun.objects.create(status=ImportRun.Status.COMPLETED, checkpoint="2024-01-01T00:00:00Z")
    ImportRun.objects.create(status=ImportRun.Status.FAILED, checkpoint="2024-01-05T00:00:00Z")
    captured = {}

    def fake_run_import(**kwargs):
        captured.update(kwargs)
        return ImportRun.objects.create(status=ImportRun.Status.COMPLETED)

    monkeypatch.setattr("clinical.management.commands.import_fhir.run_import", fake_run_import)
    call_command("import_fhir", "--resume")

    assert captured["since"] == "2024-01-05T00:00:00Z"


def test_resume_only_when_last_run_is_unfinished():
    ImportRun.objects.create(status=ImportRun.Status.FAILED, checkpoint="2024-01-01T00:00:00Z")
    ImportRun.objects.create(status=ImportRun.Status.COMPLETED, checkpoint="2024-01-05T00:00:00Z")

    with pytest.raises(CommandError):
        call_command("import_fhir", "--resume")
