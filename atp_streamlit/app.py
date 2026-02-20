import pandas as pd
import streamlit as st
from datetime import date
import sys
from pathlib import Path

# MUST be the first Streamlit command
st.set_page_config(page_title="Point System", layout="wide")

# --- Path setup / imports -----------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atp_core.db import connect, get_db_path
from atp_core.schema import ensure_schema
from atp_core.rules import REASON_OPTIONS
from atp_core import repo, services

# --- Helpers ------------------------------------------------------------------
def fmt_metric_date(value):
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    if value:
        return str(value)
    return "—"

def sidebar_logo():
    logo_path = APP_DIR / "assets" / "logo.png"
    if logo_path.is_file():
        st.sidebar.image(str(logo_path), use_container_width=True)

def get_conn():
    conn = connect()
    ensure_schema(conn)
    return conn

@st.cache_data(ttl=60)
def load_employees(active_only: bool):
    conn = get_conn()
    rows = repo.search_employees(conn, q="", active_only=active_only, limit=5000)
    return [dict(r) for r in rows]

# --- Styling ------------------------------------------------------------------
st.markdown(
    """
<style>
/* Layout polish */
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }

/* Sidebar slightly wider (more SharePoint-ish) */
section[data-testid="stSidebar"] { width: 320px !important; }

/* Softer card feel */
div[data-testid="stMetric"] {
  background: #F3F6FB;
  padding: 14px 14px 10px 14px;
  border-radius: 14px;
  border: 1px solid #E6EAF2;
}

/* Round buttons a bit */
button[kind="primary"], button[kind="secondary"] {
  border-radius: 12px !important;
}

/* Hide Streamlit footer */
footer { visibility: hidden; }
</style>
""",
    unsafe_allow_html=True,
)

# --- Connection ---------------------------------------------------------------
conn = get_conn()

# --- Header -------------------------------------------------------------------
st.title("Points Database")
st.caption("Internal HR Tool • Attendance Tracking")
st.divider()

# --- Sidebar ------------------------------------------------------------------
sidebar_logo()

st.sidebar.header("Employee Info")

st.sidebar.divider()
st.sidebar.subheader("Selected Employee")

selected_emp_id = st.session_state.get("selected_emp_id")

if selected_emp_id:
    emp_row = repo.get_employee(conn, int(selected_emp_id))
    emp = dict(emp_row) if emp_row else None

    if emp:
        st.sidebar.markdown(f"**{emp.get('last_name')}, {emp.get('first_name')}**")
        st.sidebar.caption(f"Employee ID: {emp.get('employee_id')}")
        st.sidebar.metric("Point Total", f"{float(emp.get('point_total') or 0.0):.1f}")
        st.sidebar.caption(f"Location: {emp.get('location', '—')}")
        st.sidebar.caption(f"Last Point Date: {fmt_metric_date(emp.get('last_point_date'))}")
        st.sidebar.caption(f"Next Roll-Off Date: {fmt_metric_date(emp.get('rolloff_date'))}")
        st.sidebar.caption(f"Perfect Attendance Date: {fmt_metric_date(emp.get('perfect_attendance'))}")
    else:
        st.sidebar.info("Employee not found.")
else:
    st.sidebar.caption("Select an employee from the Employees tab.")

# --- Tabs ---------------------------------------------------------------------
tab_emp, tab_add, tab_reports = st.tabs(["Employees", "Add Points", "Reports"])

