from __future__ import annotations

from pathlib import Path

from .models import Confidence, FigureRecord, ProvenanceRecord, SourceType, SOURCE_LEVELS


def extract_pdf_candidates(pdf_path: Path, workdir: Path, dpi: int = 400, strict: bool = True) -> tuple[list[FigureRecord], list[str]]:
    try:
        import fitz
    except ImportError:
        return [], ["PyMuPDF is not installed; PDF extraction is unavailable."]
    records: list[FigureRecord] = []
    warnings: list[str] = []
    image_dir = workdir / "pdf_images"
    crop_dir = workdir / "pdf_crops"
    image_dir.mkdir(parents=True, exist_ok=True)
    crop_dir.mkdir(parents=True, exist_ok=True)
    document = fitz.open(pdf_path)
    try:
        for page_index in range(document.page_count):
            page = document[page_index]
            records.extend(_embedded_image_records(document, page, page_index, image_dir, pdf_path))
            records.extend(_caption_crop_records(page, page_index, crop_dir, pdf_path, dpi))
    finally:
        document.close()
    if strict:
        warnings.append("PDF rendered crops and unmatched embedded images were kept as candidates in strict mode.")
    return records, warnings


def _embedded_image_records(document, page, page_index: int, image_dir: Path, pdf_path: Path) -> list[FigureRecord]:
    records: list[FigureRecord] = []
    for image_index, image in enumerate(page.get_images(full=True), start=1):
        xref = image[0]
        extracted = document.extract_image(xref)
        extension = extracted.get("ext") or "png"
        image_path = image_dir / f"page_{page_index + 1}_image_{image_index}.{extension}"
        image_path.write_bytes(extracted["image"])
        provenance = ProvenanceRecord(
            source_type=SourceType.PDF_EMBEDDED,
            level=SOURCE_LEVELS[SourceType.PDF_EMBEDDED],
            locator=f"{pdf_path}:page[{page_index + 1}]:xref[{xref}]",
            details={"pdf_page": page_index + 1, "xref": xref, "image_index": image_index},
        )
        records.append(
            FigureRecord(
                fig_id=None,
                source_type=SourceType.PDF_EMBEDDED,
                source_image=str(image_path),
                original_file=str(pdf_path),
                confidence=Confidence.LOW,
                provenance=[provenance],
                candidate_reason="PDF embedded image is not reliably mapped to an explicit figure index.",
            )
        )
    return records


def _caption_crop_records(page, page_index: int, crop_dir: Path, pdf_path: Path, dpi: int) -> list[FigureRecord]:
    records: list[FigureRecord] = []
    matches = []
    for needle in ("Fig.", "Figure"):
        matches.extend(page.search_for(needle))
    for crop_index, rect in enumerate(matches, start=1):
        clip = _expanded_clip(page.rect, rect)
        matrix = page.parent.Matrix(dpi / 72, dpi / 72) if hasattr(page.parent, "Matrix") else None
        if matrix is None:
            import fitz

            matrix = fitz.Matrix(dpi / 72, dpi / 72)
        pixmap = page.get_pixmap(matrix=matrix, clip=clip)
        image_path = crop_dir / f"page_{page_index + 1}_caption_crop_{crop_index}.png"
        pixmap.save(image_path)
        provenance = ProvenanceRecord(
            source_type=SourceType.PDF_RENDERED_CROP,
            level=SOURCE_LEVELS[SourceType.PDF_RENDERED_CROP],
            locator=f"{pdf_path}:page[{page_index + 1}]:caption_match[{crop_index}]",
            details={"pdf_page": page_index + 1, "crop_index": crop_index},
        )
        records.append(
            FigureRecord(
                fig_id=None,
                source_type=SourceType.PDF_RENDERED_CROP,
                source_image=str(image_path),
                original_file=str(pdf_path),
                confidence=Confidence.LOW,
                provenance=[provenance],
                candidate_reason="Rendered PDF crop is uncertain and cannot be promoted to a final figure.",
            )
        )
    return records


def _expanded_clip(page_rect, rect):
    x0 = max(page_rect.x0, rect.x0 - 40)
    y0 = max(page_rect.y0, rect.y0 - 260)
    x1 = min(page_rect.x1, rect.x1 + 420)
    y1 = min(page_rect.y1, rect.y1 + 120)
    return page_rect.__class__(x0, y0, x1, y1)
