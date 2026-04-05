"""Shared constants used across the Attendance Point Tracker."""
from __future__ import annotations

BUILDINGS = ["APIM", "APIS", "AAP"]
POINT_BALANCE_REPAIR_VERSION = 2
EMPLOYEE_CACHE_TTL_SECONDS = 60
DASHBOARD_CACHE_TTL_SECONDS = 90
LEDGER_HISTORY_DEFAULT_LIMIT = 500
LEDGER_HISTORY_FULL_LIMIT = 5000

EXPORT_LABELS = {
    "employee audit":             "Employee Audit",
    "30-day point history":        "30-Day Point History",
    "upcoming 2-month roll-offs":  "Upcoming 2-Month Roll-offs",
    "upcoming perfect attendance": "Upcoming Perfect Attendance",
    "pending ytd roll-offs":       "Pending YTD Roll-offs",
    "applied ytd roll-off history": "Applied YTD Roll-off History",
}
