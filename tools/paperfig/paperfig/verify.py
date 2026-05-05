from __future__ import annotations

from pathlib import Path

from .models import Confidence, FigureRecord, PanelRecord, SourceType, SOURCE_LEVELS

_FINAL_CONFIDENCE = {Confidence.HIGH.value, Confidence.MEDIUM.value, Confidence.HIGH, Confidence.MEDIUM}


def verify_records(records: list[FigureRecord], strict: bool = True) -> tuple[list[FigureRecord], list[FigureRecord]]:
    verified_by_id: dict[str, FigureRecord] = {}
    candidates: list[FigureRecord] = []
    for record in sorted(records, key=_record_level):
        _verify_panels(record)
        reason = _final_rejection_reason(record, strict)
        if reason is not None:
            candidates.append(_downgrade(record, reason))
            continue
        assert record.fig_id is not None
        existing = verified_by_id.get(record.fig_id)
        if existing is None:
            record.verified = True
            verified_by_id[record.fig_id] = record
            continue
        if _record_level(record) < _record_level(existing):
            candidates.append(_downgrade(existing, f"Higher reliability source replaced {existing.fig_id}."))
            record.verified = True
            verified_by_id[record.fig_id] = record
        else:
            candidates.append(_downgrade(record, f"Lower or duplicate reliability source did not override verified {record.fig_id}."))
    return list(verified_by_id.values()), candidates


def _verify_panels(record: FigureRecord) -> None:
    for panel in record.panels:
        reason = _panel_rejection_reason(panel)
        if reason is None:
            panel.verified = True
        else:
            panel.verified = False
            panel.candidate_reason = panel.candidate_reason or reason


def _final_rejection_reason(record: FigureRecord, strict: bool) -> str | None:
    if not record.provenance:
        return "Missing provenance."
    if record.candidate_reason:
        return record.candidate_reason
    if record.fig_id is None:
        return "Figure index is unknown."
    if not _valid_fig_id(record.fig_id):
        return "Figure index is not a final FigXX identifier."
    if not record.source_image:
        return "No source-backed full figure image exists."
    if not _path_exists(record.source_image):
        return "Source image path does not exist."
    if record.confidence not in _FINAL_CONFIDENCE:
        return "Confidence is below medium."
    if strict and SourceType(record.source_type) == SourceType.PDF_RENDERED_CROP:
        return "Rendered PDF crops are candidate-only in strict mode."
    return None


def _panel_rejection_reason(panel: PanelRecord) -> str | None:
    if not panel.provenance:
        return "Missing panel provenance."
    if panel.candidate_reason:
        return panel.candidate_reason
    if not panel.parent_fig_id:
        return "Panel parent figure is unknown."
    if not panel.label or len(panel.label) != 1 or not panel.label.isalpha():
        return "Panel label is not source-verified."
    if not panel.source_image:
        return "No source-backed panel image exists."
    if not _path_exists(panel.source_image):
        return "Panel source image path does not exist."
    if panel.confidence not in _FINAL_CONFIDENCE:
        return "Panel confidence is below medium."
    return None


def _downgrade(record: FigureRecord, reason: str) -> FigureRecord:
    record.verified = False
    record.candidate_reason = record.candidate_reason or reason
    if not record.provenance:
        record.confidence = Confidence.UNCERTAIN
    return record


def _record_level(record: FigureRecord) -> int:
    return SOURCE_LEVELS[SourceType(record.source_type)]


def _valid_fig_id(fig_id: str) -> bool:
    return len(fig_id) >= 5 and fig_id.startswith("Fig") and fig_id[3:].isdigit()


def _path_exists(value: str) -> bool:
    return Path(value).exists()
