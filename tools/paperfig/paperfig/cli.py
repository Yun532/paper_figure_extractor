from __future__ import annotations

from pathlib import Path

import typer

from .api import extract_figures

app = typer.Typer(no_args_is_help=True, help="Extract evidence-backed scientific paper figures.")


@app.command("version")
def version() -> None:
    typer.echo("paperfig 0.1.0")


@app.command()
def extract(
    input: str = typer.Argument(..., help="arXiv ID/URL, local PDF/source path, or journal article URL."),
    out: Path = typer.Option(..., "--out", "-o", help="Output directory."),
    dpi: int = typer.Option(400, "--dpi", help="Rendering DPI for PDF/image conversion."),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Keep uncertain outputs as candidates."),
) -> None:
    result = extract_figures(input, out, dpi=dpi, strict=strict)
    verified_panels = sum(len([panel for panel in figure.panels if panel.verified]) for figure in result.figures + result.candidates)
    typer.echo(f"verified figures: {len(result.figures)}")
    typer.echo(f"verified panels: {verified_panels}")
    typer.echo(f"candidates: {len(result.candidates)}")
    if result.metadata_path:
        typer.echo(f"metadata: {result.metadata_path}")
    for warning in result.warnings:
        typer.echo(f"warning: {warning}", err=True)


if __name__ == "__main__":
    app()
