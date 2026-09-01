from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field

IPV4_REGEX = (
    r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
)
IPV6_REGEX = (
    r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"
    r"|(?:[0-9a-fA-F]{1,4}:){1,7}:"
    r"|:(?::[0-9a-fA-F]{1,4}){1,7}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}"
    r"|[0-9a-fA-F]{1,4}:(?:(?::[0-9a-fA-F]{1,4}){1,6})"
)
CIDR_REGEX = (
    r"(?<![\w.:])(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F:]*"
    r"/(?:12[0-8]|1[01][0-9]|[1-9]?[0-9])(?![\w.])"
    r"|(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}"
    r"/(?:3[0-2]|[12]?\d)(?![\w.])"
)
MD5_REGEX = r"\b[a-fA-F0-9]{32}\b"
SHA1_REGEX = r"\b[a-fA-F0-9]{40}\b"
SHA256_REGEX = r"\b[a-fA-F0-9]{64}\b"
DOMAIN_REGEX = r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b"
URL_REGEX = r"https?://[^\s<>\"'{}|\\^`\[\]]+"
CVE_REGEX = r"\bCVE-\d{4}-\d{4,7}\b"


@dataclass
class ExtractedIOCs:
    ipv4: list[str] = field(default_factory=list)
    ipv6: list[str] = field(default_factory=list)
    md5: list[str] = field(default_factory=list)
    sha1: list[str] = field(default_factory=list)
    sha256: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    cves: list[str] = field(default_factory=list)
    cidrs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "ipv4": self.ipv4,
            "ipv6": self.ipv6,
            "md5": self.md5,
            "sha1": self.sha1,
            "sha256": self.sha256,
            "domains": self.domains,
            "urls": self.urls,
            "cves": self.cves,
            "cidrs": self.cidrs,
        }

    def count(self) -> int:
        return sum(len(v) for v in self.to_dict().values())


def refang_text(text: str) -> str:
    text = re.sub(r"(?i)\bhxxps(?=(?::|\[:\]|\[:/\]|\[://\]))", "https", text)
    text = re.sub(r"(?i)\bhxxp(?=(?::|\[:\]|\[:/\]|\[://\]))", "http", text)
    replacements = (
        (r"(?i)\[://\]", "://"),
        (r"(?i)\[:/\]", ":/"),
        (r"(?i)\[:\]", ":"),
        (r"(?i)\[/\]", "/"),
        (r"(?i)\[\.\]|\(\.\)|\[\\\.\]|\{\.\}|<\.>", "."),
        (r"(?i)\[@\]|\(@\)|\{@\}", "@"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def is_private_or_reserved_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_multicast
            or ip.is_link_local
            or ip.is_reserved
        )
    except ValueError:
        return False


class IOCExtractor:
    """Stateless facade for deterministic indicator extraction."""

    @staticmethod
    def refang_text(text: str) -> str:
        return refang_text(text)

    @staticmethod
    def is_private_or_reserved_ip(ip_str: str) -> bool:
        return is_private_or_reserved_ip(ip_str)

    @staticmethod
    def extract_iocs(
        text: str,
        filter_private_ips: bool = True,
        filter_example_domains: bool = True,
    ) -> ExtractedIOCs:
        return extract_iocs(text, filter_private_ips, filter_example_domains)


def extract_iocs(
    text: str,
    filter_private_ips: bool = True,
    filter_example_domains: bool = True,
) -> ExtractedIOCs:
    text = refang_text(text)

    ipv4s = list(set(re.findall(IPV4_REGEX, text)))
    if filter_private_ips:
        ipv4s = [ip for ip in ipv4s if not is_private_or_reserved_ip(ip)]

    raw_ipv6s = list(set(re.findall(IPV6_REGEX, text)))
    valid_ipv6s: list[str] = []
    for candidate in raw_ipv6s:
        try:
            parsed_ip = ipaddress.IPv6Address(candidate)
            if filter_private_ips and (
                parsed_ip.is_private
                or parsed_ip.is_loopback
                or parsed_ip.is_multicast
                or parsed_ip.is_link_local
                or parsed_ip.is_reserved
            ):
                continue
            valid_ipv6s.append(candidate)
        except ValueError:
            continue

    md5s = list(set(re.findall(MD5_REGEX, text)))
    sha1s = list(set(re.findall(SHA1_REGEX, text)))
    sha256s = list(set(re.findall(SHA256_REGEX, text)))

    domains = list(set(re.findall(DOMAIN_REGEX, text)))
    if filter_example_domains:
        domains = [
            d
            for d in domains
            if d.lower() != "example.com" and not d.lower().endswith(".example.com")
        ]

    urls = []
    for url in set(re.findall(URL_REGEX, text)):
        url = url.rstrip(".,;!?\"'")
        if url.endswith(")") and url.count(")") > url.count("("):
            url = url[:-1]
        urls.append(url)
    if filter_example_domains:
        urls = [
            url
            for url in urls
            if not re.search(
                r"(?i)https?://(?:[^/@]+@)?(?:[^./]+\.)*example\.com"
                r"(?::\d+)?(?:/|$)",
                url,
            )
        ]

    cves = sorted({cve.upper() for cve in re.findall(CVE_REGEX, text, re.IGNORECASE)})

    cidrs: list[str] = []
    for candidate in set(re.findall(CIDR_REGEX, text, re.IGNORECASE)):
        try:
            network = ipaddress.ip_network(candidate, strict=False)
        except ValueError:
            continue
        if filter_private_ips and (
            network.is_private
            or network.is_loopback
            or network.is_link_local
            or network.is_multicast
            or network.is_reserved
        ):
            continue
        cidrs.append(str(network))

    return ExtractedIOCs(
        ipv4=sorted(ipv4s),
        ipv6=sorted(valid_ipv6s),
        md5=sorted(md5s),
        sha1=sorted(sha1s),
        sha256=sorted(sha256s),
        domains=sorted(domains),
        urls=sorted(urls),
        cves=cves,
        cidrs=sorted(set(cidrs)),
    )
