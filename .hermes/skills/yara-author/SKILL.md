---
name: yara-author
description: Converts file headers, magic bytes, string patterns, and byte sequences into valid YARA rules for memory and file triage.
---

# 🎯 yara-author // Malware Triage & Signature Authoring Skill

## Overview
The `yara-author` skill extracts file-based artifacts, strings, magic byte signatures, and code sequences from CTI reports and threat write-ups, producing syntactically valid **YARA rules** for incident responders to scan disk images, endpoint filesystems, and memory dumps.

## Why Create It
- Generates endpoint-level detection signatures for malware binaries mentioned in threat write-ups.
- Translates extracted string patterns (mutexes, C2 URIs, internal PDB paths) into compiled YARA logic.
- Ensures rules pass YARA syntax verification without compiler errors.

## Rule Schema Template (YARA)

```yara
rule Hermes_Malware_Triage_Sample {
    meta:
        description = "Detects file artifacts associated with analyzed campaign"
        author = "Hermes Autonomous CTI Agent"
        reference = "https://hermes-cti-portal.local"
        date = "2026-08-12"
        score = 80

    strings:
        $magic = { 4D 5A } // PE Header
        $str1 = "malicious_mutex_name" ascii wide
        $str2 = "http://c2-infrastructure.local/gate.php" ascii wide
        $hex_pattern = { E8 [4] 85 C0 74 05 E8 [4] 50 }

    condition:
        $magic at 0 and 2 of ($str*) or $hex_pattern
}
```

## Step-by-Step Procedure
1. **Extract Artifact Indicators:** Identify unique PDB paths, mutex names, static strings, and byte sequences.
2. **Define Metadata Block:** Attach author, description, reference link, and risk score.
3. **Assemble Strings & Hex Patterns:** Define ASCII/wide strings and hex patterns with appropriate wildcard bounds (`[4]`).
4. **Construct Condition Block:** Ensure file header magic checks (`$magic at 0`) are present to prevent unnecessary performance overhead.
5. **Verify Syntax:** Validate YARA syntax compliance prior to storing or publishing.
