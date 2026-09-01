"""Static Site and Portal Builder for Hermes CTI.

Compiles static portal HTML/JSON assets into output directory (e.g. `portal/`):
- `index.html`: Main portal landing dashboard
- `reports.html`: Standalone reports catalog
- `cves.html`: Standalone CVE intelligence catalog
- `data/cti_database.json`: Full CTI database export
- `data/stix2_bundle.json`: Global STIX 2.1 JSON export bundle
- `assets/portal.css` and `assets/portal.js`
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from hermes_cti.publisher.stix_exporter import STIXExporter


def _make_dummy_request(path: str = "/") -> Any:
    """Create lightweight request-like object for static Jinja template rendering."""
    return type(
        "DummyRequest",
        (),
        {
            "url": type("Url", (), {"path": path})(),
            "app": type(
                "App",
                (),
                {
                    "state": type(
                        "State",
                        (),
                        {
                            "settings": type(
                                "Settings",
                                (),
                                {"app_version": "2.0"},
                            )()
                        },
                    )()
                },
            )(),
        },
    )()


def classify_epss_quadrant(cvss_score: float | None, epss_score: float | None) -> int:
    """Classify CVE into one of the 4 EPSS vs CVSS Exploitability Quadrants.

    Quadrant Definitions:
    - Quadrant 1 (CVSS >= 7.0, EPSS >= 0.15): Urgent Action
    - Quadrant 2 (CVSS >= 7.0, EPSS < 0.15): High Impact / Low Exploit Prob
    - Quadrant 3 (CVSS < 7.0, EPSS < 0.15): Low Priority
    - Quadrant 4 (CVSS < 7.0, EPSS >= 0.15): Weaponized Fast Attack
    """
    cvss = float(cvss_score) if cvss_score is not None else None
    epss = float(epss_score) if epss_score is not None else None

    if cvss is not None and epss is not None:
        if cvss >= 7.0 and epss >= 0.15:
            return 1
        elif cvss >= 7.0 and epss < 0.15:
            return 2
        elif cvss < 7.0 and epss < 0.15:
            return 3
        else:
            return 4
    elif cvss is not None and cvss >= 7.0:
        return 2
    elif epss is not None and epss >= 0.15:
        return 4
    else:
        return 3


def get_quadrant_metadata(quadrant: int) -> dict[str, Any]:
    """Return descriptive label, name, and color for a quadrant integer."""
    meta = {
        1: {
            "quadrant": 1,
            "name": "Quadrant I",
            "label": "Urgent Action / Active Exploitation",
            "color": "rose",
            "priority": "critical",
        },
        2: {
            "quadrant": 2,
            "name": "Quadrant II",
            "label": "High Impact / Low Exploitation Probability",
            "color": "amber",
            "priority": "high",
        },
        3: {
            "quadrant": 3,
            "name": "Quadrant III",
            "label": "Low Priority",
            "color": "emerald",
            "priority": "low",
        },
        4: {
            "quadrant": 4,
            "name": "Quadrant IV",
            "label": "Weaponized Fast Attack",
            "color": "purple",
            "priority": "medium",
        },
    }
    return meta.get(quadrant, meta[3])


class SiteBuilder:
    """Static site and portal export compiler."""

    def __init__(
        self,
        template_dir: Path | None = None,
        stix_exporter: STIXExporter | None = None,
    ) -> None:
        if template_dir is None:
            template_dir = Path(__file__).resolve().parents[1] / "portal" / "templates"
        self.template_dir = template_dir
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True,
        )
        self.stix_exporter = stix_exporter or STIXExporter()

    def build_portal(
        self,
        output_dir: Path,
        reports_data: list[dict[str, Any]],
        cves_data: list[dict[str, Any]],
        iocs_data: list[dict[str, Any]],
        failures_data: list[dict[str, Any]] | None = None,
    ) -> None:
        """Compile complete static portal HTML and JSON data into output directory."""
        output_dir.mkdir(parents=True, exist_ok=True)
        data_dir = output_dir / "data"
        assets_dir = output_dir / "assets"
        data_dir.mkdir(parents=True, exist_ok=True)
        assets_dir.mkdir(parents=True, exist_ok=True)

        # 1. Enrich CVEs with Exploitability Quadrant
        enriched_cves: list[dict[str, Any]] = []
        quadrant_counts = {1: 0, 2: 0, 3: 0, 4: 0}
        for cve in cves_data:
            q_num = classify_epss_quadrant(
                cve.get("cvss_score")
                if cve.get("cvss_score") is not None
                else cve.get("cvss"),
                cve.get("epss_score")
                if cve.get("epss_score") is not None
                else cve.get("epss"),
            )
            q_meta = get_quadrant_metadata(q_num)
            cve_copy = dict(cve)
            cve_copy["quadrant"] = q_num
            cve_copy["quadrant_info"] = q_meta
            quadrant_counts[q_num] += 1
            enriched_cves.append(cve_copy)

        # 2. Hero Metrics Computation
        total_reports = len(reports_data)
        total_cves = len(cves_data)
        total_iocs = len(iocs_data)
        failed_count = len(failures_data) if failures_data else 0

        def _cvss_is_critical(c: dict[str, Any]) -> bool:
            val = (
                c.get("cvss_score")
                if c.get("cvss_score") is not None
                else c.get("cvss")
            )
            if val is None:
                return False
            try:
                return float(val) >= 9.0
            except (ValueError, TypeError):
                return False

        critical_cves = sum(1 for c in cves_data if _cvss_is_critical(c))
        urgent_action_cves = quadrant_counts[1]
        active_kev_count = sum(1 for c in cves_data if c.get("known_exploited") is True)

        metrics = {
            "total_reports": total_reports,
            "total_cves": total_cves,
            "total_iocs": total_iocs,
            "failed_sources_count": failed_count,
            "critical_cves": critical_cves,
            "urgent_action_cves": urgent_action_cves,
            "active_kev_count": active_kev_count,
            "quadrant_counts": quadrant_counts,
        }

        # 3. Export cti_database.json
        reconciled_ts = datetime.now(UTC).isoformat()
        cti_database = {
            "metrics": metrics,
            "reports": reports_data,
            "cves": enriched_cves,
            "iocs": iocs_data,
            "failures": failures_data or [],
            "reconciled_at": reconciled_ts,
        }
        (data_dir / "cti_database.json").write_text(
            json.dumps(cti_database, indent=2, sort_keys=True), encoding="utf-8"
        )

        # 4. Export stix2_bundle.json
        summary_text = (
            f"Consolidated STIX 2.1 intelligence bundle containing "
            f"{total_reports} reports, {total_cves} CVEs, and {total_iocs} IOCs."
        )
        # Aggregate techniques across reports
        aggregated_techniques: list[dict[str, Any]] = []
        seen_tech_ids: set[str] = set()
        for r in reports_data:
            tech_list = r.get("techniques", [])
            for item in tech_list:
                tech_id = (
                    item.get("technique_id")
                    if isinstance(item, dict)
                    else str(item).strip()
                )
                if tech_id and tech_id not in seen_tech_ids:
                    seen_tech_ids.add(tech_id)
                    if isinstance(item, dict):
                        aggregated_techniques.append(item)
                    else:
                        aggregated_techniques.append(
                            {
                                "technique_id": tech_id,
                                "technique_name": f"Technique {tech_id}",
                            }
                        )

        stix_bundle = self.stix_exporter.create_stix_bundle(
            report_title="Hermes CTI Consolidated Threat Feed",
            summary=summary_text,
            iocs=iocs_data,
            cves=enriched_cves,
            techniques=aggregated_techniques,
        )
        (data_dir / "stix2_bundle.json").write_text(
            json.dumps(stix_bundle, indent=2, sort_keys=True), encoding="utf-8"
        )

        # 5. Copy static assets (portal.css and portal.js)
        src_static_dir = Path(__file__).resolve().parents[1] / "portal" / "static"
        if src_static_dir.exists():
            for asset_file in src_static_dir.glob("*"):
                if asset_file.is_file():
                    shutil.copy(asset_file, assets_dir / asset_file.name)

        # Ensure portal.css & portal.js exist
        if not (assets_dir / "portal.css").exists():
            (assets_dir / "portal.css").write_text(
                "/* Portal styles */\n", encoding="utf-8"
            )
        if not (assets_dir / "portal.js").exists():
            (assets_dir / "portal.js").write_text(
                "/* Portal scripts */\n", encoding="utf-8"
            )

        # 6. Render index.html (Dashboard Landing Page)
        index_template = self._get_or_create_index_template()
        rendered_index = index_template.render(
            request=_make_dummy_request("/"),
            metrics=metrics,
            reports=reports_data[:10],
            cves=enriched_cves,
            iocs=iocs_data[:20],
        )
        (output_dir / "index.html").write_text(rendered_index, encoding="utf-8")

        # 7. Render reports.html
        rendered_reports = self._render_reports_page(reports_data)
        (output_dir / "reports.html").write_text(rendered_reports, encoding="utf-8")

        # 8. Render cves.html
        rendered_cves = self._render_cves_page(enriched_cves)
        (output_dir / "cves.html").write_text(rendered_cves, encoding="utf-8")

    def _render_reports_page(self, reports_data: list[dict[str, Any]]) -> str:
        """Render reports.html static page."""
        try:
            reports_tpl = self.jinja_env.get_template("reports.html")

            class DummyPage:
                items = reports_data
                page = 1
                page_size = 20
                total = len(reports_data)
                total_pages = 1
                query = type(
                    "Query",
                    (),
                    {
                        "search": "",
                        "date_from": "",
                        "confidence_min": None,
                        "sort": "priority",
                        "severities": (),
                        "change_states": (),
                    },
                )()

            return reports_tpl.render(
                request=_make_dummy_request("/reports"),
                page=DummyPage,
            )
        except Exception:
            return (
                "<!doctype html><html><head><title>Reports · Hermes CTI</title>"
                '<link rel="stylesheet" href="assets/portal.css"></head>'
                f"<body><h1>Reports Catalog</h1><p>{len(reports_data)} reports</p>"
                "</body></html>"
            )

    def _render_cves_page(self, cves_data: list[dict[str, Any]]) -> str:
        """Render cves.html static page."""
        try:
            cves_tpl = self.jinja_env.get_template("cves.html")

            class DummyCVEPage:
                items = cves_data
                page = 1
                page_size = 20
                total = len(cves_data)
                total_pages = 1
                query = type(
                    "Query",
                    (),
                    {
                        "search": "",
                        "min_cvss": None,
                        "min_epss": None,
                        "sort": "priority",
                        "severities": (),
                        "known_exploited_only": False,
                    },
                )()

            return cves_tpl.render(
                request=_make_dummy_request("/cves"),
                page=DummyCVEPage,
            )
        except Exception:
            return (
                "<!doctype html><html><head><title>CVEs · Hermes CTI</title>"
                '<link rel="stylesheet" href="assets/portal.css"></head>'
                f"<body><h1>CVE Center</h1><p>{len(cves_data)} CVEs</p>"
                "</body></html>"
            )

    def _get_or_create_index_template(self) -> Any:
        """Load or compile the main index.html landing dashboard template."""
        try:
            return self.jinja_env.get_template("index.html")
        except Exception:
            return self.jinja_env.from_string(_FALLBACK_INDEX_TEMPLATE)


_FALLBACK_INDEX_TEMPLATE = (
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<title>Hermes CTI · Dashboard</title>"
    "<link rel='stylesheet' href='assets/portal.css'>"
    "<script defer src='assets/portal.js'></script></head>"
    "<body><main><h1>CTI Operations &amp; Intelligence Portal</h1>"
    "<div class='metrics'><span>Reports: {{ metrics.total_reports }}</span>"
    "<span>CVEs: {{ metrics.total_cves }}</span></div></main></body></html>"
)
