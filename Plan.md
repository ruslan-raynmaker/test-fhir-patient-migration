# Migration plan: 50k patients + observations

## 1. Overall approach

So the main thing is not to do one big copy in one night. It is a batch pipeline, we can run it many times, stop it and continue.
This is so that legacy stays the source of truth until we switch.

How it goes:

1. We'll do a dry run on ~500 patients in non-prod. Here we find the bad data early and fix the mapping if needed.
2. Then we do full backfill, legacy still works as usual.
3. Delta runs with `_lastUpdated=gt{watermark}` until the delta is small.
4. Then we do a short write freeze on legacy, last delta, validation, we deicde go/no-go, switch behind a feature flag.

About api limits, first we agree on a rate budget with the legacy team, сфгіу it is a clinical system and people work in it
while we migrate. On our side a small worker pool, we respect `429` and `Retry-After`, backoff with jitter on 5xx and
timeouts, and a circuit breaker that pauses the run when errors go up. Backfill runs at night.

About Reliability is simple: work goes in batcehs of patient ids through a queue. A failed batch is retried, after n tries it
goes to DLQ with the reason and the run continues. All writes are upserts by `fhir_id`, so re-runs are safe. Checkpoint
after every batch, so a crash continues from where it stopped. Raw fhir json goes to staging first, if the mapping has
a bug we re-transorm from staging and don't call legacy again.

For observability every run has a `run_id`, it is in every log line and every row. Logs have only resource ids. Metrics
are records/s, error rate, 429 count, DLQ size. Alerts on error rate and on a stuck run. At the end a short report: in /
out/ skipped/failed.

## 2. Data mapping

We take only what the new service needs, not all of FHIR. Less PHI is also good.

For Patient we take the id as `fhir_id` plus `source_system`, this is our key for upserts. MRN we take from
`identifier[]` where the sstem is our MRN system, not just the first identifier. Name from `name[]`, first we look for
`use=official`, then `usual`, then just the first one, and `name.text` as a fallback. Gender only if it is one of the 4 FHIR
codes, everything else is empty + warning. Birth date s is, but partial dates like "1980" we do not pad, we keep the
precision or store null. And `meta.lastUpdated` goes to `source_updated_at`, we need it later for delta sync.

For Observayion the id and `subject.reference` give us `fhir_id` and `patient_id`. The reference can be relative, absolute
or missing, if mising it goes to DLQ, we never guess the patient. Code from `code.coding[]`, LOINC first, else the first
coding, `code.text` as a fallback for display. Category from `category[0]`, status as is, but we need to ask clinicians what
to do with `entered-in-error`, probably skip. Dae from `effectiveDateTime`, or `effectiveInstant`, or `effectivePeriod.start`,
or `issued`, stored in UTC. Value is the tricky part because `value[x]` is polymorphic: Quantity and Integer go to number +
unit, CodeableConcept, String and Boolean go to text. Components (blood pressure for example, it has no top level value, only
systolic and diastolic) go to a small JSON list.

What the mapper can't handle (Range, Ratio, SampledData, `dataAbsentReason`...) we count and put in the
report, we do not drop silently. Then we look and decide per type if it needs a field. Important that units stay as is, UCUM
normalisation is a separate step and needs a clinician to check.

## 3. Validation

As p4er validation first we check counts: `Patient?_summary=count` and `Observation?_summary=count` vs our tables, plus observations
per patient.

Then we check content: random 1-2% sample plus all records that used a fallback path. We fetch them again from
legacy, thn=n map again and compare field by field with what we saved
Then we check integrity: there should be no orphan observations, no duplicate `fhir_id`, no birth dates in the future.

Then we check distributions: gender split, observations per patient, top codes. Source and target should look the same,
this catches systematic mapping bugs that a sample can miss.
And also a human check, clinicians or ops open some known patients in the new UI before go-live.

All of this is one script and we run it after every delta. Important that go/no-go criteria are written down before the
last run, for example 100% patients, 99.9%+ observations, DLQ fully checked.

## 4. Safety (PHI)

So first rule, only synthetic data in dev, tests and demos. Prod data never goes to laptops, tickets, Slack or AI tools.

Then encryption: TLS in transit, encryptinon at rest for the DB, staging bucket and backups. Staging has a TTL and we
delete it after sign-off.
It's really important that logs, metrics, error tracker and DLQ messages have only resource ids, no names, birth dates or values.
Exception messages we clean too, because payloads like to leak into stack traces.

Access: the migration has its own read-only credential for legacy and a limited write role for the target. Secrets live
in a vault and we rotate them after the migration. Every access to PHI is logged for audit.
And we migrate only the fields we really need, less PHI is less risk. BAA with every vendor in the data path, everything
runs inside the compliant network.

## 5. Rollback

Main thing here is that we only read from legacy and it stays the source of truth until cutover. So if the migration
fails we lose time, not data.
If something fails in the middle of backfill, the run pauses (circuit breaker or we stop it by hand), we fix the problem
and continue from the checkpoint. Upserts are idempotent, so there is nothing to clean up.

If we find a bad mapping, we fix the mapper and transform again from raw staging, no need to call legacy again. If some
rows must go, every row has a `run_id`, so we delete exactly by run id. Also we do a DB snapshot before every full run.
If the problem shows up after cutover, reads are behind a feature flag, we just switch it back to legacy. The freeze
window guarantees that legacy did not change. If the new service already took some writes, we export them and reconcile
by hand, so we keep this window short and watch it.

And we test the rollback once in staging. A rollback plan that nobody tried is not a plan)
