from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EmployeeSummary(BaseModel):
    employee_id: int
    first_name: str
    last_name: str
    location: str = ''
    start_date: str | None = None
    point_total: float = 0.0
    rolloff_date: str | None = None
    perfect_attendance: str | None = None
    is_active: bool = True


class EmployeeDetail(EmployeeSummary):
    last_point_date: str | None = None
    point_warning_date: str | None = None


class EmployeeCreateRequest(BaseModel):
    employee_id: int
    first_name: str
    last_name: str
    start_date: str = Field(..., description='ISO date in YYYY-MM-DD format')
    location: str | None = None


class EmployeeUpdateRequest(BaseModel):
    first_name: str
    last_name: str
    start_date: str | None = Field(None, description='ISO date in YYYY-MM-DD format')
    location: str | None = None
    is_active: bool = True


class PointHistoryEntry(BaseModel):
    id: int
    point_date: str
    points: float
    reason: str | None = None
    note: str | None = None
    flag_code: str | None = None
    point_total: float


class PointMutationRequest(BaseModel):
    point_date: str = Field(..., description='ISO date in YYYY-MM-DD format')
    points: float
    reason: str
    note: str | None = None
    flag_code: str | None = None


class DashboardSummary(BaseModel):
    total_employees: int
    active_employees: int
    employees_at_or_above_five: int
    upcoming_rolloffs: int
    upcoming_perfect_attendance: int


class DashboardPulse(BaseModel):
    points_added_24h: int
    points_added_7d: int
    rolloffs_due_7d: int
    perfect_due_7d: int


class DashboardBucketCounts(BaseModel):
    above_one: int
    one_to_four: int
    five_to_six: int
    seven_plus: int


class DashboardEmployeeSpotlight(BaseModel):
    employee_id: int
    first_name: str
    last_name: str
    location: str = ''
    point_total: float = 0.0
    rolloff_date: str | None = None
    perfect_attendance: str | None = None
    last_point_date: str | None = None


class DashboardRecentActivity(BaseModel):
    employee_id: int
    first_name: str
    last_name: str
    location: str = ''
    point_date: str
    points: float
    reason: str | None = None
    note: str | None = None


class DashboardDetail(BaseModel):
    summary: DashboardSummary
    pulse: DashboardPulse
    bucket_counts: DashboardBucketCounts
    at_risk_employees: list[DashboardEmployeeSpotlight]
    upcoming_rolloffs: list[DashboardEmployeeSpotlight]
    upcoming_perfect_attendance: list[DashboardEmployeeSpotlight]
    recent_activity: list[DashboardRecentActivity]


class CorrectiveActionEmployee(BaseModel):
    employee_id: int
    first_name: str
    last_name: str
    location: str = ''
    point_total: float = 0.0
    last_positive_point_date: str | None = None
    point_warning_date: str | None = None
    tier_key: str
    tier_label: str
    tier_range: str


class CorrectiveActionTierCount(BaseModel):
    key: str
    label: str
    count: int


class CorrectiveActionOverview(BaseModel):
    total_flagged: int
    tiers: list[CorrectiveActionTierCount]
    employees: list[CorrectiveActionEmployee]


class CorrectiveActionUpdateRequest(BaseModel):
    point_warning_date: str = Field(..., description='ISO date in YYYY-MM-DD format')


class MaintenanceRunRequest(BaseModel):
    run_date: str = Field(..., description='ISO date in YYYY-MM-DD format')
    dry_run: bool = True


class MaintenanceJobResult(BaseModel):
    job: str
    dry_run: bool
    affected: int
    rows: list[dict[str, Any]]
    summary: DashboardSummary


class MutationResult(BaseModel):
    employee: EmployeeDetail
    history: list[PointHistoryEntry]
