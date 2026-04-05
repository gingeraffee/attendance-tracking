"""Exports & Forecasts page."""
from __future__ import annotations

import html
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import atp_core.db as db
from atp_core import repo, services
from atp_core.rules import REASON_OPTIONS

from atp_streamlit.constants import (
    BUILDINGS,
    DASHBOARD_CACHE_TTL_SECONDS,
    EMPLOYEE_CACHE_TTL_SECONDS,
    EXPORT_LABELS,
    LEDGER_HISTORY_DEFAULT_LIMIT,
    LEDGER_HISTORY_FULL_LIMIT,
)
from atp_streamlit.shared.db import (
    _db_cache_key,
    _fetchall_cached,
    _get_cached_conn,
    _load_employees_cached,
    clear_read_caches,
    exec_sql,
    fetchall,
    first_value,
    get_conn,
    is_pg,
    load_employees,
    _apply_bulk_employee_override,
    _get_history_point_total,
    _normalize_bulk_override_columns,
    _parse_bulk_override_employee_id,
    _parse_bulk_override_point_total,
    _parse_bulk_override_date,
)
from atp_streamlit.shared.formatting import (
    days_badge,
    days_until,
    divider,
    fmt_date,
    info_box,
    page_heading,
    pt_badge,
    section_header,
    section_label,
    to_csv,
    warn_box,
)
from atp_streamlit.shared.hud import render_hr_live_monitor, render_tech_hud


import hashlib

EXPORT_LABELS = {
    "employee audit":             "Employee Audit",
    "30-day point history":        "30-Day Point History",
    "upcoming 2-month roll-offs":  "Upcoming 2-Month Roll-offs",
    "upcoming perfect attendance": "Upcoming Perfect Attendance",
    "pending ytd roll-offs":       "Pending YTD Roll-offs",
    "applied ytd roll-off history": "Applied YTD Roll-off History",
}


