"""Hermes CTI command-line interface."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
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
    no_args_is_help=True,
)
sources_app = typer.Typer(help="Validate the authoritative source registry.")
app.add_typer(sources_app, name="sources")
app.add_typer(database_app, name="db")


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
