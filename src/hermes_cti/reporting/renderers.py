"""Safe deterministic Markdown, JSON, and portal-ready report renderers."""

from __future__ import annotations

import html
from collections.abc import Iterable

from hermes_cti.models.contracts import sha256_text
from hermes_cti.reporting.contracts import (
    RenderedArtifact,
    RenderedReport,
    ReportBundle,
)

RENDERER_VERSION = "phase7-renderer-v1"


def _safe(value: object) -> str:
    return html.escape(str(value), quote=True).replace("`", "\\`")


def _list(title: str, values: Iterable[object]) -> list[str]:
    items = list(values)
    if not items:
        return [f"### {title}", "- None evidenced.", ""]
    return [f"### {title}", *(f"- {_safe(value)}" for value in items), ""]


class ReportRenderer:
    """Render only escaped values and validated public-source URLs."""

    def markdown(self, bundle: ReportBundle) -> str:
        lines = [
            f"# {_safe(bundle.headline)}",
            "",
            f"**Severity:** {_safe(bundle.severity.value)}  ",
            f"**Confidence:** {_safe(bundle.confidence)}  ",
            f"**State:** {_safe(bundle.state.value)}",
            "",
            "## Executive summary",
            _safe(bundle.executive_summary),
            "",
            "## Technical analysis",
            _safe(bundle.technical_analysis),
            "",
            "## Evidence",
            _safe(bundle.evidence_summary),
            "",
        ]
        lines.extend(_list("IOCs", (item.display_value for item in bundle.iocs)))
        lines.extend(
            _list(
                "Vulnerabilities and affected products",
                (item.cve_id for item in bundle.vulnerabilities),
            )
        )
        lines.extend(
            _list("ATT&CK mapping", (item.attack_id for item in bundle.attack_mappings))
        )
        lines.extend(
            _list("Detection content", (item.title for item in bundle.detections))
        )
        if bundle.hunt is not None:
            lines.extend(
                _list("Threat hunting", (bundle.hunt.objective, *bundle.hunt.procedure))
            )
        else:
            lines.extend(_list("Threat hunting", ()))
        if bundle.remediation is not None:
            lines.extend(
                _list(
                    "Remediation",
                    bundle.remediation.patching or bundle.remediation.verification,
                )
            )
        else:
            lines.extend(_list("Remediation", ()))
        lines.extend(
            _list(
                "Historical relationships",
                (
                    item.relationship.justification
                    for item in bundle.historical_relationships
                ),
            )
        )
        lines.extend(_list("Timeline", (item.description for item in bundle.timeline)))
        lines.extend(_list("Caveats", bundle.caveats))
        return "\n".join(lines).strip() + "\n"

    def portal(self, bundle: ReportBundle) -> str:
        """Return a safe static fragment; dynamic portal routes remain Phase 8."""

        def li(values: Iterable[object]) -> str:
            return "".join(f"<li>{_safe(value)}</li>" for value in values)

        hunt = (
            f'<section data-section="hunt"><h2>Threat hunting</h2>'
            f"<p>{_safe(bundle.hunt.objective)}</p></section>"
            if bundle.hunt is not None
            else (
                '<section data-section="hunt"><h2>Threat hunting</h2>'
                "<p>None evidenced.</p></section>"
            )
        )
        remediation = (
            f'<section data-section="remediation"><h2>Remediation</h2>'
            f"<ul>{li(bundle.remediation.patching if bundle.remediation else ())}"
            "</ul></section>"
        )
        return (
            f'<article data-report="{_safe(bundle.public_id)}">'
            f"<h1>{_safe(bundle.headline)}</h1>"
            f"<p>{_safe(bundle.executive_summary)}</p>"
            f'<p data-severity="{_safe(bundle.severity.value)}">'
            f"Confidence: {_safe(bundle.confidence)}</p>"
            f"<section><h2>Evidence</h2><p>{_safe(bundle.evidence_summary)}</p></section>"
            f"<section><h2>IOCs</h2><ul>"
            f"{li(item.display_value for item in bundle.iocs)}</ul></section>"
            f"{hunt}{remediation}</article>"
        )

    def render(self, bundle: ReportBundle) -> RenderedReport:
        markdown = self.markdown(bundle)
        payload = bundle.stable_json()
        portal = self.portal(bundle)
        downloads = tuple(
            RenderedArtifact(
                artifact_name=f"{item.detection_id}.{item.detection_type.value}",
                media_type="text/plain",
                content=item.content,
                artifact_hash=item.artifact_hash or sha256_text(item.content),
            )
            for item in bundle.detections
        )
        return RenderedReport(
            markdown=RenderedArtifact(
                artifact_name=f"{bundle.slug}.md",
                media_type="text/markdown",
                content=markdown,
                artifact_hash=sha256_text(markdown),
            ),
            json_artifact=RenderedArtifact(
                artifact_name=f"{bundle.slug}.json",
                media_type="application/json",
                content=payload,
                artifact_hash=sha256_text(payload),
            ),
            portal=RenderedArtifact(
                artifact_name=f"{bundle.slug}.html",
                media_type="text/html",
                content=portal,
                artifact_hash=sha256_text(portal),
            ),
            downloads=downloads,
            renderer_version=RENDERER_VERSION,
        )
