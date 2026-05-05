from __future__ import annotations

import shutil
import tarfile
import zipfile
from pathlib import Path

import httpx

from .fetch import normalize_arxiv_id
from .latex_parser import figure_records_from_latex
from .models import FigureRecord

_COMMON_MAIN_NAMES = ("main.tex", "paper.tex", "ms.tex", "article.tex")


def extract_arxiv_source(input_value: str, workdir: Path) -> tuple[list[FigureRecord], list[str]]:
    arxiv_id = normalize_arxiv_id(input_value)
    if arxiv_id is None:
        return [], ["Input is not a recognized arXiv ID or URL."]
    archive = download_arxiv_eprint(arxiv_id, workdir / "arxiv" / f"{arxiv_id.replace('/', '_')}.src")
    source_dir = workdir / "arxiv" / arxiv_id.replace("/", "_")
    if source_dir.exists():
        shutil.rmtree(source_dir)
    source_dir.mkdir(parents=True, exist_ok=True)
    warnings = safe_extract_source(archive, source_dir)
    records, source_warnings = extract_latex_source_directory(source_dir)
    return records, warnings + source_warnings


def extract_latex_source_directory(source_dir: Path) -> tuple[list[FigureRecord], list[str]]:
    main_tex = detect_main_tex(source_dir)
    if main_tex is None:
        return [], [f"No reliable main TeX file found in {source_dir}."]
    return figure_records_from_latex(source_dir, main_tex), []


def extract_latex_file(tex_file: Path) -> tuple[list[FigureRecord], list[str]]:
    return figure_records_from_latex(tex_file.parent, tex_file), []


def download_arxiv_eprint(arxiv_id: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://arxiv.org/e-print/{arxiv_id}"
    with httpx.stream("GET", url, follow_redirects=True, timeout=90.0) as response:
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    return target


def safe_extract_source(archive: Path, target_dir: Path) -> list[str]:
    warnings: list[str] = []
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                destination = (target_dir / member.name).resolve()
                if not _inside(target_dir, destination):
                    warnings.append(f"Skipped unsafe archive member: {member.name}")
                    continue
                tar.extract(member, target_dir)
        return warnings
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zip_file:
            for member in zip_file.infolist():
                destination = (target_dir / member.filename).resolve()
                if not _inside(target_dir, destination):
                    warnings.append(f"Skipped unsafe archive member: {member.filename}")
                    continue
                zip_file.extract(member, target_dir)
        return warnings
    text_target = target_dir / "source.tex"
    text_target.write_bytes(archive.read_bytes())
    warnings.append("arXiv e-print was not an archive; saved as source.tex.")
    return warnings


def detect_main_tex(source_dir: Path) -> Path | None:
    tex_files = sorted(source_dir.rglob("*.tex"))
    if not tex_files:
        return None
    scored: list[tuple[int, int, Path]] = []
    for tex_file in tex_files:
        text = tex_file.read_text(encoding="utf-8", errors="replace")
        name = tex_file.name.lower()
        score = 0
        if "\\documentclass" in text:
            score += 100
        if "\\begin{document}" in text:
            score += 50
        if name in _COMMON_MAIN_NAMES:
            score += 25
        if "\\begin{figure" in text:
            score += 10
        scored.append((score, tex_file.stat().st_size, tex_file))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return scored[0][2] if scored[0][0] > 0 else None


def _inside(root: Path, candidate: Path) -> bool:
    root = root.resolve()
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False
