# FHIR migration slice

Takes Patients and Observations from the HAPI FHIR R4 sandbox, maps them to a simple internal model in SQLite,
REST API and a small Vue UI on top. Plan for the real migration is in [Plan.md](Plan.md). Only synthetic
sandbox data.

## Notes

Client retries 429/5xx/timeouts with exponential backoff and jitter, other 4xx fail at once.

Pagination: every search Bundle has a `link` with `relation=next`, `FHIRClient._pages` follows it page by page until
there is no next link. Page size is `_count` (`FHIR_PAGE_SIZE`, 50 by default), `limit` stops early. Observations are
fetched per patient, not with `_revinclude`, so one patient is one unit of work.

`value[x]` goes to number + unit or to text, components go to a JSON list. Partial birth dates ("1980")
are saved as null, better nothing than a fake date.

## AI

Claude Code wrote Readme file and some code parts from my design, I ran and checked everything against the sandbox.
plan.md is human written, while I asked Claude for few advices
