# Hermes Agent Memory Log (MEMORY.md)

## Durable Knowledge & Learned Insights

### Ingestion Sources & Reliability
- CISA KEV JSON feed is updated daily and serves as the baseline for active vulnerability exploitation.
- Security blogs require HTML cleaning and regex extraction to filter boilerplate headers and navigation links.

### Rule Synthesis Best Practices
- Sigma rules should be formatted in standard YAML schema with default status set to `experimental` or `test`.
- YARA rules require strict condition definitions to avoid false-positive memory scans.
