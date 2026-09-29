import pytest
import requests
import responses

from clinical.fhir.client import FHIRClient, FHIRRequestError, FHIRUnavailable

BASE = "https://fhir.test/baseR4"


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("clinical.fhir.client.time.sleep", lambda s: None)


def bundle(ids, next_url=None, resource_type="Patient"):
    links = [{"relation": "next", "url": next_url}] if next_url else []
    return {
        "resourceType": "Bundle",
        "link": links,
        "entry": [{"resource": {"resourceType": resource_type, "id": i}} for i in ids],
    }


@responses.activate
def test_retries_on_5xx_and_then_succeeds():
    responses.get(f"{BASE}/Patient", status=503)
    responses.get(f"{BASE}/Patient", status=502)
    responses.get(f"{BASE}/Patient", json=bundle(["1"]))

    result = list(FHIRClient(base_url=BASE, max_retries=3).search("Patient"))

    assert [r["id"] for r in result] == ["1"]
    assert len(responses.calls) == 3


@responses.activate
def test_retries_on_connection_error():
    responses.get(f"{BASE}/Patient", body=requests.ConnectionError("boom"))
    responses.get(f"{BASE}/Patient", json=bundle(["1"]))

    result = list(FHIRClient(base_url=BASE, max_retries=2).search("Patient"))

    assert len(result) == 1


@responses.activate
def test_gives_up_after_max_retries():
    responses.get(f"{BASE}/Patient", status=503)

    with pytest.raises(FHIRUnavailable):
        list(FHIRClient(base_url=BASE, max_retries=2).search("Patient"))

    assert len(responses.calls) == 3


@responses.activate
def test_4xx_is_not_retried():
    responses.get(f"{BASE}/Patient", status=400)

    with pytest.raises(FHIRRequestError):
        list(FHIRClient(base_url=BASE, max_retries=3).search("Patient"))

    assert len(responses.calls) == 1


def test_retry_after_header_wins_over_backoff():
    client = FHIRClient(base_url=BASE)

    assert client._backoff(1, retry_after="7") == 7
    assert 1 <= client._backoff(1) <= 1.5
    assert 4 <= client._backoff(3) <= 6


@responses.activate
def test_follows_next_links_and_respects_limit():
    page2 = f"{BASE}?_getpages=abc&_getpagesoffset=2"
    responses.get(f"{BASE}/Patient", json=bundle(["1", "2"], next_url=page2))
    responses.get(page2, json=bundle(["3", "4"]))

    client = FHIRClient(base_url=BASE)

    assert [r["id"] for r in client.search("Patient")] == ["1", "2", "3", "4"]
    assert [r["id"] for r in client.search("Patient", limit=3)] == ["1", "2", "3"]


@responses.activate
def test_next_link_to_another_host_is_rejected():
    responses.get(f"{BASE}/Patient", json=bundle(["1"], next_url="https://evil.test/page2"))

    with pytest.raises(FHIRRequestError):
        list(FHIRClient(base_url=BASE).search("Patient"))
