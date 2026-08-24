---
name: ioc-evidence-review
description: Review extracted indicators against source evidence and provenance.
---

# IOC evidence review

Use `ioc-parser` for deterministic extraction and refanging. Confirm each IOC
appears in source evidence, validate type and canonical form, reject private or
non-routable addresses when the pipeline requires it, deduplicate by value and
source, and retain evidence IDs, URLs, timestamps, and confidence. Never infer
an IOC from narrative context alone.
