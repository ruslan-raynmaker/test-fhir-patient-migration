from datetime import date, datetime, timezone

from clinical.fhir.mappers import map_observation, map_patient, parse_datetime


def test_patient_prefers_official_name():
    resource = {
        "id": "p1",
        "meta": {"lastUpdated": "2024-03-01T10:00:00Z"},
        "name": [
            {"use": "nickname", "given": ["Bob"]},
            {"use": "official", "family": "Smith", "given": ["Robert", "James"]},
        ],
        "gender": "male",
        "birthDate": "1980-01-15",
    }

    patient = map_patient(resource)

    assert patient["given_name"] == "Robert James"
    assert patient["family_name"] == "Smith"
    assert patient["gender"] == "male"
    assert patient["birth_date"] == date(1980, 1, 15)
    assert patient["source_updated_at"] == datetime(2024, 3, 1, 10, 0, tzinfo=timezone.utc)


def test_patient_with_almost_nothing():
    patient = map_patient({"id": "p2"})

    assert patient["fhir_id"] == "p2"
    assert patient["given_name"] == ""
    assert patient["family_name"] == ""
    assert patient["birth_date"] is None


def test_patient_partial_birth_date_is_not_guessed():
    assert map_patient({"id": "p3", "birthDate": "1980"})["birth_date"] is None
    assert map_patient({"id": "p3", "birthDate": "1980-05"})["birth_date"] is None


def test_patient_unknown_gender_value_dropped():
    assert map_patient({"id": "p4", "gender": "M"})["gender"] == ""


def test_observation_quantity_prefers_loinc_coding():
    resource = {
        "id": "o1",
        "status": "final",
        "category": [{"coding": [{"code": "vital-signs"}]}],
        "code": {
            "coding": [
                {"system": "http://local/codes", "code": "HR", "display": "local hr"},
                {"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"},
            ],
        },
        "effectiveDateTime": "2024-05-01T09:30:00-05:00",
        "valueQuantity": {"value": 78, "unit": "beats/minute"},
    }

    obs = map_observation(resource)

    assert obs["code"] == "8867-4"
    assert obs["display"] == "Heart rate"
    assert obs["category"] == "vital-signs"
    assert obs["value_number"] == 78.0
    assert obs["value_unit"] == "beats/minute"
    assert obs["value_text"] == ""
    assert obs["effective_at"] == datetime(2024, 5, 1, 14, 30, tzinfo=timezone.utc)


def test_observation_components_blood_pressure():
    resource = {
        "id": "o2",
        "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9"}], "text": "Blood pressure"},
        "component": [
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic"}]},
                "valueQuantity": {"value": 120, "unit": "mmHg"},
            },
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic"}]},
                "valueQuantity": {"value": 80, "unit": "mmHg"},
            },
        ],
    }

    obs = map_observation(resource)

    assert obs["display"] == "Blood pressure"
    assert obs["value_number"] is None
    assert obs["components"] == [
        {"code": "8480-6", "display": "Systolic", "value": 120.0, "unit": "mmHg"},
        {"code": "8462-4", "display": "Diastolic", "value": 80.0, "unit": "mmHg"},
    ]


def test_observation_codeable_concept_value():
    resource = {
        "id": "o3",
        "code": {"text": "Smoking status"},
        "valueCodeableConcept": {"coding": [{"code": "8517006", "display": "Former smoker"}]},
        "effectivePeriod": {"start": "2024-01-01"},
    }

    obs = map_observation(resource)

    assert obs["display"] == "Smoking status"
    assert obs["code"] == ""
    assert obs["value_text"] == "Former smoker"
    assert obs["effective_at"] == datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_parse_datetime_handles_partial_and_garbage():
    assert parse_datetime("2024") == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert parse_datetime("2024-06") == datetime(2024, 6, 1, tzinfo=timezone.utc)
    assert parse_datetime("not a date") is None
    assert parse_datetime(None) is None