def run_export_query(conn, export_type: str, building: str, start_date: date, end_date: date) -> pd.DataFrame:
    pg = is_pg(conn)

    if export_type == "employee audit":
        if pg:
            sql = """SELECT employee_id   AS "Employee #",
                            last_name     AS "Last Name",
                            first_name    AS "First Name",
                            COALESCE(point_total, 0.0) AS "Point Total",
                            rolloff_date  AS "2 Month Roll Off Date",
                            perfect_attendance AS "Perfect Attendance Date"
                       FROM employees
                      WHERE is_active = 1"""
        else:
            sql = """SELECT employee_id   AS "Employee #",
                            last_name     AS "Last Name",
                            first_name    AS "First Name",
                            COALESCE(point_total, 0.0) AS "Point Total",
                            rolloff_date  AS "2 Month Roll Off Date",
                            perfect_attendance AS "Perfect Attendance Date"
                       FROM employees
                      WHERE is_active = 1"""
        params = []
        if building != "All":
            sql += ' AND COALESCE("Location",\'\') = ?'
            params.append(building)
        sql += " ORDER BY last_name, first_name"
        df = pd.DataFrame([dict(r) for r in fetchall(conn, sql, tuple(params))])
        return df

    elif export_type == "30-day point history":
        if pg:
            sql = """
                SELECT e.employee_id AS "Employee #",
                       e.last_name AS "Last Name",
                       e.first_name AS "First Name",
                       COALESCE(e."Location", '') AS "Location",
                       ph.id AS "_History ID",
                       ph.point_date AS "Point Date",
                       ph.points AS "Point",
                       ph.reason AS "Reason",
                       COALESCE(ph.note, '') AS "Note",
                       COALESCE(ph.flag_code, '') AS "Flag Code"
                  FROM points_history ph
                  JOIN employees e ON e.employee_id = ph.employee_id
            """
        else:
            sql = """
                SELECT e.employee_id AS "Employee #",
                       e.last_name AS "Last Name",
                       e.first_name AS "First Name",
                       COALESCE(e."Location", '') AS "Location",
                       ph.id AS "_History ID",
                       ph.point_date AS "Point Date",
                       ph.points AS "Point",
                       ph.reason AS "Reason",
                       COALESCE(ph.note, '') AS "Note",
                       COALESCE(ph.flag_code, '') AS "Flag Code"
                  FROM points_history ph
                  JOIN employees e ON e.employee_id = ph.employee_id
            """
        params = []
        if building != "All":
            sql += " WHERE COALESCE(e.\"Location\", '') = ?"
            params.append(building)
        if pg:
            sql += ' ORDER BY "Employee #", (ph.point_date::date), "_History ID"'
        else:
            sql += ' ORDER BY "Employee #", date(ph.point_date), "_History ID"'

        rows = [dict(r) for r in fetchall(conn, sql, tuple(params))]
        history_by_employee: dict[int, list[dict]] = {}
        export_rows: list[dict] = []
        start_iso = start_date.isoformat()
        end_iso = end_date.isoformat()

        for row in rows:
            employee_id = int(row["Employee #"])
            history_row = {
                "id": row.get("_History ID"),
                "point_date": row.get("Point Date"),
                "points": row.get("Point"),
                "reason": row.get("Reason"),
                "note": row.get("Note"),
                "flag_code": row.get("Flag Code"),
                "_export_row": row,
            }
            history_by_employee.setdefault(employee_id, []).append(history_row)

        for employee_history in history_by_employee.values():
            computed_history = repo.with_running_point_totals(employee_history)
            for history_row in computed_history:
                point_day = str(history_row.get("point_date") or "")[:10]
                row = dict(history_row["_export_row"])
                row["Point Total"] = round(float(history_row.get("point_total") or 0.0), 1)
                row.pop("_History ID", None)
                if start_iso <= point_day <= end_iso:
                    export_rows.append(row)

        df = pd.DataFrame(export_rows)
        if not df.empty:
            if "Point" in df.columns:
                df = df.astype({"Point": "object"})
                df.loc[:, "Point"] = pd.to_numeric(df["Point"], errors="coerce").map(
                    lambda v: f"{v:.1f}" if pd.notna(v) else ""
                )
            if "Point Total" in df.columns:
                df = df.astype({"Point Total": "object"})
                df.loc[:, "Point Total"] = pd.to_numeric(df["Point Total"], errors="coerce").map(
                    lambda v: f"{v:.1f}" if pd.notna(v) else ""
                )
        return df

    elif export_type == "upcoming 2-month roll-offs":
        if pg:
            sql = """SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS location,
                            point_total, rolloff_date
                       FROM employees WHERE rolloff_date IS NOT NULL
                         AND COALESCE(point_total, 0.0) >= 0.5
                         AND (rolloff_date::date) BETWEEN (%s::date) AND (%s::date)"""
        else:
            sql = """SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS location,
                            point_total, rolloff_date
                       FROM employees WHERE rolloff_date IS NOT NULL
                         AND COALESCE(point_total, 0.0) >= 0.5
                         AND date(rolloff_date) BETWEEN date(?) AND date(?)"""
        params = [start_date.isoformat(), end_date.isoformat()]

    elif export_type == "upcoming perfect attendance":
        if pg:
            sql = """SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS location,
                            point_total, perfect_attendance
                       FROM employees WHERE perfect_attendance IS NOT NULL
                         AND (perfect_attendance::date) BETWEEN (%s::date) AND (%s::date)"""
        else:
            sql = """SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS location,
                            point_total, perfect_attendance
                       FROM employees WHERE perfect_attendance IS NOT NULL
                         AND date(perfect_attendance) BETWEEN date(?) AND date(?)"""
        params = [start_date.isoformat(), end_date.isoformat()]

    elif export_type == "pending ytd roll-offs":
        # Show pending YTD roll-offs for the current month (not yet applied)
        pending = services.preview_ytd_rolloffs(conn, run_date=date.today(), exclude_applied=True)
        rows_out = []
        for employee_id, net_points, roll_date, label in pending:
            emp = repo.get_employee(conn, int(employee_id))
            if not emp:
                continue
            emp = dict(emp)
            loc = (emp.get("Location") or "")
            if building != "All" and loc != building:
                continue
            current_total = round(float(emp.get("point_total", 0) or 0), 1)
            if current_total <= 0.0:
                continue
            rows_out.append({
                "Employee ID": int(employee_id),
                "First Name": emp.get("first_name", ""),
                "Last Name": emp.get("last_name", ""),
                "Point Total": round(float(emp.get("point_total", 0) or 0), 1),
                "Points": round(float(net_points), 1),
                "Point Date": roll_date.isoformat(),
                "Note": "YTD Roll Off",
                "Notes": "",
            })
        if rows_out:
            return pd.DataFrame(rows_out)
        return pd.DataFrame(columns=["Employee ID", "First Name", "Last Name", "Point Total", "Points", "Point Date", "Note", "Notes"])

    else:  # applied ytd roll-off history
        year_start = date(date.today().year, 1, 1)
        if pg:
            sql = """SELECT e.employee_id AS "Employee ID",
                            e.first_name  AS "First Name",
                            e.last_name   AS "Last Name",
                            COALESCE(e.point_total, 0.0) AS "Point Total",
                            p.points      AS "Points",
                            p.point_date  AS "Point Date",
                            'YTD Roll Off' AS "Note",
                            COALESCE(p.note,'') AS "Notes"
                       FROM points_history p JOIN employees e ON e.employee_id=p.employee_id
                      WHERE p.reason='YTD Roll-Off' AND p.flag_code='AUTO'
                        AND (p.point_date::date) >= (%s::date)"""
        else:
            sql = """SELECT e.employee_id AS "Employee ID",
                            e.first_name  AS "First Name",
                            e.last_name   AS "Last Name",
                            COALESCE(e.point_total, 0.0) AS "Point Total",
                            p.points      AS "Points",
                            p.point_date  AS "Point Date",
                            'YTD Roll Off' AS "Note",
                            COALESCE(p.note,'') AS "Notes"
                       FROM points_history p JOIN employees e ON e.employee_id=p.employee_id
                      WHERE p.reason='YTD Roll-Off' AND p.flag_code='AUTO'
                        AND date(p.point_date) >= date(?)"""
        params = [year_start.isoformat()]

    if building != "All":
        e_ref = 'e."Location"' if " JOIN employees e" in sql else '"Location"'
        sql += f" AND COALESCE({e_ref},'') = ?"
        params.append(building)

    sql += " ORDER BY e.last_name, e.first_name" if export_type == "applied ytd roll-off history" else " ORDER BY last_name, first_name"
    df = pd.DataFrame([dict(r) for r in fetchall(conn, sql, tuple(params))])

    if export_type == "30-day point history" and not df.empty:
        if "Point" in df.columns:
            df["Point"] = pd.to_numeric(df["Point"], errors="coerce").map(
                lambda v: f"{v:.1f}" if pd.notna(v) else ""
            )
        if "Point Total" in df.columns:
            df["Point Total"] = pd.to_numeric(df["Point Total"], errors="coerce").map(
                lambda v: f"{v:.1f}" if pd.notna(v) else ""
            )

    return df


