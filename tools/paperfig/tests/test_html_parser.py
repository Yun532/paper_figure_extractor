from __future__ import annotations

from paperfig.journal_html import parse_html_figures


def test_html_parser_maps_explicit_figure_label() -> None:
    html = """
    <html><body>
      <figure id="f1">
        <img src="fig1.png" />
        <figcaption>Fig. 1 A measured result.</figcaption>
      </figure>
    </body></html>
    """

    records = parse_html_figures(html, base_url="https://example.test/articles/paper/", original_locator="article.html")

    assert len(records) == 1
    assert records[0].fig_id == "Fig01"
    assert records[0].caption == "Fig. 1 A measured result."
    assert records[0].source_image == "https://example.test/articles/paper/fig1.png"
    assert records[0].provenance


def test_html_parser_deduplicates_equivalent_picture_sources() -> None:
    html = """
    <figure>
      <picture>
        <source srcset="https://media.example/Fig1.png?as=webp" />
        <img src="https://media.example/Fig1.png" />
      </picture>
      <figcaption>Fig. 1 One Nature-style figure.</figcaption>
    </figure>
    """

    records = parse_html_figures(html)

    assert records[0].fig_id == "Fig01"
    assert records[0].source_image == "https://media.example/Fig1.png"
    assert records[0].candidate_reason is None
    assert records[0].panels == []


def test_html_parser_keeps_ambiguous_label_as_candidate() -> None:
    html = """
    <figure>
      <img src="plot.png" />
      <figcaption>A measured result without an explicit figure number.</figcaption>
    </figure>
    """

    records = parse_html_figures(html)

    assert records[0].fig_id is None
    assert records[0].candidate_reason == "HTML figure label is missing or ambiguous."


def test_html_parser_does_not_map_extended_data_to_main_figxx() -> None:
    html = """
    <figure>
      <img src="extended.png" />
      <figcaption>Extended Data Fig. 1 Control experiment.</figcaption>
    </figure>
    """

    records = parse_html_figures(html)

    assert records[0].fig_id is None
    assert records[0].candidate_reason


def test_html_multiple_images_are_source_backed_panels() -> None:
    html = """
    <figure>
      <img src="a.png" />
      <img src="b.png" />
      <figcaption>Figure 2 Two source images.</figcaption>
    </figure>
    """

    records = parse_html_figures(html, base_url="https://example.test/")

    assert records[0].fig_id == "Fig02"
    assert records[0].source_image is None
    assert records[0].candidate_reason
    assert [panel.label for panel in records[0].panels] == ["a", "b"]
    assert [panel.source_image for panel in records[0].panels] == ["https://example.test/a.png", "https://example.test/b.png"]
