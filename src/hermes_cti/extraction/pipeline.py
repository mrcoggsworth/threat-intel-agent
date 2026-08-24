"""Deterministic, evidence-preserving IOC and CVE extraction."""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit
from uuid import NAMESPACE_URL, uuid5

from hermes_cti.extraction.contracts import (
    CveCandidate,
    ExtractionConfig,
    ExtractionResult,
    IndicatorObservation,
    IPExclusionClass,
)
from hermes_cti.models.contracts import (
    IndicatorType,
    IndicatorValidationState,
    SourceDocument,
)


class ExtractionLimitError(ValueError):
    """Raised when a document exceeds the configured deterministic limit."""


class ExtractionError(ValueError):
    """Raised for an invalid extraction input or policy."""


@dataclass(frozen=True, slots=True)
class _MappedText:
    text: str
    starts: tuple[int, ...]
    ends: tuple[int, ...]

    def original_span(self, start: int, end: int) -> tuple[int, int]:
        if start < 0 or end <= start or end > len(self.text):
            raise ValueError("invalid transformed text span")
        return self.starts[start], self.ends[end - 1]


@dataclass(frozen=True, slots=True)
class _Candidate:
    indicator_type: IndicatorType
    start: int
    end: int
    normalized_value: str
    extraction_rule: str
    transformed_start: int
    transformed_end: int
    suppressed_reason: str | None = None


_REFANG_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?i)hxxps(?=:\/\/|\[:\]|\[:\/\/\]|\(:\)|\(:\/\/\)|\{:\}|\{:\/\/\})"
        ),
        "https",
    ),
    (
        re.compile(
            r"(?i)hxxp(?=:\/\/|\[:\]|\[:\/\/\]|\(:\)|\(:\/\/\)|\{:\}|\{:\/\/\})"
        ),
        "http",
    ),
    (re.compile(r"(?i)\[://\]|\(:\/\/\)|\{:\/\/\}"), "://"),
    (re.compile(r"(?i)\[:\]|\(:\)|\{:\}"), ":"),
    (re.compile(r"(?i)\[\.\]|\(\.\)|\{\.\}|<\.>"), "."),
    (re.compile(r"(?i)\[@\]|\(@\)|\{@\}"), "@"),
    (re.compile(r"(?i)\[-\]|\(-\)|\{-\}"), "-"),
)

_URL_RE = re.compile(r"(?i)(?<![\w])https?://[^\s<>\"'`]+")
_EMAIL_RE = re.compile(
    r"(?i)(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[A-Z0-9\u0080-\uffff-]+\.)+[A-Z\u0080-\uffff]{2,63}(?![\w.-])"
)
_DOMAIN_RE = re.compile(
    r"(?<![@\w.-])(?:[A-Z0-9\u0080-\uffff]"
    r"(?:[A-Z0-9\u0080-\uffff-]{0,61}[A-Z0-9\u0080-\uffff])?\.)+"
    r"[A-Z\u0080-\uffff](?:[A-Z0-9\u0080-\uffff-]{0,61}"
    r"[A-Z0-9\u0080-\uffff])?(?![\w.-])",
    re.IGNORECASE,
)
_IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
_IPV6_RE = re.compile(
    r"(?<![0-9A-Za-z:])(?:::1|::|(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4})(?![0-9A-Za-z:])"
)
_HASH_RE = {
    IndicatorType.SHA256: re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{64}(?![0-9A-Fa-f])"),
    IndicatorType.SHA1: re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{40}(?![0-9A-Fa-f])"),
    IndicatorType.MD5: re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{32}(?![0-9A-Fa-f])"),
}
_CVE_RE = re.compile(r"(?i)(?<![A-Z0-9])CVE[\s_-]?(\d{4})[\s_-](\d{4,})(?!\d)")
_REGISTRY_RE = re.compile(
    r"(?i)(?<![\w])(?:HKLM|HKCU|HKCR|HKU|HKCC|HKEY_[A-Z_]+)\\[^\s<>\"']+"
)
_WINDOWS_PATH_RE = re.compile(r"(?<![\w])(?:[A-Z]:\\|\\\\)[^\s<>\"']+")
_POSIX_PATH_RE = re.compile(r"(?<![\w])/(?:[A-Za-z0-9._~-]+/){1,}[A-Za-z0-9._~-]+")
_TRAILING_PUNCTUATION = ".,;!?" + "'\""

_DOCUMENTATION_NETWORKS = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("2001:db8::/32"),
)

