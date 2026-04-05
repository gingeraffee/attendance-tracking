"""Database helpers, caching, and connection management."""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

import atp_core.db as db
from atp_core.schema import ensure_schema
from atp_core import repo, services

from atp_streamlit.constants import (
    EMPLOYEE_CACHE_TTL_SECONDS,
    DASHBOARD_CACHE_TTL_SECONDS,
    POINT_BALANCE_REPAIR_VERSION,
)


def _db_cache_key() -> str:
    return db.get_db_path()


@st.cache_resource(show_spinner=False)
def _get_cached_conn(db_key: str):
    return db.connect()


@st.cache_resource(show_spinner=False)
def _initialize_database(db_key: str, repair_version: int) -> None:
    conn = _get_cached_conn(db_key)
    ensure_schema(conn)
    try:
        if is_pg(conn):
            exec_sql(conn, "ALTER TABLE employees ADD COLUMN IF NOT EXISTS point_warning_date DATE")
            conn.commit()
        else:
            cols = [r[1] for r in fetchall(conn, "PRAGMA table_info(employees)")]
            if "point_warning_date" not in cols:
                exec_sql(conn, "ALTER TABLE employees ADD COLUMN point_warning_date DATE")
                conn.commit()
    except Exception:
        pass

    bulk_recalc = getattr(services, "recalculate_all_employee_dates", None)
    single_recalc = getattr(services, "recalculate_employee_dates", None)
    if callable(bulk_recalc):
        bulk_recalc(conn)
    elif callable(single_recalc):
        employee_rows = fetchall(conn, "SELECT employee_id FROM employees")
        with db.tx(conn):
            for row in employee_rows:
                single_recalc(conn, int(row["employee_id"]))


@st.cache_data(ttl=EMPLOYEE_CACHE_TTL_SECONDS, show_spinner=False)
def _load_employees_cached(db_key: str, q: str, building: str) -> list[dict]:
    conn = _get_cached_conn(db_key)
    rows = [dict(r) for r in repo.search_employees(conn, q=q, limit=3000)]
    if building != "All":
        rows = [r for r in rows if (r.get("location") or "") == building]
    return rows


@st.cache_data(ttl=DASHBOARD_CACHE_TTL_SECONDS, show_spinner=False)
def _fetchall_cached(db_key: str, sql: str, params: tuple = ()) -> list[dict]:
    conn = _get_cached_conn(db_key)
    return [dict(r) for r in fetchall(conn, sql, params)]


def clear_read_caches() -> None:
    _load_employees_cached.clear()
    _fetchall_cached.clear()


def get_conn():
    db_key = _db_cache_key()
    _initialize_database(db_key, POINT_BALANCE_REPAIR_VERSION)
    return _get_cached_conn(db_key)

def is_pg(conn) -> bool:
    return conn.__class__.__module__.startswith("psycopg2")


def _normalize_bulk_override_columns(csv_df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        col: str(col).replace("\ufeff", "").strip()
        for col in csv_df.columns
    }
    return csv_df.rename(columns=rename_map)


def _parse_bulk_override_employee_id(value) -> int:
    if pd.isna(value):
        raise ValueError("Employee # is blank.")

    text = str(value).strip()
    if not text:
        raise ValueError("Employee # is blank.")

    try:
        numeric = float(text)
    except ValueError as exc:
        raise ValueError(f"Employee # '{text}' is not a valid number.") from exc

    if not numeric.is_integer():
        raise ValueError(f"Employee # '{text}' must be a whole number.")

    return int(numeric)


def _parse_bulk_override_point_total(value) -> float:
    if pd.isna(value) or str(value).strip() == "":
        return 0.0
    try:
        parsed = round(float(value), 1)
    except ValueError as exc:
        raise ValueError(f"Point Total '{value}' is not a valid number.") from exc
    if parsed < 0:
        raise ValueError("Point Total cannot be negative.")
    return parsed


def _parse_bulk_override_date(value, column_name: str) -> date | None:
    if pd.isna(value) or str(value).strip() == "":
        return None
    try:
        return pd.to_datetime(str(value)).date()
    except Exception as exc:
        raise ValueError(f"{column_name} '{value}' is not a valid date.") from exc


def _get_history_point_total(conn, employee_id: int) -> float:
    svc = getattr(services, "get_history_point_total", None)
    if callable(svc):
        return round(float(svc(conn, int(employee_id))), 1)

    rows = repo.with_running_point_totals(
        repo.get_points_history_ordered(conn, int(employee_id))
    )
    return round(float(rows[-1]["point_total"]) if rows else 0.0, 1)


def _apply_bulk_employee_override(
    conn,
    *,
    employee_id: int,
    point_total: float | None = None,
    update_point_total: bool = False,
    rolloff_date: date | None = None,
    update_rolloff_date: bool = False,
    perfect_attendance: date | None = None,
    update_perfect_attendance: bool = False,
    note: str | None = None,
) -> None:
    svc = getattr(services, "apply_bulk_employee_override", None)
    if callable(svc):
        svc(
            conn,
            employee_id=int(employee_id),
            point_total=point_total,
            update_point_total=update_point_total,
            rolloff_date=rolloff_date,
            update_rolloff_date=update_rolloff_date,
            perfect_attendance=perfect_attendance,
            update_perfect_attendance=update_perfect_attendance,
            note=note,
        )
        return

    employee_id = int(employee_id)
    with db.tx(conn):
        if update_point_total:
            current_total = _get_history_point_total(conn, employee_id)
            target_total = round(float(point_total or 0.0), 1)
            adjustment = round(target_total - current_total, 3)
            if abs(adjustment) >= 0.001:
                repo.insert_points_history(
                    conn,
                    employee_id=employee_id,
                    point_date=date.today(),
                    points=adjustment,
                    reason="Manual Adjustment",
                    note=(note or "").strip() or "Bulk override",
                    flag_code="MANUAL",
                )
            services.recalculate_employee_dates(conn, employee_id)

        if update_rolloff_date or update_perfect_attendance:
            current = dict(repo.get_employee(conn, employee_id) or {})
            rolloff_iso = current.get("rolloff_date")
            perfect_iso = current.get("perfect_attendance")

            if update_rolloff_date:
                rolloff_iso = rolloff_date.isoformat() if rolloff_date else None
            if update_perfect_attendance:
                perfect_iso = perfect_attendance.isoformat() if perfect_attendance else None

            exec_sql(
                conn,
                "UPDATE employees SET rolloff_date = ?, perfect_attendance = ? WHERE employee_id = ?",
                (rolloff_iso, perfect_iso, employee_id),
            )


def fetchall(conn, sql: str, params=()):
    if is_pg(conn):
        cur = conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        rows = cur.fetchall()
        cur.close()
        return rows
    return conn.execute(sql, params).fetchall()


def exec_sql(conn, sql: str, params=()):
    if is_pg(conn):
        cur = conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        cur.close()
    else:
        conn.execute(sql, params)



# ── first_value helper ────────────────────────────────────────────────
def first_value(rows, default=0):
    """Return the first scalar value from a query result for tuple/dict-like rows."""
    if not rows:
        return default

    row = rows[0]
    if isinstance(row, dict):
        return next(iter(row.values()), default)

    try:
        return row[0]
    except Exception:
        return default


def load_employees(conn, q: str = "", building: str = "All") -> list[dict]:
    return _load_employees_cached(_db_cache_key(), q, building)

