# Production ingestion incident: ThreatFox oversized response

- **Observed:** 2026-09-12T20:00:51.685946Z
- **Monitor event:** `a2d78640-143f-4cb3-a7f5-39733aaafc4f`
- **Correlation:** `c39db4c5-3cac-4423-83a6-204eba486a9b`
- **Run:** `e3f0e4df-f6eb-5828-9eb3-25de925befbc`
- **Monitor state:** `actionable_failure`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200

## Impact

The 2026-09-12 scheduled ingestion completed with partial source coverage: 37/38 sources succeeded and one source failed. The latest full-success run remains 2026-09-11; the latest usable projection is the partial run. Existing persisted evidence and publications were not deleted or rewritten.

## Diagnosis

The failed source is `threatfox-recent-indicators-abuse-ch` (ThreatFox Recent Indicators, Abuse.ch). PostgreSQL records `oversized_response` with detail `response exceeds 10485760 bytes`, no HTTP status, and `retry_count=0`. The source has `consecutive_failure_count=2`; its last successful retrieval was 2026-09-11T12:06:49.272951Z. This is a source/provider-size-boundary failure, not a web, proxy, worker, scheduler, database, disk, memory, file-descriptor, certificate, backup, or migration failure.

## Actions

1. Read the monitor evidence and acquired the recovery gate at 2026-09-12T20:01:53.917542Z. The gate event was `3777ffd2-2ede-4764-8a9d-98a61ee88668`.
2. Performed read-only diagnostics. Web, scheduler, monitor, and PostgreSQL containers are healthy; worker is intentionally reserved and exited 0. PostgreSQL accepts connections and is at migration revision `0015_contradiction_lifecycle`.
3. Did not retry or raise the response limit. A retry would reproduce the deterministic upstream-size failure, while raising the cap would weaken the bounded-ingestion safety control without validation. The recovery lock must be released with a failed/no-safe-recovery outcome by the recovery job.

## Follow-up

Validate a bounded ThreatFox pagination/filtering or streaming approach, retain the 10 MiB safety limit unless a reviewed configuration change proves safe, add a fixture for oversized responses, and deploy only after focused tests and `./scripts/update-app.sh` verification. Continue preserving partial-run and source-level failure metadata.

## Recovery-job follow-up

- **Observed:** 2026-09-12T23:02:04.675972Z
- **Monitor event:** `945cea2c-1c09-4a4c-84f5-e9b04b5e4bf9`
- **Correlation:** `2475e0a8-c0a5-40f6-959c-f4be5dad4050`
- **Run:** `e3f0e4df-f6eb-5828-9eb3-25de925befbc`
- **Gate:** acquired at 2026-09-12T23:02:10.862097Z; completed with `failed` / no-safe-recovery outcome after read-only diagnosis.

The current evidence is the same bounded ThreatFox source failure, so this
follow-up extends the existing incident rather than creating a duplicate.
No ingestion retry, response-limit change, restart, deployment, migration,
or data mutation was performed. Web, private readiness, scheduler heartbeat,
PostgreSQL, backup metadata, disk, memory, file descriptors, and certificate
routing remain operational based on the captured checks.

## Recovery-job follow-up (cooldown suppression)

- **Observed:** 2026-09-12T23:31:06.729674+00:00
- **Monitor event:** `efcde819-5c6f-4508-b260-b3250d3e89d4`
- **Correlation:** `c2f3d0b4-d9d1-4c03-8290-2551b56953e2`
- **Run:** `e3f0e4df-f6eb-5828-9eb3-25de925befbc`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Gate event:** `24983dee-4df2-4cf1-9e46-f4a2b9ccbd95`; suppressed at 2026-09-12T23:32:08.601682+00:00 because the 30-minute recovery cooldown was active.

Read-only diagnosis confirms the same deterministic ThreatFox `oversized_response`
(source limit 10 MiB) failure: 37/38 sources succeeded, PostgreSQL remains
healthy at migration `0015_contradiction_lifecycle`, and no recovery, restart,
deployment, migration, or data mutation was performed. The existing partial
run and persisted evidence remain intact; this is an extension of the existing
incident, not a new incident.

The monitor refreshed the same actionable state at 2026-09-12T23:33:06.873989+00:00
with event `618d9d95-8671-421f-be7f-2e626f8c7261`, correlation
`d230dfe2-7e28-4f7b-8d80-def9f12521d8`, run
`e3f0e4df-f6eb-5828-9eb3-25de925befbc`, and endpoint/status
`http://web:8000/api/v1/ops/run-status` / HTTP 200. It remains the same
source-level failure; the prior cooldown suppression governs this job.

## Recovery-job follow-up (2026-09-13)

- **Observed:** 2026-09-13T00:46:12.084549+00:00
- **Monitor event:** `1060fe2e-9e45-4ba1-bdf0-8a0d21492cd2`
- **Correlation:** `5ec75ef6-308a-40ee-b91f-6600857350b2`
- **Run:** `e3f0e4df-f6eb-5828-9eb3-25de925befbc`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Gate:** acquired at 2026-09-13T00:46:48.201089+00; completed with `failed` / no-safe-recovery outcome.

