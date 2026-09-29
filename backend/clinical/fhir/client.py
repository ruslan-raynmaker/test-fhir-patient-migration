import logging
import random
import time
from urllib.parse import urlparse

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
MAX_BACKOFF = 60


class FHIRError(Exception):
    pass


class FHIRUnavailable(FHIRError):
    pass


class FHIRRequestError(FHIRError):
    pass


class FHIRClient:
    def __init__(self, base_url=None, max_retries=None):
        self.base_url = (base_url or settings.FHIR_BASE_URL).rstrip("/")
        self.max_retries = settings.FHIR_MAX_RETRIES if max_retries is None else max_retries
        self.session = requests.Session()
        self.session.headers["Accept"] = "application/fhir+json"

    def search(self, resource_type, params=None, limit=None):
        yielded = 0
        for bundle in self._pages(resource_type, params):
            for entry in bundle.get("entry", []):
                resource = entry.get("resource") or {}
                if resource.get("resourceType") != resource_type:
                    continue
                yield resource
                yielded += 1
                if limit and yielded >= limit:
                    return

    def _pages(self, resource_type, params):
        url = f"{self.base_url}/{resource_type}"
        page = 1
        while url:
            bundle = self._get(url, params)
            if bundle.get("resourceType") != "Bundle":
                raise FHIRRequestError(f"expected a Bundle, got {bundle.get('resourceType')!r}")
            logger.debug("%s search page %s: %s entries", resource_type, page, len(bundle.get("entry", [])))
            yield bundle
            url = self._next_link(bundle)
            params = None
            page += 1

    def _next_link(self, bundle):
        for link in bundle.get("link", []):
            if link.get("relation") == "next":
                url = link.get("url")
                if url and urlparse(url).netloc != urlparse(self.base_url).netloc:
                    raise FHIRRequestError("next link points to a different host")
                return url
        return None

    def _get(self, url, params=None):
        attempts = self.max_retries + 1
        last_error = None

        for attempt in range(1, attempts + 1):
            retry_after = None
            try:
                response = self.session.get(url, params=params, timeout=settings.FHIR_TIMEOUT)
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_error = exc.__class__.__name__
            else:
                if response.status_code in RETRYABLE_STATUSES:
                    last_error = f"HTTP {response.status_code}"
                    retry_after = response.headers.get("Retry-After")
                elif response.status_code >= 400:
                    raise FHIRRequestError(f"HTTP {response.status_code} for {response.url}")
                else:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise FHIRRequestError("response is not valid JSON") from exc

            if attempt < attempts:
                delay = self._backoff(attempt, retry_after)
                logger.warning(
                    "FHIR request failed (%s), attempt %s/%s, retrying in %.1fs",
                    last_error, attempt, attempts, delay,
                )
                time.sleep(delay)

        raise FHIRUnavailable(f"giving up after {attempts} attempts: {last_error}")

    def _backoff(self, attempt, retry_after=None):
        if retry_after and retry_after.isdigit():
            return min(int(retry_after), MAX_BACKOFF)
        delay = 2 ** (attempt - 1)
        return min(delay + random.uniform(0, delay / 2), MAX_BACKOFF)
