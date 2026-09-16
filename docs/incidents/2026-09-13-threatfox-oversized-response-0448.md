# Production ingestion incident: ThreatFox bounded response failure (04:48Z)

- **Observed:** 2026-09-13T04:48:29.224473+00:00
- **Monitor state:** `actionable_failure`
- **Monitor event:** `24c17da0-4f19-4195-8a44-856ef8f36302`
- **Correlation:** `739d310e-363b-45e6-8e46-cd3f2df0d367`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200

## Impact

The latest daily collection remains failed: 37 of 38 sources completed and
5,943 new documents were persisted. ThreatFox Recent Indicators (Abuse.ch)
failed. The latest full-success run is
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed 2026-09-11T12:06:50.050468Z.
Reports remain at 186 and publications at 201, with latest publication
2026-09-11T22:24:37.183379Z. Partial successful evidence is preserved; no
persistent data, volume, backup, or evidence deletion occurred.

## Diagnosis and evidence

High confidence: deterministic source/provider bounded-ingestion failure. The
failed source row records `http_status` NULL, `item_count=0`, `retry_count=0`,
`cache_state=miss`, `error_classification=oversized_response`, and
`error_detail=response exceeds 10485760 bytes`. Its configured response cap is
10,485,760 bytes, configuration version 2, last successful retrieval was
2026-09-11T12:06:49.272951Z, and consecutive failures is 3. The run uses
application version `0.1.0` and configuration hash
`d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.

This is not currently supported by evidence as a web, proxy, scheduler,
database, disk, certificate, backup, migration, or credential outage:

- Monitor, web, scheduler, backup, and PostgreSQL containers are up/healthy;
  restart count is 0. The worker exited 0 with its documented reserved-worker
  message.
- Web liveness and readiness returned HTTP 200; readiness reported
  configuration and database `ok`. PostgreSQL `pg_isready` accepted.
- Scheduler heartbeat was fresh at 2026-09-13T04:47:51.992616Z.
- PostgreSQL and Alembic both report revision `0015_contradiction_lifecycle`.
- Host disk is 42% used with 280G available; memory reports 53GiB available;
  open-file limit is 4096. Docker events showed no service restart in the
  observation window.
- Backup metadata is present, mode 600, 198 bytes, modified
  2026-09-12T12:55:18Z; the backup volume is read-only and was not changed.
- The certificate observed on port 9444 is valid through
  2026-11-16T14:30:36Z. No certificate or proxy configuration mutation was made.
- Running image is `cti-hermes:local`, compose image digest
  `sha256:0e5b124207549321f124f73c4ae1a4d56a945e683f9f09849651c3ea952da291`,
  created 2026-09-12T12:55:03.601753Z and started 2026-09-12T12:55:15.193550Z.

## Recovery gate and action

The recovery gate was evaluated against actionable evidence at
2026-09-13T04:47:15.910413Z and recorded an `attempted` event for monitor event
`b140e114-090e-4e66-8a39-2f3bbf8d85b5` (same failed run). Because the monitor
refreshes event IDs while the gate is held, completion was recorded at
2026-09-13T04:48:40.815355Z as event
`24c17da0-4f19-4195-8a44-856ef8f36302`, outcome `failed`; the lock was then
verified absent. No retry, restart, deployment, migration, response-limit
change, credential change, or data mutation was performed. The prior
cooldown suppression at 2026-09-13T03:31:49.888125Z remains in the gate audit.

## Recovery / prevention

The smallest safe action was abstention: restarting a healthy stack would not
repair a deterministic oversized provider payload and retrying would add load
without changing the bounded request. The incident remains unresolved at the
source/provider boundary. Before changing the 10 MiB safety limit, validate
bounded pagination, an alternate endpoint, or a provider-side filter using an
offline fixture and add a regression fixture for oversized responses. Keep
partial-run and source-error evidence visible and do not automatically retry
this source until a bounded collection strategy is tested.

No rollback is required because no application or data change was made.
Existing uncommitted repository changes were present before this diagnosis;
this incident record is the only file added by this response.

## Recovery-job follow-up (05:02Z evidence)

The monitor still reports the same actionable failure at
2026-09-13T05:02:30.203876Z: event `95113319-f1b0-4260-a99c-8619798bedb6`,
correlation `ae3958bb-e978-4be5-8f4f-72eca3449dd6`, run
`5caec866-d2eb-51b1-905f-ecc8a66da107`, endpoint
`http://web:8000/api/v1/ops/run-status`, HTTP 200. The recovery gate recorded
suppression at 2026-09-13T05:01:43.405861Z as event
`7c32941c-a6d2-4a0f-9e38-37c8586f4d09`, correlation
`00325773-378e-44c6-8480-608096e98522`, because the 30-minute cooldown was
active. The recovery lock was verified absent; no recovery was attempted.

