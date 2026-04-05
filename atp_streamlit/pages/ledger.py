"""Points Ledger page."""
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



def points_ledger_page(conn, building: str) -> None:
    page_heading("Points Ledger", "Record attendance transactions and maintain a complete audit trail.")

    notice = st.session_state.pop("ledger_notice", None)
    if notice:
        st.success(notice)

    employees = load_employees(conn, building=building)
    if not employees:
        warn_box("No active employees found for this building filter.")
        return

    opts = [
        (int(e["employee_id"]), f"#{e['employee_id']} - {e['last_name']}, {e['first_name']}")
        for e in employees
    ]

    prev_emp = st.session_state.get("ledger_emp_id")
    default_idx = 0
    if prev_emp is not None:
        for i, o in enumerate(opts):
            if o[0] == prev_emp:
                default_idx = i
                break

    selected = st.selectbox(
        "Employee",
        opts,
        index=default_idx,
        format_func=lambda x: x[1],
        key="ledger_emp_select",
    )
    emp_id = int(selected[0])
    st.session_state["ledger_emp_id"] = emp_id

    ledger_date_key = f"ledger_date_str_{emp_id}"
    ledger_points_key = f"ledger_points_{emp_id}"
    ledger_reason_key = f"ledger_reason_{emp_id}"
    ledger_note_key = f"ledger_note_{emp_id}"
    ledger_flag_key = f"ledger_flag_{emp_id}"

    def focus_ledger_date_field() -> None:
        components.html(
            """<script>
            const rootDoc = (window.parent && window.parent.document) ? window.parent.document : document;
            const selectors = [
              'input[aria-label="Date (MM/DD/YYYY)"]',
              'input[placeholder="MM/DD/YYYY"]',
              'div[data-testid="stTextInput"] input'
            ];
            const sel = () => {
              for (const s of selectors) {
                const el = rootDoc.querySelector(s);
                if (el && !el.disabled) return el;
              }
              return null;
            };
            const tryFocus = () => {
              const el = sel();
              if (!el) return false;
              el.focus({ preventScroll: true });
              if (typeof el.select === "function") el.select();
              return true;
            };
            let tries = 0;
            if (!tryFocus()) {
              const t = setInterval(() => {
                tries += 1;
                if (tryFocus() || tries > 40) clearInterval(t);
              }, 75);
            }
            </script>""",
            height=0,
        )

    def set_ledger_notice(message: str) -> None:
        st.session_state["ledger_notice"] = message

    def parse_mdy(value: str) -> date:
        return datetime.strptime(value.strip(), "%m/%d/%Y").date()

    def format_mdy(value: str | None) -> str:
        if not value:
            return date.today().strftime("%m/%d/%Y")
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime("%m/%d/%Y")

    prev_focus_emp = st.session_state.get("_focus_emp_id")
    if prev_focus_emp != emp_id:
        st.session_state["_focus_emp_id"] = emp_id
        focus_ledger_date_field()

    emp = dict(repo.get_employee(conn, emp_id))
    pts = float(emp.get("point_total") or 0)

    st.markdown(
        f"<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin:.55rem 0 1.2rem 0'>"
        f"<div class='card-sm'>"
        f"<div style='font-size:.67rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;"
        f"color:#6a8ab8;margin-bottom:.3rem'>Points</div>{pt_badge(pts)}</div>"
        f"<div class='card-sm'>"
        f"<div style='font-size:.67rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;"
        f"color:#6a8ab8;margin-bottom:.3rem'>Next Roll-off</div>"
        f"<div style='font-size:.9rem;font-weight:700;color:#d4e1f7'>{fmt_date(emp.get('rolloff_date'))}</div></div>"
        f"<div class='card-sm'>"
        f"<div style='font-size:.67rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;"
        f"color:#6a8ab8;margin-bottom:.3rem'>Perfect Att.</div>"
        f"<div style='font-size:.9rem;font-weight:700;color:#d4e1f7'>{fmt_date(emp.get('perfect_attendance'))}</div></div>"
        f"<div class='card-sm'>"
        f"<div style='font-size:.67rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;"
        f"color:#6a8ab8;margin-bottom:.3rem'>Last Entry</div>"
        f"<div style='font-size:.9rem;font-weight:700;color:#d4e1f7'>{fmt_date(emp.get('last_point_date'))}</div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    col_form, col_hist = st.columns([1, 2], gap="large")

    with col_form:
        section_label("New Transaction")
        with st.form("ledger_entry", clear_on_submit=False):
            date_str = st.text_input(
                "Date (MM/DD/YYYY)",
                value=date.today().strftime("%m/%d/%Y"),
                placeholder="MM/DD/YYYY",
                key=ledger_date_key,
            )

            points = st.selectbox(
                "Points",
                [0.5, 1.0, 1.5],
                index=0,
                key=ledger_points_key,
            )

            reason = st.selectbox(
                "Reason",
                REASON_OPTIONS,
                index=0,
                key=ledger_reason_key,
            )

            note = st.text_input("Note (optional)", key=ledger_note_key)
            flag_code = st.text_input("Flag code (optional)", key=ledger_flag_key)

            submit = st.form_submit_button("Add Point", use_container_width=True)

        if submit:
            try:
                p_date = parse_mdy(date_str)
            except Exception:
                st.error("Invalid date. Use MM/DD/YYYY (example: 03/02/2026).")
            else:
                if p_date > date.today():
                    st.error("Date cannot be in the future.")
                else:
                    try:
                        preview = services.preview_add_point(emp_id, p_date, float(points), reason, note)
                        services.add_point(conn, preview, flag_code=(flag_code or "").strip() or None)
                        clear_read_caches()
                        set_ledger_notice(f"Added {float(points):.1f} pts on {fmt_date(p_date)}.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

        section_label("Adjust Current Total")
        st.caption(
            "Set a corrected current balance when prior calculations were wrong. "
            "This adds a `Manual Adjustment` transaction so the audit trail stays intact."
        )
        with st.form(f"ledger_adjust_total_{emp_id}", clear_on_submit=False):
            adjust_total = st.number_input(
                "Corrected Point Total",
                min_value=0.0,
                step=0.5,
                value=pts,
                format="%.1f",
                key=f"ledger_adjust_total_value_{emp_id}",
            )
            adjust_note = st.text_input(
                "Adjustment Note",
                value="Manual correction - prior point total calculation error",
                key=f"ledger_adjust_total_note_{emp_id}",
            )
            apply_adjust_total = st.form_submit_button("Apply Total Adjustment", use_container_width=True)

        if apply_adjust_total:
            try:
                target_total = round(float(adjust_total or 0.0), 1)
                if abs(target_total - pts) < 0.001:
                    st.warning("Corrected total matches the employee's current total.")
                else:
                    _apply_bulk_employee_override(
                        conn,
                        employee_id=emp_id,
                        point_total=target_total,
                        update_point_total=True,
                        note=adjust_note,
                    )
                    clear_read_caches()
                    set_ledger_notice(
                        f"Adjusted employee #{emp_id} from {pts:.1f} to {target_total:.1f} points."
                    )
                    st.rerun()
            except Exception as exc:
                st.error(str(exc))

        section_label("Repair Totals")
        st.caption("Employee totals are calculated from transaction history. Recalculate after correcting a bad roll-off or manual entry.")
        repair_col1, repair_col2 = st.columns(2)
        with repair_col1:
            if st.button("Recalculate Employee", key=f"repair_emp_{emp_id}", use_container_width=True):
                try:
                    with db.tx(conn):
                        services.recalculate_employee_dates(conn, emp_id)
                    clear_read_caches()
                    set_ledger_notice(f"Recalculated point totals for employee #{emp_id}.")
                    st.toast(f"Recalculated employee #{emp_id}.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        with repair_col2:
            if st.button("Recalculate Everyone", key="repair_all_employees", use_container_width=True):
                try:
                    services.recalculate_all_employee_dates(conn)
                    clear_read_caches()
                    set_ledger_notice("Recalculated point totals for all employees.")
                    st.toast("All employees recalculated.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with col_hist:
        section_label("Transaction History (all events)")
        history_limit_key = f"ledger_history_limit_{emp_id}"
        current_history_limit = int(st.session_state.get(history_limit_key, LEDGER_HISTORY_DEFAULT_LIMIT))
        hist = [dict(r) for r in repo.get_points_history(conn, emp_id, limit=current_history_limit)]
        if hist:
            df_h = pd.DataFrame(hist)[["id", "point_date", "points", "reason", "note", "point_total"]]
            df_h["point_date"] = df_h["point_date"].apply(fmt_date)
            df_h["points"] = df_h["points"].apply(lambda v: f"{float(v or 0):.1f}")
            df_h["point_total"] = df_h["point_total"].apply(lambda v: f"{float(v or 0):.1f}")
            df_h.columns = ["ID", "Date", "Pts", "Reason", "Note", "Running Total"]
            st.dataframe(df_h.drop(columns=["ID"]), use_container_width=True, hide_index=True, height=430)

            if len(hist) >= current_history_limit and current_history_limit < LEDGER_HISTORY_FULL_LIMIT:
                if st.button("Load Full History", key=f"load_full_history_{emp_id}"):
                    st.session_state[history_limit_key] = LEDGER_HISTORY_FULL_LIMIT
                    st.toast("Loading full history...")
                    st.rerun()

            if st.button("Undo Last Entry", key="undo_last"):
                try:
                    services.delete_point_history_entry(conn, point_id=int(df_h.iloc[0]["ID"]), employee_id=emp_id)
                    clear_read_caches()
                    set_ledger_notice("Last entry removed.")
                    st.toast("Last entry removed.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

            section_label("Edit Transaction")
            entry_options = [
                (
                    int(row["id"]),
                    f"{fmt_date(row.get('point_date'))} | {float(row.get('points') or 0):+.1f} | {row.get('reason') or 'No reason'}",
                )
                for row in hist
            ]
            selected_entry = st.selectbox(
                "Select transaction",
                entry_options,
                format_func=lambda x: x[1],
                key=f"ledger_edit_entry_{emp_id}",
            )
            selected_point_id = int(selected_entry[0])
            selected_row = next(row for row in hist if int(row["id"]) == selected_point_id)

            with st.form(f"ledger_edit_form_{emp_id}_{selected_point_id}", clear_on_submit=False):
                edit_date_str = st.text_input(
                    "Date (MM/DD/YYYY)",
                    value=format_mdy(selected_row.get("point_date")),
                    key=f"ledger_edit_date_{selected_point_id}",
                )
                edit_points = st.number_input(
                    "Points",
                    value=float(selected_row.get("points") or 0.0),
                    step=0.5,
                    format="%.1f",
                    key=f"ledger_edit_points_{selected_point_id}",
                )
                edit_reason = st.text_input(
                    "Reason",
                    value=str(selected_row.get("reason") or ""),
                    key=f"ledger_edit_reason_{selected_point_id}",
                )
                edit_note = st.text_input(
                    "Note",
                    value=str(selected_row.get("note") or ""),
                    key=f"ledger_edit_note_{selected_point_id}",
                )
                edit_flag_code = st.text_input(
                    "Flag code",
                    value=str(selected_row.get("flag_code") or ""),
                    key=f"ledger_edit_flag_{selected_point_id}",
                )

                save_col, delete_col = st.columns(2)
                save_entry = save_col.form_submit_button("Save Entry", use_container_width=True)
                delete_entry = delete_col.form_submit_button("Delete Entry", use_container_width=True)

            st.caption(f"Running total after this entry: {float(selected_row.get('point_total') or 0):.1f} pts")

            if save_entry:
                try:
                    edit_date = parse_mdy(edit_date_str)
                except Exception:
                    st.error("Invalid date. Use MM/DD/YYYY (example: 03/02/2026).")
                else:
                    if edit_date > date.today():
                        st.error("Date cannot be in the future.")
                    else:
                        try:
                            services.update_point_history_entry(
                                conn,
                                point_id=selected_point_id,
                                employee_id=emp_id,
                                point_date=edit_date,
                                points=float(edit_points),
                                reason=edit_reason,
                                note=edit_note,
                                flag_code=(edit_flag_code or "").strip() or None,
                            )
                            clear_read_caches()
                            set_ledger_notice(f"Updated transaction #{selected_point_id}.")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

            if delete_entry:
                try:
                    services.delete_point_history_entry(conn, point_id=selected_point_id, employee_id=emp_id)
                    clear_read_caches()
                    set_ledger_notice(f"Deleted transaction #{selected_point_id}.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        else:
            info_box("No history entries for this employee yet.")

