# FHIR migration slice

Takes Patients and Observations from the HAPI FHIR R4 sandbox, maps them to a simple internal model in SQLite,
REST API and a small Vue UI on top. Plan for the real migration is in [Plan.md](Plan.md). Only synthetic
sandbox data.

## Run

```bash
poetry install && cd backend
poetry run python manage.py migrate
poetry run python manage.py import_fhir --patients 20 --only-with-observations
poetry run python manage.py runserver

cd ../frontend && npm install && npm run dev
```

Tests: `poetry run pytest`. Import can be run many times, records are upserted by FHIR id.
Flags: `--patients`, `--max-observations`, `--only-with-observations`, `--resume`.

## API

- `GET /api/patients/` - list with observation counts
- `GET /api/patients/{id}/` - patient with observations, 404 if missing

## Notes

Client retries 429/5xx/timeouts with exponential backoff and jitter, other 4xx fail at once.

Pagination: every search Bundle has a `link` with `relation=next`, `FHIRClient._pages` follows it page by page until
there is no next link. Page size is `_count` (`FHIR_PAGE_SIZE`, 50 by default), `limit` stops early. Observations are
fetched per patient, not with `_revinclude`, so one patient is one unit of work.

One patient = one transaction. If a patient fails, its id goes to the log and the run goes on. 3 failures
in a row stop the run, the server is probably down.

Progress (counters and `lastUpdated` of the last imported patient) is saved on `ImportRun` after every patient, not
at the end. Patients come sorted by `_lastUpdated`, so `import_fhir --resume` can continue the last unfinished run from
that checkpoint with `_lastUpdated=ge...`. Re-importing a patient twice is fine, it is an upsert.

`value[x]` goes to number + unit or to text, components go to a JSON list. Partial birth dates ("1980")
are saved as null, better nothing than a fake date.

Logs have only FHIR ids, no names and no values.

Not done: deletes on the source side, delta sync, some value types (Range, Ratio...). This is what I would
do next, then reconciliation by counts, and Postgres + workers for real volume.

## AI

Claude Code wrote Readme file and some code parts from my design, I ran and checked everything against the sandbox.
plan.md is human written, while I asked Claude for few advices
