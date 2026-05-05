from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import url2pathname

from bs4 import BeautifulSoup

from .fetch import download_url_to, safe_filename
from .models import Confidence, FigureRecord, PanelRecord, ProvenanceRecord, SourceType, SOURCE_LEVELS

_FIG_ID_RE = re.compile(r"\b(?:Fig\.?|Figure)\s*(\d+)\b", re.IGNORECASE)


def extract_html(input_value: str, workdir: Path) -> tuple[list[FigureRecord], list[str]]:
    html_path, base_url = _load_html(input_value, workdir)
    html = html_path.read_text(encoding="utf-8", errors="replace")
    records = parse_html_figures(html, base_url=base_url, original_locator=str(input_value))
    warnings = materialize_html_images(records, workdir / "html_images")
    return records, warnings


def parse_html_figures(html: str, base_url: str = "", original_locator: str = "") -> list[FigureRecord]:
    soup = BeautifulSoup(html, "lxml")
    records: list[FigureRecord] = []
    for index, figure in enumerate(soup.find_all("figure"), start=1):
        caption_node = figure.find("figcaption")
        caption = caption_node.get_text(" ", strip=True) if caption_node else None
        fig_id = _explicit_fig_id(caption or "")
        image_urls = _image_urls(figure, base_url)
        provenance = ProvenanceRecord(
            source_type=SourceType.HTML_FIGURE,
            level=SOURCE_LEVELS[SourceType.HTML_FIGURE],
            locator=_html_locator(original_locator, index),
            details={
                "figure_index": index,
                "image_urls": image_urls,
                "caption_present": caption is not None,
            },
        )
        panels = _panels_from_images(fig_id, image_urls, caption, provenance) if len(image_urls) > 1 else []
        source_image = image_urls[0] if len(image_urls) == 1 else None
        candidate_reason = None
        if not image_urls:
            candidate_reason = "HTML figure has no image evidence."
        elif fig_id is None:
            candidate_reason = "HTML figure label is missing or ambiguous."
        elif len(image_urls) > 1:
            candidate_reason = "Multiple HTML images were found, but no source-backed full composite figure file exists."
        records.append(
            FigureRecord(
                fig_id=fig_id,
                source_type=SourceType.HTML_FIGURE,
                source_image=source_image,
                original_file=image_urls[0] if image_urls else original_locator,
                caption=caption,
                confidence=Confidence.MEDIUM if fig_id and image_urls else Confidence.UNCERTAIN,
                panels=panels,
                provenance=[provenance],
                candidate_reason=candidate_reason,
            )
        )
    return records


def materialize_html_images(records: list[FigureRecord], image_dir: Path) -> list[str]:
    warnings: list[str] = []
    for record in records:
        if record.source_image:
            local, warning = _materialize_image(record.source_image, image_dir)
            if local:
                record.source_image = str(local)
            elif warning:
                warnings.append(warning)
        for panel in record.panels:
            if panel.source_image:
                local, warning = _materialize_image(panel.source_image, image_dir)
                if local:
                    panel.source_image = str(local)
                elif warning:
                    warnings.append(warning)
    return warnings


def _load_html(input_value: str, workdir: Path) -> tuple[Path, str]:
    parsed = urlparse(input_value)
    if parsed.scheme in {"http", "https"}:
        target = workdir / "html" / safe_filename(input_value, "article.html")
        return download_url_to(input_value, target), input_value
    path = Path(input_value)
    return path, path.resolve().as_uri()


def _materialize_image(value: str, image_dir: Path) -> tuple[Path | None, str | None]:
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        target = image_dir / safe_filename(value, "figure_image")
        try:
            return download_url_to(value, target), None
        except Exception as exc:  # noqa: BLE001
            return None, f"Failed to download HTML image {value}: {exc}"
    if parsed.scheme == "file":
        path = Path(url2pathname(parsed.path))
        return (path if path.exists() else None), None if path.exists() else f"Local HTML image not found: {value}"
    path = Path(value)
    return (path if path.exists() else None), None if path.exists() else f"Local HTML image not found: {value}"


def _image_urls(figure, base_url: str) -> list[str]:
    urls: list[str] = []
    for source in figure.find_all("source"):
        srcset = source.get("srcset")
        if srcset:
            urls.append(urljoin(base_url, _best_srcset_url(srcset)))
    for image in figure.find_all("img"):
        src = image.get("src") or image.get("data-src")
        srcset = image.get("srcset")
        if srcset:
            urls.append(urljoin(base_url, _best_srcset_url(srcset)))
        elif src:
            urls.append(urljoin(base_url, src))
    return _dedupe_equivalent_image_urls(urls)


def _dedupe_equivalent_image_urls(urls: list[str]) -> list[str]:
    keyed: dict[tuple[str, str, str], str] = {}
    order: list[tuple[str, str, str]] = []
    for url in urls:
        if not url:
            continue
        parsed = urlparse(url)
        key = (parsed.scheme, parsed.netloc, parsed.path)
        existing = keyed.get(key)
        if existing is None:
            keyed[key] = url
            order.append(key)
            continue
        if urlparse(existing).query and not parsed.query:
            keyed[key] = url
    return [keyed[key] for key in order]


def _best_srcset_url(srcset: str) -> str:
    parts = [part.strip().split()[0] for part in srcset.split(",") if part.strip()]
    return parts[-1] if parts else ""


def _explicit_fig_id(text: str) -> str | None:
    if re.search(r"Extended\s+Data\s+Fig", text, re.IGNORECASE):
        return None
    match = _FIG_ID_RE.search(text)
    return f"Fig{int(match.group(1)):02d}" if match else None


def _panels_from_images(
    fig_id: str | None,
    image_urls: list[str],
    caption: str | None,
    provenance: ProvenanceRecord,
) -> list[PanelRecord]:
    if fig_id is None:
        return []
    panels: list[PanelRecord] = []
    for index, image_url in enumerate(image_urls):
        label = chr(ord("a") + index) if index < 26 else None
        panels.append(
            PanelRecord(
                parent_fig_id=fig_id,
                label=label,
                source_type=SourceType.HTML_FIGURE,
                source_image=image_url,
                original_file=image_url,
                caption=caption,
                confidence=Confidence.MEDIUM,
                provenance=[provenance],
                panel_label_source="source_order" if label else None,
                candidate_reason=None if label else "Panel label could not be source-verified.",
            )
        )
    return panels


def _html_locator(original_locator: str, index: int) -> str:
    prefix = original_locator or "html"
    return f"{prefix}#figure[{index}]"