# =============================================================================
# Employees tab
# =============================================================================
with tab_emp:
    st.subheader("Employee Lookup")
    q = st.text_input("Search by Employee #, last name, or first name", value="")
    rows = repo.search_employees(conn, q, active_only=active_only, limit=100)

    if not rows:
        st.info("No employees match that search.")
    else:
        rows_d = [dict(r) for r in rows]
        df = pd.DataFrame(rows_d).copy()

        # Hide is_active; show point_total
        if "is_active" in df.columns:
            df = df.drop(columns=["is_active"]).copy()

        # Format columns
        if "employee_id" in df.columns:
            df.loc[:, "employee_id"] = df["employee_id"].astype(str)

        if "point_total" in df.columns:
            df.loc[:, "point_total"] = (
                pd.to_numeric(df["point_total"], errors="coerce")
                .fillna(0)
                .round(1)
            )

        # --- Click-to-select table (show only the 4 columns you want) ---
        display = pd.DataFrame({
            "Employee #": df["employee_id"],
            "Last Name": df.get("last_name", ""),
            "First Name": df.get("first_name", ""),
            "Point Total": df.get("point_total", 0),
        }).copy()
        
        display.loc[:, "Employee #"] = display["Employee #"].astype(str)
        display.loc[:, "Point Total"] = pd.to_numeric(display["Point Total"], errors="coerce").fillna(0).round(1)
        
        event = st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun",
        )
        
        emp_id = None
        
        # If user clicked a row
        if event is not None and getattr(event, "selection", None) and event.selection.rows:
            idx = event.selection.rows[0]
            emp_id = int(display.iloc[idx]["Employee #"])
            st.session_state["selected_emp_id"] = emp_id

        # Fallback: dropdown (optional)
        with st.expander("Or select from a list"):
            options = [
                (
                    str(r["employee_id"]),
                    f'{r["employee_id"]} — {r["last_name"]}, {r["first_name"]} ({r.get("location","")})'
                )
                for r in rows_d
            ]
            
            # Default dropdown selection to current selected employee if possible
            selected_emp_id = st.session_state.get("selected_emp_id")
            default_index = 0
            if selected_emp_id is not None:
                s = str(selected_emp_id)
                for i, opt in enumerate(options):
                    if opt[0] == s:
                        default_index = i
                        break

            sel = st.selectbox(
                "Select an employee",
                options,
                format_func=lambda x: x[1],
                index=default_index,
                key="emp_select",
            )
            if sel:
                emp_id = int(sel[0])
                st.session_state["selected_emp_id"] = emp_id

        # If no click and no dropdown change, fall back to the pinned selection
        if emp_id is None:
            pinned = st.session_state.get("selected_emp_id")
            if pinned is not None:
                emp_id = int(pinned)

        # --- Details + history (run once) ---
        if emp_id:
            emp_row = repo.get_employee(conn, emp_id)
            emp = dict(emp_row) if emp_row else None

            if emp:
                st.markdown("### Employee Details")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Point Total", f'{float(emp.get("point_total") or 0.0):.1f}')
                c2.metric("Last Point Date", fmt_metric_date(emp.get("last_point_date")))
                c3.metric("Rolloff Date", fmt_metric_date(emp.get("rolloff_date")))
                c4.metric("Perfect Attendance", fmt_metric_date(emp.get("perfect_attendance")))
            else:
                st.warning("Employee record not found.")

            st.markdown("### Points History (latest 200)")
            hist = repo.get_points_history(conn, emp_id, limit=200)
            hdf = (
                pd.DataFrame([dict(r) for r in hist]).copy()
                if hist
                else pd.DataFrame(columns=["id", "point_date", "points", "reason", "note", "flag_code"])
            )
            if "points" in hdf.columns:
                hdf.loc[:, "points"] = pd.to_numeric(hdf["points"], errors="coerce").round(1)
            st.dataframe(hdf, use_container_width=True, hide_index=True)

# =============================================================================
# Add Points tab (defaults to the selected employee + keeps selection in sync)
# =============================================================================
with tab_add:
    st.subheader("Add Points / Entry")

    employees = load_employees(active_only)

    if not employees:
        st.info("No employees found.")
    else:
        options2 = [
            (str(e["employee_id"]), f'{e["employee_id"]} — {e["last_name"]}, {e["first_name"]} ({e.get("location","")})')
            for e in employees
        ]

        # Default selection based on sidebar-selected employee
        selected_emp_id = st.session_state.get("selected_emp_id")
        default_index = 0
        if selected_emp_id is not None:
            selected_str = str(selected_emp_id)
            for i, opt in enumerate(options2):
                if opt[0] == selected_str:
                    default_index = i
                    break

        sel2 = st.selectbox(
            "Select an employee",
            options2,
            format_func=lambda x: x[1],
            index=default_index,
            key="add_emp",
        )

        emp_id2 = int(sel2[0]) if sel2 else None
        if emp_id2:
            # Keep global selection in sync
            st.session_state["selected_emp_id"] = emp_id2

            with st.form("add_point_form", clear_on_submit=False):
                pdate = st.date_input("Point date", value=date.today())
                points = st.selectbox("Points", [0.5, 1.0, 1.5], index=0)
                reason = st.selectbox("Reason", REASON_OPTIONS, index=0)
                note = st.text_area("Note (recommended)")
                confirm = st.checkbox("I reviewed the preview and confirm this entry is correct.")
                submitted = st.form_submit_button("Preview & Save")

            if submitted:
                try:
                    preview = services.preview_add_point(emp_id2, pdate, float(points), reason, note)

                    emp_row = repo.get_employee(conn, emp_id2)
                    emp = dict(emp_row) if emp_row else {}
                    before_total = float(emp.get("point_total") or 0.0)
                    after_total = before_total + float(points)

                    st.markdown("### Preview")
                    st.write(
                        {
                            "employee_id": preview.employee_id,
                            "date": preview.point_date.isoformat(),
                            "points": preview.points,
                            "reason": preview.reason,
                            "note": preview.note,
                        }
                    )
                    st.info(f"Point Total: {before_total:.1f}  →  {after_total:.1f}")

                    if confirm:
                        services.add_point(conn, preview, flag_code="MANUAL")
                        st.success("Saved successfully.")
                        st.rerun()
                    else:
                        st.warning("Check the confirmation box to save.")
                except Exception as e:
                    st.error(str(e))

