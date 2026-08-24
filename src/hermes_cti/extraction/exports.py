"""Deterministic JSON and CSV serialization for extraction results."""

from __future__ import annotations

import csv
import io

from hermes_cti.extraction.contracts import ExtractionResult, IndicatorObservation

_CSV_FIELDS = (
    "record_type",
    "indicator_type",
    "original_display_value",
    "normalized_value",
    "source_document_id",
    "start_offset",
    "end_offset",
    "context",
    "extraction_rule",
    "validation_state",
    "suppression_reason",
)


def to_json(result: ExtractionResult) -> str:
    """Serialize extraction output with stable field and list ordering."""

    return result.stable_json()


def to_csv(result: ExtractionResult, include_suppressed: bool = False) -> str:
    """Serialize observations and CVE candidates in deterministic row order."""

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=_CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    observations: tuple[IndicatorObservation, ...] = result.observations
    if include_suppressed:
        observations += result.suppressed_observations
    for observation in observations:
        writer.writerow(
            {
                "record_type": "indicator",
                "indicator_type": observation.indicator_type.value,
                "original_display_value": observation.original_display_value,
                "normalized_value": observation.normalized_value,
                "source_document_id": str(observation.source_document_id),
                "start_offset": observation.start_offset,
                "end_offset": observation.end_offset,
                "context": observation.context,
                "extraction_rule": observation.extraction_rule,
                "validation_state": observation.validation_state.value,
                "suppression_reason": observation.suppression_reason or "",
            }
        )
    for candidate in result.cve_candidates:
        writer.writerow(
            {
                "record_type": "cve_candidate",
                "indicator_type": "cve",
                "original_display_value": candidate.original_display_value,
                "normalized_value": candidate.normalized_value,
                "source_document_id": str(candidate.source_document_id),
                "start_offset": candidate.start_offset,
                "end_offset": candidate.end_offset,
                "context": candidate.context,
                "extraction_rule": candidate.extraction_rule,
                "validation_state": candidate.validation_state.value,
                "suppression_reason": "",
            }
        )
    return stream.getvalue()