Read-only verification remains healthy at the service boundary: web liveness
and readiness are HTTP 200, readiness reports configuration and database `ok`,
PostgreSQL accepts connections, the scheduler heartbeat was fresh at
2026-09-13T05:03:22Z, and all CTI-Hermes application containers have restart
count 0. The reserved worker is intentionally exited 0. PostgreSQL remains at
Alembic revision `0015_contradiction_lifecycle` (also the current migration
head). Host disk is 42% used with 280G available, 53GiB memory is available,
and the open-file limit is 4096. Backup metadata remains present and mode 600
at 2026-09-12T12:55:18Z; the latest encrypted artifact is 21,621,808 bytes.
The certificate is valid through 2026-11-16T14:30:36Z. The running application
image is `cti-hermes:local`, digest
`sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`,
associated with repository commit `c925cd5bbb1b2c872841205b90ea05ea4636da76`.

The source/provider boundary remains the only supported cause: ThreatFox
returned an oversized response before an HTTP status was recorded. No restart,
retry, deployment, migration, response-limit change, credential change, or data
mutation was performed. Partial successful evidence and the failed source row
remain preserved. The existing incident remains open pending a bounded
ThreatFox retrieval strategy and regression fixture; no rollback is required.

## Recovery-job follow-up (07:03Z evidence)

The latest machine-readable monitor evidence was read from the monitor
container at `/runtime/monitor-evidence.json`: state `actionable_failure`, event
`df34e9a2-a2d4-4d4f-b519-28698dcf927d`, observed
`2026-09-13T07:02:38.767246+00`, correlation
`205fcc9a-5534-4539-bcd6-2889609a5976`, run
`5caec866-d2eb-51b1-905f-ecc8a66da107`, endpoint/status
`http://web:8000/api/v1/ops/run-status` / HTTP 200. The 30-minute recovery gate
allowed an attempt at `2026-09-13T07:02:22.860260Z` (event
`f75ea1ef-ebc0-46c6-a2c9-dde0f3729040`); completion was recorded at
`2026-09-13T07:03:27.696476Z` with outcome `failed` (event
`df34e9a2-a2d4-4d4f-b519-28698dcf927d`). The recovery lock was verified absent.
No retry, restart, deployment, migration, configuration, credential, or data
mutation was performed because the unchanged request would reproduce the
bounded ThreatFox response failure.

Read-only verification confirms web liveness and readiness HTTP 200 with
configuration/database `ok`, PostgreSQL accepting connections, a fresh
scheduler heartbeat (`2026-09-13T07:02:52.897213Z`), and restart count 0 for
monitor, web, scheduler, backup, and PostgreSQL. The reserved worker remains
intentionally exited 0. PostgreSQL and Alembic are at
`0015_contradiction_lifecycle`. The failed run remains 38 total sources, 37
successful, 1 failed, and 5,943 new documents; ThreatFox remains failed with
`http_status` NULL, `item_count=0`, `retry_count=0`, `cache_state=miss`,
`oversized_response`, and `response exceeds 10485760 bytes`. The latest full
success remains `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; reports/publications are
186/201, latest publication `2026-09-11T22:24:37.183379+00`.

The running image is `cti-hermes:local`, image ID and compose digest
`sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`,
associated with repository HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`.
Host disk is 42% used with 280G available, memory has 53GiB available, and the
open-file limit is 4096. The latest encrypted backup metadata is mode 600,
completed `2026-09-12T12:55:18Z`, artifact size 21,621,808 bytes, with its
recorded SHA-256 preserved. The internal certificate on port 9444 is currently
valid through `2026-09-13T11:39:23Z`; renewal follow-up remains required. The
incident is unresolved at the source/provider boundary, partial evidence is
intact, and no rollback is required. Prevention remains bounded ThreatFox
pagination/filtering or an alternate endpoint validated by offline fixture,
plus an oversized-response regression test; do not raise the 10 MiB cap or
retry automatically without that validation.

