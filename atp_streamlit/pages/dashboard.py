"""Dashboard page and employee spotlight."""
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



def get_employee_spotlight(conn, employee_id: int | None) -> dict | None:
    if not employee_id:
        return None

    if is_pg(conn):
        sql = '''
            SELECT e.employee_id,
                   e.first_name,
                   e.last_name,
                   COALESCE(e."Location", '') AS building,
                   COALESCE(e.point_total, 0.0) AS point_total,
                   (
                       SELECT MAX(ph2.point_date::date)
                         FROM points_history ph2
                        WHERE ph2.employee_id = e.employee_id
                          AND COALESCE(ph2.points, 0.0) > 0.0
                   )::text AS last_positive_point_date,
                   e.rolloff_date::text AS rolloff_date,
                   e.perfect_attendance::text AS perfect_attendance
              FROM employees e
             WHERE e.employee_id = %s
             LIMIT 1
        '''
        rows = fetchall(conn, sql, (employee_id,))
    else:
        sql = '''
            SELECT e.employee_id,
                   e.first_name,
                   e.last_name,
                   COALESCE(e."Location", '') AS building,
                   COALESCE(e.point_total, 0.0) AS point_total,
                   (
                       SELECT MAX(date(ph2.point_date))
                         FROM points_history ph2
                        WHERE ph2.employee_id = e.employee_id
                          AND COALESCE(ph2.points, 0.0) > 0.0
                   ) AS last_positive_point_date,
                   e.rolloff_date,
                   e.perfect_attendance
              FROM employees e
             WHERE e.employee_id = ?
             LIMIT 1
        '''
        rows = fetchall(conn, sql, (employee_id,))

    if not rows:
        return None
    return dict(rows[0])


