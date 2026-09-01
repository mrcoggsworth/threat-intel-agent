"""STIX 2.1 JSON export bundle generator for Hermes CTI.

Produces OASIS STIX 2.1 JSON bundles connecting:
- identity (Author organization: CTI-Hermes Autonomous Agent)
- report (Main CTI report SDO)
- indicator (SDOs with STIX patterning)
- vulnerability (SDOs with external_references)
- attack-pattern (SDOs with MITRE ATT&CK technique IDs)
- relationship (SROs linking indicator -> attack-pattern -> vulnerability)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid5

from hermes_cti.reporting.contracts import ReportBundle

# Deterministic namespace for STIX 2.1 UUIDv5 generation
STIX_NAMESPACE = UUID("00ab0000-0000-0000-0000-000000000000")
AUTHOR_IDENTITY_ID = "identity--f431f809-377b-45e0-aa1c-6a4751cae5ff"


def _format_stix_datetime(dt: datetime | str | None) -> str:
    """Format datetime into standard ISO 8601 UTC string with Z suffix."""
    if dt is None:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(dt, str):
        if not dt:
            return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        if "T" in dt:
            return dt if dt.endswith("Z") else f"{dt}Z"
        return f"{dt}T00:00:00.000Z"
    dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _generate_stix_pattern(indicator_type: str, value: str) -> str:
    """Generate valid STIX 2.1 patterning query string."""
    itype = indicator_type.lower().strip()
    val = value.strip().replace("'", "\\'")

    if itype in {"ipv4", "ipv4-addr", "ip", "ips"}:
        return f"[ipv4-addr:value = '{val}']"
    if itype in {"ipv6", "ipv6-addr"}:
        return f"[ipv6-addr:value = '{val}']"
    if itype in {"domain", "domain-name", "domains", "hostname"}:
        return f"[domain-name:value = '{val}']"
    if itype in {"url", "urls"}:
        return f"[url:value = '{val}']"
    if itype in {"email", "email-addr", "emails"}:
        return f"[email-addr:value = '{val}']"
    if itype in {"sha256", "sha-256", "hashes"}:
        return f"[file:hashes.'SHA-256' = '{val}']"
    if itype in {"sha1", "sha-1"}:
        return f"[file:hashes.'SHA-1' = '{val}']"
    if itype in {"md5"}:
        return f"[file:hashes.'MD5' = '{val}']"
    if itype in {"file_path", "file-name", "filename", "files"}:
        return f"[file:name = '{val}']"
    if itype in {"registry_path", "windows-registry-key"}:
        return f"[windows-registry-key:key = '{val}']"

    return f"[network-traffic:dst_ref.value = '{val}']"


def create_stix_bundle(
    report_title: str,
    summary: str,
    published_date: str | datetime | None = None,
    iocs: dict[str, list[str]] | list[dict[str, Any]] | None = None,
    cves: list[str] | list[dict[str, Any]] | None = None,
    techniques: list[str] | list[dict[str, Any]] | None = None,
    report_id: str | UUID | None = None,
    confidence: float | None = None,
    report_url: str | None = None,
) -> dict[str, Any]:
    """Functional interface to create an OASIS STIX 2.1 Bundle."""
    exporter = STIXExporter()
    return exporter.create_stix_bundle(
        report_title=report_title,
        summary=summary,
        published_date=published_date,
        iocs=iocs,
        cves=cves,
        techniques=techniques,
        report_id=report_id,
        confidence=confidence,
        report_url=report_url,
    )


class STIXExporter:
    """Builder for OASIS STIX 2.1 JSON Bundles from CTI reports and threat data."""

    def __init__(self, author_name: str = "CTI-Hermes Autonomous Agent") -> None:
        self.author_name = author_name

    def create_author_identity(self) -> dict[str, Any]:
        return {
            "type": "identity",
            "spec_version": "2.1",
            "id": AUTHOR_IDENTITY_ID,
            "created": "2026-01-01T00:00:00.000Z",
            "modified": "2026-01-01T00:00:00.000Z",
            "name": self.author_name,
            "identity_class": "organization",
        }

    def create_stix_bundle(
        self,
        report_title: str,
        summary: str,
        published_date: str | datetime | None = None,
        iocs: dict[str, list[str]] | list[dict[str, Any]] | None = None,
        cves: list[str] | list[dict[str, Any]] | None = None,
        techniques: list[str] | list[dict[str, Any]] | None = None,
        report_id: str | UUID | None = None,
        confidence: float | None = None,
        report_url: str | None = None,
    ) -> dict[str, Any]:
        """Construct an OASIS STIX 2.1 Bundle containing SDOs and SROs."""
        published_ts = _format_stix_datetime(published_date)
        now_ts = _format_stix_datetime(datetime.now(UTC))
        bundle_id = (
            f"bundle--{uuid5(STIX_NAMESPACE, f'bundle:{report_title}:{published_ts}')}"
        )

        objects: list[dict[str, Any]] = []
        object_refs: list[str] = []

        # 1. Author Identity
        author = self.create_author_identity()
        objects.append(author)
        object_refs.append(author["id"])

        # 2. Vulnerability SDOs
        vuln_objects: list[dict[str, Any]] = []
        if cves:
            for item in cves:
                cve_id = (
                    item.get("cve_id") or item.get("id", "")
                    if isinstance(item, dict)
                    else str(item).strip()
                )
                if not cve_id:
                    continue
                v_obj_id = f"vulnerability--{uuid5(STIX_NAMESPACE, cve_id.upper())}"
                v_desc = (
                    item.get("summary")
                    if isinstance(item, dict) and item.get("summary")
                    else f"Vulnerability {cve_id}"
                )
                ext_refs = [
                    {
                        "source_name": "cve",
                        "external_id": cve_id.upper(),
                        "url": f"https://nvd.nist.gov/vuln/detail/{cve_id.upper()}",
                    }
                ]
                if isinstance(item, dict):
                    source_url = item.get("source_url") or item.get("link")
                    if source_url:
                        ext_refs.append(
                            {
                                "source_name": str(item.get("source_name") or "source"),
                                "url": str(source_url),
                            }
                        )

                v_obj: dict[str, Any] = {
                    "type": "vulnerability",
                    "spec_version": "2.1",
                    "id": v_obj_id,
                    "created_by_ref": AUTHOR_IDENTITY_ID,
                    "created": published_ts,
                    "modified": published_ts,
                    "name": cve_id.upper(),
                    "description": v_desc,
                    "external_references": ext_refs,
                }
                vuln_objects.append(v_obj)
                objects.append(v_obj)
                object_refs.append(v_obj_id)

        # 3. Attack Pattern SDOs
        attack_objects: list[dict[str, Any]] = []
        if techniques:
            for item in techniques:
                tech_id = (
                    item["technique_id"]
                    if isinstance(item, dict) and "technique_id" in item
                    else item.get("attack_id")
                    if isinstance(item, dict)
                    else str(item).strip()
                )
                tech_name = (
                    item.get("technique_name")
                    if isinstance(item, dict) and item.get("technique_name")
                    else item.get("name")
                    if isinstance(item, dict)
                    else f"Technique {tech_id}"
                )
                if not tech_id:
                    continue
                ap_obj_id = f"attack-pattern--{uuid5(STIX_NAMESPACE, tech_id.upper())}"
                ap_obj: dict[str, Any] = {
                    "type": "attack-pattern",
                    "spec_version": "2.1",
                    "id": ap_obj_id,
                    "created_by_ref": AUTHOR_IDENTITY_ID,
                    "created": published_ts,
                    "modified": published_ts,
                    "name": tech_name,
                    "external_references": [
                        {
                            "source_name": "mitre-attack",
                            "external_id": tech_id.upper(),
                            "url": (
                                "https://attack.mitre.org/techniques/"
                                f"{tech_id.upper().replace('.', '/')}/"
                            ),
                        }
                    ],
                }
                attack_objects.append(ap_obj)
                objects.append(ap_obj)
                object_refs.append(ap_obj_id)

        # 4. Indicator SDOs
        indicator_objects: list[dict[str, Any]] = []
        if iocs:
            ioc_entries: list[tuple[str, str, dict[str, Any]]] = []
            if isinstance(iocs, dict):
                for itype, values in iocs.items():
                    for val in values:
                        ioc_entries.append((itype, str(val), {}))
            elif isinstance(iocs, list):
                for item in iocs:
                    if isinstance(item, dict):
                        itype = (
                            item.get("indicator_type")
                            or item.get("type")
                            or "indicator"
                        )
                        val = (
                            item.get("display_value")
                            or item.get("value")
                            or item.get("normalized_value")
                            or ""
                        )
                        if val:
                            ioc_entries.append((itype, str(val), item))

            for itype, val, item_dict in ioc_entries:
                pattern = _generate_stix_pattern(itype, val)
                ind_id = f"indicator--{uuid5(STIX_NAMESPACE, f'{itype}:{val}')}"
                ind_obj: dict[str, Any] = {
                    "type": "indicator",
                    "spec_version": "2.1",
                    "id": ind_id,
                    "created_by_ref": AUTHOR_IDENTITY_ID,
                    "created": published_ts,
                    "modified": published_ts,
                    "name": f"{itype.upper()}: {val}",
                    "indicator_types": ["malicious-activity"],
                    "pattern": pattern,
                    "pattern_type": "stix",
                    "pattern_version": "2.1",
                    "valid_from": published_ts,
                }
                if confidence is not None:
                    ind_obj["confidence"] = (
                        int(confidence * 100) if confidence <= 1.0 else int(confidence)
                    )
                source_url = item_dict.get("source_url") or item_dict.get("link")
                if source_url:
                    ind_obj["external_references"] = [
                        {
                            "source_name": str(
                                item_dict.get("source_name") or "source"
                            ),
                            "url": str(source_url),
                        }
                    ]
                indicator_objects.append(ind_obj)
                objects.append(ind_obj)
                object_refs.append(ind_id)

        # 5. Relationship SROs
        # Relationship: Indicator -> indicates -> Attack Pattern
        for ind_obj in indicator_objects:
            for ap_obj in attack_objects:
                rel_key = f"{ind_obj['id']}->indicates->{ap_obj['id']}"
                rel_id = f"relationship--{uuid5(STIX_NAMESPACE, rel_key)}"
                rel_obj = {
                    "type": "relationship",
                    "spec_version": "2.1",
                    "id": rel_id,
                    "created_by_ref": AUTHOR_IDENTITY_ID,
                    "created": published_ts,
                    "modified": published_ts,
                    "relationship_type": "indicates",
                    "source_ref": ind_obj["id"],
                    "target_ref": ap_obj["id"],
                }
                objects.append(rel_obj)
                object_refs.append(rel_id)

        # Relationship: Attack Pattern -> targets -> Vulnerability
        for ap_obj in attack_objects:
            for v_obj in vuln_objects:
                rel_key = f"{ap_obj['id']}->targets->{v_obj['id']}"
                rel_id = f"relationship--{uuid5(STIX_NAMESPACE, rel_key)}"
                rel_obj = {
                    "type": "relationship",
                    "spec_version": "2.1",
                    "id": rel_id,
                    "created_by_ref": AUTHOR_IDENTITY_ID,
                    "created": published_ts,
                    "modified": published_ts,
                    "relationship_type": "targets",
                    "source_ref": ap_obj["id"],
                    "target_ref": v_obj["id"],
                }
                objects.append(rel_obj)
                object_refs.append(rel_id)

        # 6. Report SDO
        rep_uuid = (
            str(report_id)
            if report_id
            else str(uuid5(STIX_NAMESPACE, f"report:{report_title}"))
        )
        report_sdo_id = (
            f"report--{rep_uuid}"
            if not str(rep_uuid).startswith("report--")
            else str(rep_uuid)
        )
        report_obj: dict[str, Any] = {
            "type": "report",
            "spec_version": "2.1",
            "id": report_sdo_id,
            "created_by_ref": AUTHOR_IDENTITY_ID,
            "created": published_ts,
            "modified": now_ts,
            "name": report_title,
            "description": summary,
            "published": published_ts,
            "report_types": ["threat-report"],
            "object_refs": list(dict.fromkeys(object_refs)),
        }
        if confidence is not None:
            report_obj["confidence"] = (
                int(confidence * 100) if confidence <= 1.0 else int(confidence)
            )
        if report_url:
            report_obj["external_references"] = [
                {"source_name": "hermes-cti", "url": report_url}
            ]

        objects.append(report_obj)

        return {
            "type": "bundle",
            "id": bundle_id,
            "objects": objects,
        }

    def export_bundle_from_report(self, bundle: ReportBundle) -> dict[str, Any]:
        """Convert a Hermes ReportBundle into a full STIX 2.1 bundle dict."""
        iocs: dict[str, list[str]] = {}
        for item in bundle.iocs:
            itype = item.indicator_type
            iocs.setdefault(itype, []).append(item.display_value)

        cves: list[dict[str, Any]] = [
            {"cve_id": v.cve_id, "summary": v.summary} for v in bundle.vulnerabilities
        ]

        techniques: list[dict[str, Any]] = [
            {
                "attack_id": m.attack_id,
                "name": getattr(m, "name", getattr(m, "technique_name", "")),
            }
            for m in bundle.attack_mappings
        ]

        return self.create_stix_bundle(
            report_title=bundle.headline,
            summary=bundle.executive_summary,
            published_date=datetime.now(UTC),
            iocs=iocs,
            cves=cves,
            techniques=techniques,
            report_id=bundle.report_id,
            confidence=bundle.confidence,
            report_url=f"/reports/{bundle.slug}",
        )

    def export_stix_json(self, *args: Any, **kwargs: Any) -> str:
        """Create bundle and return stable, indented JSON string."""
        bundle_dict = self.create_stix_bundle(*args, **kwargs)
        return json.dumps(bundle_dict, indent=2, sort_keys=True)
