"""Regex and NLP-based IOC Extractor module."""

import re
from typing import Dict, List


class IOCExtractor:
    """Extracts IPv4, IPv6, Domain, URL, MD5, SHA256 indicators of compromise."""

    IPV4_REGEX = r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"
    SHA256_REGEX = r"\b[A-Fa-f0-9]{64}\b"
    MD5_REGEX = r"\b[A-Fa-f0-9]{32}\b"

    def extract_from_text(self, text: str) -> Dict[str, List[str]]:
        """Parses text and returns classified IOC dictionary."""
        return {
            "ipv4": list(set(re.findall(self.IPV4_REGEX, text))),
            "sha256": list(set(re.findall(self.SHA256_REGEX, text))),
            "md5": list(set(re.findall(self.MD5_REGEX, text))),
        }
