"""Manage Employees page."""
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



def manage_employees_page(conn) -> None:
    page_heading("Manage Employees", "Onboard new employees, update details, archive, or permanently delete records.")

    BLDG_OPTS = ["", *BUILDINGS]
    tab_add, tab_edit = st.tabs(["Add Employee", "Edit / Archive / Delete"])

    # ── Add ──────────────────────────────────────────────────────────────────
    with tab_add:
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        col_form, col_info = st.columns([1, 1], gap="large")

        with col_form:
            with st.form("add_employee", clear_on_submit=True):
                emp_id     = st.number_input("Employee #", min_value=1, step=1)
                first      = st.text_input("First Name")
                last       = st.text_input("Last Name")
                start_date = st.date_input("Hire / Start Date", value=date.today())
                location   = st.selectbox("Building", BLDG_OPTS)
                added      = st.form_submit_button("Add Employee", use_container_width=True)

            if added:
                if not first.strip() or not last.strip():
                    st.error("First and last name are required.")
                else:
                    try:
                        services.create_employee(
                            conn,
                            int(emp_id),
                            last.strip(),
                            first.strip(),
                            start_date,
                            location or None,
                        )
                        conn.commit()
                        clear_read_caches()
                        st.success(f"Employee #{int(emp_id)} — {last}, {first} added.")
                    except Exception as exc:
                        st.error(str(exc))

        with col_info:
            st.markdown("<div style='height:2.5rem'></div>", unsafe_allow_html=True)
            st.markdown(
                "<div class='info-box'><b>New employee checklist</b><br>"
                "&bull; Employee # must be unique across all locations<br>"
                "&bull; Building can be set now or updated later via the Edit tab<br>"
                "&bull; All policy dates are blank until the first point entry is posted</div>",
                unsafe_allow_html=True,
            )

    # ── Edit / Archive / Delete ───────────────────────────────────────────────
    with tab_edit:
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        all_rows = [dict(r) for r in repo.search_employees(conn, q="", active_only=False, limit=3000)]
        if not all_rows:
            info_box("No employees in the database yet.")
            return

        opts = [
            (
                int(r["employee_id"]),
                f"#{r['employee_id']} - {r['last_name']}, {r['first_name']}"
                + (" (inactive)" if not r.get("is_active", 1) else ""),
            )
            for r in all_rows
        ]
        sel = st.selectbox("Select employee", opts, format_func=lambda x: x[1], label_visibility="collapsed")
        emp = dict(repo.get_employee(conn, sel[0]))
        loc_val = emp.get("Location") or emp.get("location") or ""
        loc_idx = BLDG_OPTS.index(loc_val) if loc_val in BLDG_OPTS else 0
        start_raw = str(emp.get("start_date") or "")[:10]
        rolloff_raw = str(emp.get("rolloff_date") or "")[:10]
        perfect_raw = str(emp.get("perfect_attendance") or "")[:10]
        try:
            start_val = date.fromisoformat(start_raw) if start_raw else date.today()
        except ValueError:
            start_val = date.today()

        col_edit, col_del = st.columns([1, 1], gap="large")

        with col_edit:
            section_label("Edit Details")
            with st.form("edit_employee"):
                first_e = st.text_input("First Name", value=emp.get("first_name") or "")
                last_e  = st.text_input("Last Name",  value=emp.get("last_name") or "")
                start_e = st.date_input("Hire / Start Date", value=start_val)
                bldg_e  = st.selectbox("Building", BLDG_OPTS, index=loc_idx)
                act_e   = st.checkbox("Active", value=bool(emp.get("is_active", 1)))
                rolloff_e = st.text_input(
                    "2-Month Roll-off Date (MM/DD/YYYY)",
                    value=(datetime.strptime(rolloff_raw, "%Y-%m-%d").strftime("%m/%d/%Y") if rolloff_raw else ""),
                )
                perfect_e = st.text_input(
                    "Perfect Attendance Date (MM/DD/YYYY)",
                    value=(datetime.strptime(perfect_raw, "%Y-%m-%d").strftime("%m/%d/%Y") if perfect_raw else ""),
                )
                st.caption("Leave either date blank to clear it.")
                saved   = st.form_submit_button("Save Changes", use_container_width=True)

            if saved:
                try:
                    rolloff_clean = (rolloff_e or "").strip()
                    perfect_clean = (perfect_e or "").strip()
                    rolloff_new_iso = datetime.strptime(rolloff_clean, "%m/%d/%Y").date().isoformat() if rolloff_clean else None
                    perfect_new_iso = datetime.strptime(perfect_clean, "%m/%d/%Y").date().isoformat() if perfect_clean else None
                    manual_dates_changed = (
                        (rolloff_new_iso != (rolloff_raw or None))
                        or (perfect_new_iso != (perfect_raw or None))
                    )
                    exec_sql(
                        conn,
                        'UPDATE employees SET first_name=?, last_name=?, start_date=?, "Location"=?, is_active=?, rolloff_date=?, perfect_attendance=? WHERE employee_id=?',
                        (
                            first_e.strip(),
                            last_e.strip(),
                            start_e.isoformat(),
                            bldg_e or None,
                            1 if act_e else 0,
                            rolloff_new_iso,
                            perfect_new_iso,
                            sel[0],
                        ),
                    )
                    if (start_raw != start_e.isoformat()) and not manual_dates_changed:
                        exec_sql(conn, 'UPDATE employees SET perfect_attendance=NULL WHERE employee_id=?', (sel[0],))
                    if not manual_dates_changed:
                        services.recalculate_employee_dates(conn, sel[0])
                    conn.commit()
                    clear_read_caches()
                    st.success("Changes saved.")
                    st.toast("Employee changes saved.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

        with col_del:
            section_label("Danger Zone")
            st.markdown(
                "<div class='danger-box'>Permanently removes this employee "
                "<b>and all their point history</b>. This cannot be undone.</div>",
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
            confirmed = st.checkbox(f"I understand — permanently delete #{sel[0]}")
            if confirmed:
                if st.button("Delete Employee", key="del_emp"):
                    try:
                        services.delete_employee(conn, sel[0])
                        conn.commit()
                        clear_read_caches()
                        st.success(f"Employee #{sel[0]} deleted.")
                        st.toast(f"Employee #{sel[0]} deleted.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