def selected_employee_sidebar(conn, employee_id: int | None) -> None:
    emp = get_employee_spotlight(conn, employee_id)
    if not emp:
        return
    full_name = f"{emp.get('first_name') or ''} {emp.get('last_name') or ''}".strip() or "Unknown Employee"
    full_name_html = _html_inline(full_name)
    emp_id_html = _html_inline(emp.get("employee_id") or "�")
    building_html = _html_inline(emp.get("building") or "�")
    last_point_html = _html_inline(fmt_date(emp.get("last_positive_point_date")))
    roll_off_html = _html_inline(fmt_date(emp.get("rolloff_date")))
    perfect_attendance_html = _html_inline(fmt_date(emp.get("perfect_attendance")))
    st.markdown(
        "<div class='sidebar-employee-card'>"
        "<div class='sidebar-employee-title'>&#9673; Employee Spotlight</div>"
        f"<div class='sidebar-employee-name'>{full_name_html}</div>"
        "<div class='sidebar-employee-grid'>"
        f"<div class='sidebar-employee-item'><span class='label'>Emp #</span><span class='value'>{emp_id_html}</span></div>"
        f"<div class='sidebar-employee-item'><span class='label'>Building</span><span class='value'>{building_html}</span></div>"
        f"<div class='sidebar-employee-item full-width'><span class='label'>Point Total</span><span class='value highlight'>{float(emp.get('point_total') or 0):.1f} pts</span></div>"
        f"<div class='sidebar-employee-item'><span class='label'>Last Point</span><span class='value'>{last_point_html}</span></div>"
        f"<div class='sidebar-employee-item'><span class='label'>Roll Off</span><span class='value'>{roll_off_html}</span></div>"
        f"<div class='sidebar-employee-item full-width'><span class='label'>Perfect Attendance</span><span class='value'>{perfect_attendance_html}</span></div>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        """<style>
        .st-key-spotlight_add_point button {
            background: transparent !important;
            border: 1px solid rgba(0,200,240,.45) !important;
            color: rgba(0,200,240,.95) !important;
            font-size: .6rem !important;
            padding: .18rem .5rem !important;
            border-radius: 6px !important;
            font-family: 'SF Mono','Fira Code',monospace !important;
            letter-spacing: .1em !important;
            text-transform: uppercase !important;
            font-weight: 600 !important;
            margin-top: .4rem !important;
            transition: all .15s ease !important;
        }
        .st-key-spotlight_add_point button:hover {
            background: rgba(0,200,240,.10) !important;
            border-color: rgba(0,200,240,.9) !important;
            color: #00c8f0 !important;
            box-shadow: 0 0 10px rgba(0,200,240,.28) !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )
    if st.button("⊕  Add Point to Record", key="spotlight_add_point", use_container_width=True):
        st.session_state["ledger_emp_id"] = int(emp["employee_id"])
        st.session_state["_nav_to"] = "Points Ledger"
        st.rerun()


# ── Dashboard ─────────────────────────────────────────────────────────────────
def dashboard_page(conn, building: str) -> None:
    page_heading(
        '<span class="live-dot"></span>Active',
        "Track attendance momentum, risk thresholds, and next actions in one polished workspace.",
        allow_title_html=True,
    )

    _dash_status = st.empty()
    _dash_status.caption("Loading dashboard data...")

    today = date.today()
    in_30_days = today + timedelta(days=30)
    employees = load_employees(conn, building=building)
    emp_ids = [int(e["employee_id"]) for e in employees]

    if not emp_ids:
        _dash_status.empty()
        render_tech_hud(building)
        info_box("No employees found for this building filter.")
        return
    ph = ",".join(["?" if not is_pg(conn) else "%s"] * len(emp_ids))
    db_key = _db_cache_key()

    def _read_rows(sql: str, params: tuple) -> list[dict]:
        return _fetchall_cached(db_key, sql, tuple(params))

    def _scalar_n(sql: str, params: tuple) -> int:
        rows = _read_rows(sql, params)
        if not rows:
            return 0
        return int(rows[0].get("n") or 0)

    # ── HR Live Monitor data ──────────────────────────────────────────────────
    since_24h = (today - timedelta(days=1)).isoformat()
    since_7d = (today - timedelta(days=7)).isoformat()
    due_7d = (today + timedelta(days=7)).isoformat()
    if is_pg(conn):
        sql_points_since = f"""
            SELECT COUNT(*) AS n
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND (ph.point_date::date) >= (%s::date)
               AND COALESCE(ph.points, 0.0) > 0.0
        """
        sql_roll_due_7d = f"""
            SELECT COUNT(*) AS n
              FROM employees
             WHERE employee_id IN ({ph})
               AND rolloff_date IS NOT NULL
               AND COALESCE(point_total, 0.0) >= 0.5
               AND (rolloff_date::date) >= (%s::date)
               AND (rolloff_date::date) <= (%s::date)
        """
        sql_perf_due_7d = f"""
            SELECT COUNT(*) AS n
              FROM employees
             WHERE employee_id IN ({ph})
               AND perfect_attendance IS NOT NULL
               AND (perfect_attendance::date) >= (%s::date)
               AND (perfect_attendance::date) <= (%s::date)
        """

        points_24h = _scalar_n(sql_points_since, (*emp_ids, since_24h))
        points_7d = _scalar_n(sql_points_since, (*emp_ids, since_7d))
        rolloffs_due_7d = _scalar_n(sql_roll_due_7d, (*emp_ids, today.isoformat(), due_7d))
        perfect_due_7d = _scalar_n(sql_perf_due_7d, (*emp_ids, today.isoformat(), due_7d))

    else:
        sql_points_since = f"""
            SELECT COUNT(*) AS n
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND date(ph.point_date) >= date(?)
               AND COALESCE(ph.points, 0.0) > 0.0
        """
        sql_roll_due_7d = f"""
            SELECT COUNT(*) AS n
              FROM employees
             WHERE employee_id IN ({ph})
               AND rolloff_date IS NOT NULL
               AND COALESCE(point_total, 0.0) >= 0.5
               AND date(rolloff_date) >= date(?)
               AND date(rolloff_date) <= date(?)
        """
        sql_perf_due_7d = f"""
            SELECT COUNT(*) AS n
              FROM employees
             WHERE employee_id IN ({ph})
               AND perfect_attendance IS NOT NULL
               AND date(perfect_attendance) >= date(?)
               AND date(perfect_attendance) <= date(?)
        """

        points_24h = _scalar_n(sql_points_since, (*emp_ids, since_24h))
        points_7d = _scalar_n(sql_points_since, (*emp_ids, since_7d))
        rolloffs_due_7d = _scalar_n(sql_roll_due_7d, (*emp_ids, today.isoformat(), due_7d))
        perfect_due_7d = _scalar_n(sql_perf_due_7d, (*emp_ids, today.isoformat(), due_7d))

    if is_pg(conn):
        sql_emp_detail = f'''
            SELECT e.employee_id, e.last_name, e.first_name,
                   COALESCE(e."Location",'') AS building,
                   COALESCE(e.point_total, 0.0) AS point_total,
                   e.last_point_date, e.rolloff_date, e.perfect_attendance
              FROM employees e
              LEFT JOIN points_history ph ON ph.employee_id = e.employee_id
             WHERE e.employee_id IN ({ph})
             GROUP BY e.employee_id, e.last_name, e.first_name, e."Location",
                      e.last_point_date, e.rolloff_date, e.perfect_attendance
        '''
        sql_roll_due = f'''
            SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS building,
                   rolloff_date, COALESCE(point_total,0) AS point_total
              FROM employees
             WHERE employee_id IN ({ph})
               AND rolloff_date IS NOT NULL
               AND COALESCE(point_total, 0.0) >= 0.5
               AND (rolloff_date::date) >= (%s::date)
               AND (rolloff_date::date) <= (%s::date)
             ORDER BY (rolloff_date::date), lower(last_name), lower(first_name)
        '''
        sql_perf_due = f'''
            SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS building,
                   perfect_attendance, COALESCE(point_total,0) AS point_total
              FROM employees
             WHERE employee_id IN ({ph})
               AND perfect_attendance IS NOT NULL
               AND (perfect_attendance::date) >= (%s::date)
               AND (perfect_attendance::date) <= (%s::date)
             ORDER BY (perfect_attendance::date), lower(last_name), lower(first_name)
        '''
        sql_build_reasons = '''
            SELECT ph.reason, COUNT(*) AS n
              FROM points_history ph
              JOIN employees e ON e.employee_id = ph.employee_id
             WHERE (ph.point_date::date) >= (%s::date)
               AND COALESCE(ph.points, 0.0) > 0.0
               AND COALESCE(e."Location", '') = %s
               AND COALESCE(e.is_active, 1) = 1
               AND COALESCE(ph.reason, '') <> ''
             GROUP BY ph.reason
             ORDER BY n DESC, ph.reason
             LIMIT 1
        '''
        sql_active_emp_points = '''
            SELECT e.employee_id,
                   COALESCE(e."Location", '') AS building,
                   COALESCE(e.point_total, 0.0) AS point_total
              FROM employees e
              LEFT JOIN points_history ph ON ph.employee_id = e.employee_id
             WHERE COALESCE(e.is_active, 1) = 1
             GROUP BY e.employee_id, e."Location"
        '''
        sql_build_points_window = f'''
            SELECT COALESCE(e."Location", '') AS building,
                   ROUND(COALESCE(SUM(ph.points), 0.0)::numeric, 1)::float8 AS pts
              FROM points_history ph
              JOIN employees e ON e.employee_id = ph.employee_id
             WHERE ph.employee_id IN ({ph})
               AND (ph.point_date::date) >= (%s::date)
               AND (ph.point_date::date) < (%s::date)
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY COALESCE(e."Location", '')
        '''
        sql_insights_gt1 = f'''
            SELECT e.employee_id,
                   e.last_name,
                   e.first_name,
                   COALESCE(e."Location", '') AS building,
                   ROUND(COALESCE(SUM(ph.points), 0.0)::numeric, 1)::float8 AS points_30d,
                   MAX(ph.point_date::date)::text AS last_point_date,
                   COALESCE((
                       SELECT ph2.reason
                         FROM points_history ph2
                        WHERE ph2.employee_id = e.employee_id
                          AND (ph2.point_date::date) >= (%s::date)
                          AND EXTRACT(DOW FROM ph2.point_date::date) NOT IN (0, 6)
                          AND COALESCE(ph2.points, 0.0) > 0.0
                          AND COALESCE(ph2.reason, '') <> ''
                        GROUP BY ph2.reason
                        ORDER BY COUNT(*) DESC, MAX(ph2.point_date::date) DESC, ph2.reason
                        LIMIT 1
                   ), '�') AS top_reason
              FROM employees e
              JOIN points_history ph ON ph.employee_id = e.employee_id
             WHERE e.employee_id IN ({ph})
               AND (ph.point_date::date) >= (%s::date)
               AND EXTRACT(DOW FROM ph.point_date::date) NOT IN (0, 6)
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY e.employee_id, e.last_name, e.first_name, e."Location"
            HAVING COALESCE(SUM(ph.points), 0.0) > 1.0
             ORDER BY points_30d DESC, MAX(ph.point_date::date) DESC, lower(e.last_name), lower(e.first_name)
        '''
        sql_points_60d = f'''
            SELECT ph.employee_id,
                   ROUND(COALESCE(SUM(ph.points), 0.0)::numeric, 1)::float8 AS points_60d
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND (ph.point_date::date) >= (%s::date)
               AND EXTRACT(DOW FROM ph.point_date::date) NOT IN (0, 6)
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY ph.employee_id
        '''
        sql_trend_90d = f'''
            SELECT (ph.point_date::date)::text AS point_day,
                   ROUND(COALESCE(SUM(ph.points), 0.0)::numeric, 1)::float8 AS pts
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND (ph.point_date::date) >= (%s::date)
               AND EXTRACT(DOW FROM ph.point_date::date) NOT IN (0, 6)
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY (ph.point_date::date)
             ORDER BY (ph.point_date::date)
        '''
        sql_weekday_window = f'''
            WITH totals AS (
                SELECT EXTRACT(DOW FROM ph.point_date::date)::int AS dow,
                       ROUND(COALESCE(SUM(ph.points), 0.0)::numeric, 1)::float8 AS total_points,
                       COUNT(*) AS incidents
                  FROM points_history ph
                 WHERE ph.employee_id IN ({ph})
                   AND (ph.point_date::date) >= (%s::date)
                   AND (ph.point_date::date) < (%s::date)
                   AND COALESCE(ph.points, 0.0) > 0.0
                 GROUP BY EXTRACT(DOW FROM ph.point_date::date)
            ),
            emp_counts AS (
                SELECT d.dow,
                       COUNT(*) AS employees_pointed
                  FROM (
                        SELECT EXTRACT(DOW FROM ph.point_date::date)::int AS dow,
                               ph.employee_id,
                               SUM(COALESCE(ph.points, 0.0)) AS employee_points
                          FROM points_history ph
                         WHERE ph.employee_id IN ({ph})
                           AND (ph.point_date::date) >= (%s::date)
                           AND (ph.point_date::date) < (%s::date)
                           AND COALESCE(ph.points, 0.0) > 0.0
                         GROUP BY EXTRACT(DOW FROM ph.point_date::date), ph.employee_id
                        HAVING SUM(COALESCE(ph.points, 0.0)) >= 1.0
                  ) d
                 GROUP BY d.dow
            )
            SELECT t.dow,
                   t.total_points,
                   t.incidents,
                   COALESCE(e.employees_pointed, 0) AS employees_pointed
              FROM totals t
              LEFT JOIN emp_counts e ON e.dow = t.dow
        '''
        sql_weekday_reason = f'''
            SELECT ph.reason, COUNT(*) AS n
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND (ph.point_date::date) >= (%s::date)
               AND (ph.point_date::date) < (%s::date)
               AND EXTRACT(DOW FROM ph.point_date::date)::int = (%s)
               AND COALESCE(ph.points, 0.0) > 0.0
               AND COALESCE(ph.reason, '') <> ''
             GROUP BY ph.reason
             ORDER BY n DESC, ph.reason
             LIMIT 1
        '''
        sql_weekday_employees = f'''
            SELECT e.employee_id,
                   e.last_name || ', ' || e.first_name AS employee,
                   COALESCE(e."Location", '') AS building,
                   COUNT(*) AS incidents,
                   ROUND(COALESCE(SUM(ph.points), 0.0)::numeric, 1)::float8 AS total_points
              FROM points_history ph
              JOIN employees e ON e.employee_id = ph.employee_id
             WHERE ph.employee_id IN ({ph})
               AND (ph.point_date::date) >= (%s::date)
               AND (ph.point_date::date) < (%s::date)
               AND EXTRACT(DOW FROM ph.point_date::date)::int = (%s)
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY e.employee_id, e.last_name, e.first_name, e."Location"
             ORDER BY total_points DESC, lower(e.last_name), lower(e.first_name)
        '''
    else:
        sql_emp_detail = f'''
            SELECT e.employee_id, e.last_name, e.first_name,
                   COALESCE(e."Location",'') AS building,
                   COALESCE(e.point_total, 0.0) AS point_total,
                   e.last_point_date, e.rolloff_date, e.perfect_attendance
              FROM employees e
             WHERE e.employee_id IN ({ph})
        '''
        sql_roll_due = f'''
            SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS building,
                   rolloff_date, COALESCE(point_total,0) AS point_total
              FROM employees
             WHERE employee_id IN ({ph})
               AND rolloff_date IS NOT NULL
               AND COALESCE(point_total, 0.0) >= 0.5
               AND date(rolloff_date) >= date(?)
               AND date(rolloff_date) <= date(?)
             ORDER BY date(rolloff_date), lower(last_name), lower(first_name)
        '''
        sql_perf_due = f'''
            SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS building,
                   perfect_attendance, COALESCE(point_total,0) AS point_total
              FROM employees
             WHERE employee_id IN ({ph})
               AND perfect_attendance IS NOT NULL
               AND date(perfect_attendance) >= date(?)
               AND date(perfect_attendance) <= date(?)
             ORDER BY date(perfect_attendance), lower(last_name), lower(first_name)
        '''
        sql_build_reasons = '''
            SELECT ph.reason, COUNT(*) AS n
              FROM points_history ph
              JOIN employees e ON e.employee_id = ph.employee_id
             WHERE date(ph.point_date) >= date(?)
               AND COALESCE(ph.points, 0.0) > 0.0
               AND COALESCE(e."Location", '') = ?
               AND COALESCE(e.is_active, 1) = 1
               AND COALESCE(ph.reason, '') <> ''
             GROUP BY ph.reason
             ORDER BY n DESC, ph.reason
             LIMIT 1
        '''
        sql_active_emp_points = '''
            SELECT e.employee_id,
                   COALESCE(e."Location", '') AS building,
                   COALESCE(e.point_total, 0.0) AS point_total
              FROM employees e
             WHERE COALESCE(e.is_active, 1) = 1
             GROUP BY e.employee_id, e."Location"
        '''
        sql_build_points_window = f'''
            SELECT COALESCE(e."Location", '') AS building,
                   ROUND(COALESCE(SUM(ph.points), 0.0), 1) AS pts
              FROM points_history ph
              JOIN employees e ON e.employee_id = ph.employee_id
             WHERE ph.employee_id IN ({ph})
               AND date(ph.point_date) >= date(?)
               AND date(ph.point_date) < date(?)
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY COALESCE(e."Location", '')
        '''
        sql_insights_gt1 = f'''
            SELECT e.employee_id,
                   e.last_name,
                   e.first_name,
                   COALESCE(e."Location", '') AS building,
                   ROUND(COALESCE(SUM(ph.points), 0.0), 1) AS points_30d,
                   MAX(date(ph.point_date)) AS last_point_date,
                   COALESCE((
                       SELECT ph2.reason
                         FROM points_history ph2
                        WHERE ph2.employee_id = e.employee_id
                          AND date(ph2.point_date) >= date(?)
                          AND strftime('%w', ph2.point_date) NOT IN ('0', '6')
                          AND COALESCE(ph2.points, 0.0) > 0.0
                          AND COALESCE(ph2.reason, '') <> ''
                        GROUP BY ph2.reason
                        ORDER BY COUNT(*) DESC, MAX(date(ph2.point_date)) DESC, ph2.reason
                        LIMIT 1
                   ), '�') AS top_reason
              FROM employees e
              JOIN points_history ph ON ph.employee_id = e.employee_id
             WHERE e.employee_id IN ({ph})
               AND date(ph.point_date) >= date(?)
               AND strftime('%w', ph.point_date) NOT IN ('0', '6')
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY e.employee_id, e.last_name, e.first_name, e."Location"
            HAVING COALESCE(SUM(ph.points), 0.0) > 1.0
             ORDER BY points_30d DESC, MAX(date(ph.point_date)) DESC, lower(e.last_name), lower(e.first_name)
        '''
        sql_points_60d = f'''
            SELECT ph.employee_id,
                   ROUND(COALESCE(SUM(ph.points), 0.0), 1) AS points_60d
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND date(ph.point_date) >= date(?)
               AND strftime('%w', ph.point_date) NOT IN ('0', '6')
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY ph.employee_id
        '''
        sql_trend_90d = f'''
            SELECT date(ph.point_date) AS point_day,
                   ROUND(COALESCE(SUM(ph.points), 0.0), 1) AS pts
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND date(ph.point_date) >= date(?)
               AND strftime('%w', ph.point_date) NOT IN ('0', '6')
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY date(ph.point_date)
             ORDER BY date(ph.point_date)
        '''
        sql_weekday_window = f'''
            WITH totals AS (
                SELECT CAST(strftime('%w', ph.point_date) AS INTEGER) AS dow,
                       ROUND(COALESCE(SUM(ph.points), 0.0), 1) AS total_points,
                       COUNT(*) AS incidents
                  FROM points_history ph
                 WHERE ph.employee_id IN ({ph})
                   AND date(ph.point_date) >= date(?)
                   AND date(ph.point_date) < date(?)
                   AND COALESCE(ph.points, 0.0) > 0.0
                 GROUP BY CAST(strftime('%w', ph.point_date) AS INTEGER)
            ),
            emp_counts AS (
                SELECT d.dow,
                       COUNT(*) AS employees_pointed
                  FROM (
                        SELECT CAST(strftime('%w', ph.point_date) AS INTEGER) AS dow,
                               ph.employee_id,
                               SUM(COALESCE(ph.points, 0.0)) AS employee_points
                          FROM points_history ph
                         WHERE ph.employee_id IN ({ph})
                           AND date(ph.point_date) >= date(?)
                           AND date(ph.point_date) < date(?)
                           AND COALESCE(ph.points, 0.0) > 0.0
                         GROUP BY CAST(strftime('%w', ph.point_date) AS INTEGER), ph.employee_id
                        HAVING SUM(COALESCE(ph.points, 0.0)) >= 1.0
                  ) d
                 GROUP BY d.dow
            )
            SELECT t.dow,
                   t.total_points,
                   t.incidents,
                   COALESCE(e.employees_pointed, 0) AS employees_pointed
              FROM totals t
              LEFT JOIN emp_counts e ON e.dow = t.dow
        '''
        sql_weekday_reason = f'''
            SELECT ph.reason, COUNT(*) AS n
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND date(ph.point_date) >= date(?)
               AND date(ph.point_date) < date(?)
               AND CAST(strftime('%w', ph.point_date) AS INTEGER) = ?
               AND COALESCE(ph.points, 0.0) > 0.0
               AND COALESCE(ph.reason, '') <> ''
             GROUP BY ph.reason
             ORDER BY n DESC, ph.reason
             LIMIT 1
        '''
        sql_weekday_employees = f'''
            SELECT e.employee_id,
                   e.last_name || ', ' || e.first_name AS employee,
                   COALESCE(e."Location", '') AS building,
                   COUNT(*) AS incidents,
                   ROUND(COALESCE(SUM(ph.points), 0.0), 1) AS total_points
              FROM points_history ph
              JOIN employees e ON e.employee_id = ph.employee_id
             WHERE ph.employee_id IN ({ph})
               AND date(ph.point_date) >= date(?)
               AND date(ph.point_date) < date(?)
               AND CAST(strftime('%w', ph.point_date) AS INTEGER) = ?
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY e.employee_id, e.last_name, e.first_name, e."Location"
             ORDER BY total_points DESC, lower(e.last_name), lower(e.first_name)
        '''

    emp_detail_rows = _read_rows(sql_emp_detail, tuple(emp_ids))
    roll_due_rows = _read_rows(sql_roll_due, (*emp_ids, today.isoformat(), in_30_days.isoformat()))
    perf_due_rows = _read_rows(sql_perf_due, (*emp_ids, today.isoformat(), in_30_days.isoformat()))

    bucket_defs = {
        "gt1": lambda pts: pts > 1.0,
        "1-4": lambda pts: 1.0 <= pts <= 4.5,
        "5-6": lambda pts: 5.0 <= pts <= 6.5,
        "7": lambda pts: pts >= 7.0,
    }
    bucket_counts = {
        key: sum(1 for r in emp_detail_rows if fn(float(r.get("point_total") or 0)))
        for key, fn in bucket_defs.items()
    }

    _dash_status.empty()

    # ── Now that we have real data, fill the top-of-page widgets ─────────────
    at_risk_5plus = bucket_counts.get("5-6", 0) + bucket_counts.get("7", 0)
    total_active  = len(emp_detail_rows)

    render_tech_hud(
        building,
        at_risk_5plus=at_risk_5plus,
        total_employees=total_active,
    )

    active_bucket_label = "All Employees"
    _bucket_label_map = {
        "gt1": ">1.0 Point",
        "1-4": "1.0-4.5 Pts",
        "5-6": "5.0-6.5 Pts",
        "7": "7.0+ Pts",
    }
    if st.session_state.get("dashboard_bucket") in _bucket_label_map:
        active_bucket_label = _bucket_label_map[st.session_state["dashboard_bucket"]]

    st.markdown(
        f"""<div class='dashboard-hero'>
                <div class='dashboard-hero-grid'>
                    <div class='dashboard-hero-stat'><div class='k'>Active Employees</div><div class='v'>{total_active}</div></div>
                    <div class='dashboard-hero-stat'><div class='k'>At Risk (5+)</div><div class='v'>{at_risk_5plus}</div></div>
                    <div class='dashboard-hero-stat'><div class='k'>Rolloffs Due 7d</div><div class='v'>{rolloffs_due_7d}</div></div>
                    <div class='dashboard-hero-stat'><div class='k'>Perfect Due 7d</div><div class='v'>{perfect_due_7d}</div></div>
                </div>
                <div class='dashboard-filter-pill'>Active threshold view: {active_bucket_label}</div>
            </div>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """<style>
        .st-key-dashboard_bucket_all div[data-testid="stButton"],
        .st-key-dashboard_bucket_gt1 div[data-testid="stButton"],
        .st-key-dashboard_bucket_1-4 div[data-testid="stButton"],
        .st-key-dashboard_bucket_5-6 div[data-testid="stButton"],
        .st-key-dashboard_bucket_7 div[data-testid="stButton"] {
            margin-top: -92px !important;
            position: relative;
            z-index: 30;
        }
        .st-key-dashboard_bucket_all div[data-testid="stButton"] > button,
        .st-key-dashboard_bucket_gt1 div[data-testid="stButton"] > button,
        .st-key-dashboard_bucket_1-4 div[data-testid="stButton"] > button,
        .st-key-dashboard_bucket_5-6 div[data-testid="stButton"] > button,
        .st-key-dashboard_bucket_7 div[data-testid="stButton"] > button {
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            min-height: 92px !important;
            width: 100% !important;
            padding: 0 !important;
        }
        .st-key-dashboard_bucket_all div[data-testid="stButton"] > button p,
        .st-key-dashboard_bucket_gt1 div[data-testid="stButton"] > button p,
        .st-key-dashboard_bucket_1-4 div[data-testid="stButton"] > button p,
        .st-key-dashboard_bucket_5-6 div[data-testid="stButton"] > button p,
        .st-key-dashboard_bucket_7 div[data-testid="stButton"] > button p {
            opacity: 0 !important;
            margin: 0 !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    tile_cols = st.columns(5)
    tile_specs = [
        ("all", "All Employees"),
        ("gt1", ">1.0 Point"),
        ("1-4", "1.0-4.5 Pts"),
        ("5-6", "5.0-6.5 Pts"),
        ("7", "7.0+ Pts"),
    ]
    active_bucket = st.session_state.get("dashboard_bucket")

    for col, (key, label) in zip(tile_cols, tile_specs):
        selected = (active_bucket == key) if key != "all" else (active_bucket not in bucket_defs)
        accent, glow = {
            "all": ("#87a4c6", "rgba(135,164,198,.22)"),
            "gt1": ("#00d4ff", "rgba(0,212,255,.24)"),
            "1-4": ("#2da8e8", "rgba(45,168,232,.24)"),
            "5-6": ("#ff6a7f", "rgba(255,106,127,.30)"),
            "7": ("#ff304f", "rgba(255,48,79,.34)"),
        }.get(key, ("#87a4c6", "rgba(135,164,198,.22)"))
        card_border = "rgba(24,49,92,.22)" if not selected else accent
        card_shadow = f"0 0 0 2px {glow}, 0 10px 20px rgba(8,22,52,.22)" if selected else "0 6px 14px rgba(8,22,52,.18)"
        employees_count = len(emp_detail_rows) if key == "all" else bucket_counts[key]
        hint = "selected" if selected else "tap to filter"

        col.markdown(
            f"<div class='dashboard-threshold-card' style='border-color:{card_border};box-shadow:{card_shadow};'>"
            f"<div style='height:4px;border-radius:999px;background:{accent};margin:-.2rem 0 .55rem 0;'></div>"
            f"<div class='title' style='color:{accent}'>{label}</div>"
            f"<div class='meta'>"
            f"<span class='count'>{employees_count}</span>"
            f"<span class='hint' style='color:{accent};'>{hint}</span>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

        if col.button("filter", key=f"dashboard_bucket_{key}", use_container_width=True):
            if key == "all":
                st.session_state.pop("dashboard_bucket", None)
            else:
                st.session_state["dashboard_bucket"] = key
            st.toast(f"Filter applied: {label}")
            st.rerun()

    col_left, col_right = st.columns([1.6, 1], gap="large")

    with col_left:
        section_label("Employee Point Overview")
        bucket_key = st.session_state.get("dashboard_bucket")
        source_rows = list(emp_detail_rows)
        if bucket_key in bucket_defs:
            source_rows = [r for r in emp_detail_rows if bucket_defs[bucket_key](float(r.get("point_total") or 0))]

        source_rows = sorted(
            source_rows,
            key=lambda r: (
                -float(r.get("point_total") or 0),
                str(r.get("last_point_date") or ""),
            ),
        )

        if source_rows:
            df_emps = pd.DataFrame(
                [
                    {
                        "employee_id": int(r["employee_id"]),
                        "Employee #": str(r["employee_id"]),
                        "Name": f"{r['last_name']}, {r['first_name']}",
                        "Building": r.get("building") or "�",
                        "Point Total": f"{float(r.get('point_total') or 0):.1f}",
                        "Last Point Date": fmt_date(r.get("last_point_date")),
                    }
                    for r in source_rows
                ]
            )
            event = st.dataframe(
                df_emps[["Employee #", "Name", "Building", "Point Total", "Last Point Date"]],
                use_container_width=True,
                hide_index=True,
                height=575,
                key="dash_emp_above5_table",
                on_select="rerun",
                selection_mode="single-row",
            )
            selected_rows = (event.selection.get("rows") if event else []) or []
            if selected_rows:
                idx = int(selected_rows[0])
                if 0 <= idx < len(df_emps):
                    st.session_state["selected_employee_id"] = int(df_emps.iloc[idx]["employee_id"])

        else:
            info_box("No employees match the selected threshold.")


    with col_right:
        section_label("Roll Offs Due (Next 30 Days)")
        if roll_due_rows:
            df_roll = pd.DataFrame(
                [
                    {
                        "Employee #": str(r["employee_id"]),
                        "Name": f"{r['last_name']}, {r['first_name']}",
                        "Building": r.get("building") or "�",
                        "Rolloff Date": fmt_date(r.get("rolloff_date")),
                        "Current Points": f"{float(r.get('point_total') or 0):.1f}",
                    }
                    for r in roll_due_rows
                ]
            )
            st.dataframe(df_roll, use_container_width=True, hide_index=True, height=235)
        else:
            info_box("No roll-offs due in the next 30 days.")

        divider()
        section_label("Perfect Attendance Due (Next 30 Days)")
        if perf_due_rows:
            df_perf = pd.DataFrame(
                [
                    {
                        "Employee #": str(r["employee_id"]),
                        "Name": f"{r['last_name']}, {r['first_name']}",
                        "Building": r.get("building") or "�",
                        "Perfect Date": fmt_date(r.get("perfect_attendance")),
                        "Current Points": f"{float(r.get('point_total') or 0):.1f}",
                    }
                    for r in perf_due_rows
                ]
            )
            st.dataframe(df_perf, use_container_width=True, hide_index=True, height=235)
        else:
            info_box("No perfect attendance dates due in the next 30 days.")

    divider()
    section_label("Building Snapshot (Average Points per Employee)")

    # ── Consolidated building stats (1 query instead of 5) ──────────────────
    build_stats_rows = _read_rows(
        """SELECT COALESCE("Location", '') AS building,
                  COUNT(*) AS n,
                  AVG(COALESCE(point_total, 0.0)) AS avg_point_total
           FROM employees
          WHERE COALESCE(is_active,1)=1
          GROUP BY COALESCE("Location", '')""",
        (),
    )
    active_by_build = {b: 0 for b in BUILDINGS}
    avg_total_by_build = {b: 0.0 for b in BUILDINGS}
    for r in build_stats_rows:
        if r["building"] in active_by_build:
            active_by_build[r["building"]] = int(r["n"] or 0)
            avg_total_by_build[r["building"]] = float(r.get("avg_point_total") or 0.0)

    since_30 = (today - timedelta(days=30)).isoformat()
    since_60 = (today - timedelta(days=60)).isoformat()
    tomorrow = (today + timedelta(days=1)).isoformat()

    current_rows = _read_rows(sql_build_points_window, (*emp_ids, since_30, tomorrow))
    prior_rows = _read_rows(sql_build_points_window, (*emp_ids, since_60, since_30))
    current_points = {r.get("building") or "": float(r.get("pts") or 0.0) for r in current_rows}
    prior_points = {r.get("building") or "": float(r.get("pts") or 0.0) for r in prior_rows}

    # ── Consolidated top reason per building (1 query instead of 3) ───────
    if is_pg(conn):
        sql_all_build_reasons = '''
            SELECT sub.building, sub.reason
              FROM (
                SELECT COALESCE(e."Location", '') AS building,
                       ph.reason,
                       COUNT(*) AS n,
                       ROW_NUMBER() OVER (PARTITION BY COALESCE(e."Location", '') ORDER BY COUNT(*) DESC, ph.reason) AS rn
                  FROM points_history ph
                  JOIN employees e ON e.employee_id = ph.employee_id
                 WHERE (ph.point_date::date) >= (%s::date)
                   AND COALESCE(ph.points, 0.0) > 0.0
                   AND COALESCE(e.is_active, 1) = 1
                   AND COALESCE(ph.reason, '') <> ''
                 GROUP BY COALESCE(e."Location", ''), ph.reason
              ) sub
             WHERE sub.rn = 1
        '''
    else:
        sql_all_build_reasons = '''
            SELECT sub.building, sub.reason
              FROM (
                SELECT COALESCE(e."Location", '') AS building,
                       ph.reason,
                       COUNT(*) AS n
                  FROM points_history ph
                  JOIN employees e ON e.employee_id = ph.employee_id
                 WHERE date(ph.point_date) >= date(?)
                   AND COALESCE(ph.points, 0.0) > 0.0
                   AND COALESCE(e.is_active, 1) = 1
                   AND COALESCE(ph.reason, '') <> ''
                 GROUP BY COALESCE(e."Location", ''), ph.reason
              ) sub
             WHERE sub.n = (
                SELECT MAX(sub2.n)
                  FROM (
                    SELECT COALESCE(e2."Location", '') AS building,
                           ph2.reason,
                           COUNT(*) AS n
                      FROM points_history ph2
                      JOIN employees e2 ON e2.employee_id = ph2.employee_id
                     WHERE date(ph2.point_date) >= date(?)
                       AND COALESCE(ph2.points, 0.0) > 0.0
                       AND COALESCE(e2.is_active, 1) = 1
                       AND COALESCE(ph2.reason, '') <> ''
                     GROUP BY COALESCE(e2."Location", ''), ph2.reason
                  ) sub2
                 WHERE sub2.building = sub.building
             )
             GROUP BY sub.building
        '''
    reason_params = (since_30,) if is_pg(conn) else (since_30, since_30)
    all_reason_rows = _read_rows(sql_all_build_reasons, reason_params)
    reason_by_build = {r.get("building", ""): r.get("reason", "") for r in all_reason_rows}

    snap_rows = []
    for b in BUILDINGS:
        headcount = int(active_by_build.get(b) or 0)
        avg_point_total = float(avg_total_by_build.get(b) or 0.0)
        cur_total = float(current_points.get(b) or 0.0)
        prev_total = float(prior_points.get(b) or 0.0)
        cur_avg_30d = (cur_total / headcount) if headcount else 0.0
        prev_avg_30d = (prev_total / headcount) if headcount else 0.0
        if prev_avg_30d > 0:
            pct_change = ((cur_avg_30d - prev_avg_30d) / prev_avg_30d) * 100.0
            pct_txt = f"{pct_change:+.1f}%"
        else:
            pct_txt = "\u2014"
        most_common_reason = reason_by_build.get(b) or "\u2014"
        snap_rows.append(
            {
                "Building": b,
                "Active Employees": headcount,
                "Avg Point Total / Employee": f"{avg_point_total:.2f}",
                "% Change in Avg Points (30d)": pct_txt,
                "Most Common Reason (30d)": most_common_reason,
            }
        )

    st.dataframe(pd.DataFrame(snap_rows), use_container_width=True, hide_index=True)

    divider()
    section_label("Forecasting")

    st.markdown("#### Employees > 1.0 Point (Last 30 Days)")
    gt1_rows = _read_rows(sql_insights_gt1, (since_30, *emp_ids, since_30))
    if gt1_rows:
        df_gt1 = pd.DataFrame(
            [
                {
                    "Employee #": str(r["employee_id"]),
                    "Name": f"{r['last_name']}, {r['first_name']}",
                    "Building": r.get("building") or "�",
                    "Points (30d)": f"{float(r.get('points_30d') or 0.0):.1f}",
                    "Last Point Date": fmt_date(r.get("last_point_date")),
                    "Top Reason": (r.get("top_reason") or "�"),
                }
                for r in gt1_rows
            ]
        )
        st.dataframe(df_gt1.head(25), use_container_width=True, hide_index=True)
        if len(df_gt1) > 25:
            with st.expander(f"Show all ({len(df_gt1)})"):
                st.dataframe(df_gt1, use_container_width=True, hide_index=True)
    else:
        info_box("No employees over 1.0 points in the last 30 days.")

    st.markdown("#### Trending Risks  � On track to exceed 8 points")
    pts60_rows = _read_rows(sql_points_60d, (*emp_ids, since_60))
    points60_by_emp = {int(r.get("employee_id")): float(r.get("points_60d") or 0.0) for r in pts60_rows}
    weekdays_60 = max(len(pd.bdate_range(start=today - timedelta(days=60), end=today)), 1)
    weekdays_30 = len(pd.bdate_range(start=today + timedelta(days=1), end=today + timedelta(days=30)))
    risk_rows = []
    for r in emp_detail_rows:
        emp_id = int(r["employee_id"])
        current_points = float(r.get("point_total") or 0.0)
        points_60d = float(points60_by_emp.get(emp_id) or 0.0)
        projected_30d = (points_60d / weekdays_60) * weekdays_30
        projected_total = current_points + projected_30d
        if projected_total >= 8.0:
            risk_rows.append(
                {
                    "Employee #": str(emp_id),
                    "Name": f"{r['last_name']}, {r['first_name']}",
                    "Building": r.get("building") or "�",
                    "Current Points": f"{current_points:.1f}",
                    "Points (60d)": f"{points_60d:.1f}",
                    "Projected +30d": f"{projected_30d:.1f}",
                    "Projected Total": f"{projected_total:.1f}",
                    "Confidence Note": "Low data" if points_60d < 2.0 else "Based on last 60 days",
                    "_projected_total": projected_total,
                }
            )
    if risk_rows:
        df_risk = pd.DataFrame(risk_rows).sort_values(by="_projected_total", ascending=False).drop(columns=["_projected_total"])
        st.dataframe(df_risk, use_container_width=True, hide_index=True)
    else:
        info_box("No active employees currently trend to 8.0+ points in the next 30 days.")

    st.markdown("#### Absenteeism Trend (90 Days)")
    trend_rows = _read_rows(sql_trend_90d, (*emp_ids, (today - timedelta(days=90)).isoformat()))
    # Merge on plain string dates to avoid pandas datetime-resolution mismatches
    # (bdate_range may return datetime64[ns] while pd.to_datetime from SQL strings
    #  returns datetime64[us] in newer pandas, causing silent merge failures).
    all_day_strs = pd.bdate_range(start=today - timedelta(days=90), end=today).strftime("%Y-%m-%d").tolist()
    trend_df = pd.DataFrame({"point_day": all_day_strs, "Total Points": 0.0})
    if trend_rows:
        trend_points = pd.DataFrame(
            {
                "point_day": [str(r.get("point_day") or "")[:10] for r in trend_rows],
                "Total Points": [float(r.get("pts") or 0.0) for r in trend_rows],
            }
        )
        trend_df = trend_df.merge(trend_points, on="point_day", how="left", suffixes=("", "_q"))
        trend_df["Total Points"] = trend_df["Total Points_q"].fillna(trend_df["Total Points"])
        trend_df = trend_df.drop(columns=["Total Points_q"])
    trend_df["point_day"] = pd.to_datetime(trend_df["point_day"])
    trend_df = trend_df.rename(columns={"point_day": "Date"}).set_index("Date")
    st.line_chart(trend_df)

    st.markdown("#### Day-of-Week Trend")
    ctrl_col1, ctrl_col2 = st.columns([1.2, 1])
    with ctrl_col1:
        window_label = st.selectbox(
            "Window",
            ["Last 30 days", "Last 90 days", "Last 12 months"],
            index=1,
            key="dow_window",
        )
    with ctrl_col2:
        metric_choice = st.radio("Metric", ["Count", "Points", "Rate"], index=0, horizontal=True, key="dow_metric")

    window_days = {"Last 30 days": 30, "Last 90 days": 90, "Last 12 months": 365}[window_label]
    window_start = today - timedelta(days=window_days - 1)
    window_end = today + timedelta(days=1)
    prior_start = window_start - timedelta(days=window_days)
    prior_end = window_start

    current_rows = [
        dict(r)
        for r in _read_rows(sql_weekday_window, (*emp_ids, window_start.isoformat(), window_end.isoformat(), *emp_ids, window_start.isoformat(), window_end.isoformat()))
    ]
    prior_rows = [
        dict(r)
        for r in _read_rows(sql_weekday_window, (*emp_ids, prior_start.isoformat(), prior_end.isoformat(), *emp_ids, prior_start.isoformat(), prior_end.isoformat()))
    ]

    current_by_dow = {
        int(r.get("dow") or 0): {
            "incidents": int(r.get("incidents") or 0),
            "employees_pointed": int(r.get("employees_pointed") or 0),
            "points": float(r.get("total_points") or 0.0),
        }
        for r in current_rows
    }
    prior_by_dow = {
        int(r.get("dow") or 0): {
            "incidents": int(r.get("incidents") or 0),
            "employees_pointed": int(r.get("employees_pointed") or 0),
            "points": float(r.get("total_points") or 0.0),
        }
        for r in prior_rows
    }

    dow_order = [1, 2, 3, 4, 5]
    dow_labels = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}

    denominator_count = max(len(emp_ids), 1)
    if metric_choice == "Rate":
        st.caption("Rate uses approximate active-headcount denominator: incidents � active employees � 100.")

    def metric_value(stats: dict, metric: str) -> float:
        incidents = float(stats.get("incidents") or 0)
        employees_pointed = float(stats.get("employees_pointed") or 0)
        points = float(stats.get("points") or 0)
        if metric == "Count":
            return employees_pointed
        if metric == "Points":
            return points
        return (incidents / denominator_count) * 100.0

    # ── Fetch all weekday top-reasons in one query (instead of 5) ───────────
    if is_pg(conn):
        sql_weekday_reason_all = f'''
            SELECT sub.dow, sub.reason
              FROM (
                SELECT EXTRACT(DOW FROM ph.point_date::date)::int AS dow,
                       ph.reason,
                       COUNT(*) AS n,
                       ROW_NUMBER() OVER (
                           PARTITION BY EXTRACT(DOW FROM ph.point_date::date)::int
                           ORDER BY COUNT(*) DESC, ph.reason
                       ) AS rn
                  FROM points_history ph
                 WHERE ph.employee_id IN ({ph})
                   AND (ph.point_date::date) >= (%s::date)
                   AND (ph.point_date::date) < (%s::date)
                   AND COALESCE(ph.points, 0.0) > 0.0
                   AND COALESCE(ph.reason, '') <> ''
                 GROUP BY EXTRACT(DOW FROM ph.point_date::date), ph.reason
              ) sub
             WHERE sub.rn = 1
        '''
    else:
        sql_weekday_reason_all = f'''
            SELECT sub.dow, sub.reason
              FROM (
                SELECT CAST(strftime('%w', ph.point_date) AS INTEGER) AS dow,
                       ph.reason,
                       COUNT(*) AS n
                  FROM points_history ph
                 WHERE ph.employee_id IN ({ph})
                   AND date(ph.point_date) >= date(?)
                   AND date(ph.point_date) < date(?)
                   AND COALESCE(ph.points, 0.0) > 0.0
                   AND COALESCE(ph.reason, '') <> ''
                 GROUP BY CAST(strftime('%w', ph.point_date) AS INTEGER), ph.reason
              ) sub
             WHERE sub.n = (
                SELECT MAX(sub2.n)
                  FROM (
                    SELECT CAST(strftime('%w', ph2.point_date) AS INTEGER) AS dow2,
                           ph2.reason,
                           COUNT(*) AS n
                      FROM points_history ph2
                     WHERE ph2.employee_id IN ({ph})
                       AND date(ph2.point_date) >= date(?)
                       AND date(ph2.point_date) < date(?)
                       AND COALESCE(ph2.points, 0.0) > 0.0
                       AND COALESCE(ph2.reason, '') <> ''
                     GROUP BY CAST(strftime('%w', ph2.point_date) AS INTEGER), ph2.reason
                  ) sub2
                 WHERE sub2.dow2 = sub.dow
             )
             GROUP BY sub.dow
        '''
    if is_pg(conn):
        all_weekday_reason_rows = _read_rows(
            sql_weekday_reason_all,
            (*emp_ids, window_start.isoformat(), window_end.isoformat()),
        )
    else:
        all_weekday_reason_rows = _read_rows(
            sql_weekday_reason_all,
            (*emp_ids, window_start.isoformat(), window_end.isoformat(), *emp_ids, window_start.isoformat(), window_end.isoformat()),
        )
    top_reason_by_dow = {int(r.get("dow") or 0): r.get("reason", "") for r in all_weekday_reason_rows}

    table_rows = []
    metric_values = {}
    for dow in dow_order:
        stats = current_by_dow.get(dow, {"incidents": 0, "employees_pointed": 0, "points": 0.0})
        incidents = int(stats.get("incidents") or 0)
        employees_pointed = int(stats.get("employees_pointed") or 0)
        points = float(stats.get("points") or 0.0)
        selected_val = metric_value(stats, metric_choice)
        metric_values[dow] = selected_val

        top_reason_day = top_reason_by_dow.get(dow) or "\u2014"

        table_rows.append(
            {
                "Weekday": dow_labels[dow],
                "# of Employees Pointed": employees_pointed,
                "Total Points Issued": round(points, 1),
                "Top Reason": top_reason_day,
            }
        )

    dow_df = pd.DataFrame(table_rows)
    dow_event = st.dataframe(
        dow_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    selected_rows = dow_event.selection.rows
    if selected_rows:
        sel_idx = selected_rows[0]
        sel_dow = dow_order[sel_idx]
        sel_label = dow_labels[sel_dow]
        emp_rows = _read_rows(
            sql_weekday_employees,
            (*emp_ids, window_start.isoformat(), window_end.isoformat(), sel_dow),
        )
        if emp_rows:
            st.markdown(f"**Employees pointed on {sel_label}s** ({window_start.strftime('%b %d')} � {window_end.strftime('%b %d, %Y')})")
            emp_display = pd.DataFrame([
                {
                    "Employee": r["employee"],
                    "Building": r["building"],
                    "Incidents": int(r["incidents"]),
                    "Points": float(r["total_points"]),
                }
                for r in emp_rows
            ])
            st.dataframe(emp_display, use_container_width=True, hide_index=True)
        else:
            st.info(f"No employees pointed on {sel_label}s in this window.")

    worst_dow = max(dow_order, key=lambda d: metric_values.get(d, 0.0))
    worst_label = dow_labels[worst_dow]
    worst_value = metric_values.get(worst_dow, 0.0)
    if metric_choice == "Count":
        worst_value_txt = f"{int(round(worst_value))} employees pointed"
    elif metric_choice == "Points":
        worst_value_txt = f"{worst_value:.1f} points"
    else:
        worst_value_txt = f"{worst_value:.2f} incidents per 100 active"
    st.markdown(f"� Worst weekday ({metric_choice.lower()}): **{worst_label}** � **{worst_value_txt}**")

    delta_rows = []
    for dow in dow_order:
        cur_val = metric_value(current_by_dow.get(dow, {"incidents": 0, "employees_pointed": 0, "points": 0.0}), metric_choice)
        prev_val = metric_value(prior_by_dow.get(dow, {"incidents": 0, "employees_pointed": 0, "points": 0.0}), metric_choice)
        if prev_val > 0:
            pct = ((cur_val - prev_val) / prev_val) * 100.0
            pct_txt = f"{pct:+.1f}%"
        elif cur_val > 0:
            pct_txt = "new activity"
        else:
            pct_txt = "0.0%"
        delta_rows.append((dow, abs(cur_val - prev_val), pct_txt))

    if delta_rows:
        ch_dow, _, pct_txt = max(delta_rows, key=lambda x: x[1])
        st.markdown(f"� Biggest change vs prior matching window: **{dow_labels[ch_dow]}** � **{pct_txt}**")

    reason_rows = _read_rows(
        sql_weekday_reason,
        (*emp_ids, window_start.isoformat(), window_end.isoformat(), worst_dow),
    )
    top_reason = (reason_rows[0].get("reason") if reason_rows else None) or "�"
    if top_reason != "�":
        st.markdown(f"� Most common reason on {worst_label}: **{top_reason}**")

