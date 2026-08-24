# CTI-Hermes

CTI-Hermes is an independently deployable service foundation for public cyber
threat intelligence. It is being built phase by phase with deterministic
processing, immutable evidence, explicit provenance, and a public read-only
scope. This repository currently provides Phase 2 ingestion and normalization, Phase 3 deterministic IOC and CVE extraction, Phase 4 PostgreSQL persistence and scheduling, Phase 5 bounded enrichment with explainable priority scoring, Phase 6 historical correlation and resurfacing, Phase 7 evidence-backed detection, hunting, remediation, and report validation, and Phase 8 dynamic analyst portal and public-private API projections.

## Current capability status

Working now:

- Installable `src/hermes_cti` package for Python 3.12+.
- FastAPI application factory with `/health/live`, `/health/ready`, and `/version`.
- Typed settings with YAML defaults and `HERMES_*` environment overrides.
- JSON logging with request/run correlation fields and secret redaction.
- Versioned Pydantic contracts for source evidence, indicators, vulnerabilities,
  products, ATT&CK mappings, enrichment envelopes, relationship proposals,
  reports, hunts, remediation, detections, run manifests, and operational events.
- Typed offline loading and validation of the authoritative `config/sources.json`
  registry, including deterministic defaults and secret-field rejection.
- Typer CLI with `version`, `doctor`, `sources validate`, database-independent `collect-once`, and explicit `db migrate`, `db run-daily`, `db status`, and `db retry-failed` commands.
- Provider-neutral HTTPX retrieval with bounded timeouts, redirects, response bytes, retries, user-agent, TLS verification, and conditional requests.
- RSS/Atom and CISA KEV normalization with sanitized text, hashes, raw-artifact metadata, and deterministic ordering.
- Partial-failure ingestion manifests that retain successful source documents.
- Deterministic, evidence-preserving IOC and CVE extraction with refanging, validation, configurable IP exclusions and domain suppression, stable ordering, and JSON/CSV export.
- Offline `extract` CLI support for UTF-8 files and standard input; extraction performs no network enrichment.
- Typed PostgreSQL persistence models, Alembic baseline migrations, immutable raw-artifact enforcement, idempotent repository upserts, transaction boundaries, stale-run queries, and a session-held daily advisory lock.
- A dedicated timezone-aware scheduler process and development Compose service independent of Hermes cron.
- Phase 5 enrichment contracts and bounded CISA KEV, EPSS, and NVD clients in fixed order, with optional VirusTotal, OTX, and AbuseIPDB clients disabled unless explicitly configured with runtime credentials.
- Per-provider timeout, response-size, retry, Retry-After, rate/concurrency, cache TTL, stale-if-error, quota metadata, and secret-free provider-health behavior.
- Versioned provider results and risk assessments with preserved conflicts and a reproducible exploitation/CVSS/EPSS/recency/product/source/corroboration score breakdown.
- Phase 6 deterministic exact-match correlation, non-relational candidate leads, contradiction records, versioned resurfacing events, reviewed-only public projections, and a guarded `db submit-proposal` model-proposal path.
- Phase 7 structured report bundles, evidence-coverage validation, Sigma/YARA/SPL/KQL artifact generation, separate hunt and remediation guidance, safe Markdown/JSON/portal-ready rendering, version history, and rollback-safe publication persistence.
- Frozen uv environment, Ruff, strict mypy, pytest, Dockerfile, development
  Compose configuration, and CI quality gates.

Phase boundaries:

- Phase 9 deployment package, backup, monitoring, CI, rollback, and Hermes profile instructions are prepared; production deployment remains approval-gated.
- LLM-assisted report generation is not part of Phase 7; report bundles require structured evidence inputs.
- External sigma-cli and yara-python integrations are used when installed; deterministic compatibility validation remains explicit when unavailable.

Planned after Phase 8:

- Approved production deployment, proxy separation, backup, monitoring, and Hermes operations.

The public CTI scope does not include internal asset inventory or claims about
an organization’s exposure.

## Local setup

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), and Docker for
container checks.

```bash
git clone https://github.com/mrcoggsworth/threat-intel-agent.git
cd threat-intel-agent
uv sync --frozen
```

`pyproject.toml` is authoritative. `requirements.txt` is intentionally absent;
`uv.lock` is the reproducible dependency artifact.

## API

Start the development API:

```bash
uv run hermes-cti-api
```

The liveness endpoint is dependency-independent. Readiness is expected to
return HTTP 503 until a required PostgreSQL URL is configured and reachable:

```bash
curl http://127.0.0.1:8000/health/live
curl -i http://127.0.0.1:8000/health/ready
curl http://127.0.0.1:8000/version
```

## CLI and source configuration

The source registry is validated locally and never fetched by this command:

```bash
uv run hermes-cti version
uv run hermes-cti doctor
uv run hermes-cti sources validate
uv run hermes-cti sources validate --path config/sources.json
uv run hermes-cti collect-once --sources config/sources.json --output ingestion-manifest.json
uv run hermes-cti db migrate
uv run hermes-cti db run-daily
uv run hermes-cti db status
uv run hermes-cti db enrich --cve CVE-2021-40438
uv run hermes-cti extract report.txt --format json --output extraction.json
cat report.txt | uv run hermes-cti extract - --format csv
```

The loader accepts the Phase 0 `type` field and supplies typed defaults for
enabled state, polling interval, timeout, response size, reliability, tags, and
adapter settings. It does not rewrite the existing registry or add credentials.
Validation failures identify the file, source, and invalid field without
echoing secret-like values. Provider credentials are runtime-only HERMES_* secrets; missing optional credentials disable those providers without startup failure.

## Tests and quality gates

The default suite uses no live internet. Phase 4 integration tests start an ephemeral local PostgreSQL container (or use HERMES_TEST_DATABASE_URL):

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```

## Docker

```bash
docker build --file deploy/Dockerfile --tag hermes-cti:dev .
docker compose --file deploy/docker-compose.dev.yml config
docker compose --file deploy/docker-compose.dev.yml up --build
```

The development Compose file includes web, PostgreSQL, and a dedicated scheduler.
Migrations remain explicit via `uv run hermes-cti db migrate`; web workers do not
run migrations automatically. Proxy, backup, monitoring, authentication, and
production deployment operations remain planned.

## Configuration and source policy

`config/sources.json` remains the authoritative public-source registry. Phase 2
uses it for bounded collection and preserves backward compatibility with its existing
shape. Runtime secrets and database URLs must be supplied through environment
variables and must never be committed.

## Roadmap

1. Phase 2: bounded public-source ingestion and evidence preservation (implemented).
2. Phase 3: deterministic IOC and CVE extraction (implemented).
3. Phase 4: PostgreSQL persistence, deduplication, and independent scheduling (implemented).
4. Phase 5: bounded enrichment and explainable priority scoring (implemented).
5. Phase 6: historical correlation and resurfacing (implemented).
6. Phase 7: detection, hunting, remediation, and report pipeline (implemented).
7. Phase 8: dynamic portal/API, public projections, private token-gated operations, and progressive enhancement (implemented).
8. Phase 9: production deployment and operations package prepared; deployment remains approval-gated.

See the supplied architecture and implementation-plan documents under
`CTI-Hermes/` for the approved later-phase contracts. License: MIT.
