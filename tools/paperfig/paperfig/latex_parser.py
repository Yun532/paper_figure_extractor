from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .models import Confidence, FigureRecord, PanelRecord, ProvenanceRecord, SourceType, SOURCE_LEVELS


@dataclass(frozen=True)
class LatexFigure:
    index: int
    environment: str
    tex_file: str
    body: str
    caption: str | None
    graphics: list[str]
    start_offset: int


_INCLUDE_RE = re.compile(r"\\includegraphics(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}", re.DOTALL)
_NEWCOMMAND_GRAPHIC_RE = re.compile(
    r"\\(?:re)?newcommand\s*\{\\([A-Za-z@]+)\}\s*(?:\[\s*1\s*\])\s*\{\\includegraphics(?:\s*\[[^\]]*\])?\s*\{([^{}]*#1[^{}]*)\}\}",
    re.DOTALL,
)
_ENV_RE = re.compile(r"\\begin\{(figure\*?)\}([\s\S]*?)\\end\{\1\}", re.MULTILINE)
_CAPTIONOF_ENV_RE = re.compile(r"\\begin\{(table\*?)\}([\s\S]*?)\\end\{\1\}", re.MULTILINE)
_PANEL_REF_RE = re.compile(r"\(([a-z])\)", re.IGNORECASE)
_INPUT_RE = re.compile(r"\\(?:input|include)\s*\{([^{}]+)\}")
_GRAPHICSPATH_RE = re.compile(r"\\graphicspath\s*\{([\s\S]*?)\}")
_GRAPHICSPATH_ENTRY_RE = re.compile(r"\{([^{}]+)\}")


def parse_latex_figures(tex_text: str, tex_file: str = "main.tex") -> list[LatexFigure]:
    text = _strip_comments(tex_text)
    includegraphics_macros = _includegraphics_macros(text)
    matches: list[tuple[int, str, str, str | None, list[str]]] = []
    for match in _ENV_RE.finditer(text):
        body = match.group(2)
        matches.append((match.start(), match.group(1), body, _extract_caption(body), _graphics(body, includegraphics_macros)))
    for match in _CAPTIONOF_ENV_RE.finditer(text):
        environment = match.group(1)
        if environment in {"figure", "figure*"}:
            continue
        body = match.group(2)
        caption = _extract_captionof_figure(body)
        graphics = _graphics(body, includegraphics_macros)
        if caption is None or not graphics:
            continue
        matches.append((match.start(), environment, body, caption, graphics))
    figures: list[LatexFigure] = []
    for index, (start_offset, environment, body, caption, graphics) in enumerate(sorted(matches, key=lambda item: item[0]), start=1):
        figures.append(
            LatexFigure(
                index=index,
                environment=environment,
                tex_file=tex_file,
                body=body,
                caption=caption,
                graphics=graphics,
                start_offset=start_offset,
            )
        )
    return figures


def figure_records_from_latex(source_dir: Path, tex_file: Path) -> list[FigureRecord]:
    text, included_files = expand_latex_inputs(tex_file)
    parsed = parse_latex_figures(text, _relative_to_source(tex_file, source_dir))
    search_dirs = _latex_search_dirs(source_dir, tex_file, included_files, text)
    records: list[FigureRecord] = []
    for parsed_figure in parsed:
        fig_id = f"Fig{parsed_figure.index:02d}"
        resolved = [_resolve_graphic_path(source_dir, search_dirs, graphic) for graphic in parsed_figure.graphics]
        composite_image = _compose_source_order_figure(source_dir, fig_id, resolved) if len(resolved) > 1 and all(resolved) else None
        source_image = str(resolved[0]) if len(resolved) == 1 and resolved[0] is not None else str(composite_image) if composite_image else None
        provenance = ProvenanceRecord(
            source_type=SourceType.ARXIV_SOURCE,
            level=SOURCE_LEVELS[SourceType.ARXIV_SOURCE],
            locator=f"{parsed_figure.tex_file}:figure[{parsed_figure.index}]",
            details={
                "environment": parsed_figure.environment,
                "figure_environment_index": parsed_figure.index,
                "includegraphics": parsed_figure.graphics,
                "resolved_images": [str(path) if path else None for path in resolved],
                "start_offset": parsed_figure.start_offset,
                "expanded_inputs": [_relative_to_source(path, source_dir) for path in included_files],
                "graphicspath": [_relative_to_source(path, source_dir) for path in search_dirs if path.resolve() != source_dir.resolve()],
                "composite_strategy": "source_order_vertical_stack" if composite_image else None,
            },
        )
        panels = _panels_from_graphics(fig_id, parsed_figure, resolved, provenance) if len(parsed_figure.graphics) > 1 else []
        candidate_reason = None
        if not parsed_figure.graphics:
            candidate_reason = "LaTeX figure environment has no includegraphics evidence."
        elif source_image is None:
            candidate_reason = "includegraphics path could not be resolved to source-backed image output."
        records.append(
            FigureRecord(
                fig_id=fig_id,
                source_type=SourceType.ARXIV_SOURCE,
                source_image=source_image,
                original_file=parsed_figure.graphics[0] if parsed_figure.graphics else str(tex_file),
                caption=parsed_figure.caption,
                confidence=Confidence.HIGH,
                panels=panels,
                provenance=[provenance],
                candidate_reason=candidate_reason,
            )
        )
    return records