Read-only verification again found the same deterministic ThreatFox
`oversized_response` failure (`response exceeds 10485760 bytes`): 37/38
sources succeeded, the latest run remains partial/failed, web/monitor/scheduler/
PostgreSQL/backup/certificate/disk/memory/file-descriptor health is otherwise
operational, and migration revision remains `0015_contradiction_lifecycle`.
No retry, response-limit change, restart, deployment, migration, or data
mutation was performed. Existing partial evidence and publications remain
intact. Follow-up remains bounded ThreatFox pagination/filtering or streaming
with a fixture and focused tests before any deployment.

## Recovery-job follow-up (2026-09-13 cooldown suppression)

- **Observed:** 2026-09-13T01:01:13.164529+00
- **Monitor event:** `bac72cf6-c132-4d7e-b8d3-71d530b5a640`
- **Correlation:** `3232d69a-d9c8-4163-bb8a-b8bff5dbc486`
- **Run:** `e3f0e4df-f6eb-5828-9eb3-25de925befbc`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Gate:** suppressed at 2026-09-13T01:01:38.669539+00 because the 30-minute recovery cooldown was active.
- **Verification gate event:** `83deec2a-6d9a-4650-a342-1a2c77d7af6e`, correlation `cbb8dad4-e864-4bdf-920d-036a37e8a2a5`, suppressed at 2026-09-13T01:03:57.512191+00 for the same cooldown.
- **Latest evidence refresh:** event `7218f7ad-ef60-476e-b9a0-74a413a505e3`, observed 2026-09-13T01:04:13.385893+00, correlation `b2a7a5ad-4a0d-4e7f-9833-5e7e5448eb60`, state `actionable_failure`, same run.

Read-only verification confirms the same deterministic ThreatFox
`oversized_response` failure (`response exceeds 10485760 bytes`): 37/38
sources succeeded, the run is `failed` with one failed source, and the latest
full-success run is 2026-09-11. Web live/readiness, scheduler heartbeat,
monitor, PostgreSQL connectivity, backup volume state, disk, memory,
file-descriptor, Caddy configuration, and certificate validity remain
operational. PostgreSQL remains at migration `0015_contradiction_lifecycle`.
Reports remain intact (186 reports, 201 report versions, and 201 publications; latest publication
2026-09-11T22:24:37Z). No retry, restart, deployment, migration, response-limit
change, credential change, or data mutation was performed. The existing
incident remains open pending a bounded ThreatFox retrieval fix and focused
tests.

## Recovery-job follow-up (2026-09-13 latest actionable evidence)

- **Observed:** 2026-09-13T01:18:14.389787+00:00
- **Monitor event:** `a902a8b9-e73e-490c-88a5-13710aa817c0`
- **Correlation:** `f62ecffd-7869-4fb0-bbb6-ebaab83d053e`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Run:** `e3f0e4df-f6eb-5828-9eb3-25de925befbc`
- **Gate:** event `8f834933-a389-4ee9-9d72-8fd880963ce4` acquired at 2026-09-13T01:16:51.116324+00 and completed `failed` at 2026-09-13T01:18:50.468290+00; lock released.

The latest evidence is unchanged: ThreatFox failed deterministically with
`oversized_response` (`response exceeds 10485760 bytes`), while 37/38 sources
succeeded. Web live/readiness and PostgreSQL remain healthy; scheduler heartbeat
is current; the worker remains intentionally reserved and exited 0; the latest
full-success run remains 2026-09-11. Backup metadata is present from
2026-09-12T12:55:18Z, disk use is 42%, memory pressure is not indicated, the
certificate is valid through 2026-11-16, and migrations remain at
`0015_contradiction_lifecycle`. Reports/publications remain intact at 186/201/201,
with latest publication 2026-09-11T22:24:37Z.

No safe reversible recovery action applies to a bounded upstream-size failure;
no retry, restart, deployment, migration, response-limit change, credential
change, or data mutation was performed. Preserve the partial run and source
failure metadata. Follow-up remains a reviewed bounded ThreatFox
pagination/filtering or streaming change with fixture and focused tests.

## Recovery-job follow-up (2026-09-13 latest actionable evidence)

- **Observed:** 2026-09-13T07:47:42.054068+00Z
- **Monitor event:** `39e2d526-382f-4ee0-8db4-997bcfaf5f2b`
- **Correlation:** `240276fb-7df5-4f16-a22c-6c1bc0ea2c99`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Gate:** acquired at 2026-09-13T07:47:12.274630+00Z and completed with `failed` / no-safe-recovery outcome at 2026-09-13T07:48:24.097018+00Z; lock verified released.

Read-only diagnosis remains unchanged: ThreatFox failed with the bounded
`oversized_response` classification (`response exceeds 10485760 bytes`), while
37/38 sources succeeded. The latest full-success run remains
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6` (2026-09-11), and the latest usable run
is the partial failed run above. Web, proxy-facing health, scheduler,
monitor, PostgreSQL, disk, memory, file descriptors, and backup service are
operational; PostgreSQL remains at migration `0015_contradiction_lifecycle`.
The worker is intentionally reserved and exited 0. Application version is
`0.1.0`; the running image is `cti-hermes:local` (image created
2026-09-12T07:54:53-05:00). Reports/publications remain intact at 186/201/201,
latest publication 2026-09-11T22:24:37Z. No retry, restart, deployment,
migration, response-limit change, credential change, or data mutation was
performed. The incident remains open pending a reviewed bounded ThreatFox
retrieval fix with fixture and focused tests.
