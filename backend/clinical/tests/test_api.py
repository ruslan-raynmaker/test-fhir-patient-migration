import pytest
from rest_framework.test import APIClient

from clinical.models import Observation, Patient

pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def patient():
    patient = Patient.objects.create(fhir_id="p1", given_name="Jane", family_name="Doe", gender="female")
    Observation.objects.create(
        patient=patient, fhir_id="o1", display="Heart rate", value_number=72, value_unit="bpm"
    )
    Observation.objects.create(patient=patient, fhir_id="o2", display="Smoking status", value_text="Never")
    return patient


def test_list_patients_includes_observation_count(api, patient):
    Patient.objects.create(fhir_id="p2", family_name="Adams")

    response = api.get("/api/patients/")

    assert response.status_code == 200
    body = response.json()
    assert [p["fhir_id"] for p in body] == ["p2", "p1"]
    assert [p["observation_count"] for p in body] == [0, 2]
    assert "observations" not in body[0]


def test_patient_detail_has_nested_observations(api, patient):
    response = api.get(f"/api/patients/{patient.pk}/")

    assert response.status_code == 200
    body = response.json()
    assert body["family_name"] == "Doe"
    assert {o["fhir_id"] for o in body["observations"]} == {"o1", "o2"}


def test_unknown_patient_is_404(api):
    assert api.get("/api/patients/12345/").status_code == 404


def test_api_is_read_only(api, patient):
    assert api.post("/api/patients/", {"fhir_id": "x"}).status_code == 405
    assert api.delete(f"/api/patients/{patient.pk}/").status_code == 405
