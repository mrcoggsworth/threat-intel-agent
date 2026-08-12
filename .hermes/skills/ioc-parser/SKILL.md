---
name: ioc-parser
description: Deterministic extraction and sanitization of IoCs (IPv4, IPv6, MD5, SHA256, domains, defanged URLs) using regex engines.
---

# 🔍 ioc-parser // Deterministic IoC Extraction Skill

## Overview
LLMs can occasionally hallucinate or misread complex network indicators, file hashes, or defanged URLs. The `ioc-parser` skill enforces deterministic extraction using precise regular expressions and parsing libraries (e.g., `iocextract`, `re`) to ensure zero false-positive hash or IP reads.

## Why Create It
- Prevents LLM hallucination of IP addresses, hashes, or domain names.
- Automatically handles defanged IoCs (`192[.]168[.]1[.]1`, `hxxps://malicious[.]com`).
- Standardizes raw unstructured security write-ups into valid JSON output.

## Technical Execution & Regular Expressions

### Pattern Specifications
- **IPv4 Address:** `\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b`
- **MD5 Hash:** `\b[A-Fa-f0-9]{32}\b`
- **SHA256 Hash:** `\b[A-Fa-f0-9]{64}\b`
- **Domain Name:** `\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b`
- **Defanged URL Handling:** Replaces `hxxp`, `hxxps`, `[.]`, `(.)` with canonical network primitives before parsing.

## Output Schema
```json
{
  "ipv4": ["192.0.2.1", "198.51.100.45"],
  "sha256": ["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
  "md5": ["d41d8cd98f00b204e9800998ecf8427e"],
  "domains": ["malicious-domain.com"],
  "urls": ["http://malicious-domain.com/payload.exe"]
}
```

## Step-by-Step Procedure
1. **Refang Raw Input:** Replace defanged patterns (`[.]` -> `.`, `hxxp` -> `http`).
2. **Execute Pattern Matching:** Run regex extractors across normalized text.
3. **Deduplicate & Validate:** Filter out private RFC1918 IPs, localhost, and non-routable addresses.
4. **Return Clean JSON:** Output formatted IoC payload ready for SIEM ingestion or enrichment lookups.
