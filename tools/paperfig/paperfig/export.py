from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image

from .models import ExtractionResult, FigureRecord, PanelRecord, SourceType
from .panel_split import candidate_panels, verified_panels


def export_result(result: ExtractionResult, outdir: Path, dpi: int = 400) -> ExtractionResult:
    figures_dir = outdir / "figures"
    candidates_dir = outdir / "candidates"
    captions_dir = outdir / "captions"
    for directory in (figures_dir, candidates_dir, captions_dir):
        directory.mkdir(parents=True, exist_ok=True)

    _export_verified_figures(result, figures_dir, captions_dir, dpi)
    _export_candidates(result, candidates_dir, dpi)

    result.output_dir = str(outdir)
    metadata_path = outdir / "metadata.json"
    result.metadata_path = str(metadata_path)
    metadata_path.write_text(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def _export_verified_figures(result: ExtractionResult, figures_dir: Path, captions_dir: Path, dpi: int) -> None:
    still_verified: list[FigureRecord] = []
    for figure in result.figures:
        assert figure.fig_id is not None
        target = figures_dir / f"{figure.fig_id}.png"
        if figure.source_image and _write_image(Path(figure.source_image), target, dpi):
            figure.output_file = _relative(target, figures_dir.parent)
            if figure.caption:
                caption_target = captions_dir / f"{figure.fig_id}.txt"
                caption_target.write_text(figure.caption, encoding="utf-8")
                figure.caption_file = _relative(caption_target, figures_dir.parent)
            still_verified.append(figure)
        else:
            figure.verified = False
            figure.candidate_reason = figure.candidate_reason or "Could not export source image as PNG."
            result.candidates.append(figure)
            continue
        _export_verified_panels(figure, figures_dir, dpi)
    result.figures = still_verified


def _export_verified_panels(figure: FigureRecord, figures_dir: Path, dpi: int) -> None:
    for panel in verified_panels(figure):
        if not panel.parent_fig_id or not panel.label or not panel.source_image:
            continue
        target = figures_dir / f"{panel.parent_fig_id}_panel_{panel.label.lower()}.png"
        if _write_image(Path(panel.source_image), target, dpi):
            panel.output_file = _relative(target, figures_dir.parent)
        else:
            panel.verified = False
            panel.candidate_reason = panel.candidate_reason or "Could not export source panel image as PNG."


def _export_candidates(result: ExtractionResult, candidates_dir: Path, dpi: int) -> None:
    for index, candidate in enumerate(result.candidates, start=1):
        if candidate.source_image:
            target = candidates_dir / _candidate_filename(candidate, index)
            if _write_image(Path(candidate.source_image), target, dpi):
                candidate.output_file = _relative(target, candidates_dir.parent)
        _export_candidate_panels(candidate, candidates_dir, dpi)


def _export_candidate_panels(candidate: FigureRecord, candidates_dir: Path, dpi: int) -> None:
    counter = 1
    for panel in candidate.panels:
        if not panel.source_image:
            continue
        if panel.verified and panel.parent_fig_id and panel.label:
            target = candidates_dir.parent / "figures" / f"{panel.parent_fig_id}_panel_{panel.label.lower()}.png"
        else:
            prefix = panel.parent_fig_id or "unknown"
            target = candidates_dir / f"{prefix}_panel_candidate_{counter:02d}.png"
            counter += 1
        if _write_image(Path(panel.source_image), target, dpi):
            panel.output_file = _relative(target, candidates_dir.parent)


def _candidate_filename(candidate: FigureRecord, index: int) -> str:
    if SourceType(candidate.source_type) == SourceType.PDF_RENDERED_CROP:
        page = _provenance_detail(candidate, "pdf_page")
        if page:
            return f"page_{page}_figure_candidate_{index:02d}.png"
    if candidate.fig_id:
        return f"{candidate.fig_id}_candidate_{index:02d}.png"
    return f"candidate_{index:03d}.png"


def _provenance_detail(record: FigureRecord, key: str):
    for provenance in record.provenance:
        if key in provenance.details:
            return provenance.details[key]
    return None


def _write_image(source: Path, target: Path, dpi: int) -> bool:
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower()
    try:
        if suffix == ".png":
            shutil.copy2(source, target)
            return True
        if suffix == ".pdf":
            import fitz

            document = fitz.open(source)
            try:
                page = document[0]
                matrix = fitz.Matrix(dpi / 72, dpi / 72)
                pixmap = page.get_pixmap(matrix=matrix)
                pixmap.save(target)
            finally:
                document.close()
            return True
        with Image.open(source) as image:
            image.convert("RGBA").save(target)
        return True
    except Exception:
        return False


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
