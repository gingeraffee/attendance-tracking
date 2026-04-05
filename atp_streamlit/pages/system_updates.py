"""System Updates page."""
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

def _build_full_backup_excel(conn) -> bytes:
    """Build an Excel workbook with Employees and Point History sheets."""
    import io
    buf = io.BytesIO()
    emp_df = pd.DataFrame([dict(r) for r in fetchall(conn,
        'SELECT employee_id, last_name, first_name, COALESCE("Location",\'\') AS "Location", '
        'start_date, point_total, last_point_date, rolloff_date, perfect_attendance, '
        'point_warning_date, is_active FROM employees ORDER BY last_name, first_name'
    )])
    hist_df = pd.DataFrame([dict(r) for r in fetchall(conn,
        'SELECT id, employee_id, point_date, points, reason, note, flag_code '
        'FROM points_history ORDER BY employee_id, point_date, id'
    )])
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        emp_df.to_excel(writer, sheet_name="Employees", index=False)
        hist_df.to_excel(writer, sheet_name="Point History", index=False)
    return buf.getvalue()


def system_updates_page(conn) -> None:
    page_heading(
        "System Updates",
        "Run automated maintenance jobs: 2-month roll-offs, perfect attendance advancement, and YTD roll-offs.",
    )

    if "maintenance_log" not in st.session_state:
        st.session_state["maintenance_log"] = []

    # ── Database Backup ──────────────────────────────────────────────────
    section_label("Database Backup")
    st.caption("Download a full snapshot of all employees and point history as an Excel file. "
               "Always download a backup before running bulk operations.")
    bk_col1, bk_col2 = st.columns([1, 2])
    with bk_col1:
        if st.button("Generate Backup", use_container_width=True, key="gen_backup"):
            with st.spinner("Building backup..."):
                st.session_state["_backup_bytes"] = _build_full_backup_excel(conn)
                st.session_state["_backup_downloaded"] = True
            st.toast("Backup ready for download.")
    with bk_col2:
        if st.session_state.get("_backup_bytes"):
            st.download_button(
                "Download Full Backup (Excel)",
                data=st.session_state["_backup_bytes"],
                file_name=f"atp_full_backup_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dl_backup",
            )

    divider()

    # ── Recalculate All ──────────────────────────────────────────────────
    section_label("Recalculate All Employee Totals")
    st.caption("Recomputes every employee's point total, roll-off date, and perfect attendance date "
               "from their full point history. Use this after fixing calculation bugs.")
    backup_done = st.session_state.get("_backup_downloaded", False)
    if not backup_done:
        st.markdown("<div class='warn-box'>You must generate a backup above before recalculating.</div>", unsafe_allow_html=True)
    recalc_confirm = st.checkbox("I confirm — recalculate all employee totals", disabled=not backup_done, key="recalc_confirm")
    if st.button("Recalculate All", disabled=not (backup_done and recalc_confirm), use_container_width=False, key="btn_recalc_all"):
        try:
            with st.spinner("Recalculating all employees..."):
                emp_rows = fetchall(conn, "SELECT employee_id FROM employees ORDER BY employee_id")
                count = 0
                with db.tx(conn):
                    for row in emp_rows:
                        services.recalculate_employee_dates(conn, int(row["employee_id"]))
                        count += 1
                conn.commit()
                clear_read_caches()
            st.success(f"Recalculated {count} employee(s). Point totals and dates are now recomputed from history.")
            st.toast(f"Recalculated {count} employee(s).")
        except Exception as exc:
            st.error(str(exc))

    divider()

    # ── Bulk Employee Override ─────────────────────────────────────────
    if "bulk_override_result" in st.session_state:
        result = st.session_state.pop("bulk_override_result")
        if result["errors"]:
            st.warning(
                f"Bulk override finished with issues. Updated {result['applied']} employee(s), "
                f"skipped {result['unchanged']} already-matching row(s), and hit {len(result['errors'])} error(s)."
            )
            for msg in result["errors"][:8]:
                st.write(f"- {msg}")
            if len(result["errors"]) > 8:
                st.caption(f"{len(result['errors']) - 8} additional apply error(s) not shown.")
        else:
            st.success(
                f"Bulk override complete. Updated {result['applied']} employee(s) and skipped "
                f"{result['unchanged']} row(s) that already matched your audit."
            )
            st.caption("The corrected point totals and date overrides are now saved in the tracker.")
    section_label("Bulk Employee Override")
    st.caption("Upload a CSV with corrected employee data. Required column: **Employee #**. "
               "Optional columns: **Point Total**, **2 Month Roll Off Date**, **Perfect Attendance Date**. "
               "Point adjustments are inserted as history entries; dates are set directly.")
    uploaded = st.file_uploader("Upload corrections CSV", type=["csv"], key="bulk_override_csv")
    current_upload_sig = None
    if uploaded is None:
        for key in (
            "bulk_override_upload_sig",
            "bulk_override_changes",
            "bulk_override_summary",
            "bulk_override_preview",
            "bulk_override_row_errors",
            "bulk_override_parse_error",
        ):
            st.session_state.pop(key, None)
    else:
        uploaded_bytes = uploaded.getvalue()
        current_upload_sig = f"{uploaded.name}:{len(uploaded_bytes)}:{hashlib.sha1(uploaded_bytes).hexdigest()}"
        if st.session_state.get("bulk_override_upload_sig") != current_upload_sig:
            for key in (
                "bulk_override_changes",
                "bulk_override_summary",
                "bulk_override_preview",
                "bulk_override_row_errors",
                "bulk_override_parse_error",
            ):
                st.session_state.pop(key, None)
            st.session_state["bulk_override_upload_sig"] = current_upload_sig
            st.session_state.pop("bulk_override_confirm", None)

            try:
                csv_df = _normalize_bulk_override_columns(pd.read_csv(BytesIO(uploaded_bytes)))
                if "Employee #" not in csv_df.columns:
                    st.session_state["bulk_override_parse_error"] = "CSV must contain an 'Employee #' column."
                else:
                    has_points = "Point Total" in csv_df.columns
                    has_rolloff = "2 Month Roll Off Date" in csv_df.columns
                    has_perfect = "Perfect Attendance Date" in csv_df.columns
                    if not (has_points or has_rolloff or has_perfect):
                        st.session_state["bulk_override_parse_error"] = (
                            "CSV must contain at least one of: 'Point Total', '2 Month Roll Off Date', "
                            "'Perfect Attendance Date'."
                        )
                    else:
                        changes = []
                        row_errors = []
                        total_rows = len(csv_df.index)
                        for _, row in csv_df.iterrows():
                            try:
                                eid = _parse_bulk_override_employee_id(row["Employee #"])
                            except ValueError as exc:
                                row_errors.append(f"Row {_ + 2}: {exc}")
                                continue

                            emp = repo.get_employee(conn, eid)
                            if not emp:
                                row_errors.append(f"Row {_ + 2}: Employee #{eid} was not found.")
                                continue
                            emp = dict(emp)
                            change = {
                                "Employee #": eid,
                                "Last Name": emp.get("last_name", ""),
                                "First Name": emp.get("first_name", ""),
                            }
                            changed = False

                            if has_points:
                                try:
                                    new_total = _parse_bulk_override_point_total(row["Point Total"])
                                except ValueError as exc:
                                    row_errors.append(f"Row {_ + 2}: {exc}")
                                    continue

                                stored_total = round(float(emp.get("point_total", 0) or 0), 1)
                                history_total = _get_history_point_total(conn, eid)
                                diff = round(new_total - history_total, 3)
                                change["Stored Points"] = stored_total
                                change["History Points"] = history_total
                                change["New Points"] = new_total
                                change["Pt Adjustment"] = round(diff, 1)
                                change["_update_points"] = (
                                    abs(new_total - history_total) >= 0.05
                                    or abs(stored_total - new_total) >= 0.05
                                )
                                if change["_update_points"]:
                                    changed = True

                            if has_rolloff:
                                try:
                                    new_ro = _parse_bulk_override_date(row["2 Month Roll Off Date"], "2 Month Roll Off Date")
                                except ValueError as exc:
                                    row_errors.append(f"Row {_ + 2}: {exc}")
                                    continue

                                cur_ro_raw = emp.get("rolloff_date")
                                cur_ro = date.fromisoformat(str(cur_ro_raw)) if cur_ro_raw else None
                                change["Current Roll-off"] = str(cur_ro) if cur_ro else ""
                                change["New Roll-off"] = str(new_ro) if new_ro else ""
                                change["_update_rolloff"] = new_ro != cur_ro
                                if new_ro != cur_ro:
                                    changed = True

                            if has_perfect:
                                try:
                                    new_pa = _parse_bulk_override_date(row["Perfect Attendance Date"], "Perfect Attendance Date")
                                except ValueError as exc:
                                    row_errors.append(f"Row {_ + 2}: {exc}")
                                    continue

                                cur_pa_raw = emp.get("perfect_attendance")
                                cur_pa = date.fromisoformat(str(cur_pa_raw)) if cur_pa_raw else None
                                change["Current Perfect Att."] = str(cur_pa) if cur_pa else ""
                                change["New Perfect Att."] = str(new_pa) if new_pa else ""
                                change["_update_perfect"] = new_pa != cur_pa
                                if new_pa != cur_pa:
                                    changed = True

                            if changed:
                                changes.append(change)

                        rejected_rows = len(row_errors)
                        update_rows = len(changes)
                        unchanged_rows = max(total_rows - rejected_rows - update_rows, 0)
                        st.session_state["bulk_override_row_errors"] = row_errors
                        st.session_state["bulk_override_summary"] = {
                            "total_rows": total_rows,
                            "update_rows": update_rows,
                            "unchanged_rows": unchanged_rows,
                            "rejected_rows": rejected_rows,
                        }
                        if changes:
                            chg_df = pd.DataFrame(changes).drop(
                                columns=["_update_points", "_update_rolloff", "_update_perfect"],
                                errors="ignore",
                            )
                            st.session_state["bulk_override_changes"] = changes
                            st.session_state["bulk_override_preview"] = chg_df.to_dict("records")
            except Exception as exc:
                st.session_state["bulk_override_parse_error"] = f"Error reading CSV: {exc}"

    parse_error = st.session_state.get("bulk_override_parse_error")
    summary = st.session_state.get("bulk_override_summary")
    staged_errors = st.session_state.get("bulk_override_row_errors", [])
    preview_rows = st.session_state.get("bulk_override_preview", [])

    if parse_error:
        st.error(parse_error)
    elif summary:
        sum_col1, sum_col2, sum_col3, sum_col4 = st.columns(4)
        sum_col1.metric("CSV Rows", summary["total_rows"])
        sum_col2.metric("Ready To Update", summary["update_rows"])
        sum_col3.metric("Already Matching", summary["unchanged_rows"])
        sum_col4.metric("Rejected", summary["rejected_rows"])

        if staged_errors:
            st.warning("Some rows were rejected. Fix those rows before applying this batch.")
            for msg in staged_errors[:12]:
                st.write(f"- {msg}")
            if len(staged_errors) > 12:
                st.caption(f"{len(staged_errors) - 12} additional row error(s) not shown.")
        elif not preview_rows:
            info_box("No changes needed — all values match.")
        else:
            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
            st.info(
                f"Confirmation ready: {summary['update_rows']} employee(s) will be updated. "
                f"{summary['unchanged_rows']} row(s) already match your audit."
            )

    # --- Apply step (outside file-upload block so button survives reruns) ---
    if "bulk_override_changes" in st.session_state:
        changes = st.session_state["bulk_override_changes"]
        summary = st.session_state.get("bulk_override_summary", {})
        st.caption(
            f"Apply {len(changes)} override(s). "
            f"{summary.get('unchanged_rows', 0)} row(s) already match and will be skipped."
        )
        bulk_confirm = st.checkbox("I confirm — apply these overrides", key="bulk_override_confirm")
        if st.button("Apply Bulk Overrides", disabled=not bulk_confirm, key="btn_bulk_override"):
            errors = []
            applied = 0
            for chg in changes:
                eid = int(chg["Employee #"])
                try:
                    _apply_bulk_employee_override(
                        conn,
                        employee_id=eid,
                        point_total=chg.get("New Points"),
                        update_point_total=bool(chg.get("_update_points")),
                        rolloff_date=(
                            date.fromisoformat(chg["New Roll-off"])
                            if chg.get("New Roll-off")
                            else None
                        ),
                        update_rolloff_date=bool(chg.get("_update_rolloff")),
                        perfect_attendance=(
                            date.fromisoformat(chg["New Perfect Att."])
                            if chg.get("New Perfect Att.")
                            else None
                        ),
                        update_perfect_attendance=bool(chg.get("_update_perfect")),
                        note="Bulk override — prior calculation correction",
                    )
                    applied += 1
                except Exception as exc:
                    errors.append(f"Employee {eid}: {exc}")
            conn.commit()
            clear_read_caches()
            del st.session_state["bulk_override_changes"]
            summary = st.session_state.pop("bulk_override_summary", {})
            st.session_state.pop("bulk_override_preview", None)
            st.session_state.pop("bulk_override_row_errors", None)
            st.session_state.pop("bulk_override_parse_error", None)
            st.session_state.pop("bulk_override_upload_sig", None)
            st.session_state.pop("bulk_override_confirm", None)
            st.session_state["bulk_override_result"] = {
                "applied": applied,
                "unchanged": summary.get("unchanged_rows", 0),
                "errors": errors,
            }
            st.rerun()

    divider()

    # ── Automated Jobs ───────────────────────────────────────────────────
    col_ctrl, col_results = st.columns([1, 2.2], gap="large")

    with col_ctrl:
        section_label("Job Controls")
        run_date = st.date_input("Run jobs through date", value=date.today())
        dry_run  = st.toggle("Dry run (preview only)", value=True)

        if dry_run:
            st.markdown("<div class='info-box' style='margin:.6rem 0'>Dry run — no data will be changed.</div>", unsafe_allow_html=True)
            ok = True
        else:
            st.markdown("<div class='warn-box' style='margin:.6rem 0'>Live mode — changes will be written to the database.</div>", unsafe_allow_html=True)
            ok = st.checkbox("I confirm — apply changes to the database")

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        btn_roll = st.button("Run 2-Month Roll-offs",      use_container_width=True, disabled=not ok)
        btn_perf = st.button("Advance Perfect Attendance", use_container_width=True, disabled=not ok)
        btn_ytd  = st.button("Apply YTD Roll-offs",        use_container_width=True, disabled=not ok)

        st.markdown(
            "<div style='margin-top:.9rem;font-size:.79rem;color:#6a8ab8'>"
            "<b style='color:#7eb3ff'>2-Month Roll-offs</b> — removes 1 pt per overdue period, "
            "advances the roll-off date.<br><br>"
            "<b style='color:#7eb3ff'>Perfect Attendance</b> — advances eligible milestone dates "
            "by one month per overdue period. No points are removed.<br><br>"
            "<b style='color:#7eb3ff'>YTD Roll-offs</b> — applies a rolling 12-month net point "
            "reduction. Does not move roll-off or perfect attendance anchors.</div>",
            unsafe_allow_html=True,
        )

    with col_results:
        if btn_roll and ok:
            try:
                with st.spinner("Running 2-month roll-offs..."):
                    rows = services.apply_2mo_rolloffs(conn, run_date=run_date, dry_run=dry_run)
                if not dry_run:
                    clear_read_caches()
                st.session_state["maintenance_log"].append({
                    "Time": datetime.now().strftime("%H:%M:%S"),
                    "Job": "2-Month Roll-offs",
                    "Dry Run": dry_run,
                    "Affected": len(rows),
                })
                if rows:
                    df = pd.DataFrame(rows)
                    st.success(f"{'Preview:' if dry_run else 'Applied:'} {len(rows)} employee(s) affected.")
                    st.toast(f"2-Month Roll-offs: {len(rows)} employee(s).")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.download_button("Download CSV", to_csv(df), file_name=f"rolloffs_{run_date}.csv", mime="text/csv", key="dl_roll")
                else:
                    info_box("No 2-month roll-offs are due as of the selected date.")
                    st.toast("No roll-offs due.")
            except Exception as exc:
                st.error(str(exc))

        if btn_perf and ok:
            try:
                with st.spinner("Advancing perfect attendance..."):
                    rows = services.advance_due_perfect_attendance_dates(conn, run_date=run_date, dry_run=dry_run)
                if not dry_run:
                    clear_read_caches()
                st.session_state["maintenance_log"].append({
                    "Time": datetime.now().strftime("%H:%M:%S"),
                    "Job": "Perfect Attendance",
                    "Dry Run": dry_run,
                    "Affected": len(rows),
                })
                if rows:
                    df = pd.DataFrame(rows)
                    st.success(f"{'Preview:' if dry_run else 'Applied:'} {len(rows)} employee(s) affected.")
                    st.toast(f"Perfect Attendance: {len(rows)} employee(s).")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.download_button("Download CSV", to_csv(df), file_name=f"perfect_att_{run_date}.csv", mime="text/csv", key="dl_perf")
                else:
                    info_box("No perfect attendance dates are due for advancement.")
                    st.toast("No perfect attendance dates due.")
            except Exception as exc:
                st.error(str(exc))

        if btn_ytd and ok:
            try:
                with st.spinner("Applying YTD roll-offs..."):
                    rows = services.apply_ytd_rolloffs(conn, run_date=run_date, dry_run=dry_run)
                if not dry_run:
                    clear_read_caches()
                st.session_state["maintenance_log"].append({
                    "Time": datetime.now().strftime("%H:%M:%S"),
                    "Job": "YTD Roll-offs",
                    "Dry Run": dry_run,
                    "Affected": len(rows),
                })
                if rows:
                    try:
                        df = pd.DataFrame(
                            [{"Employee ID": r[0], "Net Points": r[1], "Roll Date": r[2]} for r in rows]
                        )
                    except Exception:
                        df = pd.DataFrame(rows)
                    st.success(f"{'Preview:' if dry_run else 'Applied:'} {len(rows)} YTD entry(ies).")
                    st.toast(f"YTD Roll-offs: {len(rows)} entry(ies).")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.download_button("Download CSV", to_csv(df), file_name=f"ytd_rolloffs_{run_date}.csv", mime="text/csv", key="dl_ytd")
                else:
                    info_box("No YTD roll-offs are applicable for the selected date.")
                    st.toast("No YTD roll-offs applicable.")
            except Exception as exc:
                st.error(str(exc))

        if st.session_state["maintenance_log"]:
            divider()
            section_label("Session Run Log")
            st.dataframe(
                pd.DataFrame(st.session_state["maintenance_log"]),
                use_container_width=True,
                hide_index=True,
            )