def expand_latex_inputs(tex_file: Path) -> tuple[str, list[Path]]:
    included: list[Path] = []
    expanded = _expand_latex_file(tex_file.resolve(), seen=set(), included=included)
    return expanded, included


def _expand_latex_file(tex_file: Path, seen: set[Path], included: list[Path]) -> str:
    tex_file = tex_file.resolve()
    if tex_file in seen:
        return ""
    seen.add(tex_file)
    if tex_file not in included:
        included.append(tex_file)
    text = tex_file.read_text(encoding="utf-8", errors="replace")
    stripped = _strip_comments(text)

    def replace_input(match: re.Match[str]) -> str:
        child = match.group(1).strip().strip("\"'")
        child_path = tex_file.parent / child
        if child_path.suffix == "":
            child_path = child_path.with_suffix(".tex")
        if not child_path.exists() or not child_path.is_file():
            return ""
        return _expand_latex_file(child_path, seen, included)

    return _INPUT_RE.sub(replace_input, stripped)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _relative_to_source(path: Path, source_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(source_dir.resolve()))
    except ValueError:
        return str(path)


def _includegraphics_macros(text: str) -> dict[str, str]:
    return {match.group(1): match.group(2).strip() for match in _NEWCOMMAND_GRAPHIC_RE.finditer(text)}


def _graphics(body: str, includegraphics_macros: dict[str, str] | None = None) -> list[str]:
    expanded = body
    for name, template in (includegraphics_macros or {}).items():
        expanded = re.sub(rf"\\{re.escape(name)}\s*\{{([^{{}}]+)\}}", lambda match: f"\\includegraphics{{{template.replace('#1', match.group(1).strip())}}}", expanded)
    return [item.strip() for item in _INCLUDE_RE.findall(expanded) if item.strip()]


def _panels_from_graphics(
    fig_id: str,
    parsed_figure: LatexFigure,
    resolved: list[Path | None],
    provenance: ProvenanceRecord,
) -> list[PanelRecord]:
    labels = _panel_labels(parsed_figure.caption, len(parsed_figure.graphics))
    panels: list[PanelRecord] = []
    for index, graphic in enumerate(parsed_figure.graphics):
        label = labels[index] if index < len(labels) else None
        panels.append(
            PanelRecord(
                parent_fig_id=fig_id,
                label=label,
                source_type=SourceType.ARXIV_SOURCE,
                source_image=str(resolved[index]) if index < len(resolved) and resolved[index] else None,
                original_file=graphic,
                caption=parsed_figure.caption,
                confidence=Confidence.HIGH,
                provenance=[provenance],
                panel_label_source="source_order" if label else None,
                candidate_reason=None if label else "Panel label could not be source-verified.",
            )
        )
    return panels


def _panel_labels(caption: str | None, count: int) -> list[str]:
    if count <= 0:
        return []
    explicit = [] if caption is None else [match.group(1).lower() for match in _PANEL_REF_RE.finditer(caption)]
    if len(dict.fromkeys(explicit)) >= count:
        return list(dict.fromkeys(explicit))[:count]
    if count <= 26:
        return [chr(ord("a") + index) for index in range(count)]
    return []


def _latex_search_dirs(source_dir: Path, tex_file: Path, included_files: list[Path], expanded_text: str) -> list[Path]:
    dirs: list[Path] = [tex_file.parent.resolve(), source_dir.resolve()]
    dirs.extend(path.parent.resolve() for path in included_files)
    for graphicspath in _graphicspath_dirs(expanded_text):
        dirs.append((source_dir / graphicspath).resolve())
        dirs.append((tex_file.parent / graphicspath).resolve())
    deduped: list[Path] = []
    for directory in dirs:
        if directory not in deduped:
            deduped.append(directory)
    return deduped


def _graphicspath_dirs(text: str) -> list[str]:
    dirs: list[str] = []
    start = 0
    command = "\\graphicspath"
    while True:
        command_at = text.find(command, start)
        if command_at == -1:
            break
        brace_at = text.find("{", command_at + len(command))
        if brace_at == -1:
            break
        block, end = _read_balanced(text, brace_at, "{", "}")
        dirs.extend(entry.strip().strip("\"'") for entry in _GRAPHICSPATH_ENTRY_RE.findall(block) if entry.strip())
        start = end
    return dirs


