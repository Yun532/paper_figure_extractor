from __future__ import annotations

import base64
import json

from paperfig.export import export_result
from paperfig.models import Confidence, ExtractionResult, FigureRecord, ProvenanceRecord, SourceType, SOURCE_LEVELS

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lw9s8wAAAABJRU5ErkJggg=="
)


def _provenance(source_type: SourceType) -> ProvenanceRecord:
    return ProvenanceRecord(source_type=source_type, level=SOURCE_LEVELS[source_type], locator="fixture")


def test_export_writes_required_structure_and_metadata(tmp_path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(_PNG)
    figure = FigureRecord(
        fig_id="Fig01",
        source_type=SourceType.ARXIV_SOURCE,
        source_image=str(source),
        caption="A real source caption.",
        confidence=Confidence.HIGH,
        verified=True,
        provenance=[_provenance(SourceType.ARXIV_SOURCE)],
    )
    result = ExtractionResult(input="fixture", figures=[figure], candidates=[])

    exported = export_result(result, tmp_path / "OUTPUT")

    assert (tmp_path / "OUTPUT" / "metadata.json").exists()
    assert (tmp_path / "OUTPUT" / "figures" / "Fig01.png").exists()
    assert (tmp_path / "OUTPUT" / "captions" / "Fig01.txt").read_text(encoding="utf-8") == "A real source caption."
    metadata = json.loads((tmp_path / "OUTPUT" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["figures"][0]["fig_id"] == "Fig01"
    assert metadata["figures"][0]["provenance"]
    assert exported.metadata_path is not None


def test_export_places_uncertain_record_in_candidates(tmp_path) -> None:
    source = tmp_path / "candidate.png"
    source.write_bytes(_PNG)
    candidate = FigureRecord(
        fig_id="Fig03",
        source_type=SourceType.PDF_RENDERED_CROP,
        source_image=str(source),
        confidence=Confidence.LOW,
        verified=False,
        provenance=[_provenance(SourceType.PDF_RENDERED_CROP)],
        candidate_reason="Rendered crop is uncertain.",
    )
    result = ExtractionResult(input="fixture", figures=[], candidates=[candidate])

    export_result(result, tmp_path / "OUTPUT")

    assert not (tmp_path / "OUTPUT" / "figures" / "Fig03.png").exists()
    assert (tmp_path / "OUTPUT" / "candidates" / "Fig03_candidate_01.png").exists()
