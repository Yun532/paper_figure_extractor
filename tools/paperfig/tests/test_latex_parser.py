from __future__ import annotations

from pathlib import Path

from PIL import Image

from paperfig.latex_parser import figure_records_from_latex, parse_latex_figures


def _write_png(path: Path) -> None:
    Image.new("RGB", (2, 2), (255, 0, 0)).save(path)


def test_parse_latex_figures_in_order_with_captions_and_graphics() -> None:
    text = r"""
    \begin{figure}
      \includegraphics[width=\linewidth]{fig1}
      \caption{First real caption.}
    \end{figure}
    \begin{figure*}
      \includegraphics{fig2.png}
      \caption[short]{Second real caption with \label{fig:two}}
    \end{figure*}
    """

    figures = parse_latex_figures(text, "main.tex")

    assert [figure.index for figure in figures] == [1, 2]
    assert figures[0].graphics == ["fig1"]
    assert figures[0].caption == "First real caption."
    assert figures[1].graphics == ["fig2.png"]
    assert figures[1].caption == "Second real caption with"


def test_latex_parser_does_not_create_figures_without_figure_environment() -> None:
    text = r"\includegraphics{loose-image}\caption{Loose caption}"

    assert parse_latex_figures(text) == []


def test_latex_records_do_not_fabricate_missing_caption(tmp_path) -> None:
    _write_png(tmp_path / "fig1.png")
    tex_file = tmp_path / "main.tex"
    tex_file.write_text(
        r"""
        \documentclass{article}
        \begin{document}
        \begin{figure}
          \includegraphics{fig1}
        \end{figure}
        \end{document}
        """,
        encoding="utf-8",
    )

    records = figure_records_from_latex(tmp_path, tex_file)

    assert len(records) == 1
    assert records[0].fig_id == "Fig01"
    assert records[0].caption is None
    assert records[0].source_image is not None
    assert records[0].provenance


def test_latex_input_files_are_expanded_for_main_document(tmp_path) -> None:
    _write_png(tmp_path / "included.png")
    (tmp_path / "main.tex").write_text(
        r"""
        \documentclass{article}
        \begin{document}
        \input{section}
        \end{document}
        """,
        encoding="utf-8",
    )
    (tmp_path / "section.tex").write_text(
        r"""
        \begin{figure}
          \includegraphics{included}
          \caption{Included figure caption.}
        \end{figure}
        """,
        encoding="utf-8",
    )

    records = figure_records_from_latex(tmp_path, tmp_path / "main.tex")

    assert len(records) == 1
    assert records[0].fig_id == "Fig01"
    assert records[0].caption == "Included figure caption."
    assert records[0].source_image is not None
    assert "section.tex" in records[0].provenance[0].details["expanded_inputs"]


def test_captionof_figure_inside_table_environment_is_extracted(tmp_path) -> None:
    _write_png(tmp_path / "zero-shot-transfer.png")
    tex_file = tmp_path / "main.tex"
    tex_file.write_text(
        r"""
        \documentclass{article}
        \usepackage{capt-of}
        \begin{document}
        \begin{table*}
          \includegraphics[width=\textwidth]{zero-shot-transfer}
          \captionof{figure}{CLIP's zero-shot performance compared to linear-probe ResNet performance}
          \label{all-zero-shot-performance-figure}
        \end{table*}
        \end{document}
        """,
        encoding="utf-8",
    )

    records = figure_records_from_latex(tmp_path, tex_file)

    assert len(records) == 1
    assert records[0].fig_id == "Fig01"
    assert records[0].source_image is not None
    assert records[0].caption == "CLIP's zero-shot performance compared to linear-probe ResNet performance"
    assert records[0].provenance[0].details["environment"] == "table*"


def test_graphicspath_is_used_to_resolve_images(tmp_path) -> None:
    figures_dir = tmp_path / "Figures"
    figures_dir.mkdir()
    _write_png(figures_dir / "plot.png")
    tex_file = tmp_path / "main.tex"
    tex_file.write_text(
        r"""
        \documentclass{article}
        \graphicspath{{Figures/}}
        \begin{document}
        \begin{figure}
          \includegraphics{plot}
          \caption{Graphicspath figure.}
        \end{figure}
        \end{document}
        """,
        encoding="utf-8",
    )

    records = figure_records_from_latex(tmp_path, tex_file)

    assert len(records) == 1
    assert records[0].source_image is not None
    assert records[0].source_image.endswith("plot.png")
    assert records[0].candidate_reason is None
    assert "Figures" in records[0].provenance[0].details["graphicspath"]


def test_multiple_includegraphics_are_source_backed_panels(tmp_path) -> None:
    _write_png(tmp_path / "a.png")
    _write_png(tmp_path / "b.png")
    tex_file = tmp_path / "main.tex"
    tex_file.write_text(
        r"""
        \documentclass{article}
        \begin{document}
        \begin{figure}
          \includegraphics{a}
          \includegraphics{b}
          \caption{(a) First panel. (b) Second panel.}
        \end{figure}
        \end{document}
        """,
        encoding="utf-8",
    )

    records = figure_records_from_latex(tmp_path, tex_file)

    assert records[0].fig_id == "Fig01"
    assert records[0].source_image is not None
    assert records[0].source_image.endswith("Fig01.png")
    assert records[0].candidate_reason is None
    assert records[0].provenance[0].details["composite_strategy"] == "source_order_vertical_stack"
    assert [panel.label for panel in records[0].panels] == ["a", "b"]
    assert all(panel.provenance for panel in records[0].panels)
