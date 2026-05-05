from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

import httpx


class InputKind(str, Enum):
    ARXIV = "arxiv"
    LOCAL_PDF = "local_pdf"
    LOCAL_HTML = "local_html"
    LOCAL_TEX = "local_tex"
    LOCAL_SOURCE_DIR = "local_source_dir"
    PDF_URL = "pdf_url"
    ARTICLE_URL = "article_url"
    UNKNOWN = "unknown"


_ARXIV_RE = re.compile(r"(?:arxiv:)?(\d{4}\.\d{4,5}(?:v\d+)?|[\w.-]+/\d{7}(?:v\d+)?)", re.IGNORECASE)


def classify_input(value: str) -> InputKind:
    path = Path(value)
    if path.exists():
        if path.is_dir():
            return InputKind.LOCAL_SOURCE_DIR
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return InputKind.LOCAL_PDF
        if suffix in {".html", ".htm"}:
            return InputKind.LOCAL_HTML
        if suffix == ".tex":
            return InputKind.LOCAL_TEX
        return InputKind.UNKNOWN
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        if normalize_arxiv_id(value):
            return InputKind.ARXIV
        if parsed.path.lower().endswith(".pdf"):
            return InputKind.PDF_URL
        return InputKind.ARTICLE_URL
    if normalize_arxiv_id(value):
        return InputKind.ARXIV
    return InputKind.UNKNOWN


def normalize_arxiv_id(value: str) -> str | None:
    parsed = urlparse(value)
    source = value
    if parsed.netloc.lower().endswith("arxiv.org"):
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"abs", "pdf", "e-print"}:
            source = parts[1].removesuffix(".pdf")
    match = _ARXIV_RE.search(source.strip())
    return match.group(1) if match else None


def prepare_workdir(outdir: Path) -> Path:
    workdir = outdir / ".work"
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir


def download_url_to(url: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as response:
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    return target


def safe_filename(value: str, fallback: str) -> str:
    parsed = urlparse(value)
    name = Path(parsed.path).name if parsed.path else fallback
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")
    return name or fallback