## Recovery-job follow-up (06:03Z evidence)

The latest machine-readable monitor evidence was read from the monitor
container at `/runtime/monitor-evidence.json`: state `actionable_failure`, event
`096f24bb-41ed-458b-adb0-d9de759f542d`, observed
`2026-09-13T06:01:34.436612+00:00`, correlation
`31267caf-21e7-4a97-abd9-cfa33b1ebd9e`, run
`5caec866-d2eb-51b1-905f-ecc8a66da107`, endpoint/status
`http://web:8000/api/v1/ops/run-status` / HTTP 200. The recovery gate acquired
that evidence at `2026-09-13T06:02:22.632037Z`, then completed at
`2026-09-13T06:02:59.067176Z` with outcome `failed`; the lock was verified
absent. No service restart, retry, deployment, migration, configuration,
credential, or data mutation was performed because the failure is deterministic
and a repeated unchanged request would reproduce the provider boundary error.

Read-only verification found the monitor, web, scheduler, and PostgreSQL
containers healthy with restart count 0; liveness and readiness were HTTP 200
(the internal operational routes are not exposed on the host port). PostgreSQL
accepted connections at revision `0015_contradiction_lifecycle`. The latest run
still has 38 total sources, 37 successful, 1 failed, and 5,943 new documents;
the failed source remains ThreatFox with `oversized_response` and
`response exceeds 10485760 bytes`. Reports/publications remain 186/201. Host
disk is 42% used with 280G available, memory has approximately 53GiB
available, and open-file limit is 4096. Backup metadata remains mode 600 with
the encrypted artifact present. The certificate on port 9444 is valid through
`2026-09-13T11:39:23Z` and requires follow-up before expiry.

The running application image remains `cti-hermes:local`, image ID
`sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`,
associated with repository HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`.
Uncommitted repository changes predate this diagnostic and were not altered
except for this incident record. The incident remains open; no rollback is
required. Prevention: validate bounded ThreatFox pagination/filtering or an
alternate endpoint with an offline fixture, add an oversized-response
regression fixture, and renew/verify the port-9444 certificate before its
remaining validity window closes.

## Recovery-job follow-up (05:34Z)

The latest machine-readable monitor evidence remains actionable at
2026-09-13T05:31:32.289246Z: event `3e4ba9d2-7f88-45dd-9782-b5b9258f9733`,
correlation `e7d2c0bb-0df5-4a3e-b59d-91d5a32f05b8`, run
`5caec866-d2eb-51b1-905f-ecc8a66da107`, endpoint
`http://web:8000/api/v1/ops/run-status`, HTTP 200. The recovery gate allowed
one attempt after the cooldown at 2026-09-13T05:32:16.060270Z and recorded
completion at 2026-09-13T05:34:04.837855Z with outcome `failed`; the lock was
verified absent. A subsequent gate check was correctly suppressed by the
30-minute cooldown (event `e7a88544-a5c4-40d7-954a-09b80cea5d98`).

