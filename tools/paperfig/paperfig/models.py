from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceType(str, Enum):
    ARXIV_SOURCE = "arxiv_source"
    HTML_FIGURE = "html_figure"
    PDF_EMBEDDED = "pdf_embedded"
    PDF_RENDERED_CROP = "pdf_rendered_crop"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


SOURCE_LEVELS: dict[SourceType, int] = {
    SourceType.ARXIV_SOURCE: 1,
    SourceType.HTML_FIGURE: 2,
    SourceType.PDF_EMBEDDED: 3,
    SourceType.PDF_RENDERED_CROP: 4,
}


class ProvenanceRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    source_type: SourceType
    level: int
    locator: str
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("level")
    @classmethod
    def valid_level(cls, value: int) -> int:
        if value not in {1, 2, 3, 4}:
            raise ValueError("provenance level must be 1, 2, 3, or 4")
        return value


class PanelRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    parent_fig_id: str | None = None
    label: str | None = None
    source_type: SourceType
    source_image: str | None = None
    original_file: str | None = None
    output_file: str | None = None
    caption: str | None = None
    confidence: Confidence = Confidence.UNCERTAIN
    verified: bool = False
    provenance: list[ProvenanceRecord] = Field(default_factory=list)
    candidate_reason: str | None = None
    panel_label_source: str | None = None


class FigureRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    fig_id: str | None = None
    source_type: SourceType
    source_image: str | None = None
    original_file: str | None = None
    output_file: str | None = None
    caption: str | None = None
    caption_file: str | None = None
    confidence: Confidence = Confidence.UNCERTAIN
    verified: bool = False
    panels: list[PanelRecord] = Field(default_factory=list)
    provenance: list[ProvenanceRecord] = Field(default_factory=list)
    candidate_reason: str | None = None


class ExtractionResult(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    input: str
    strict: bool = True
    dpi: int = 400
    figures: list[FigureRecord] = Field(default_factory=list)
    candidates: list[FigureRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    output_dir: str | None = None
    metadata_path: str | None = None
