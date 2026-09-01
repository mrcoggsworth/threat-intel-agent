"""HTML & PDF article extraction and boilerplate stripper."""

from __future__ import annotations

import io
import re
from html.parser import HTMLParser

from hermes_cti.ingestion.http_client import (
    AsyncHTTPClient,
    FetchError,
    HTTPClientConfig,
)


class HTMLArticleParser(HTMLParser):
    """Sanitizing HTML parser that strips boilerplate and formats text."""

    _ignored = {
        "script",
        "style",
        "noscript",
        "template",
        "svg",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
    }
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
        if lowered in self._ignored and self._ignored_depth > 0:
            self._ignored_depth -= 1
        elif self._ignored_depth == 0 and lowered in self._blocks:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0:
            self.parts.append(data)


def clean_html_content(raw_html: str) -> str:
    """Pure function for sanitizing HTML strings into normalized clean text."""
    if not raw_html:
        return ""
    parser = HTMLArticleParser()
    parser.feed(raw_html)
    parser.close()
    text = "".join(parser.parts)
    # Collapse consecutive horizontal whitespace while preserving paragraph breaks
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    # Remove excessive blank lines
    non_empty: list[str] = []
    for line in lines:
        if line:
            non_empty.append(line)
        elif non_empty and non_empty[-1] != "":
            non_empty.append("")
    return "\n".join(non_empty).strip()


def extract_pdf_text_fallback(pdf_bytes: bytes) -> str:
    """Safe extractor for PDF advisories with fallback when libraries are absent."""
    if not pdf_bytes:
        return ""

    # Attempt PyPDF / pypdf / pdfplumber if installed
    try:
        import pypdf  # type: ignore[import-not-found]

        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages_text: list[str] = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages_text.append(t)
        if pages_text:
            return "\n\n".join(pages_text).strip()
    except (ImportError, Exception):
        pass

    # Fallback to plain text / stream extraction using regex heuristics on raw PDF bytes
    extracted_text_chunks: list[str] = []
    # Match text within PDF stream text objects BT ... ET
    bt_chunks = re.findall(rb"BT[\s\S]*?ET", pdf_bytes)
    for chunk in bt_chunks:
        # Extract string literals in parentheses (text)
        text_literals = re.findall(rb"\((.*?)\)", chunk)
        for lit in text_literals:
            try:
                decoded = lit.decode("utf-8", errors="ignore").strip()
                if decoded:
                    extracted_text_chunks.append(decoded)
            except Exception:
                continue

    if extracted_text_chunks:
        return " ".join(extracted_text_chunks)

    return ""


async def fetch_article_text(
    url: str,
    timeout: float = 20.0,
    user_agent: str = "HermesCTI/1.0 (+https://cti.scogin.dev)",
    client: AsyncHTTPClient | None = None,
) -> str:
    """Fetch article content via AsyncHTTPClient and extract clean text."""

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
        content_type = (res.content_type or "").lower()
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            return extract_pdf_text_fallback(res.body)
        raw_text = res.body.decode(res.encoding or "utf-8", errors="replace")
        return clean_html_content(raw_text)
    except FetchError:
        raise
    finally:
        if managed_client:
            await http_client.aclose()
