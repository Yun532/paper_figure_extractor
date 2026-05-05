# Paper Figure Extractor

Evidence-based scientific paper figure extraction for arXiv papers, local PDFs, and journal article pages.

This repository contains a reusable Claude Code skill and a Python package named `paperfig`. The goal is to extract real paper figures with strict provenance, while avoiding hallucinated figure numbers, captions, panel labels, or reconstructed images.

## GitHub project introduction

**Short description**

> Extract real figures from scientific papers with strict provenance and non-hallucination guarantees.

**Long description**

Paper Figure Extractor is a local-first tool for extracting figures from scientific papers. It supports arXiv IDs/URLs, local PDFs, local LaTeX source trees, and journal HTML pages such as Nature-style article pages. The extractor prefers source-backed evidence, records provenance in `metadata.json`, separates verified figures from uncertain candidates, and avoids inventing missing figures, captions, figure numbers, or panel labels.

Suggested GitHub topics:

- `paper-figures`
- `scientific-papers`
- `arxiv`
- `pdf-extraction`
- `latex`
- `research-tools`
- `provenance`
- `claude-code-skill`

## What it does

`paperfig` extracts figures using a strict source reliability hierarchy:

1. **arXiv / LaTeX source**: parses `figure` environments, `\includegraphics`, and `\caption`.
2. **Journal HTML**: parses `<figure>` / `<figcaption>` and source image URLs.
3. **PDF embedded images**: extracts embedded image objects as candidates when the figure mapping is uncertain.
4. **Rendered PDF crops**: renders caption-nearby crops as low-confidence candidates.

Verified outputs go to `figures/`. Uncertain outputs go to `candidates/`.

## Non-hallucination rules

The tool is intentionally conservative:

- It does not fabricate figures.
- It does not fabricate captions.
- It does not fabricate figure numbers.
- It does not generate, redraw, or reconstruct figures.
- It does not promote uncertain PDF crops to final `FigXX` outputs in strict mode.
- Every output record includes provenance pointing back to a source file, HTML location, LaTeX location, or PDF page/object location.

## Repository layout

```text
paper_figure_extractor/
  SKILL.md                         # Claude Code skill instructions
  prompt.txt                       # Original build prompt / requirements
  tools/
    paperfig/
      pyproject.toml               # Python package metadata
      paperfig/
        api.py                     # Python API orchestration
        cli.py                     # CLI entry point
        arxiv_source.py            # arXiv source download/extraction
        latex_parser.py            # LaTeX figure parser
        journal_html.py            # Journal HTML parser
        pdf_extract.py             # Conservative PDF candidate extraction
        verify.py                  # Verification and source hierarchy
        export.py                  # Output writer
        models.py                  # Pydantic data models
      tests/
```

## Installation

### Local editable install

From this repository root:

```bash
pip install -e tools/paperfig
```

For development and tests:

```bash
pip install -e "tools/paperfig[dev]"
pytest tools/paperfig
```

### Install from GitHub

Because the Python package lives in `tools/paperfig`, install with the `subdirectory` fragment:

```bash
pip install "git+https://github.com/Yun532/paper_figure_extractor.git#subdirectory=tools/paperfig"
```

## CLI usage

```bash
paperfig extract INPUT --out OUTPUT_DIR --dpi 400 --strict
```

Examples:

```bash
# arXiv ID
paperfig extract 1706.03762 --out outputs/attention --dpi 400 --strict

# arXiv URL
paperfig extract https://arxiv.org/abs/2103.00020 --out outputs/clip --dpi 400 --strict

# local PDF
paperfig extract path/to/paper.pdf --out outputs/paper --dpi 400 --strict

# journal article page
paperfig extract https://www.nature.com/articles/example --out outputs/nature_article --dpi 400 --strict
```

The command prints counts for verified figures, verified panels, candidates, warnings, and the metadata path.

## Python API usage

```python
from pathlib import Path

from paperfig import extract_figures

result = extract_figures(
    "1706.03762",
    outdir=Path("outputs/attention"),
    dpi=400,
    strict=True,
)

print(result.metadata_path)
for figure in result.figures:
    print(figure.fig_id, figure.output_file, figure.caption_file)

for candidate in result.candidates:
    print("candidate", candidate.output_file, candidate.candidate_reason)
```

## Output structure

```text
OUTPUT_DIR/
  metadata.json
  figures/
    Fig01.png
    Fig01_panel_a.png
  candidates/
    candidate_001.png
    page_5_figure_candidate_02.png
  captions/
    Fig01.txt
```

`metadata.json` contains:

- input
- strict mode and DPI
- verified figures
- candidate records
- figure IDs
- source type
- original/source files
- output paths
- captions and caption files
- confidence
- verification status
- panel metadata
- provenance records
- warnings

## Expected behavior by input type

### arXiv ID or arXiv URL

This is the highest-confidence path. The tool downloads the arXiv source package, finds the main LaTeX file, parses figure environments, resolves graphics paths, and exports verified `FigXX.png` files when source evidence is sufficient.

### Local LaTeX source directory or `.tex` file

The tool parses local source directly. This is useful when another project has already downloaded or unpacked paper source files.

### Journal HTML page

The tool parses `<figure>` elements and associated captions. Figures with explicit source-backed mappings can become verified outputs; ambiguous mappings remain candidates.

### Local PDF or PDF URL

The PDF path is intentionally conservative. Embedded PDF images and rendered caption-nearby crops are usually candidates because PDF layout alone often cannot prove the figure number/image mapping.

## Claude Code skill usage

`SKILL.md` describes the Claude Code skill behavior. When using this repository as a skill, Claude should call the bundled `paperfig` tool rather than visually inventing or redrawing paper figures.

## Current limitations

- PDF extraction is conservative and usually produces candidates rather than verified `FigXX` outputs.
- arXiv source extraction is strongest when the source package contains clear `figure` environments and resolvable graphics files.
- Panel extraction only treats source-backed multi-image figures as verified; visual/grid inference should remain candidate-only.
- The tool does not perform OCR-heavy figure reconstruction or visual hallucination.

## License

No license has been specified yet. Add a license before distributing the project broadly.