def exports_page(conn, building: str) -> None:
    page_heading(
        "Exports & Forecasts",
        "Generate and download operational reports for roll-offs, perfect attendance, and point history.",
    )

    col_ctrl, col_data = st.columns([1, 2.8], gap="large")

    with col_ctrl:
        section_label("Report Settings")
        export_type = st.radio(
            "Report type",
            list(EXPORT_LABELS.keys()),
            format_func=lambda k: EXPORT_LABELS[k],
            key="export_type",
            label_visibility="collapsed",
        )
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        start_date = st.date_input("From", value=date.today() - timedelta(days=30))
        end_date   = st.date_input("To",   value=date.today() + timedelta(days=60))
        run = st.button("Run Report", use_container_width=True)

    with col_data:
        if run:
            with st.spinner("Generating report..."):
                df = run_export_query(conn, export_type, building, start_date, end_date)
            st.session_state["last_export"] = (export_type, df)
            st.toast("Report ready.")

        if "last_export" in st.session_state:
            label, df = st.session_state["last_export"]
            section_label(EXPORT_LABELS.get(label, label))
            if df.empty:
                info_box("No records found for the selected date range and building filter.")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True, height=500)
                st.download_button(
                    "Download CSV",
                    data=to_csv(df),
                    file_name=f"atp_{label.replace(' ', '_')}_{date.today()}.csv",
                    mime="text/csv",
                )
        else:
            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
            info_box("Choose a report type and date range, then click <b>Run Report</b>.")
