from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PTOFilters(BaseModel):
    available_buildings: list[str] = Field(default_factory=list)
    available_types: list[str] = Field(default_factory=list)
    selected_building: str = 'All'
    selected_types: list[str] = Field(default_factory=list)
    selected_start_date: str | None = None
    selected_end_date: str | None = None
    date_min: str | None = None
    date_max: str | None = None
    total_records: int = 0


class PTOSummary(BaseModel):
    total_records: int = 0
    total_hours: float = 0.0
    total_days: float = 0.0
    days_impacted: int = 0
    employees_used: int = 0
    utilization_pct: float = 0.0
    top_type: str | None = None
    avg_days_per_employee: float = 0.0
    utilization_30d_pct: float = 0.0


class PTOTypeTotal(BaseModel):
    pto_type: str
    hours: float
    days: float
    percentage: float
    color: str
    category: str


class PTOMonthlyTrendPoint(BaseModel):
    month: str
    label: str
    total_hours: float
    total_days: float
    dominant_type: str | None = None


class PTOBuildingTotal(BaseModel):
    building: str
    hours: float
    days: float
    employees: int


class PTOEmployeeUsage(BaseModel):
    employee_id: int | None = None
    employee: str
    building: str
    hours: float
    days: float
    entries: int = 0


class PTOCategoryMetric(BaseModel):
    key: str
    label: str
    hours: float
    days: float
    percentage: float


class PTOPaceSummary(BaseModel):
    annualized_total_days: float = 0.0
    annualized_per_employee_days: float = 0.0
    trend_delta_pct: float = 0.0
    trend_direction: str = 'flat'
    trend_label: str = 'Steady'


class PTORow(BaseModel):
    employee_id: int | None = None
    employee: str
    building: str
    pto_type: str
    start_date: str
    end_date: str
    hours: float
    days: float


class PTOOverview(BaseModel):
    has_data: bool
    filters: PTOFilters
    summary: PTOSummary
    type_totals: list[PTOTypeTotal] = Field(default_factory=list)
    monthly_trend: list[PTOMonthlyTrendPoint] = Field(default_factory=list)
    building_totals: list[PTOBuildingTotal] = Field(default_factory=list)
    top_users: list[PTOEmployeeUsage] = Field(default_factory=list)
    low_usage_employees: list[PTOEmployeeUsage] = Field(default_factory=list)
    zero_pto_employees: list[str] = Field(default_factory=list)
    category_metrics: list[PTOCategoryMetric] = Field(default_factory=list)
    pace: PTOPaceSummary = Field(default_factory=PTOPaceSummary)
    rows: list[PTORow] = Field(default_factory=list)


class PTOImportRow(BaseModel):
    employee_id: int | str | None = None
    last_name: str | None = None
    first_name: str | None = None
    building: str | None = None
    pto_type: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    date: str | None = None
    hours: float | str | None = None


class PTOImportRequest(BaseModel):
    rows: list[PTOImportRow] = Field(default_factory=list)


class PTOImportResult(BaseModel):
    inserted: int
    duplicate: int
    total: int
    excluded: int
    invalid: int
    excluded_employees: list[str] = Field(default_factory=list)


class PTOClearResult(BaseModel):
    ok: bool


class PTOExportRow(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
