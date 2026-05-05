from __future__ import annotations

from pathlib import Path

from .arxiv_source import extract_arxiv_source, extract_latex_file, extract_latex_source_directory
from .export import export_result
from .fetch import InputKind, classify_input, download_url_to, prepare_workdir, safe_filename
from .journal_html import extract_html
from .models import ExtractionResult, FigureRecord
from .pdf_extract import extract_pdf_candidates
from .verify import verify_records


def extract_figures(input: str, outdir: str | Path, dpi: int = 400, strict: bool = True) -> ExtractionResult:
    out_path = Path(outdir)
    workdir = prepare_workdir(out_path)
    records: list[FigureRecord] = []
    warnings: list[str] = []
    kind = classify_input(input)

    if kind == InputKind.ARXIV:
        extracted, new_warnings = extract_arxiv_source(input, workdir)
    elif kind == InputKind.LOCAL_SOURCE_DIR:
        extracted, new_warnings = extract_latex_source_directory(Path(input))
    elif kind == InputKind.LOCAL_TEX:
        extracted, new_warnings = extract_latex_file(Path(input))
    elif kind in {InputKind.LOCAL_HTML, InputKind.ARTICLE_URL}:
        extracted, new_warnings = extract_html(input, workdir)
    elif kind == InputKind.LOCAL_PDF:
        extracted, new_warnings = extract_pdf_candidates(Path(input), workdir, dpi=dpi, strict=strict)
    elif kind == InputKind.PDF_URL:
        pdf_path = download_url_to(input, workdir / "downloads" / safe_filename(input, "article.pdf"))
        extracted, new_warnings = extract_pdf_candidates(pdf_path, workdir, dpi=dpi, strict=strict)
    else:
        extracted, new_warnings = [], [f"Unsupported or unrecognized input: {input}"]

    records.extend(extracted)
    warnings.extend(new_warnings)
    figures, candidates = verify_records(records, strict=strict)
    result = ExtractionResult(
        input=input,
        strict=strict,
        dpi=dpi,
        figures=figures,
        candidates=candidates,
        warnings=warnings,
    )
    return export_result(result, out_path, dpi=dpi)