def _resolve_graphic_path(source_dir: Path, search_dirs: list[Path], graphic: str) -> Path | None:
    raw = graphic.strip().strip("\"'")
    raw_path = Path(raw)
    bases = [raw_path] if raw_path.is_absolute() else [directory / raw for directory in search_dirs]
    extensions = [".pdf", ".png", ".jpg", ".jpeg", ".eps"]
    expanded: list[Path] = []
    for candidate in bases:
        expanded.append(candidate)
        if candidate.suffix == "":
            expanded.extend(candidate.with_suffix(ext) for ext in extensions)
    for candidate in expanded:
        if candidate.exists() and candidate.is_file() and _is_relative_to(candidate, source_dir):
            return candidate.resolve()
    return None


def _compose_source_order_figure(source_dir: Path, fig_id: str, images: list[Path | None]) -> Path | None:
    rendered: list[Image.Image] = []
    for image in images:
        loaded = _load_image_for_composite(image)
        if loaded is None:
            for rendered_image in rendered:
                rendered_image.close()
            return None
        rendered.append(loaded)
    if not rendered:
        return None
    try:
        width = max(image.width for image in rendered)
        gap = 12 if len(rendered) > 1 else 0
        height = sum(image.height for image in rendered) + gap * (len(rendered) - 1)
        composite = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        y = 0
        for image in rendered:
            x = (width - image.width) // 2
            composite.alpha_composite(image, (x, y))
            y += image.height + gap
        output_dir = source_dir / ".paperfig_composites"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{fig_id}.png"
        composite.save(output_path)
        return output_path.resolve()
    finally:
        for image in rendered:
            image.close()


def _load_image_for_composite(path: Path | None) -> Image.Image | None:
    if path is None or not path.exists() or path.suffix.lower() == ".eps":
        return None
    try:
        if path.suffix.lower() == ".pdf":
            import fitz

            document = fitz.open(path)
            try:
                pixmap = document[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=True)
                return Image.frombytes("RGBA" if pixmap.alpha else "RGB", [pixmap.width, pixmap.height], pixmap.samples).convert("RGBA")
            finally:
                document.close()
        with Image.open(path) as image:
            return image.convert("RGBA")
    except Exception:
        return None


def _strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        cut_at = None
        for index, char in enumerate(line):
            if char == "%" and (index == 0 or line[index - 1] != "\\"):
                cut_at = index
                break
        lines.append(line[:cut_at] if cut_at is not None else line)
    return "\n".join(lines)


def _extract_caption(body: str) -> str | None:
    command = "\\caption"
    start = body.find(command)
    if start == -1:
        return None
    pos = start + len(command)
    while pos < len(body) and body[pos].isspace():
        pos += 1
    if pos < len(body) and body[pos] == "[":
        _, pos = _read_balanced(body, pos, "[", "]")
        while pos < len(body) and body[pos].isspace():
            pos += 1
    if pos >= len(body) or body[pos] != "{":
        return None
    caption, _ = _read_balanced(body, pos, "{", "}")
    cleaned = _clean_caption(caption)
    return cleaned if cleaned else None


def _extract_captionof_figure(body: str) -> str | None:
    command = "\\captionof"
    start = body.find(command)
    while start != -1:
        pos = start + len(command)
        while pos < len(body) and body[pos].isspace():
            pos += 1
        if pos >= len(body) or body[pos] != "{":
            start = body.find(command, start + len(command))
            continue
        kind, pos = _read_balanced(body, pos, "{", "}")
        if kind.strip() != "figure":
            start = body.find(command, start + len(command))
            continue
        while pos < len(body) and body[pos].isspace():
            pos += 1
        if pos >= len(body) or body[pos] != "{":
            return None
        caption, _ = _read_balanced(body, pos, "{", "}")
        cleaned = _clean_caption(caption)
        return cleaned if cleaned else None
    return None


def _read_balanced(text: str, start: int, opener: str, closer: str) -> tuple[str, int]:
    if text[start] != opener:
        return "", start
    depth = 0
    chars: list[str] = []
    pos = start
    while pos < len(text):
        char = text[pos]
        escaped = pos > 0 and text[pos - 1] == "\\"
        if char == opener and not escaped:
            depth += 1
            if depth > 1:
                chars.append(char)
        elif char == closer and not escaped:
            depth -= 1
            if depth == 0:
                return "".join(chars), pos + 1
            chars.append(char)
        else:
            chars.append(char)
        pos += 1
    return "".join(chars), pos


def _clean_caption(text: str) -> str:
    text = re.sub(r"\\label\{[^{}]*\}", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
