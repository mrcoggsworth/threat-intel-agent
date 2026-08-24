---
name: ioc-parser
description: Deterministically extract and validate indicators of compromise.
---

# IOC parser

Normalize defanged `hxxp`, `[.]`, and `(.)` forms, then use deterministic
parsers or regexes for IPv4/IPv6, MD5/SHA-1/SHA-256, domains, URLs, and CVEs.
Deduplicate and validate values; exclude private, localhost, and non-routable
addresses where the service contract requires it. Emit machine-readable JSON
with source and evidence references. The model must not invent indicators.
