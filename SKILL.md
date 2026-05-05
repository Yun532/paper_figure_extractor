---
name: paper_figure_extractor
description: Extract real figures from scientific papers with strict provenance and non-hallucination guarantees.
---

# paper_figure_extractor

Use this skill when the user asks to extract figures from scientific papers, including arXiv IDs/URLs, local PDFs, and journal article pages such as Nature-style pages.

## Hard rules

- Never fabricate figures.
- Never fabricate captions.
- Never fabricate figure numbers.
- Never fabricate panel labels such as `a`, `b`, or `c`.
- Never generate, redraw, reconstruct, or visually invent images.
- Never infer missing panels without evidence.
- If anything is uncertain, mark it uncertain, save it as a candidate, and do not promote it to final `FigXX`.
- Every output must have provenance pointing to a source file, LaTeX location, HTML location, or PDF page/object location.

## Tool usage

Use the bundled `paperfig` tool rather than visually inventing figures:

```bash
paperfig extract INPUT --out OUTPUT --dpi 400 --strict
```

Python API:

```python
from paperfig import extract_figures
extract_figures(input, outdir, dpi=400, strict=True)
```

## Reliability hierarchy

Always prefer higher-confidence sources. Lower levels must not override higher levels.

1. High: arXiv source LaTeX, parsed from `figure` environments, `\includegraphics`, and `\caption`.
2. Medium: journal HTML `<figure>` and `<figcaption>` elements.
3. Low/medium candidate source: PDF embedded image objects.
4. Low: rendered PDF page crops and caption-based crops. In strict mode these are candidates only.

## Output contract

The tool writes:

```text
OUTPUT/
  metadata.json
  figures/
    Fig01.png
    Fig01_panel_a.png
  candidates/
    Fig03_candidate_page_5.png
    Fig04_panel_candidate_01.png
  captions/
    Fig01.txt
```

Only verified source-backed figures and panels belong in `figures/`. Uncertain images, ambiguous mappings, rendered PDF crops, and visually inferred panels belong in `candidates/`.

## Panel rules

Verified panel labels require source evidence, such as multiple `\includegraphics` entries inside one LaTeX figure environment or multiple images inside one HTML figure. Caption-only references can support metadata but must not cause visual crops or labels unless alignment is reliable. Visual/grid inference is candidate-only and must not assign `a`, `b`, or `c`.

## Reporting results

When presenting results to the user, distinguish verified figures from candidates. Do not describe candidates as extracted final figures. Refer to `metadata.json` for provenance and confidence.
