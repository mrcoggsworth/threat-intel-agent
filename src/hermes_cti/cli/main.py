"""Hermes CTI command-line interface."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

import typer
from pydantic import ValidationError

from hermes_cti import __version__
from hermes_cti.cli.database_commands import database_app
from hermes_cti.core.settings import load_settings
from hermes_cti.db.readiness import DatabaseReadinessChecker
from hermes_cti.extraction import (
    ExtractionConfig,
    ExtractionLimitError,
    extract_document,
    to_csv,
    to_json,
)
from hermes_cti.ingestion.service import IngestionService
from hermes_cti.ingestion.source_config import (
    SourceConfigurationError,
    load_source_registry,
)
from hermes_cti.models.contracts import DocumentType, SourceDocument, sha256_text

app = typer.Typer(
    name="hermes-cti",
    help="Operate the CTI-Hermes foundation and diagnostics.",
    no_args_is_help=False,
)
sources_app = typer.Typer(help="Validate the authoritative source registry.")
app.add_typer(sources_app, name="sources")
app.add_typer(database_app, name="db")


def _execute_sync_db(
    source_path: Path = Path("config/sources.json"),
    memory_path: Path = Path(".hermes/memories/MEMORY.md"),
    output_dir: Path = Path("portal"),
) -> None:
    """Execute database migrations, collection, enrichment, and reconciliation."""
    import httpx

    from hermes_cti.analysis.cve_analyzer import extract_cves
    from hermes_cti.analysis.ioc_extractor import extract_iocs
    from hermes_cti.analysis.mitre_mapper import extract_mitre_techniques
    from hermes_cti.db.migrations import run_migrations
    from hermes_cti.ingestion.enrichment import EPSSEnricher, KEVEnricher
    from hermes_cti.ingestion.rss_parser import FeedDeduplicator, parse_feed_xml
    from hermes_cti.playbooks.hunt_playbook import generate_hunt_playbook
    from hermes_cti.playbooks.rule_generator import (
        DetectionRuleBundle,
        generate_defender_kql,
        generate_elastic_kql,
        generate_sigma_rule,
        generate_splunk_spl,
        generate_yara_rule,
    )
    from hermes_cti.publisher.site_builder import SiteBuilder

    typer.echo("Starting database migration, live ingestion, and reconciliation...")
    settings = load_settings()
    try:
        run_migrations(settings, "head")
        typer.echo("Database migration applied successfully.")
    except Exception as exc:
        typer.echo(
            f"Database migration note: {exc} (continuing offline reconciliation)"
        )

    if not source_path.is_file():
        typer.echo(f"Source configuration not found at {source_path}", err=True)
        raise typer.Exit(code=1)

    try:
        sources_raw = json.loads(source_path.read_text(encoding="utf-8"))
    except Exception as exc:
        typer.echo(f"Failed to read sources file: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Loaded {len(sources_raw)} authoritative sources from {source_path}")

    deduplicator = FeedDeduplicator()
    db_json_path = output_dir / "data" / "cti_database.json"
    existing_reports: list[dict[str, Any]] = []
    existing_cves: list[dict[str, Any]] = []
    existing_iocs: list[dict[str, Any]] = []
    existing_failures: list[dict[str, Any]] = []

    if db_json_path.is_file():
        try:
            existing_db = json.loads(db_json_path.read_text(encoding="utf-8"))
            existing_reports = existing_db.get("reports", [])
            existing_cves = existing_db.get("cves", [])
            existing_iocs = existing_db.get("iocs", [])
            existing_failures = existing_db.get("failures", [])
        except Exception as exc:
            typer.echo(
                f"Warning reading existing database at {db_json_path}: {exc}",
                err=True,
            )

    reports_map: dict[str, dict[str, Any]] = {
        r.get("title", ""): r for r in existing_reports if r.get("title")
    }
    cves_map: dict[str, dict[str, Any]] = {
        c.get("id") or c.get("cve_id", ""): c
        for c in existing_cves
        if c.get("id") or c.get("cve_id")
    }
    iocs_map: dict[tuple[str, str], dict[str, Any]] = {
        (i.get("type", ""), i.get("value", "")): i
        for i in existing_iocs
        if i.get("value")
    }
    failed_sources: list[dict[str, Any]] = list(existing_failures)

    async def run_live_collection() -> None:
        kev_enricher = KEVEnricher()
        epss_enricher = EPSSEnricher()

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                for s in sources_raw:
                    s_name = s.get("name", "Unknown Source")
                    s_url = s.get("url", "")
                    s_type = s.get("type", "rss")
                    if not s_url:
                        continue
                    try:
                        resp = await client.get(s_url)
                        if resp.status_code != 200:
                            err_msg = f"HTTP {resp.status_code}"
                            failed_sources.append(
                                {
                                    "source_name": s_name,
                                    "url": s_url,
                                    "error": err_msg,
                                    "status": "failed",
                                }
                            )
                            typer.echo(
                                f"Warning: Source '{s_name}' ({s_url}) "
                                f"returned {err_msg}",
                                err=True,
                            )
                            continue

                        if s_type == "json" or (
                            "cisa.gov" in s_url and "known_exploited" in s_url
                        ):
                            data = resp.json()
                            vulns = data.get("vulnerabilities", [])
                            for v in vulns[:50]:
                                cve_id = v.get("cveID", "").strip().upper()
                                if not cve_id:
                                    continue
                                epss_tuple = await epss_enricher.get_epss_score(cve_id)
                                epss_val = epss_tuple[0] if epss_tuple else None
                                epss_pct = epss_tuple[1] if epss_tuple else None
                                cves_map[cve_id] = {
                                    "id": cve_id,
                                    "cve_id": cve_id,
                                    "name": v.get("vulnerabilityName", cve_id),
                                    "cvss": None,
                                    "cvss_score": None,
                                    "epss": epss_val,
                                    "epss_score": epss_val,
                                    "epss_percentile": epss_pct,
                                    "known_exploited": True,
                                    "summary": v.get("shortDescription", ""),
                                    "date_added": v.get("dateAdded", ""),
                                    "source_name": s_name,
                                    "source_url": s_url,
                                }
                        else:
                            feed_items = parse_feed_xml(resp.content)
                            for item in feed_items:
                                if deduplicator.is_duplicate(item):
                                    continue
                                deduplicator.mark_seen(item)
                                text_to_analyze = (
                                    f"{item.title}\n{item.summary}\n{item.content}"
                                )
                                extracted_iocs = extract_iocs(text_to_analyze)
                                extracted_cve_list = extract_cves(text_to_analyze)
                                techniques = extract_mitre_techniques(text_to_analyze)

                                for ip in extracted_iocs.ipv4:
                                    iocs_map[("ipv4", ip)] = {
                                        "type": "ipv4",
                                        "indicator_type": "ipv4",
                                        "value": ip,
                                        "display_value": ip,
                                        "source": s_name,
                                        "source_name": s_name,
                                        "source_url": s_url,
                                        "link": item.link,
                                    }
                                for ip6 in extracted_iocs.ipv6:
                                    iocs_map[("ipv6", ip6)] = {
                                        "type": "ipv6",
                                        "indicator_type": "ipv6",
                                        "value": ip6,
                                        "display_value": ip6,
                                        "source": s_name,
                                        "source_name": s_name,
                                        "source_url": s_url,
                                        "link": item.link,
                                    }
                                for d in extracted_iocs.domains:
                                    iocs_map[("domain", d)] = {
                                        "type": "domain",
                                        "indicator_type": "domain",
                                        "value": d,
                                        "display_value": d,
                                        "source": s_name,
                                        "source_name": s_name,
                                        "source_url": s_url,
                                        "link": item.link,
                                    }
                                for u in extracted_iocs.urls:
                                    iocs_map[("url", u)] = {
                                        "type": "url",
                                        "indicator_type": "url",
                                        "value": u,
                                        "display_value": u,
                                        "source": s_name,
                                        "source_name": s_name,
                                        "source_url": s_url,
                                        "link": item.link,
                                    }
                                for h in extracted_iocs.sha256:
                                    iocs_map[("sha256", h)] = {
                                        "type": "sha256",
                                        "indicator_type": "sha256",
                                        "value": h,
                                        "display_value": h,
                                        "source": s_name,
                                        "source_name": s_name,
                                        "source_url": s_url,
                                        "link": item.link,
                                    }

                                for cve in extracted_cve_list:
                                    cve_clean = cve.strip().upper()
                                    if cve_clean not in cves_map:
                                        is_kev = await kev_enricher.is_known_exploited(
                                            cve_clean
                                        )
                                        epss_tuple = await epss_enricher.get_epss_score(
                                            cve_clean
                                        )
                                        epss_score = (
                                            epss_tuple[0] if epss_tuple else None
                                        )
                                        epss_pct = epss_tuple[1] if epss_tuple else None
                                        cves_map[cve_clean] = {
                                            "id": cve_clean,
                                            "cve_id": cve_clean,
                                            "name": cve_clean,
                                            "cvss": None,
                                            "cvss_score": None,
                                            "epss": epss_score,
                                            "epss_score": epss_score,
                                            "epss_percentile": epss_pct,
                                            "known_exploited": is_kev,
                                            "summary": f"Referenced in {item.title}",
                                            "source_name": s_name,
                                            "source_url": s_url,
                                            "link": item.link,
                                        }

                                rule_hash = hashlib.sha256(
                                    item.title.encode("utf-8")
                                ).hexdigest()[:10]
                                yara_name = f"Threat_{rule_hash}"

                                rule_bundle = DetectionRuleBundle(
                                    sigma_yaml=generate_sigma_rule(
                                        title=f"Detection: {item.title}",
                                        description=(
                                            f"Generated detection for {item.title}"
                                        ),
                                        process_names=["powershell.exe", "cmd.exe"]
                                        if techniques
                                        else [],
                                        command_lines=["-enc", "DownloadString"]
                                        if techniques
                                        else [],
                                        tags=[
                                            t["technique_id"].lower()
                                            for t in techniques
                                        ],
                                    ),
                                    splunk_spl=generate_splunk_spl(
                                        process_names=["powershell.exe"]
                                        if techniques
                                        else [],
                                        command_lines=["-enc"] if techniques else [],
                                        iocs=extracted_iocs.ipv4[:3],
                                    ),
                                    defender_kql=generate_defender_kql(
                                        process_names=["powershell.exe"]
                                        if techniques
                                        else [],
                                        command_lines=["-enc"] if techniques else [],
                                        iocs=extracted_iocs.ipv4[:3],
                                    ),
                                    elastic_kql=generate_elastic_kql(
                                        process_names=["powershell.exe"]
                                        if techniques
                                        else [],
                                        command_lines=["-enc"] if techniques else [],
                                        iocs=extracted_iocs.ipv4[:3],
                                    ),
                                    yara_rule=generate_yara_rule(
                                        rule_name=yara_name,
                                        description=f"YARA signature for {item.title}",
                                        strings=[item.title[:20]]
                                        if len(item.title) >= 5
                                        else ["malicious"],
                                    ),
                                    mitre_technique_id=(
                                        techniques[0]["technique_id"]
                                        if techniques
                                        else ""
                                    ),
                                    severity="high",
                                )

                                playbook = generate_hunt_playbook(
                                    threat_title=item.title,
                                    summary=item.summary,
                                    techniques=[t["technique_id"] for t in techniques],
                                    iocs=extracted_iocs.to_dict(),
                                    detection_bundle=rule_bundle,
                                )

                                reports_map[item.title] = {
                                    "title": item.title,
                                    "link": item.link,
                                    "published": item.published.isoformat()
                                    if item.published
                                    else datetime.now(UTC).isoformat(),
                                    "summary": item.summary,
                                    "source_name": s_name,
                                    "source_url": s_url,
                                    "techniques": [
                                        t["technique_id"] for t in techniques
                                    ],
                                    "iocs": extracted_iocs.to_dict(),
                                    "cves": extracted_cve_list,
                                    "playbook": playbook,
                                }
                    except Exception as exc:
                        failed_sources.append(
                            {
                                "source_name": s_name,
                                "url": s_url,
                                "error": str(exc),
                                "status": "failed",
                            }
                        )
                        typer.echo(
                            f"Warning: Source '{s_name}' ({s_url}) failed: {exc}",
                            err=True,
                        )
        finally:
            await kev_enricher.aclose()
            await epss_enricher.aclose()

    try:
        asyncio.run(run_live_collection())
    except Exception as exc:
        typer.echo(f"Live collection encountered error: {exc}", err=True)

    reports_data = list(reports_map.values())
    cves_data = list(cves_map.values())
    iocs_data = list(iocs_map.values())

    SiteBuilder().build_portal(
        output_dir=output_dir,
        reports_data=reports_data,
        cves_data=cves_data,
        iocs_data=iocs_data,
        failures_data=failed_sources,
    )

    if memory_path.is_file():
        content = memory_path.read_text(encoding="utf-8")
        timestamp_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        reconciliation_note = (
            f"- [{timestamp_str}] Ingestion sync completed: "
            f"{len(reports_data)} reports, {len(cves_data)} CVEs, "
            f"{len(iocs_data)} indicators tracked. "
            f"Failed sources: {len(failed_sources)}."
        )
        if "### Ingestion Reconciliation Log" not in content:
            content += f"\n\n### Ingestion Reconciliation Log\n{reconciliation_note}\n"
        else:
            content += f"{reconciliation_note}\n"
        memory_path.write_text(content, encoding="utf-8")

    typer.echo(
        f"Sync complete. Reconciled {len(reports_data)} reports, "
        f"{len(cves_data)} CVEs, and {len(iocs_data)} indicators. "
        f"Failed sources: {len(failed_sources)}."
    )


def _execute_rebuild_all(
    output_dir: Path = Path("portal"),
) -> None:
    """Rebuild static portal pages and STIX 2.1 bundles from database export."""
    from hermes_cti.publisher.site_builder import SiteBuilder

    typer.echo(f"Rebuilding static portal and STIX 2.1 exports at {output_dir}...")
    db_json_path = output_dir / "data" / "cti_database.json"
    reports_data: list[dict[str, Any]] = []
    cves_data: list[dict[str, Any]] = []
    iocs_data: list[dict[str, Any]] = []
    failures_data: list[dict[str, Any]] = []

    if db_json_path.is_file():
        try:
            db_data = json.loads(db_json_path.read_text(encoding="utf-8"))
            reports_data = db_data.get("reports", [])
            cves_data = db_data.get("cves", [])
            iocs_data = db_data.get("iocs", [])
            failures_data = db_data.get("failures", [])
        except Exception as exc:
            typer.echo(
                f"Warning reading existing database at {db_json_path}: {exc}",
                err=True,
            )

    SiteBuilder().build_portal(
        output_dir=output_dir,
        reports_data=reports_data,
        cves_data=cves_data,
        iocs_data=iocs_data,
        failures_data=failures_data,
    )
    typer.echo(f"Rebuild completed successfully. Assets generated in {output_dir}/")


@app.callback(invoke_without_command=True)
def main_entrypoint(
    ctx: typer.Context,
    sync_db: bool = typer.Option(
        False,
        "--sync-db",
        help=(
            "Run database migration, live ingestion from "
            "config/sources.json, and deduplication."
        ),
    ),
    rebuild_all: bool = typer.Option(
        False,
        "--rebuild-all",
        help=("Rebuild static portal pages, STIX 2.1 bundles, and JSON feeds."),
    ),
) -> None:
    """CTI-Hermes top-level entrypoint supporting dual CLI flag and subcommand modes."""
    if ctx.invoked_subcommand is None:
        if sync_db:
            _execute_sync_db()
        if rebuild_all:
            _execute_rebuild_all()
        if not sync_db and not rebuild_all:
            typer.echo(ctx.get_help())


@app.command("sync-db")
def sync_db_command(
    source_path: Path = typer.Option(  # noqa: B008
        Path("config/sources.json"),
        "--sources",
        help="Authoritative source registry JSON file.",
    ),
    memory_path: Path = typer.Option(  # noqa: B008
        Path(".hermes/memories/MEMORY.md"),
        "--memory-path",
        help="Memory log file path.",
    ),
    output_dir: Path = typer.Option(  # noqa: B008
        Path("portal"),
        "--output-dir",
        help="Destination portal output directory.",
    ),
) -> None:
    """Run database migration, live ingestion, and deduplication."""
    _execute_sync_db(
        source_path=source_path,
        memory_path=memory_path,
        output_dir=output_dir,
    )


@app.command("rebuild-all")
def rebuild_all_command(
    output_dir: Path = typer.Option(  # noqa: B008
        Path("portal"),
        "--output-dir",
        help="Destination portal output directory.",
    ),
) -> None:
    """Rebuild static portal pages, STIX 2.1 bundles, and JSON feeds."""
    _execute_rebuild_all(output_dir=output_dir)


@app.command()
def version() -> None:
    """Print the installed application version."""
    typer.echo(__version__)


@app.command()
def doctor() -> None:
    """Check required configuration and database connectivity."""
    try:
        settings = load_settings()
        result = asyncio.run(DatabaseReadinessChecker(settings).check())
    except (ValidationError, ValueError) as exc:
        typer.echo(f"Hermes doctor: FAIL — invalid configuration: {exc}", err=True)
        typer.echo(
            "Action: review config/settings.yaml and HERMES_* environment variables.",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    if not result.healthy:
        typer.echo(
            "Hermes doctor: FAIL — service dependencies are not ready.", err=True
        )
        typer.echo(
            "Action: set HERMES_DATABASE_URL to a reachable PostgreSQL URL, "
            "or set HERMES_DATABASE_REQUIRED=false for a no-database diagnostic run.",
            err=True,
        )
        raise typer.Exit(code=1)
    typer.echo("Hermes doctor: OK")


@sources_app.command("validate")
def validate_sources(
    path: Path = typer.Option(  # noqa: B008
        Path("config/sources.json"),
        "--path",
        help="Path to the authoritative source registry JSON file.",
    ),
) -> None:
    """Validate source configuration without retrieving any source."""
    try:
        registry = load_source_registry(path)
    except SourceConfigurationError as exc:
        typer.echo(f"Source configuration invalid: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Validated {len(registry.sources)} source configurations from {path}")


def run() -> None:
    """Run the Typer application."""
    app()


@app.command("collect-once")
def collect_once(
    source_path: Path = typer.Option(  # noqa: B008
        Path("config/sources.json"),
        "--sources",
        help="Authoritative source registry JSON file.",
    ),
    output: Path | None = typer.Option(  # noqa: B008
        None,
        "--output",
        help="Write the JSON ingestion manifest to this path; stdout otherwise.",
    ),
) -> None:
    """Fetch and normalize configured public sources once."""
    try:
        settings = load_settings()
        registry = load_source_registry(source_path)
        collection = asyncio.run(IngestionService(settings).collect_once(registry))
        manifest = collection.manifest_json()
        if output is None:
            typer.echo(manifest)
        else:
            output.write_text(manifest + "\n", encoding="utf-8")
            typer.echo(f"Wrote ingestion manifest to {output}")
    except (SourceConfigurationError, ValidationError, OSError, ValueError) as exc:
        typer.echo(f"Collection failed before run completion: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if collection.manifest.failed_sources:
        raise typer.Exit(code=2)


def _cli_source_document(
    text: str, source_key: str, source_document_id: UUID | None
) -> SourceDocument:
    document_id = source_document_id or uuid5(
        NAMESPACE_URL, f"hermes-cli-source-document:{source_key}"
    )
    content_hash = sha256_text(text)
    return SourceDocument(
        source_document_id=document_id,
        source_id="cli-input",
        raw_artifact_id=uuid5(NAMESPACE_URL, f"hermes-cli-raw-artifact:{content_hash}"),
        canonical_url="https://cli.invalid/source-document",
        title=f"CLI extraction: {source_key}",
        retrieved_at=datetime.now(UTC),
        normalized_text=text,
        document_type=DocumentType.UNKNOWN,
        normalized_content_hash=content_hash,
        parse_version="phase3-cli-1",
    )


@app.command("extract")
def extract(
    input_path: Path = typer.Argument(  # noqa: B008
        Path("-"), help="UTF-8 text file to extract, or '-' for standard input."
    ),
    output: Path | None = typer.Option(  # noqa: B008
        None, "--output", help="Write output to this path; stdout otherwise."
    ),
    output_format: Literal["json", "csv"] = typer.Option(  # noqa: B008
        "json", "--format", help="Output format."
    ),
    source_document_id: str | None = typer.Option(  # noqa: B008
        None, "--source-document-id", help="UUID to attach to every observation."
    ),
    extract_email: bool = typer.Option(  # noqa: B008
        False, "--extract-email", help="Enable analytically relevant email extraction."
    ),
    include_suppressed: bool = typer.Option(  # noqa: B008
        False, "--include-suppressed", help="Include excluded values in CSV output."
    ),
    max_input_chars: int = typer.Option(  # noqa: B008
        1_000_000, "--max-input-chars", min=1, help="Maximum accepted input size."
    ),
    suppress_domain: str | None = typer.Option(  # noqa: B008
        None, "--suppress-domain", help="Domain suffix to suppress."
    ),
) -> None:
    """Extract validated indicators and CVE candidates from text offline."""
    try:
        text = (
            typer.get_text_stream("stdin").read()
            if str(input_path) == "-"
            else input_path.read_text(encoding="utf-8")
        )
        document_id = UUID(source_document_id) if source_document_id else None
        document = _cli_source_document(text, str(input_path), document_id)
        result = extract_document(
            document,
            ExtractionConfig(
                max_input_chars=max_input_chars,
                extract_email=extract_email,
                suppressed_domains=(suppress_domain,) if suppress_domain else (),
            ),
        )
        payload = (
            to_csv(result, include_suppressed=include_suppressed)
            if output_format == "csv"
            else to_json(result)
        )
        if output is None:
            typer.echo(payload, nl=False)
        else:
            output.write_text(
                payload + ("" if payload.endswith("\n") else "\n"), encoding="utf-8"
            )
            typer.echo(f"Wrote extraction output to {output}")
    except (ExtractionLimitError, OSError, UnicodeError, ValueError) as exc:
        typer.echo(f"Extraction failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
