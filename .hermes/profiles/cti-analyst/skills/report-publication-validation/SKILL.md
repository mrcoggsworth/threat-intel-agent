---
name: report-publication-validation
description: Validate a report bundle before requesting controlled publication.
---

# Report Publication Validation

Ensure every synthesized `ReportBundle` complies strictly with schema contracts, domain validation gates, and detection compilation standards prior to API submission.

## Pre-Flight Local Validation Command

Before sending payloads across the network to `POST /api/v1/analyst/reports/validate` or `POST /api/v1/analyst/reports`, execute offline schema and coverage validation:

```bash
hermes-cti analyst validate-bundle <path_to_bundle.json>
```

This verifies Pydantic schemas, evidence cross-references, headline word attestation, Sigma translation, and YARA compilation locally, returning exact line numbers and missing words if invalid.

## Mandatory Validation Gates

### 1. Headline Word Coverage Rule
- Every word in `headline` of length >= 5 characters that is not in the stopword list (`about, after, against, documented, evidence, from, public, reported, that, this, with`) **MUST appear case-insensitively** within at least one `evidence[].statement` string.
- Forbidden internal environment phrases (`your environment`, `your organization`, `internal compromise`, `home lab`, `confirmed breach`) are strictly prohibited in headlines.

### 2. Required Report Sections
A report bundle will be rejected if any of the following are omitted:
- `hunt`: Full threat hunt playbook with hypothesis, log sources, and execution phases.
- `remediation`: Phased remediation actions with non-empty steps.
- `detections`: Machine-readable detection artifacts with valid rule definitions.
- `timeline`: Key milestone events with supporting evidence IDs.
- `caveats`: Analytical limitations and intelligence gaps.

### 3. Schema Structure Details
- **Affected Products (`AffectedProduct`)**: Requires nested `product: Product(product_id, vendor, product, ecosystem)`, plus `version_range`, `affected_status`, and `confidence`. (Do not use flat vendor/version strings).
- **Public Sources (`PublicSourceReference`)**: Requires `source_id, name, canonical_url, category, reliability`.
- **ATT&CK Mappings (`AttackTechniqueMapping`)**: Requires `mapping_id, attack_id, name, tactic, framework_version, confidence, source_document_ids`.
- **Detections**: Sigma YAML must define a valid `condition` and map to Windows/Linux log sources. YARA rules must compile cleanly without syntax errors.

### 4. Dynamic Identifier Sequence Allocation
To avoid unique constraint violations on `(report_id, version)` and `public_id`:
```bash
hermes-cti analyst next-public-id
```
Assign the returned public ID (e.g. `PUB-2026-019`) to new report bundles.
