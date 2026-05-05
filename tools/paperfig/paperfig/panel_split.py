from __future__ import annotations

from .models import FigureRecord, PanelRecord


def verified_panels(record: FigureRecord) -> list[PanelRecord]:
    return [panel for panel in record.panels if panel.verified]


def candidate_panels(record: FigureRecord) -> list[PanelRecord]:
    return [panel for panel in record.panels if not panel.verified]
