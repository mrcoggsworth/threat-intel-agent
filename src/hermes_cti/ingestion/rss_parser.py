"""Async RSS 2.0 / Atom feed parser, FeedItem model, date parsing, and deduplication."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree

from hermes_cti.ingestion.http_client import (
    AsyncHTTPClient,
    FetchError,
    HTTPClientConfig,
)
from hermes_cti.ingestion.normalization import NormalizationError, normalize_html_text
from hermes_cti.models.contracts import sha256_text


@dataclass
class FeedItem:
    """Parsed item from an RSS or Atom feed."""

    guid: str
    title: str
    link: str
    published: datetime | None
    summary: str
    content: str = ""
    categories: list[str] = field(default_factory=list)
    author: str = ""
    raw_entry: dict[str, Any] = field(default_factory=dict)


def parse_published_date(date_str: str | None) -> datetime | None:
    """Robust parser supporting RFC 2822 and ISO 8601, returning UTC datetime."""
    if not date_str:
        return None
    candidate = date_str.strip()
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


def _atom_link(item: ElementTree.Element, base_url: str = "") -> str:
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


def _safe_url(candidate: str, base_url: str = "") -> str:
    joined = urljoin(base_url, candidate.strip()) if candidate.strip() else base_url
    parsed = urlsplit(joined)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return candidate.strip() or base_url
    return urlunsplit(parsed)


def _rss_link(item: ElementTree.Element, base_url: str = "") -> str:
    link = _text(item, ("link",))
    guid = _text(item, ("guid", "id"))
    candidate = link or (guid if urlsplit(guid).scheme else "")
    return _safe_url(candidate, base_url)


def parse_feed_xml(xml_content: str | bytes, base_url: str = "") -> list[FeedItem]:
    """Parse RSS 2.0 or Atom XML content into a list of FeedItem instances."""
    if isinstance(xml_content, str):
        payload_bytes = xml_content.encode("utf-8")
    else:
        payload_bytes = xml_content

    if not payload_bytes.strip():
        raise NormalizationError("empty_feed", "Feed XML content is empty")

    try:
        root = ElementTree.fromstring(payload_bytes)
    except ElementTree.ParseError as exc:
        raise NormalizationError(
            "malformed_xml", f"XML payload could not be parsed: {exc}"
        ) from exc

    root_name = _local_name(root.tag)
    is_atom = root_name == "feed"
    if is_atom:
        items = [child for child in list(root) if _local_name(child.tag) == "entry"]
    elif root_name == "rss":
        channel = _child(root, ("channel",))
        if channel is None:
            channel = root
        items = [child for child in list(channel) if _local_name(child.tag) == "item"]
    else:
        raise NormalizationError(
            "schema_error", f"Unrecognized root element <{root_name}>"
        )

    results: list[FeedItem] = []
    for item in items:
        guid = (
            _text(item, ("id", "guid"))
            or (_atom_link(item, base_url) if is_atom else _rss_link(item, base_url))
            or ""
        )
        link = _atom_link(item, base_url) if is_atom else _rss_link(item, base_url)
        raw_title = _text(item, ("title",))
        title = normalize_html_text(unescape(raw_title)) if raw_title else guid or link

        # Categories
        categories: list[str] = []
        for child in item.iter():
            if _local_name(child.tag) == "category":
                cat_val = child.attrib.get("term") or _element_text(child)
                if cat_val and cat_val not in categories:
                    categories.append(cat_val)

        # Author
        author_parts: list[str] = []
        for child in item.iter():
            if _local_name(child.tag) in {"creator", "author", "name"}:
                txt = normalize_html_text(_element_text(child))
                if txt and txt not in author_parts:
                    author_parts.append(txt)
        author = ", ".join(author_parts)

        # Date handling
        pub_date_str = _text(
            item, ("pubdate", "published", "date", "created", "updated", "modified")
        )
        published = parse_published_date(pub_date_str)

        # Summary and content
        summary_raw = _text(item, ("summary", "description"))
        content_raw = _text(item, ("content", "encoded"))
        summary = normalize_html_text(unescape(summary_raw))
        content = normalize_html_text(unescape(content_raw)) if content_raw else summary

        raw_entry_dict: dict[str, Any] = {
            "tag": item.tag,
            "guid": guid,
            "title": title,
            "link": link,
            "pub_date_str": pub_date_str,
            "categories": categories,
            "author": author,
        }

        results.append(
            FeedItem(
                guid=guid,
                title=title,
                link=link,
                published=published,
                summary=summary,
                content=content,
                categories=categories,
                author=author,
                raw_entry=raw_entry_dict,
            )
        )

    return results


async def fetch_and_parse_feed(
    url: str,
    timeout: float = 15.0,
    user_agent: str = "HermesCTI/1.0 (+https://cti.scogin.dev)",
    client: AsyncHTTPClient | None = None,
) -> list[FeedItem]:
    """Fetch and parse an RSS or Atom feed via AsyncHTTPClient."""
    managed_client = client is None
    http_client = client or AsyncHTTPClient(
        HTTPClientConfig(
            connect_timeout_seconds=min(10.0, timeout),
            read_timeout_seconds=timeout,
            user_agent=user_agent,
        )
    )
    try:
        res = await http_client.fetch(url, timeout_seconds=timeout)
        return parse_feed_xml(res.body, base_url=url)
    except FetchError:
        raise
    finally:
        if managed_client:
            await http_client.aclose()


class FeedDeduplicator:
    """Tracks seen GUIDs, content hashes, and canonical URLs across polling cycles."""

    def __init__(self) -> None:
        self._seen_guids: set[str] = set()
        self._seen_urls: set[str] = set()
        self._seen_content_hashes: set[str] = set()

    def is_duplicate(self, item: FeedItem) -> bool:
        """Check if an item has been seen by GUID, canonical link, or content."""
        if item.guid and item.guid in self._seen_guids:
            return True
        if item.link and item.link in self._seen_urls:
            return True
        content_hash = sha256_text(item.content or item.summary or item.title)
        return content_hash in self._seen_content_hashes

    def mark_seen(self, item: FeedItem) -> None:
        """Mark an item as seen."""
        if item.guid:
            self._seen_guids.add(item.guid)
        if item.link:
            self._seen_urls.add(item.link)
        content_hash = sha256_text(item.content or item.summary or item.title)
        self._seen_content_hashes.add(content_hash)

    def filter_new(self, items: Iterable[FeedItem]) -> list[FeedItem]:
        """Filter out duplicates and record newly seen items."""
        new_items: list[FeedItem] = []
        for item in items:
            if not self.is_duplicate(item):
                self.mark_seen(item)
                new_items.append(item)
        return new_items

    def clear(self) -> None:
        """Reset deduplication state."""
        self._seen_guids.clear()
        self._seen_urls.clear()
        self._seen_content_hashes.clear()