# =============================================================================
# Reports tab (single consolidated section)
# =============================================================================
with tab_reports:
    st.subheader("Reports")

    cA, cB = st.columns(2)

    with cA:
        st.markdown("### Rolloff — Next 2 Months")
        if st.button("Run Rolloff Report"):
            rows_r = repo.report_rolloff_next_2_months(conn)
            df_r = pd.DataFrame([dict(r) for r in rows_r])
            if not df_r.empty:
                df_r["employee_id"] = df_r["employee_id"].astype(str)
                df_r["point_total"] = pd.to_numeric(df_r["point_total"], errors="coerce").round(1)
            st.dataframe(df_r, use_container_width=True, hide_index=True)

            csv = df_r.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "rolloff_next_2_months.csv", "text/csv", key="dl_rolloff")

    with cB:
        st.markdown("### Perfect Attendance — Upcoming (Next 2 Months)")
        if st.button("Run Upcoming Perfect Attendance"):
            rows_p = repo.report_perfect_attendance_upcoming(conn)
            df_p = pd.DataFrame([dict(r) for r in rows_p])
            if not df_p.empty:
                df_p["employee_id"] = df_p["employee_id"].astype(str)
                df_p["point_total"] = pd.to_numeric(df_p["point_total"], errors="coerce").round(1)
            st.dataframe(df_p, use_container_width=True, hide_index=True)

            csv = df_p.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download CSV",
                csv,
                "perfect_attendance_upcoming.csv",
                "text/csv",
                key="dl_perfect_upcoming",
            )

    st.divider()

    st.markdown("### 30-Day Point History (BambooHR Import)")
    if st.button("Run 30-Day Point History"):
        rows_30 = repo.report_points_last_30_days(conn)
        df_30 = pd.DataFrame([dict(r) for r in rows_30])
        if not df_30.empty:
            df_30["employee_id"] = df_30["employee_id"].astype(str)
            df_30["points"] = pd.to_numeric(df_30["points"], errors="coerce").round(1)
        st.dataframe(df_30, use_container_width=True, hide_index=True)

        csv = df_30.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "points_last_30_days.csv", "text/csv", key="dl_30_day")

    st.divider()

    st.markdown("### Full-Year Perfect Attendance")
    year = st.number_input(
        "Calendar year for Full-Year Perfect Attendance",
        min_value=2000,
        max_value=2100,
        value=date.today().year - 1,
        step=1,
        key="full_year_pa_year",
    )
    if st.button("Run Full-Year Perfect Attendance"):
        rows_y = repo.report_full_year_perfect_attendance(conn, int(year))
        df_y = pd.DataFrame([dict(r) for r in rows_y])
        if not df_y.empty:
            df_y["employee_id"] = df_y["employee_id"].astype(str)
        st.dataframe(df_y, use_container_width=True, hide_index=True)

        csv = df_y.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"perfect_attendance_full_year_{int(year)}.csv",
            mime="text/csv",
            key="dl_full_year",
        )

    st.divider()
    st.markdown("### Monthly YTD Roll-Off (Writes to Database)")

    run_dt = st.date_input("Run date (rolloff uses the 1st of this month)", value=date.today(), key="roll_run_dt")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Preview YTD Roll-Off"):
            items = services.apply_ytd_rolloffs(conn, run_date=run_dt, dry_run=True)
            df = pd.DataFrame(items, columns=["employee_id", "points_to_rolloff", "roll_date", "month_label"])
            if not df.empty:
                df = df.copy()
                df.loc[:, "employee_id"] = df["employee_id"].astype(str)
                df["points_to_rolloff"] = pd.to_numeric(df["points_to_rolloff"], errors="coerce").round(1)
            st.dataframe(df, use_container_width=True, hide_index=True)

    with col2:
        confirm_apply = st.checkbox("I understand this will write roll-off entries to the database.", key="roll_confirm")
        if st.button("APPLY YTD Roll-Off (Commit)") and confirm_apply:
            items = services.apply_ytd_rolloffs(conn, run_date=run_dt, dry_run=False)
            df = pd.DataFrame(items, columns=["employee_id", "points_rolled", "roll_date", "month_label"])
            if not df.empty:
                df = df.copy()
                df.loc[:, "employee_id"] = df["employee_id"].astype(str)
                df["points_rolled"] = pd.to_numeric(df["points_rolled"], errors="coerce").round(1)
            st.success(f"Applied roll-offs for {len(items)} employees.")
            st.dataframe(df, use_container_width=True, hide_index=True)
