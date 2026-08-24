---
name: yara-author
description: Generate and validate YARA only when file or memory evidence exists.
---

# YARA generation and validation

Use unique strings, magic bytes, or bounded byte patterns present in evidence.
Add provenance, date, author, and false-positive considerations. Require a
safe condition and avoid generic strings. Compile with the supported YARA
tool when available; otherwise say syntax validation was unavailable.