Read-only verification at 05:33Z found web liveness HTTP 200
(`{"status":"ok"}`), readiness HTTP 200 with configuration and database
`ok`, PostgreSQL accepting connections, and a fresh scheduler heartbeat at
2026-09-13T05:33:22Z. Web, scheduler, monitor, and PostgreSQL were healthy;
the worker remains intentionally exited 0 with its reserved-worker message.
Restart counts are zero. Host disk is 42% used with 280G available, memory
reports 53GiB available, and the open-file counter is 5,056 system-wide.
Alembic revision remains `0015_contradiction_lifecycle`. The latest encrypted
backup artifact is `hermes-20260912T125515Z.dump.enc` (21,621,808 bytes), with
metadata present at `2026-09-12T12:55:18Z`. The certificate observed on port
9444 is valid from 2026-09-12T23:39:23Z through 2026-09-13T11:39:23Z.

Database read-back confirms the failed run has 38 total sources, 37
successful, 1 failed, and 5,943 new documents; the failed source remains
`threatfox-recent-indicators-abuse-ch` with `oversized_response` and
`response exceeds 10485760 bytes`. The latest full-success run remains
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed
2026-09-11T12:06:50.050468Z. No retry, restart, deployment, migration,
response-limit change, credential change, or data mutation was performed.
Partial evidence and the failed source record remain preserved.

## Recovery-job follow-up (05:47Z cooldown suppression)

The latest machine-readable monitor evidence remains actionable at
2026-09-13T05:46:33.336538Z: event `5166673e-54df-4153-8515-206bbac1f78e`,
correlation `a64f36e6-b2f3-4b11-8fc1-e81b45dbc4ea`, run
`5caec866-d2eb-51b1-905f-ecc8a66da107`, endpoint/status
`http://web:8000/api/v1/ops/run-status` / HTTP 200. The recovery gate recorded
suppression at 2026-09-13T05:47:23.476145Z because its 30-minute cooldown was
active (the prior attempt was completed at 05:34:04Z). The recovery lock was
verified absent; no recovery action was attempted.

Read-only verification found the monitor, web, scheduler, PostgreSQL, and
backup containers running/healthy with restart count 0; the reserved worker
remains intentionally exited 0. The scheduler heartbeat was fresh at
2026-09-13T05:46:52Z. PostgreSQL accepted connections and remains at Alembic
revision `0015_contradiction_lifecycle`; the host has 280G available at 42%
used, 53GiB available memory, and a 4096 open-file limit. The latest encrypted
backup artifact remains `hermes-20260912T125515Z.dump.enc` (21,621,808 bytes)
with metadata modified at 2026-09-12T12:55:18Z. The certificate observed on
port 9444 is valid through 2026-11-16T14:30:36Z. The running image remains
`cti-hermes:local`, digest
`sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`,
associated with commit `c925cd5bbb1b2c872841205b90ea05ea4636da76`.

Database read-back confirms the failed run remains 38 total sources, 37
successful, 1 failed, and 5,943 new documents. The failed source remains
`threatfox-recent-indicators-abuse-ch` with `http_status` NULL,
`item_count=0`, `retry_count=0`, `cache_state=miss`,
`error_classification=oversized_response`, and
`response exceeds 10485760 bytes`. Reports/publications remain 186/201, with
latest publication 2026-09-11T22:24:37.183379Z. The source/provider diagnosis
and data-integrity state are unchanged; no rollback is required.

## Recovery-job follow-up (06:16Z cooldown suppression)

The latest machine-readable monitor evidence was read from the monitor
container at `/runtime/monitor-evidence.json`: state `actionable_failure`, event
`aaea61c2-343f-43d8-a4bd-bec186f9e364`, observed
`2026-09-13T06:15:35.450452+00:00`, correlation
`8b3015af-b75d-4fe1-990e-ce71d67e625d`, run
`5caec866-d2eb-51b1-905f-ecc8a66da107`, endpoint/status
`http://web:8000/api/v1/ops/run-status` / HTTP 200. The recovery gate recorded
suppression at `2026-09-13T06:16:49.629292+00:00` as event
`efb6b0e3-6ccf-43eb-a99b-2039b277b3d2`, correlation
`75892d6e-2fc7-472c-814d-d05f5efba23b`, because the 30-minute cooldown was
active. The recovery lock remains absent; no recovery was attempted.

