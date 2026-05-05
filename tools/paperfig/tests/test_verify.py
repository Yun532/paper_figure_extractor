from __future__ import annotations

import base64

from paperfig.models import Confidence, FigureRecord, PanelRecord, ProvenanceRecord, SourceType, SOURCE_LEVELS
from paperfig.verify import verify_records

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lw9s8wAAAABJRU5ErkJggg=="
)


def _image(tmp_path, name: str = "fig.png") -> str:
    path = tmp_path / name
    path.write_bytes(_PNG)
    return str(path)


def _provenance(source_type: SourceType) -> ProvenanceRecord:
    return ProvenanceRecord(source_type=source_type, level=SOURCE_LEVELS[source_type], locator="source")


def _record(tmp_path, source_type: SourceType = SourceType.ARXIV_SOURCE, fig_id: str | None = "Fig01") -> FigureRecord:
    return FigureRecord(
        fig_id=fig_id,
        source_type=source_type,
        source_image=_image(tmp_path, f"{source_type.value}.png"),
        confidence=Confidence.HIGH if source_type == SourceType.ARXIV_SOURCE else Confidence.MEDIUM,
        provenance=[_provenance(source_type)],
    )


def test_verified_final_requires_source_evidence_and_provenance(tmp_path) -> None:
    figures, candidates = verify_records([_record(tmp_path)], strict=True)

    assert len(figures) == 1
    assert figures[0].verified is True
    assert candidates == []


def test_missing_provenance_is_candidate(tmp_path) -> None:
    record = _record(tmp_path)
    record.provenance = []

    figures, candidates = verify_records([record], strict=True)

    assert figures == []
    assert len(candidates) == 1
    assert candidates[0].candidate_reason == "Missing provenance."


def test_uncertain_outputs_are_never_final_figxx(tmp_path) -> None:
    record = _record(tmp_path)
    record.confidence = Confidence.UNCERTAIN

    figures, candidates = verify_records([record], strict=True)

    assert figures == []
    assert candidates[0].fig_id == "Fig01"
    assert candidates[0].verified is False


def test_lower_level_does_not_override_higher_level(tmp_path) -> None:
    html = _record(tmp_path, SourceType.HTML_FIGURE, "Fig01")
    arxiv = _record(tmp_path, SourceType.ARXIV_SOURCE, "Fig01")

    figures, candidates = verify_records([html, arxiv], strict=True)

    assert len(figures) == 1
    assert figures[0].source_type == SourceType.ARXIV_SOURCE.value
    assert len(candidates) == 1
    assert "did not override" in candidates[0].candidate_reason


def test_rendered_pdf_crop_is_candidate_in_strict_mode(tmp_path) -> None:
    record = _record(tmp_path, SourceType.PDF_RENDERED_CROP, "Fig01")

    figures, candidates = verify_records([record], strict=True)

    assert figures == []
    assert candidates[0].candidate_reason == "Rendered PDF crops are candidate-only in strict mode."


def test_panel_without_source_verified_label_is_not_verified(tmp_path) -> None:
    record = _record(tmp_path)
    record.panels = [
        PanelRecord(
            parent_fig_id="Fig01",
            label=None,
            source_type=SourceType.ARXIV_SOURCE,
            source_image=_image(tmp_path, "panel.png"),
            confidence=Confidence.HIGH,
            provenance=[_provenance(SourceType.ARXIV_SOURCE)],
        )
    ]

    figures, _ = verify_records([record], strict=True)

    assert figures[0].panels[0].verified is False
    assert figures[0].panels[0].candidate_reason == "Panel label is not source-verified."