_CANDIDATE_PRIORITY = {
    IndicatorType.URL: 0,
    IndicatorType.EMAIL: 1,
    IndicatorType.REGISTRY_PATH: 2,
    IndicatorType.FILE_PATH: 3,
    IndicatorType.IPV6: 4,
    IndicatorType.IPV4: 5,
    IndicatorType.DOMAIN: 6,
    IndicatorType.SHA256: 7,
    IndicatorType.SHA1: 8,
    IndicatorType.MD5: 9,
}


def _refang(value: str) -> _MappedText:
    """Refang only recognized safe-display tokens while retaining source mapping."""

    pieces: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    cursor = 0
    while cursor < len(value):
        match: re.Match[str] | None = None
        replacement = ""
        for pattern, candidate_replacement in _REFANG_PATTERNS:
            found = pattern.match(value, cursor)
            if found is not None:
                match = found
                replacement = candidate_replacement
                break
        if match is None:
            pieces.append(value[cursor])
            starts.append(cursor)
            ends.append(cursor + 1)
            cursor += 1
            continue
        pieces.append(replacement)
        starts.extend([match.start()] * len(replacement))
        ends.extend([match.end()] * len(replacement))
        cursor = match.end()
    return _MappedText("".join(pieces), tuple(starts), tuple(ends))


def refang_text(value: str) -> str:
    """Return text with recognized safe-display variants refanged."""

    return _refang(value).text


def _trim_candidate(text: str, start: int, end: int) -> tuple[int, int]:
    while end > start and (
        text[end - 1] in _TRAILING_PUNCTUATION
        or unicodedata.category(text[end - 1]).startswith("P")
        and text[end - 1] not in ":/#"
    ):
        end -= 1
    while (
        end > start
        and text[end - 1] == ")"
        and text[start:end].count(")") > text[start:end].count("(")
    ):
        end -= 1
    while (
        end > start
        and text[end - 1] == "]"
        and text[start:end].count("]") > text[start:end].count("[")
    ):
        end -= 1
    return start, end


def _normalize_domain(value: str) -> str:
    candidate = value.strip().rstrip(".")
    try:
        ascii_domain = candidate.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("domain is not IDNA encodable") from exc
    labels = ascii_domain.split(".")
    if (
        not labels
        or len(ascii_domain) > 253
        or any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or not re.fullmatch(r"[a-z0-9-]+", label)
            for label in labels
        )
    ):
        raise ValueError("invalid domain")
    if len(labels[-1]) < 2:
        raise ValueError("invalid domain suffix")
    return ascii_domain