Read-only verification remains healthy at the service boundary: web liveness
and readiness returned HTTP 200, readiness reported configuration and database
`ok`, PostgreSQL accepted connections, and the scheduler heartbeat was fresh
at `2026-09-13T06:19:22Z`. Monitor, web, scheduler, PostgreSQL, and backup
containers have restart count 0 and are healthy; the worker remains the
intentional reserved worker exited 0. PostgreSQL and Alembic remain at
`0015_contradiction_lifecycle`. Host disk is 42% used with 280G available,
53GiB memory is available, and the open-file limit is 4096. Backup metadata
remains mode 600; certificate inspection shows validity through
`2026-09-13T11:39:23Z` and requires renewal follow-up. The running image remains
`cti-hermes:local`, image ID
`sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.

Database read-back confirms the failed run remains 38 total sources, 37
successful, 1 failed, and 5,943 new documents. ThreatFox remains failed with
`oversized_response` and `response exceeds 10485760 bytes`; reports/publications
remain 186/201, with latest publication `2026-09-11T22:24:37.163555+00`.
Partial evidence remains preserved. No restart, retry, deployment, migration,
configuration, credential, or data mutation was performed; no rollback is
required. The existing source/provider incident remains open pending a bounded
ThreatFox retrieval strategy and regression fixture.

## Recovery-job follow-up (07:16Z evidence)

The latest machine-readable monitor evidence was read from the monitor
container at `/runtime/monitor-evidence.json`: state `actionable_failure`, event
`911f31d2-cb08-4d6b-9e9f-07dfec9e1b7b`, observed
`2026-09-13T07:15:39.685794+00`, correlation
`55ed8845-949f-4517-a329-01f0c90a0735`, run
`5caec866-d2eb-51b1-905f-ecc8a66da107`, endpoint/status
`http://web:8000/api/v1/ops/run-status` / HTTP 200. The recovery gate was
executed against that evidence and recorded suppression at
`2026-09-13T07:16:55.299005+00` as event
`569a512e-629e-4e6b-863a-172b524472d7`, correlation
`40b08a53-1b43-4141-b27c-0aee3173b25f`, because the 30-minute cooldown was
active. The recovery lock was read back absent; no recovery action was
attempted.

Read-only verification at 07:17Z found monitor, web, scheduler, PostgreSQL,
and backup containers running/healthy with restart count 0. The reserved worker
remains intentionally exited 0. Web liveness and readiness returned HTTP 200;
readiness reported configuration and database `ok`; PostgreSQL accepted
connections; and the scheduler heartbeat was fresh at
`2026-09-13T07:17:22Z`. PostgreSQL and Alembic remain at
`0015_contradiction_lifecycle`. Host disk is 42% used with 280G available,
53GiB memory is available, and the open-file limit is 4096. Backup metadata is
present mode 600, modified `2026-09-12T12:55:18Z`; the latest encrypted backup
artifact is `hermes-20260912T125515Z.dump.enc` (21,621,808 bytes). The
certificate observed on port 9444 is valid through `2026-09-13T11:39:23Z` and
requires renewal follow-up.

Database read-back confirms the failed run remains 38 total sources, 37
successful, 1 failed, and 5,943 new documents. ThreatFox remains failed with
`http_status` NULL, `item_count=0`, `retry_count=0`, `cache_state=miss`,
`oversized_response`, and `response exceeds 10485760 bytes`. The latest
full-success run remains
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed
`2026-09-11T12:06:50.050468Z`; reports/publications remain 186/201, with latest
publication `2026-09-11T22:24:37.183379Z`. The running image is
`cti-hermes:local`, image ID
`sha256:b8f7768c15292957867be104569e8f59f3e021863d5e426e219e58472ec8ed9d`,
associated with repository HEAD
`c925cd5bbb1b2c872841205b90ea05ea4636da76`.

The supported cause remains a deterministic ThreatFox/provider bounded-response
failure with high confidence; web, proxy, scheduler, database, disk,
certificate, backup, migration, and configuration outage are not supported by
current evidence. The compose config check could not run in this shell because
protected deployment variables (`HERMES_SECRET_DIR` and `HERMES_IMAGE`) are not
exported; the running stack was not changed. No rollback is required. Keep the
incident open pending bounded ThreatFox pagination/filtering or an alternate
endpoint validated by offline fixture, plus an oversized-response regression
test; do not raise the 10 MiB cap or retry automatically without that
validation.

