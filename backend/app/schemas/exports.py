from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

ExportReportType = Literal[
    'point_history',
    'upcoming_rolloffs',
    'upcoming_perfect_attendance',
    'annual_rolloffs',
]


class ExportPreview(BaseModel):
    report_type: ExportReportType
    title: str
    subtitle: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    start_date: str
    end_date: str
    building: str