def _normalize_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"}:
            raise ValueError("unsupported URL scheme")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("URL credentials are not accepted")
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("URL host is missing")
        try:
            address = ipaddress.ip_address(hostname)
            normalized_host = str(address)
            if address.version == 6:
                normalized_host = f"[{normalized_host}]"
        except ValueError:
            normalized_host = _normalize_domain(hostname)
        port = parsed.port
        if port is not None and not 1 <= port <= 65_535:
            raise ValueError("invalid URL port")
        netloc = normalized_host + (f":{port}" if port is not None else "")
        return urlunsplit(
            SplitResult(
                parsed.scheme.lower(),
                netloc,
                parsed.path,
                parsed.query,
                parsed.fragment,
            )
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid HTTP(S) URL") from exc


def _normalize_email(value: str) -> str:
    local, separator, domain = value.rpartition("@")
    if not separator or not local or " " in local:
        raise ValueError("invalid email")
    return f"{local.lower()}@{_normalize_domain(domain)}"


def _ip_classification(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> IPExclusionClass | None:
    if any(address in network for network in _DOCUMENTATION_NETWORKS):
        return IPExclusionClass.DOCUMENTATION
    if address.is_unspecified:
        return IPExclusionClass.UNSPECIFIED
    if address.is_loopback:
        return IPExclusionClass.LOOPBACK
    if address.is_multicast:
        return IPExclusionClass.MULTICAST
    if address.is_link_local:
        return IPExclusionClass.LINK_LOCAL
    if address.is_reserved:
        return IPExclusionClass.RESERVED
    if address.is_private:
        return IPExclusionClass.PRIVATE
    return None


def _context(text: str, start: int, end: int, width: int) -> str:
    if width == 0:
        return ""
    return text[max(0, start - width) : min(len(text), end + width)]


def _candidate_span(
    mapped: _MappedText, match: re.Match[str]
) -> tuple[int, int, int, int]:
    transformed_start, transformed_end = _trim_candidate(
        mapped.text, match.start(), match.end()
    )
    if transformed_end <= transformed_start:
        raise ValueError("empty candidate")
    start, end = mapped.original_span(transformed_start, transformed_end)
    return start, end, transformed_start, transformed_end


def _candidate_value(
    indicator_type: IndicatorType, raw: str, config: ExtractionConfig
) -> tuple[str, str | None]:
    if indicator_type is IndicatorType.URL:
        normalized = _normalize_url(raw)
        hostname = urlsplit(normalized).hostname
        if hostname is not None and hostname in config.suppressed_domains:
            return normalized, "suppressed_domain"
    elif indicator_type is IndicatorType.DOMAIN:
        normalized = _normalize_domain(raw)
        if normalized in config.suppressed_domains or any(
            normalized.endswith(f".{domain}") for domain in config.suppressed_domains
        ):
            return normalized, "suppressed_domain"
    elif indicator_type is IndicatorType.EMAIL:
        normalized = _normalize_email(raw)
    elif indicator_type in {IndicatorType.IPV4, IndicatorType.IPV6}:
        address = ipaddress.ip_address(raw)
        expected_version = 4 if indicator_type is IndicatorType.IPV4 else 6
        if address.version != expected_version:
            raise ValueError("address version does not match candidate type")
        normalized = str(address)
        address_class = _ip_classification(address)
        if address_class in config.excluded_ip_classes:
            return normalized, f"excluded_ip_{address_class.value}"
    elif indicator_type in _HASH_RE:
        normalized = raw.lower()
        if len(set(normalized)) == 1 or (
            not any(character.isdigit() for character in normalized)
            and set(normalized) <= set("abcdef")
        ):
            raise ValueError("hash-like ordinary text")
    elif indicator_type in {IndicatorType.FILE_PATH, IndicatorType.REGISTRY_PATH}:
        normalized = raw.strip()
        if "\x00" in normalized:
            raise ValueError("NUL in path")
    else:
        raise ValueError("unsupported extraction type")
    if normalized in config.suppressed_values:
        return normalized, "suppressed_value"
    return normalized, None


def _iter_matches(
    mapped: _MappedText, pattern: re.Pattern[str]
) -> Iterator[tuple[re.Match[str], str]]:
    for match in pattern.finditer(mapped.text):
        yield match, mapped.text[match.start() : match.end()]


def _collect_candidates(
    mapped: _MappedText, config: ExtractionConfig
) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    patterns: tuple[tuple[IndicatorType, re.Pattern[str], str], ...] = (
        (IndicatorType.URL, _URL_RE, "url-http-parser"),
        (IndicatorType.EMAIL, _EMAIL_RE, "email-rfc5322-like"),
        (IndicatorType.REGISTRY_PATH, _REGISTRY_RE, "windows-registry-path"),
        (IndicatorType.FILE_PATH, _WINDOWS_PATH_RE, "windows-file-path"),
        (IndicatorType.FILE_PATH, _POSIX_PATH_RE, "posix-file-path"),
        (IndicatorType.IPV6, _IPV6_RE, "ipv6-ipaddress"),
        (IndicatorType.IPV4, _IPV4_RE, "ipv4-ipaddress"),
        (IndicatorType.DOMAIN, _DOMAIN_RE, "domain-idna"),
    )
    for indicator_type, pattern, rule in patterns:
        if indicator_type is IndicatorType.EMAIL and not config.extract_email:
            continue
        if indicator_type is IndicatorType.FILE_PATH and not config.extract_file_paths:
            continue
        if (
            indicator_type is IndicatorType.REGISTRY_PATH
            and not config.extract_registry_paths
        ):
            continue
        for match, _raw in _iter_matches(mapped, pattern):
            try:
                start, end, transformed_start, transformed_end = _candidate_span(
                    mapped, match
                )
                normalized, suppressed_reason = _candidate_value(
                    indicator_type,
                    mapped.text[transformed_start:transformed_end],
                    config,
                )
            except ValueError:
                continue
            candidates.append(
                _Candidate(
                    indicator_type,
                    start,
                    end,
                    normalized,
                    rule,
                    transformed_start,
                    transformed_end,
                    suppressed_reason,
                )
            )
    for indicator_type, pattern in _HASH_RE.items():
        for match, raw in _iter_matches(mapped, pattern):
            try:
                start, end, transformed_start, transformed_end = _candidate_span(
                    mapped, match
                )
                normalized, suppressed_reason = _candidate_value(
                    indicator_type, raw, config
                )
            except ValueError:
                continue
            candidates.append(
                _Candidate(
                    indicator_type,
                    start,
                    end,
                    normalized,
                    f"{indicator_type.value}-hex-length",
                    transformed_start,
                    transformed_end,
                    suppressed_reason,
                )
            )
    return candidates


def _select_candidates(candidates: list[_Candidate]) -> tuple[_Candidate, ...]:
    ordered = sorted(
        candidates,
        key=lambda item: (
            item.start,
            _CANDIDATE_PRIORITY[item.indicator_type],
            -(item.end - item.start),
        ),
    )
    urls = [item for item in ordered if item.indicator_type is IndicatorType.URL]
    emails = [item for item in ordered if item.indicator_type is IndicatorType.EMAIL]
    selected: list[_Candidate] = []
    seen: set[tuple[IndicatorType, str]] = set()
    for candidate in ordered:
        contained_by_url = any(
            url.transformed_start <= candidate.transformed_start
            and candidate.transformed_end <= url.transformed_end
            and candidate is not url
            for url in urls
        )
        contained_by_email = any(
            email.transformed_start <= candidate.transformed_start
            and candidate.transformed_end <= email.transformed_end
            and candidate is not email
            for email in emails
        )
        if contained_by_url or contained_by_email:
            continue
        key = (candidate.indicator_type, candidate.normalized_value)
        if key in seen:
            continue
        if any(
            candidate.transformed_start < prior.transformed_end
            and prior.transformed_start < candidate.transformed_end
            and candidate.indicator_type is not prior.indicator_type
            for prior in selected
        ):
            continue
        seen.add(key)
        selected.append(candidate)
    return tuple(selected)


def _extract_cves(
    document: SourceDocument, mapped: _MappedText, config: ExtractionConfig
) -> tuple[CveCandidate, ...]:
    candidates: list[CveCandidate] = []
    seen: set[str] = set()
    for match in _CVE_RE.finditer(mapped.text):
        try:
            start, end, transformed_start, transformed_end = _candidate_span(
                mapped, match
            )
            normalized = f"CVE-{match.group(1)}-{match.group(2)}".upper()
            if normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(
                CveCandidate(
                    candidate_id=uuid5(
                        NAMESPACE_URL,
                        f"cve-candidate:{document.source_document_id}:{normalized}",
                    ),
                    original_display_value=document.normalized_text[start:end],
                    normalized_value=normalized,
                    source_document_id=document.source_document_id,
                    start_offset=start,
                    end_offset=end,
                    context=_context(
                        document.normalized_text, start, end, config.context_chars
                    ),
                    extraction_rule="cve-id-format",
                )
            )
        except ValueError:
            continue
    return tuple(
        sorted(candidates, key=lambda item: (item.start_offset, item.normalized_value))
    )


def extract_document(
    document: SourceDocument, config: ExtractionConfig | None = None
) -> ExtractionResult:
    """Extract deterministic observations from one typed source document."""

    policy = config or ExtractionConfig()
    text = document.normalized_text
    if len(text) > policy.max_input_chars:
        raise ExtractionLimitError(
            f"source document exceeds max_input_chars={policy.max_input_chars}"
        )
    mapped = _refang(text)
    candidates = _select_candidates(_collect_candidates(mapped, policy))
    observations: list[IndicatorObservation] = []
    suppressed: list[IndicatorObservation] = []
    for candidate in candidates:
        observation = IndicatorObservation(
            observation_id=uuid5(
                NAMESPACE_URL,
                f"indicator-observation:{document.source_document_id}:"
                f"{candidate.indicator_type.value}:{candidate.normalized_value}",
            ),
            indicator_type=candidate.indicator_type,
            original_display_value=text[candidate.start : candidate.end],
            normalized_value=candidate.normalized_value,
            source_document_id=document.source_document_id,
            start_offset=candidate.start,
            end_offset=candidate.end,
            context=_context(
                text, candidate.start, candidate.end, policy.context_chars
            ),
            extraction_rule=candidate.extraction_rule,
            validation_state=(
                IndicatorValidationState.SUPPRESSED
                if candidate.suppressed_reason
                else IndicatorValidationState.VALIDATED
            ),
            suppression_reason=candidate.suppressed_reason,
        )
        (suppressed if candidate.suppressed_reason else observations).append(
            observation
        )
    return ExtractionResult(
        source_document_id=document.source_document_id,
        observations=tuple(observations),
        cve_candidates=_extract_cves(document, mapped, policy),
        suppressed_observations=tuple(suppressed),
    )