## Recovery-job follow-up (08:32Z evidence)

The latest machine-readable monitor evidence was read from the monitor
container at `/runtime/monitor-evidence.json`: state `actionable_failure`, event
`ae038020-8296-4206-b2e6-ac9a2185b527`, observed `2026-09-13T08:30:45.889943Z`,
correlation `143dc9f8-4542-4cb4-8aba-3db650d8610e`, run
`5caec866-d2eb-51b1-905f-ecc8a66da107`, endpoint/status
`http://web:8000/api/v1/ops/run-status` / HTTP 200. The recovery gate allowed
an attempt at `2026-09-13T08:32:17.957721Z`; completion was recorded at
`2026-09-13T08:33:46.608496Z` with outcome `failed`, and the lock was verified
absent. No retry, restart, deployment, migration, configuration, credential,
response-limit, or data mutation was performed because the unchanged failure
would reproduce the provider boundary error.

Read-only verification found monitor, web, scheduler, backup, and PostgreSQL
containers healthy with restart count 0; the reserved worker remains exited 0.
Web liveness/readiness returned HTTP 200 with configuration and database `ok`,
PostgreSQL accepted connections, and the scheduler heartbeat was fresh at
`2026-09-13T08:32:23Z`. PostgreSQL and Alembic remain at
`0015_contradiction_lifecycle`. The failed run remains 38 total sources, 37
successful, 1 failed, and 5,943 new documents; ThreatFox remains failed with
`http_status` NULL, `item_count=0`, `retry_count=0`, `cache_state=miss`,
`oversized_response`, and `response exceeds 10485760 bytes`. The latest
full-success run remains `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; reports remain
186 published and publications 201, latest publication
`2026-09-11T22:24:37.183379Z`.

The running image is `cti-hermes:local`, image ID
`sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`,
associated with repository HEAD
`c925cd5bbb1b2c872841205b90ea05ea4636da76`. Host disk is 42% used with 280G
available; memory has approximately 52GiB available; the shell open-file limit
is 4096. The encrypted backup volume contains `latest.metadata` mode 600 and
`hermes-20260912T125515Z.dump.enc`; the active port-9444 certificate is valid
through `2026-09-13T19:39:23Z` after successful automatic renewal. The incident
remains open at the source/provider boundary, partial evidence is intact, and
no rollback is required. Prevention remains bounded ThreatFox pagination/filtering
or an alternate endpoint validated by offline fixture, plus an oversized-response
regression test; do not raise the 10 MiB cap or retry automatically without that
validation.

## Recovery-job follow-up (08:47Z cooldown suppression)

The latest machine-readable monitor evidence was read from the running monitor
container at `/runtime/monitor-evidence.json`: state `actionable_failure`, event
`5059f3b1-19ef-442b-8900-50c784a8a851`, observed
`2026-09-13T08:45:46.975369+00:00`, correlation
`d10f5190-e7da-4d35-a662-78cf9818b4c1`, run
`5caec866-d2eb-51b1-905f-ecc8a66da107`, endpoint/status
`http://web:8000/api/v1/ops/run-status` / HTTP 200. The recovery gate recorded
suppression at `2026-09-13T08:46:48.300104+00:00` as event
`44418b5f-3bff-4e88-9e50-d14afea1356e`, correlation
`c25e573e-b4dd-4249-80d9-36450e9053bd`, because the 30-minute cooldown was
active after the prior failed attempt completed at 08:33:46Z. The recovery lock
was verified absent; no retry, restart, deployment, migration, or data mutation
was attempted.

