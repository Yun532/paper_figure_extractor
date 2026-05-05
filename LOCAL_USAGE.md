# Local usage and integration guide

This guide explains how another local project can call `paperfig` to extract figures from scientific papers.

## 1. Install `paperfig` locally

Assume this repository is located at:

```text
E:\paper_figure_extractor
```

Install the package in editable mode:

```bash
pip install -e E:/paper_figure_extractor/tools/paperfig
```

If the calling project uses its own virtual environment, activate that environment first, then run the install command inside it.

## 2. Call from another Python project

```python
from pathlib import Path

from paperfig import extract_figures

input_paper = "1706.03762"  # arXiv ID, arXiv URL, local PDF, local .tex, source dir, or journal URL
output_dir = Path("paper_outputs") / "1706_03762"

result = extract_figures(
    input=input_paper,
    outdir=output_dir,
    dpi=400,
    strict=True,
)

verified_figures = [figure.output_file for figure in result.figures]
candidates = [candidate.output_file for candidate in result.candidates]

print("metadata:", result.metadata_path)
print("verified figures:", verified_figures)
print("candidates:", candidates)
```

## 3. Read extracted files

After extraction, the calling project should read `metadata.json` first because it contains provenance and verification status.

```python
import json
from pathlib import Path

metadata_path = Path(result.metadata_path)
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

for figure in metadata["figures"]:
    fig_id = figure["fig_id"]
    image_path = metadata_path.parent / figure["output_file"]
    caption_path = metadata_path.parent / figure["caption_file"] if figure.get("caption_file") else None
    print(fig_id, image_path, caption_path)
```

Recommended integration rule:

- Use `metadata["figures"]` for verified final figures.
- Use `metadata["candidates"]` only for review or fallback UI.
- Do not treat candidates as final extracted figures unless a human or downstream verifier accepts them.

## 4. Example wrapper function for another project

```python
from pathlib import Path

from paperfig import extract_figures


def extract_paper_images(paper_input: str, output_root: str | Path) -> dict:
    output_root = Path(output_root)
    safe_name = paper_input.replace("/", "_").replace(":", "_").replace(".", "_")
    output_dir = output_root / safe_name

    result = extract_figures(
        input=paper_input,
        outdir=output_dir,
        dpi=400,
        strict=True,
    )

    return {
        "metadata_path": result.metadata_path,
        "output_dir": result.output_dir,
        "verified_figures": [
            {
                "fig_id": figure.fig_id,
                "image": str(output_dir / figure.output_file) if figure.output_file else None,
                "caption": figure.caption,
                "caption_file": str(output_dir / figure.caption_file) if figure.caption_file else None,
                "confidence": figure.confidence,
                "source_type": figure.source_type,
                "provenance": [p.model_dump(mode="json") for p in figure.provenance],
            }
            for figure in result.figures
        ],
        "candidates": [
            {
                "image": str(output_dir / candidate.output_file) if candidate.output_file else None,
                "reason": candidate.candidate_reason,
                "source_type": candidate.source_type,
                "provenance": [p.model_dump(mode="json") for p in candidate.provenance],
            }
            for candidate in result.candidates
        ],
        "warnings": result.warnings,
    }
```

## 5. Add as a dependency in another project

### Local path dependency

For a one-machine setup, install directly into the caller project's environment:

```bash
pip install -e E:/paper_figure_extractor/tools/paperfig
```

### GitHub dependency

After this repository is pushed to GitHub:

```bash
pip install "git+https://github.com/Yun532/paper_figure_extractor.git#subdirectory=tools/paperfig"
```

In `requirements.txt`:

```text
git+https://github.com/Yun532/paper_figure_extractor.git#subdirectory=tools/paperfig
```

In `pyproject.toml` dependencies, use a direct reference:

```toml
dependencies = [
  "paperfig @ git+https://github.com/Yun532/paper_figure_extractor.git#subdirectory=tools/paperfig",
]
```

## 6. CLI integration from another project

If the other project does not need Python-level integration, it can call the CLI:

```bash
paperfig extract 1706.03762 --out paper_outputs/1706_03762 --dpi 400 --strict
```

Then consume:

```text
paper_outputs/1706_03762/metadata.json
paper_outputs/1706_03762/figures/
paper_outputs/1706_03762/candidates/
paper_outputs/1706_03762/captions/
```

## 7. Practical notes

- Prefer arXiv IDs or arXiv URLs when available; they usually provide the strongest source evidence.
- For local PDFs, expect candidate outputs unless the image-to-figure mapping can be verified.
- Keep `strict=True` for production use.
- Store each paper's output in a separate directory.
- Treat `metadata.json` as the contract between this extractor and the calling project.
