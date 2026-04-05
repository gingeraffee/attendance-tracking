"""Corrective Action page."""
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



def corrective_action_page(conn, building: str) -> None:
    page_heading(
        "Corrective Action",
        "Employees at disciplinary point thresholds. Tap a row to log a corrective action date.",
    )

    today = date.today()
    employees = load_employees(conn, building=building)
    emp_ids = [int(e["employee_id"]) for e in employees]
    if not emp_ids:
        info_box("No employees found for this building filter.")
        return

    ph = ",".join(["%s" if is_pg(conn) else "?"] * len(emp_ids))

    if is_pg(conn):
        sql_ca = f"""
            SELECT e.employee_id,
                   e.last_name,
                   e.first_name,
                   COALESCE(e."Location", '') AS building,
                   COALESCE(e.point_total, 0.0) AS point_total,
                   (
                       SELECT MAX(ph3.point_date::date)::text
                         FROM points_history ph3
                        WHERE ph3.employee_id = e.employee_id
                          AND COALESCE(ph3.points, 0.0) > 0.0
                   ) AS last_point_date,
                   e.point_warning_date::text AS point_warning_date
              FROM employees e
             WHERE e.employee_id IN ({ph})
               AND COALESCE(e.is_active, 1) = 1
               AND COALESCE(e.point_total, 0.0) >= 5.0
             ORDER BY COALESCE(e.point_total, 0.0) DESC,
                      lower(e.last_name), lower(e.first_name)
        """
    else:
        sql_ca = f"""
            SELECT employee_id, last_name, first_name, building, point_total,
                   last_point_date, point_warning_date
              FROM (
                SELECT e.employee_id, e.last_name, e.first_name,
                       COALESCE(e."Location", '') AS building,
                       COALESCE(e.point_total, 0.0) AS point_total,
                       (SELECT MAX(date(ph3.point_date)) FROM points_history ph3
                         WHERE ph3.employee_id = e.employee_id
                           AND COALESCE(ph3.points,0.0) > 0.0
                       ) AS last_point_date,
                       e.point_warning_date
                  FROM employees e
                 WHERE e.employee_id IN ({ph})
                   AND COALESCE(e.is_active, 1) = 1
              ) sub
             WHERE point_total >= 5.0
             ORDER BY point_total DESC, lower(last_name), lower(first_name)
        """

    ca_rows = [dict(r) for r in fetchall(conn, sql_ca, tuple(emp_ids))]

    def parse_iso_date(value):
        if not value:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except Exception:
            return None

    def needs_new_warning(row: dict) -> bool:
        warning_dt = parse_iso_date(row.get("point_warning_date"))
        if warning_dt is None:
            return True
        last_positive_dt = parse_iso_date(row.get("last_point_date"))
        return last_positive_dt is not None and last_positive_dt > warning_dt

    needs_warning_rows = [row for row in ca_rows if needs_new_warning(row)]
    already_warned_rows = [row for row in ca_rows if not needs_new_warning(row)]

    # (key, label, range_str, predicate, hex, r, g, b)
    tiers = [
        ("termination",     "Termination",    "7.6 +",     lambda p: p > 7.5,         "#ff3b30", 255, 59,  48),
        ("written_warning", "Written Warning", "7.0 - 7.5", lambda p: 7.0 <= p <= 7.5, "#bf5af2", 191, 90, 242),
        ("verbal_warning",  "Verbal Warning",  "6.0 - 6.5", lambda p: 6.0 <= p <= 6.5, "#ffd60a", 255, 214, 10),
        ("verbal_coaching", "Verbal Coaching", "5.0 - 5.5", lambda p: 5.0 <= p <= 5.5, "#32ade6", 50, 173, 230),
    ]

    def tier_for(pts):
        for key, lbl, rng, fn, col, r, g, b in tiers:
            if fn(pts):
                return key, lbl, rng, col, r, g, b
        return "none", "-", "-", "#8e8e93", 142, 142, 147

    if not ca_rows:
        info_box("No active employees are currently at or above the 5.0 point threshold.")
        return

    # ── Shared CSS injected once ──────────────────────────────────────────────
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

.ca-wrap { font-family: -apple-system, 'Inter', BlinkMacSystemFont, sans-serif; }

/* Summary pills row */
.ca-pills {
  display: flex;
  gap: .55rem;
  flex-wrap: wrap;
  margin-bottom: 1.4rem;
}
.ca-pill {
  display: flex;
  align-items: center;
  gap: .45rem;
  padding: .38rem .85rem;
  border-radius: 999px;
  border: 1px solid;
  font-size: .72rem;
  font-weight: 600;
  letter-spacing: .02em;
  white-space: nowrap;
  cursor: default;
}
.ca-pill-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* Section label */
.ca-section {
  font-size: .68rem;
  font-weight: 600;
  letter-spacing: .10em;
  text-transform: uppercase;
  color: #636366;
  margin: 1.6rem 0 .55rem 0;
  padding-bottom: .35rem;
  border-bottom: 1px solid rgba(255,255,255,.06);
}