Read-only verification at 08:47Z found monitor, web, scheduler, PostgreSQL,
and backup containers healthy with restart count 0; the reserved worker remains
intentionally exited 0. Web liveness and readiness returned HTTP 200 with
configuration and database `ok`; the scheduler heartbeat was fresh at
`2026-09-13T08:46:53Z`; PostgreSQL accepted connections; and Alembic remains at
`0015_contradiction_lifecycle`. Host disk is 42% used with 280G available,
approximately 52GiB memory is available, system file usage is 6,272 with a
shell open-file limit of 4096. The latest encrypted backup remains
`hermes-20260912T125515Z.dump.enc` (21,621,808 bytes), with `latest.metadata`
mode 600. The port-9444 certificate is valid from 07:39:23Z through
19:39:23Z on 2026-09-13. The running image is `cti-hermes:local`, image ID
`sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`,
associated with repository HEAD
`c925cd5bbb1b2c872841205b90ea05ea4636da76`; the working tree has pre-existing
uncommitted changes and was not modified by this diagnostic.

Database read-back confirms the failed run remains 38 total sources, 37
successful, 1 failed, and 5,943 new documents. ThreatFox remains failed with
`http_status` NULL, `item_count=0`, `retry_count=0`, `cache_state=miss`,
`oversized_response`, and `response exceeds 10485760 bytes`. The latest
full-success run remains `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed
`2026-09-11T12:06:50.050468Z`; reports/publications remain 186/201, with latest
publication `2026-09-11T22:24:37.183379Z`. Scheduler and monitor logs show
continuous monitor detection with successful health checks and no service
restart loop; the application boundary is healthy while one source-level
collection fails. Cause confidence remains high for the ThreatFox/provider
bounded-response failure; web, proxy, worker, scheduler, database, disk,
certificate, backup, migration, and configuration outages are not supported.
The incident remains open. Prevention is bounded ThreatFox pagination/filtering
or an alternate endpoint validated with an offline fixture, plus an
oversized-response regression test; do not raise the response cap or bypass the
gate without that validation.

## Recovery-job follow-up (09:02Z cooldown suppression)

The latest machine-readable monitor evidence was read from the running monitor
container at `/runtime/monitor-evidence.json`: state `actionable_failure`, event
`d1b06b3d-c532-4469-a463-1630bca3d0aa`, observed
`2026-09-13T09:00:48.051935+00:00`, correlation
`c8d0d497-d544-4969-8297-71fd27c6d6d0`, run
`5caec866-d2eb-51b1-905f-ecc8a66da107`, endpoint/status
`http://web:8000/api/v1/ops/run-status` / HTTP 200. The recovery gate recorded
suppression at `2026-09-13T09:02:03.310927+00:00` as event
`20587ac4-6adb-4e50-ba5e-67893ef0c263`, correlation
`d35ad272-71e4-456f-8a00-1b1bc5a15398`, because the 30-minute cooldown was
active after the prior failed attempt. The recovery lock was verified absent;
no retry, restart, deployment, migration, or data mutation was attempted.

Read-only verification found web, monitor, scheduler, backup, and PostgreSQL
containers healthy with restart count 0; the reserved worker remains exited 0.
Web liveness and readiness returned HTTP 200 with configuration and database
`ok`; the scheduler heartbeat was fresh at `2026-09-13T09:03:23Z`; PostgreSQL
accepted connections; and Alembic is at `0015_contradiction_lifecycle`, matching
the five application migration files through 0015 with no pending or failed
revision observed. The running application is `cti-hermes:local`, image ID
`sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`,
created 2026-09-12T12:54:53Z, with repository HEAD
`c925cd5bbb1b2c872841205b90ea05ea4636da76`. Host disk is 42% used with 280G
available, approximately 52GiB memory available, and shell open-file limit
4096. The latest encrypted backup metadata is present through
`2026-09-12T12:55:18Z`; certificate logs show successful automatic renewal for
`hermes.cti.scogin.dev` and `matrix.scogin.dev`, and no certificate error.
Caddy and Docker events show no service restart; recent Caddy warnings are
client-disconnect/incomplete-response warnings unrelated to CTI ingestion.

