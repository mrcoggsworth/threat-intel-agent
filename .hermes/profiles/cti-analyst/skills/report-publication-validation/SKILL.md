---
name: report-publication-validation
description: Validate a report bundle before requesting controlled publication.
---

# Report publication validation

Check required sections, evidence coverage, provenance, timestamps, links,
machine-readable artifacts, safe Markdown/JSON rendering, and public/private
projection boundaries. Reject unsupported attribution or exposure claims.
When validation fails, preserve the previous published version and submit the
failure as a structured event.
