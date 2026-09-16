# Production ingestion incident: ThreatFox oversized response (11:31Z)

- **Recorded:** `2026-09-13T11:33:26+00:00` (diagnosis completed)
- **Latest monitor evidence observed:** `2026-09-13T11:32:58.866157+00:00`
- **Monitor state:** `actionable_failure`
- **Latest monitor event:** `fd7fe07b-79fc-4411-8f9e-8cc64f3131db`
- **Latest correlation:** `0ac89a86-65fa-488e-8a20-a76bbc25e26a`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Recovery-gate event:** `1794ec18-f2c5-406b-ac16-41475f15c0b5` (acquired against the prior actionable refresh at `2026-09-13T11:30:58.718232+00:00`)

## Impact and data-integrity state

The latest ingestion run is failed but usable for its successful sources: 37 of
38 sources completed and 5,943 documents were newly persisted. ThreatFox Recent
Indicators (Abuse.ch) returned no items. The latest full-success run is
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at
`2026-09-11T12:06:50.050468+00:00`. Persisted counts are 31,107 source
documents, 186 reports, and 201 publications. No deletion, volume reset,
migration rewrite, backup mutation, credential rotation, or public-assessment
edit was performed.

## Diagnosis and evidence

**Cause confidence: high.** This is a deterministic ThreatFox/provider bounded-
response failure, not a web, proxy, worker, scheduler, database, disk, backup,
migration, or certificate outage. The failed `source_run` records:
`status=failed`, no HTTP status, `item_count=0`, `retry_count=0`,
`cache_state=miss`, `error_classification=oversized_response`, and
`error_detail=response exceeds 10485760 bytes`.

Web, monitor, scheduler, backup, and PostgreSQL containers are running healthy
with restart count 0; the worker is intentionally absent/reserved. PostgreSQL
is accepting connections and Alembic is at `0015_contradiction_lifecycle`.
Scheduler heartbeat was fresh at `2026-09-13T11:32:24Z`. Host storage is 42%
used with 280G available, memory has 52GiB available, and the open-file limit
is 4096. Backup metadata is present mode 600; the latest encrypted backup
artifact is present. The served certificate is valid through
`2026-09-13T19:39:23Z` but below the configured minimum lifetime and is a
separate renewal risk. Repository-side Compose validation remains blocked by
missing production-only `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables.

## Recovery gate and action

The recovery gate acquired the actionable evidence at
`2026-09-13T11:31:55Z` (gate event equals monitor event above); the prior
30-minute cooldown had expired and no lock was present. After read-only
verification, the gate was completed with outcome `failed` and the lock was
removed. No retry, restart, deployment, migration, response-limit change,
credential change, or data mutation was performed. Re-running unchanged
ingestion would reproduce the same bounded-response failure and add provider
load without repairing it.

## Prevention and rollback

Validate pagination, provider-side filtering, or an alternate ThreatFox
endpoint against an offline fixture before deploying a source change. Preserve
failed source rows and partial-run visibility and retain an oversized-response
regression fixture. Renew the certificate before its minimum-lifetime
threshold is breached. No rollback is required because no application or data
change was made.

## Recovery-job follow-up (11:47Z cooldown suppression)

- **Recorded:** `2026-09-13T11:47:36.677457+00:00`
- **Latest monitor evidence observed:** `2026-09-13T11:46:59.863786+00:00`
- **Monitor state:** `actionable_failure`
- **Monitor event:** `e1d7c967-409a-4898-a5f6-6893de3c363c`
- **Correlation:** `71e538d3-9e06-48e6-bdb7-1d119ede1745`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Gate result:** suppressed; the 30-minute cooldown remained active after the
  `2026-09-13T11:31:55.833690+00Z` attempt. The recovery lock was absent.

Read-only verification remains unchanged: web, monitor, scheduler, and
PostgreSQL are healthy with zero restarts; worker is intentionally exited and
reserved; liveness/readiness returned 200; PostgreSQL accepts connections at
migration `0015_contradiction_lifecycle`; and the scheduler heartbeat was fresh
at `2026-09-13T11:47:54Z`. Host resources remain non-pressured (42% disk use,
280G available, 52GiB available memory, open-file limit 4096). Encrypted backup
artifacts and metadata remain present. The certificate remains valid through
`2026-09-13T19:39:23Z` but below its configured minimum-lifetime threshold.
No retry, restart, deployment, migration, response-limit change, credential
change, or data mutation was performed. The same high-confidence deterministic
ThreatFox `oversized_response` failure remains the sole source-level cause.

## Recovery-job follow-up (12:16Z gate acquisition)

- **Recorded:** `2026-09-13T12:18:25+00:00`
- **Monitor evidence observed:** `2026-09-13T12:16:01.951255+00:00`
- **Monitor state:** `actionable_failure`
- **Monitor event:** `4a4f571f-4ba7-4018-bd3a-385349b79e66`
- **Correlation:** `d984cccf-b77c-4fa2-8675-ced1af0d20e5`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Gate:** acquired after the 30-minute cooldown; audit records attempted and
  completed with outcome `failed`; the recovery lock is absent.

The latest read-only checks are unchanged: web, scheduler, monitor, backup,
and PostgreSQL are healthy with zero restarts; PostgreSQL accepts connections
at migration `0015_contradiction_lifecycle`; the latest attempt is 37/38
sources successful with 5,943 new documents, while the ThreatFox source remains
failed with `oversized_response` and `response exceeds 10485760 bytes`. Host
storage is 42% used with 280G available, memory has 52GiB available, and the
open-file limit is 4096. Backup metadata and encrypted artifacts are present.
The certificate is valid through `2026-09-13T19:39:23Z` but remains below the
configured minimum lifetime and is a separate renewal risk.

No retry, restart, deployment, migration, response-limit change, credential
change, or data mutation was performed. An intervening monitor refresh caused
an additional failed completion audit for event
`1e7a3c6a-acec-4bd5-b963-53768c88ce8c`; the intended gate event
`4a4f571f-4ba7-4018-bd3a-385349b79e66` was then completed explicitly, and the
lock was verified absent. This audit irregularity does not alter service or
data state.