Database read-back confirms the failed run remains 38 total sources, 37
successful, 1 failed, and 5,943 new documents. ThreatFox remains failed with
`http_status` NULL, `item_count=0`, `retry_count=0`, `cache_state=miss`,
`oversized_response`, and `response exceeds 10485760 bytes`; consecutive source
failures are 3. The latest full-success run remains
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed
`2026-09-11T12:06:50.050468Z`; latest usable is the partial failed run.
Reports/publications remain 186/201, with latest publication
`2026-09-11T22:24:37.183379Z`. Cause confidence remains high for a deterministic
ThreatFox/provider bounded-response failure; no web, proxy, worker, scheduler,
database, disk, certificate, backup, migration, publication, or configuration
outage is supported. Partial evidence and persistent data remain intact; no
rollback is required. Prevention is unchanged: validate bounded
pagination/filtering or an alternate endpoint with an offline fixture and add
an oversized-response regression test before any cap change or retry.

## Recovery-job follow-up (12:32Z evidence; cooldown suppression)

The latest machine-readable monitor evidence was read from the monitor
container at `/runtime/monitor-evidence.json`: state `actionable_failure`, event
`3e000e9c-cddc-4d2d-bb55-a486b9fd2f25`, observed
`2026-09-13T12:32:03.102845+00:00`, correlation
`2bd542c7-2474-419c-96d8-439e2fa9c6d0`, run
`5caec866-d2eb-51b1-905f-ecc8a66da107`, endpoint/status
`http://web:8000/api/v1/ops/run-status` / HTTP 200. The evidence records
`latest_ingestion_attempt` as actionable (`1 source(s) failed`) and
`full_success_freshness` as stale. The recovery gate recorded suppression at
`2026-09-13T12:32:18.318267+00:00` as event
`3e000e9c-cddc-4d2d-bb55-a486b9fd2f25` because the 30-minute cooldown was
active; the recovery lock is absent. No restart, retry, deployment, migration,
configuration, credential, or data mutation was performed.

Read-only verification found monitor, web, scheduler, backup, and PostgreSQL
containers running and healthy with restart count 0; the reserved worker
remains intentionally exited 0. Web liveness and readiness returned HTTP 200
with `status=ok` and configuration/database `ok`. The scheduler heartbeat was
`2026-09-13T12:32:25Z`; the private run-status projection reports latest
attempt `5caec866-d2eb-51b1-905f-ecc8a66da107` failed at
`2026-09-13T02:00:07.873460Z` with 37/38 sources successful, while latest
full-success remains `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` at
`2026-09-11T12:06:50.050468Z`; latest usable is the partial failed run.
The API reports application version `0.1.0`. The running image is
`cti-hermes:local`, image ID/digest
`sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`,
associated with repository HEAD
`c925cd5bbb1b2c872841205b90ea05ea4636da76`; no deployment or configuration
change was made during this job.

PostgreSQL accepted connections (`pg_isready`) and Alembic reports
`0015_contradiction_lifecycle`; no pending or failed migration was observed.
Host disk is 42% used with 280G available, memory has approximately 52GiB
available, and the open-file limit is 4096. Backup metadata is present mode
600 and the latest encrypted artifact is 21,621,808 bytes, completed
`2026-09-12T12:55:18Z`. The current Caddy certificate endpoint presents a
certificate valid from `2026-09-13T07:39:23Z` through `2026-09-13T19:39:23Z`.
Docker events in the window show health-check/exec probes only and no service
restart. Recent PostgreSQL error lines were from malformed manual diagnostic
queries against nonexistent/incorrect relation names, not application failures;
they do not change the database-integrity assessment.

Cause confidence remains high for the deterministic ThreatFox/provider
bounded-response failure already recorded: services, readiness, database,
disk, memory, migrations, backup, certificate, and scheduler are healthy, and
no infrastructure remediation would alter the unchanged oversized request.
Impact remains partial source coverage and stale full-success freshness; prior
persisted evidence and backups are intact. No rollback is required. Prevention
remains bounded ThreatFox pagination/filtering or an alternate endpoint tested
with an offline fixture, plus an oversized-response regression test; do not
raise the 10 MiB limit or retry automatically without that validation.
