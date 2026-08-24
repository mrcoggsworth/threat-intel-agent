"""Deterministic RSS, Atom, and CISA KEV normalization."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree

from hermes_cti.ingestion.http_client import FetchResult
from hermes_cti.models.contracts import (
    DocumentType,
    RawArtifactMetadata,
    SourceCategory,
    SourceConfig,
    SourceDocument,
    SourceType,
    sha256_text,
)

PARSER_VERSION = "phase2-normalizer-1"


class NormalizationError(Exception):
    """Expected source payload or schema failure safe for an operational manifest."""

    def __init__(self, classification: str, detail: str) -> None:
        self.classification = classification
        self.detail = detail
        super().__init__(detail)


class _HTMLTextParser(HTMLParser):
    _ignored = {"script", "style", "noscript", "template"}
    _blocks = {
        "address",
        "article",
        "br",
        "div",
        "dl",
        "dt",
        "dd",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
        "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        if lowered in self._ignored:
            self._ignored_depth += 1
        elif self._ignored_depth == 0 and lowered in self._blocks:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._ignored_depth == 0 and tag.casefold() in self._blocks:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered in self._ignored and self._ignored_depth:
            self._ignored_depth -= 1
        elif self._ignored_depth == 0 and lowered in self._blocks:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0:
            self.parts.append(data)


def normalize_html_text(value: str) -> str:
    """Strip active HTML content and collapse visible text deterministically."""

    parser = _HTMLTextParser()
    parser.feed(value)
    parser.close()
    return re.sub(r"\s+", " ", "".join(parser.parts)).strip()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _element_text(element: ElementTree.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _child(
    element: ElementTree.Element, names: Iterable[str]
) -> ElementTree.Element | None:
    wanted = {name.casefold() for name in names}
    return next(
        (
            candidate
            for candidate in list(element)
            if _local_name(candidate.tag) in wanted
        ),
        None,
    )


def _text(element: ElementTree.Element, names: Iterable[str]) -> str:
    for name in names:
        candidate = _child(element, (name,))
        if candidate is not None:
            return _element_text(candidate)
    return ""


def _parse_datetime(value: str) -> datetime | None:
    candidate = value.strip()
    if not candidate:
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
            return datetime.fromisoformat(candidate).replace(tzinfo=UTC)
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(candidate)
        except (TypeError, ValueError, IndexError, OverflowError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _decode(payload: bytes, encoding: str | None) -> str:
    if encoding:
        try:
            return payload.decode(encoding, errors="replace")
        except LookupError:
            pass
    return payload.decode("utf-8", errors="replace")


def _safe_url(candidate: str, base_url: str) -> str:
    joined = urljoin(base_url, candidate.strip()) if candidate.strip() else base_url
    parsed = urlsplit(joined)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return base_url
    return urlunsplit(parsed)


def _document_type(source: SourceConfig) -> DocumentType:
    if source.category in {
        SourceCategory.VULNERABILITIES,
        SourceCategory.CERT_ADVISORIES,
        SourceCategory.VENDOR_ADVISORIES,
    }:
        return DocumentType.ADVISORY
    return DocumentType.ARTICLE


def _language(root: ElementTree.Element, item: ElementTree.Element) -> str | None:
    for element in (item, root):
        value = element.attrib.get("{http://www.w3.org/XML/1998/namespace}lang")
        if value:
            return value.strip()
    value = _text(root, ("language",))
    if not value:
        value = next(
            (
                _element_text(candidate)
                for candidate in root.iter()
                if _local_name(candidate.tag) == "language"
            ),
            "",
        )
    return value or None


def _authors(item: ElementTree.Element) -> tuple[str, ...]:
    values: list[str] = []
    for child in item.iter():
        local = _local_name(child.tag)
        if local in {"creator", "author", "name"}:
            value = normalize_html_text(_element_text(child))
            if value and value not in values:
                values.append(value)
    return tuple(values)


def _atom_link(item: ElementTree.Element, base_url: str) -> str:
    candidates: list[tuple[str, str]] = []
    for child in list(item):
        if _local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href", "")
        if href:
            candidates.append((child.attrib.get("rel", "alternate"), href))
    for relation in ("alternate", ""):
        for candidate_relation, href in candidates:
            if candidate_relation == relation:
                return _safe_url(href, base_url)
    return base_url


def _rss_link(item: ElementTree.Element, base_url: str) -> str:
    link = _text(item, ("link",))
    guid = _text(item, ("guid", "id"))
    candidate = link or (guid if urlsplit(guid).scheme else "")
    return _safe_url(candidate, base_url)


def _source_document(
    *,
    source: SourceConfig,
    artifact: RawArtifactMetadata,
    external_id: str | None,
    canonical_url: str,
    title: str,
    authors: tuple[str, ...],
    published_at: datetime | None,
    updated_at: datetime | None,
    normalized_text: str,
    summary: str | None,
    language: str | None,
    content_type: str,
) -> SourceDocument:
    content_hash = sha256_text(normalized_text)
    identity = external_id or canonical_url
    document_id = uuid5(
        NAMESPACE_URL,
        f"source-document:{source.source_id}:{identity}:{content_hash}",
    )
    return SourceDocument(
        source_document_id=document_id,
        source_id=source.source_id,
        raw_artifact_id=artifact.raw_artifact_id,
        external_source_id=external_id,
        canonical_url=canonical_url,
        title=title or canonical_url,
        authors=authors,
        published_at=published_at,
        updated_at_source=updated_at,
        retrieved_at=artifact.retrieved_at,
        content_type=content_type or "application/octet-stream",
        normalized_text=normalized_text,
        sanitized_summary=summary,
        language=language,
        document_type=_document_type(source),
        normalized_content_hash=content_hash,
        parse_version=PARSER_VERSION,
    )


def _sort_documents(documents: Iterable[SourceDocument]) -> tuple[SourceDocument, ...]:
    def key(document: SourceDocument) -> tuple[bool, float, str, str, str]:
        timestamp = document.published_at.timestamp() if document.published_at else 0.0
        return (
            document.published_at is None,
            -timestamp,
            str(document.canonical_url),
            document.external_source_id or "",
            document.title,
        )

    unique = {
        (
            document.external_source_id or str(document.canonical_url),
            document.normalized_content_hash,
        ): document
        for document in documents
    }
    return tuple(sorted(unique.values(), key=key))


def normalize_feed(
    source: SourceConfig, fetch: FetchResult, artifact: RawArtifactMetadata
) -> tuple[SourceDocument, ...]:
    """Normalize RSS 2.0 or Atom entries into source documents."""

    try:
        root = ElementTree.fromstring(fetch.body)
    except ElementTree.ParseError as exc:
        raise NormalizationError(
            "malformed_xml", "XML payload could not be parsed"
        ) from exc

    root_name = _local_name(root.tag)
    if source.source_type is SourceType.ATOM:
        if root_name != "feed":
            raise NormalizationError(
                "schema_error", "Atom source did not return a feed"
            )
        items = [child for child in list(root) if _local_name(child.tag) == "entry"]
    else:
        if root_name == "feed":
            items = [child for child in list(root) if _local_name(child.tag) == "entry"]
        elif root_name == "rss":
            channel = _child(root, ("channel",))
            if channel is None:
                channel = root
            items = [
                child for child in list(channel) if _local_name(child.tag) == "item"
            ]
        else:
            raise NormalizationError(
                "schema_error", "RSS source did not return RSS XML"
            )

    documents: list[SourceDocument] = []
    for item in items:
        is_atom = (
            _local_name(root.tag) == "feed" or source.source_type is SourceType.ATOM
        )
        external_id = _text(item, ("id", "guid")) or None
        canonical_url = (
            _atom_link(item, str(source.url))
            if is_atom
            else _rss_link(item, str(source.url))
        )
        title = (
            normalize_html_text(_text(item, ("title",))) or external_id or canonical_url
        )
        body_value = _text(item, ("content", "encoded", "description", "summary"))
        body = normalize_html_text(_decode(body_value.encode("utf-8"), None))
        normalized_text = " ".join(part for part in (title, body) if part).strip()
        summary_value = _text(item, ("summary", "description"))
        summary = normalize_html_text(summary_value) or None
        published = _parse_datetime(
            _text(item, ("pubdate", "published", "date", "created"))
        )
        updated = _parse_datetime(_text(item, ("updated", "modified", "lastmod")))
        documents.append(
            _source_document(
                source=source,
                artifact=artifact,
                external_id=external_id,
                canonical_url=canonical_url,
                title=title,
                authors=_authors(item),
                published_at=published,
                updated_at=updated,
                normalized_text=normalized_text or title,
                summary=summary,
                language=_language(root, item),
                content_type=fetch.content_type or "application/xml",
            )
        )
    return _sort_documents(documents)


def _kev_text(entry: dict[str, Any]) -> str:
    fields = (
        ("CVE", entry.get("cveID")),
        ("Vendor", entry.get("vendorProject")),
        ("Product", entry.get("product")),
        ("Vulnerability", entry.get("vulnerabilityName")),
        ("Description", entry.get("shortDescription")),
        ("Date added", entry.get("dateAdded")),
        ("Required action", entry.get("requiredAction")),
        ("Due date", entry.get("dueDate")),
        ("Known ransomware campaign use", entry.get("knownRansomwareCampaignUse")),
        ("Notes", entry.get("notes")),
    )
    values = [f"{label}: {value}" for label, value in fields if value not in (None, "")]
    cwes = entry.get("cwes")
    if isinstance(cwes, list) and cwes:
        values.append("CWEs: " + ", ".join(str(value) for value in cwes))
    return "\n".join(values)


def normalize_kev(
    source: SourceConfig, fetch: FetchResult, artifact: RawArtifactMetadata
) -> tuple[SourceDocument, ...]:
    """Normalize the public CISA KEV catalog, one document per CVE."""

    try:
        payload = json.loads(_decode(fetch.body, fetch.encoding))
    except json.JSONDecodeError as exc:
        raise NormalizationError(
            "invalid_json", "JSON payload could not be parsed"
        ) from exc
    if not isinstance(payload, dict) or not isinstance(
        payload.get("vulnerabilities"), list
    ):
        raise NormalizationError(
            "schema_error", "KEV payload lacks a vulnerabilities array"
        )

    documents: list[SourceDocument] = []
    base_url = str(source.url)
    for raw_entry in payload["vulnerabilities"]:
        if not isinstance(raw_entry, dict) or not isinstance(
            raw_entry.get("cveID"), str
        ):
            raise NormalizationError("schema_error", "KEV entry lacks a string cveID")
        cve_id = raw_entry["cveID"].strip().upper()
        if not re.fullmatch(r"CVE-\d{4}-\d{4,}", cve_id):
            raise NormalizationError("schema_error", "KEV entry has an invalid cveID")
        text = _kev_text(raw_entry)
        summary_value = raw_entry.get("shortDescription")
        summary = normalize_html_text(str(summary_value)) if summary_value else None
        title = normalize_html_text(str(raw_entry.get("vulnerabilityName") or cve_id))
        canonical_url = f"{base_url.split('#', 1)[0]}#{quote(cve_id)}"
        documents.append(
            _source_document(
                source=source,
                artifact=artifact,
                external_id=cve_id,
                canonical_url=canonical_url,
                title=title,
                authors=("CISA",),
                published_at=_parse_datetime(str(raw_entry.get("dateAdded", ""))),
                updated_at=_parse_datetime(str(payload.get("dateReleased", ""))),
                normalized_text=normalize_html_text(text),
                summary=summary,
                language=None,
                content_type=fetch.content_type or "application/json",
            )
        )
    return _sort_documents(documents)