/* Employee row */
.ca-row {
  display: flex;
  align-items: center;
  padding: .72rem 1rem;
  border-radius: 12px;
  margin-bottom: .4rem;
  border: 1px solid rgba(255,255,255,.07);
  background: rgba(28,28,30,.55);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  transition: border-color .15s, background .15s;
  gap: .8rem;
}
.ca-row:hover {
  background: rgba(44,44,46,.70);
  border-color: rgba(255,255,255,.13);
}
.ca-row-active {
  border-color: rgba(255,255,255,.18) !important;
  background: rgba(44,44,46,.85) !important;
}

/* Left color strip */
.ca-strip {
  width: 3px;
  border-radius: 999px;
  align-self: stretch;
  min-height: 36px;
  flex-shrink: 0;
}

/* Name + meta block */
.ca-name {
  font-size: .93rem;
  font-weight: 600;
  color: #f2f2f7;
  line-height: 1.25;
}
.ca-meta {
  font-size: .72rem;
  color: #8e8e93;
  margin-top: .1rem;
}

/* Points badge */
.ca-pts {
  font-size: 1.15rem;
  font-weight: 700;
  line-height: 1;
  flex-shrink: 0;
  min-width: 2.8rem;
  text-align: right;
}

/* Date chips */
.ca-dates {
  display: flex;
  flex-direction: column;
  gap: .22rem;
  margin-left: auto;
  flex-shrink: 0;
  text-align: right;
}
.ca-date-chip {
  font-size: .67rem;
  padding: .15rem .55rem;
  border-radius: 999px;
  background: rgba(255,255,255,.05);
  color: #aeaeb2;
  white-space: nowrap;
}
.ca-date-chip span { color: #f2f2f7; font-weight: 500; }

/* Edit panel */
.ca-edit-panel {
  border-radius: 14px;
  padding: 1rem 1.2rem;
  margin-bottom: 1rem;
  border: 1px solid;
  background: rgba(28,28,30,.80);
  backdrop-filter: blur(20px);
}
.ca-edit-title {
  font-size: .68rem;
  font-weight: 600;
  letter-spacing: .09em;
  text-transform: uppercase;
  margin-bottom: .55rem;
}
.ca-edit-name {
  font-size: 1.05rem;
  font-weight: 600;
  color: #f2f2f7;
}
.ca-edit-sub {
  font-size: .78rem;
  color: #8e8e93;
  margin-top: .15rem;
  margin-bottom: .7rem;
}
</style>
<div class="ca-wrap">
""", unsafe_allow_html=True)

    # ── Summary pills ─────────────────────────────────────────────────────────
    pills_html = '<div class="ca-pills">'
    pills_html += (
        "<div class='ca-pill' style='color:#ff9f0a;border-color:rgba(255,159,10,.30);"
        "background:rgba(255,159,10,.09)'>"
        "<div class='ca-pill-dot' style='background:#ff9f0a'></div>"
        f"{len(needs_warning_rows)} need warning</div>"
    )
    pills_html += (
        "<div class='ca-pill' style='color:#8e8e93;border-color:rgba(142,142,147,.30);"
        "background:rgba(142,142,147,.08)'>"
        "<div class='ca-pill-dot' style='background:#8e8e93'></div>"
        f"{len(already_warned_rows)} already warned</div>"
    )
    for key, lbl, rng, fn, col, r, g, b in tiers:
        n = sum(1 for row in needs_warning_rows if fn(float(row.get("point_total") or 0)))
        if n == 0:
            continue
        pills_html += (
            f"<div class='ca-pill' style='color:{col};"
            f"border-color:rgba({r},{g},{b},.30);"
            f"background:rgba({r},{g},{b},.08)'>"
            f"<div class='ca-pill-dot' style='background:{col}'></div>"
            f"{n} {lbl}</div>"
        )
    pills_html += "</div>"
    st.markdown(pills_html, unsafe_allow_html=True)

    # ── Inline edit panel ─────────────────────────────────────────────────────
    if "ca_edit_id" not in st.session_state:
        st.session_state["ca_edit_id"] = None
    editing_id = st.session_state.get("ca_edit_id")

    if editing_id is not None:
        edit_row = next((r for r in ca_rows if int(r["employee_id"]) == editing_id), None)
        if edit_row:
            pts_e = float(edit_row.get("point_total") or 0)
            _, lbl_e, _, col_e, r_e, g_e, b_e = tier_for(pts_e)
            st.markdown(
                f"<div class='ca-edit-panel' style='border-color:rgba({r_e},{g_e},{b_e},.35)'>"
                f"<div class='ca-edit-title' style='color:{col_e}'>Edit warning date</div>"
                f"<div class='ca-edit-name'>{edit_row['last_name']}, {edit_row['first_name']}</div>"
                f"<div class='ca-edit-sub'>Emp #{edit_row['employee_id']} &nbsp;&middot;&nbsp; "
                f"{pts_e:.1f} pts &nbsp;&middot;&nbsp; {lbl_e}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            existing = edit_row.get("point_warning_date")
            try:
                default_val = date.fromisoformat(str(existing)[:10]) if existing else today
            except Exception:
                default_val = today
            ec1, ec2, ec3 = st.columns([2, 1, 1])
            with ec1:
                new_date = st.date_input("Warning date", value=default_val,
                                         key=f"ca_date_{editing_id}",
                                         label_visibility="collapsed")
            with ec2:
                if st.button("Save", key="ca_save", use_container_width=True):
                    try:
                        sym = "%s" if is_pg(conn) else "?"
                        exec_sql(conn,
                            f"UPDATE employees SET point_warning_date={sym} WHERE employee_id={sym}",
                            (new_date.isoformat(), editing_id))
                        conn.commit()
                        st.session_state["ca_edit_id"] = None
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            with ec3:
                if st.button("Cancel", key="ca_cancel", use_container_width=True):
                    st.session_state["ca_edit_id"] = None
                    st.rerun()

    # ── Tier sections ─────────────────────────────────────────────────────────
    def render_ca_group(group_label: str, group_key: str, rows: list[dict], empty_text: str) -> None:
        st.markdown(
            f"<div class='ca-section'>"
            f"<span>{group_label}</span>"
            f"<span style='color:#3a3a3c;margin:0 .4rem'>&middot;</span>"
            f"{len(rows)} {'employee' if len(rows) == 1 else 'employees'}"
            f"</div>",
            unsafe_allow_html=True,
        )
        if not rows:
            info_box(empty_text)
            return

        for key, label, rng, fn, col, r, g, b in tiers:
            tier_rows = [row for row in rows if fn(float(row.get("point_total") or 0))]
            if not tier_rows:
                continue

            st.markdown(
                f"<div class='ca-section'>"
                f"<span style='color:{col}'>{label}</span>"
                f"<span style='color:#3a3a3c;margin:0 .4rem'>&middot;</span>"
                f"<span>{rng} pts</span>"
                f"<span style='color:#3a3a3c;margin:0 .4rem'>&middot;</span>"
                f"{len(tier_rows)} {'employee' if len(tier_rows)==1 else 'employees'}"
                f"</div>",
                unsafe_allow_html=True,
            )

            for row in tier_rows:
                eid = int(row["employee_id"])
                pts = float(row.get("point_total") or 0)
                name = f"{row['last_name']}, {row['first_name']}"
                bldg = row.get("building") or "-"
                lpd = fmt_date(row.get("last_point_date"))
                pwd = fmt_date(row.get("point_warning_date"))
                is_ed = (editing_id == eid)

                active_cls = "ca-row-active" if is_ed else ""
                warn_color = col if pwd != "-" else "#48484a"
                warn_label = pwd if pwd != "-" else "Not logged"

                st.markdown(
                    f"<div class='ca-row {active_cls}'>"
                    f"<div class='ca-strip' style='background:{col}'></div>"
                    f"<div style='flex:1;min-width:0'>"
                    f"  <div class='ca-name'>{name}</div>"
                    f"  <div class='ca-meta'>#{eid} &nbsp;&middot;&nbsp; {bldg}</div>"
                    f"</div>"
                    f"<div class='ca-pts' style='color:{col}'>{pts:.1f}</div>"
                    f"<div class='ca-dates'>"
                    f"  <div class='ca-date-chip'>Last point &nbsp;<span>{lpd}</span></div>"
                    f"  <div class='ca-date-chip' style='color:{warn_color}'>"
                    f"    Warning &nbsp;<span style='color:{warn_color}'>{warn_label}</span></div>"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if st.button("Set date", key=f"ca_edit_{group_key}_{eid}", use_container_width=False):
                    st.session_state["ca_edit_id"] = eid
                    st.rerun()

    render_ca_group(
        "Needs Corrective Action",
        "needs",
        needs_warning_rows,
        "No employees currently need a new warning.",
    )
    with st.expander("Threshold Met - Warning Up To Date", expanded=False):
        render_ca_group(
            "Threshold Met - Warning Up To Date",
            "up_to_date",
            already_warned_rows,
            "No employees are currently in the already-warned group.",
        )

    st.markdown("</div>", unsafe_allow_html=True)
