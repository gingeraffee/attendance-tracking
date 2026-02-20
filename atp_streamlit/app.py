import pandas as pd
import streamlit as st
from datetime import date
import sys
from pathlib import Path
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

# MUST be the first Streamlit command
st.set_page_config(
    page_title="Point System",
    page_icon="📅",
    layout="wide",
)

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
    if value is None or value == "":
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%m/%d/%Y")
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(value, fmt).strftime("%m/%d/%Y")
            except ValueError:
                pass
        return value  # fallback: show whatever it is
    return str(value)

def sidebar_logo():
    logo_path = APP_DIR / "assets" / "logo.png"
    if logo_path.is_file():
        st.sidebar.image(str(logo_path), use_container_width=True)

def get_conn():
    conn = connect()
    ensure_schema(conn)
    return conn

def load_employees():
    conn = get_conn()
    rows = repo.search_employees(conn, q="", limit=150)
    return [dict(r) for r in rows]

def build_point_history_pdf(emp: dict, history_rows: list[dict]) -> bytes:
    """
    Returns PDF bytes for an employee's complete point history.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    left = 0.75 * inch
    top = height - 0.75 * inch
    y = top

    # Header
    c.setFont("Helvetica-Bold", 14)
    c.drawString(left, y, "Attendance Point History")
    y -= 0.28 * inch

    c.setFont("Helvetica", 10)
    name = f"{emp.get('last_name','')}, {emp.get('first_name','')}".strip(", ")
    c.drawString(left, y, f"Employee: {name}")
    y -= 0.18 * inch
    c.drawString(left, y, f"Employee ID: {emp.get('employee_id','')}")
    y -= 0.18 * inch
    c.drawString(left, y, f"Location: {emp.get('location','—') or '—'}    Department: {emp.get('department','—') or '—'}")
    y -= 0.18 * inch
    c.drawString(left, y, f"Generated: {date.today().strftime('%m/%d/%Y')}")
    y -= 0.30 * inch

    # Summary line (optional)
    total = float(emp.get("point_total") or 0.0)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, y, f"Current Point Total: {total:.1f}")
    y -= 0.25 * inch

    # Table header
    c.setFont("Helvetica-Bold", 9)
    c.drawString(left, y, "Date")
    c.drawString(left + 1.0*inch, y, "Points")
    c.drawString(left + 1.7*inch, y, "Reason")
    c.drawString(left + 3.7*inch, y, "Note")
    y -= 0.12 * inch
    c.line(left, y, width - left, y)
    y -= 0.15 * inch

    c.setFont("Helvetica", 9)

    def new_page():
        nonlocal y
        c.showPage()
        y = top
        c.setFont("Helvetica-Bold", 9)
        c.drawString(left, y, "Date")
        c.drawString(left + 1.0*inch, y, "Points")
        c.drawString(left + 1.7*inch, y, "Reason")
        c.drawString(left + 3.7*inch, y, "Note")
        y -= 0.12 * inch
        c.line(left, y, width - left, y)
        y -= 0.15 * inch
        c.setFont("Helvetica", 9)

    # Rows
    for r in history_rows:
        if y < 0.9 * inch:
            new_page()

        # Date
        d = r.get("point_date")
        if hasattr(d, "strftime"):
            d_str = d.strftime("%m/%d/%Y")
        else:
            d_str = str(d or "")

        pts = r.get("points", "")
        reason = str(r.get("reason", "") or "")
        note = str(r.get("note", "") or "")

        c.drawString(left, y, d_str)
        c.drawString(left + 1.0*inch, y, str(pts))
        c.drawString(left + 1.7*inch, y, reason[:35])

        # Wrap note a bit
        note_max = 60
        note_line = note[:note_max]
        c.drawString(left + 3.7*inch, y, note_line)

        y -= 0.18 * inch

        # If note is longer, write continuation line(s)
        remaining = note[note_max:]
        while remaining:
            if y < 0.9 * inch:
                new_page()
            cont = remaining[:note_max]
            c.drawString(left + 3.7*inch, y, cont)
            remaining = remaining[note_max:]
            y -= 0.18 * inch

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()

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
    rows = repo.search_employees(conn, q, limit=1000)

    if not rows:
        st.info("No employees match that search.")
    else:
        rows_d = [dict(r) for r in rows]
        needs_totals = ("point_total" not in rows_d[0]) or all((r.get("point_total") in (None, "")) for r in rows_d)
        if needs_totals:
            for r in rows_d:
                emp_row = repo.get_employee(conn, int(r["employee_id"]))
                emp = dict(emp_row) if emp_row else {}
                r["point_total"] = emp.get("point_total")
        df = pd.DataFrame(rows_d).copy()

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

    employees = load_employees()

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

    # ------------------------------------------------------------
    # 1) 30-Day Point History (CSV) — WITH running total
    # ------------------------------------------------------------
    st.markdown("### 30-Day Point History (CSV)")

    st.caption("Exports every point event in the last 30 days, including a running total per employee.")

    if st.button("Generate 30-Day Point History CSV", key="btn_30day"):
        rows_30 = repo.report_points_last_30_days(conn)
        df_30 = pd.DataFrame([dict(r) for r in rows_30])

        if df_30.empty:
            st.info("No point events found in the last 30 days.")
        else:
            # Normalize column names we expect
            # (adjust if your repo returns slightly different names)
            rename_map = {
                "employee_id": "Employee #",
                "first_name": "First Name",
                "last_name": "Last Name",
                "point_date": "Point Date",
                "points": "Point",
                "reason": "Reason",
                "note": "Note",
                "flag_code": "Flag Code",
                "point_total": "Point Total",  # current total if provided
            }
            for k, v in rename_map.items():
                if k in df_30.columns:
                    df_30 = df_30.rename(columns={k: v})

            # Ensure required columns exist (create blanks if missing)
            required = ["Employee #", "First Name", "Last Name", "Point Date", "Point", "Reason", "Note", "Point Total", "Flag Code"]
            for col in required:
                if col not in df_30.columns:
                    df_30[col] = ""

            # Types
            df_30["Employee #"] = df_30["Employee #"].astype(str)
            df_30["Point"] = pd.to_numeric(df_30["Point"], errors="coerce").fillna(0).round(1)

            # If Point Total isn't provided by the query, hydrate from employee table (safe, but more queries)
            if df_30["Point Total"].isna().all() or (df_30["Point Total"] == "").all():
                emp_ids = df_30["Employee #"].unique().tolist()
                totals = {}
                for eid in emp_ids:
                    emp_row = repo.get_employee(conn, int(eid))
                    emp = dict(emp_row) if emp_row else {}
                    totals[eid] = float(emp.get("point_total") or 0.0)
                df_30["Point Total"] = df_30["Employee #"].map(totals).astype(float).round(1)
            else:
                df_30["Point Total"] = pd.to_numeric(df_30["Point Total"], errors="coerce").fillna(0).round(1)

            # Running total per employee (chronological)
            # Start_total = current_total - sum(points in last 30 days)  (assumes all changes are represented as events)
            df_30["Point Date"] = pd.to_datetime(df_30["Point Date"], errors="coerce")
            df_30 = df_30.sort_values(["Employee #", "Point Date"], ascending=[True, True]).copy()

            sums = df_30.groupby("Employee #")["Point"].sum()
            current = df_30.groupby("Employee #")["Point Total"].first()  # same for every row after map/normalize
            start_total = (current - sums).to_dict()

            df_30["Running Total"] = (
                df_30.groupby("Employee #")["Point"].cumsum()
                + df_30["Employee #"].map(start_total)
            ).round(1)

            # Final column order (include running total)
            out_cols = ["Employee #", "First Name", "Last Name", "Point Date", "Point", "Reason", "Note", "Running Total", "Point Total", "Flag Code"]
            df_out = df_30[out_cols].copy()

            # Display + download
            st.dataframe(df_out, use_container_width=True, hide_index=True)
            csv = df_out.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "points_last_30_days_running_total.csv", "text/csv", key="dl_30day")

    st.divider()

    # ------------------------------------------------------------
    # 2) Preview reports (NO DB CHANGES)
    # ------------------------------------------------------------
    st.markdown("### Preview Reports (No Database Changes)")
    st.caption("These exports do not write anything to the database. They are previews only.")

    c1, c2 = st.columns(2)

    # ---- Preview Roll Offs ----
    with c1:
        st.markdown("#### Preview Roll Offs")
        st.caption("Employees with an upcoming roll-off date. Exports a CSV formatted for manual review/editing.")

        if st.button("Generate Preview Roll Offs CSV", key="btn_preview_rolloffs"):
            rows_r = repo.report_rolloff_next_2_months(conn)  # NOTE: currently "next 2 months" source
            df_r = pd.DataFrame([dict(r) for r in rows_r])

            if df_r.empty:
                st.info("No upcoming roll-offs found.")
            else:
                # Expected inputs: employee_id, first_name, last_name, rolloff_date, point_total
                df_r["Employee #"] = df_r["employee_id"].astype(str)
                df_r["First Name"] = df_r.get("first_name", "")
                df_r["Last Name"] = df_r.get("last_name", "")

                roll_dt = pd.to_datetime(df_r.get("rolloff_date"), errors="coerce")
                df_r["_sort_rolloff_date"] = roll_dt  # for sorting only

                df_r["Point"] = -1.0
                df_r["Reason"] = "2 Month Rolloff"
                df_r["Note"] = ""
                df_r["Point Total"] = (pd.to_numeric(df_r.get("point_total"), errors="coerce").fillna(0) - 1.0).round(1)
                df_r["Flag Code"] = df_r.get("flag_code", "")  # keep if exists; otherwise blank

                # Sort: most recent rolloff date at top
                df_r = df_r.sort_values("_sort_rolloff_date", ascending=False).copy()

                out_cols = ["Employee #", "First Name", "Last Name", "Point", "Reason", "Note", "Point Total", "Flag Code"]
                df_out = df_r[out_cols].copy()

                st.dataframe(df_out, use_container_width=True, hide_index=True)
                csv = df_out.to_csv(index=False).encode("utf-8")
                st.download_button("Download CSV", csv, "preview_rolloffs.csv", "text/csv", key="dl_preview_rolloffs")

    # ---- Preview Perfect Attendance ----
    with c2:
        st.markdown("#### Preview Perfect Attendance")
        st.caption("Employees with an upcoming Perfect Attendance date. Exports a CSV formatted for manual review/editing.")

        if st.button("Generate Preview Perfect Attendance CSV", key="btn_preview_pa"):
            rows_p = repo.report_perfect_attendance_upcoming(conn)
            df_p = pd.DataFrame([dict(r) for r in rows_p])

            if df_p.empty:
                st.info("No upcoming perfect attendance dates found.")
            else:
                df_p["Employee #"] = df_p["employee_id"].astype(str)
                df_p["First Name"] = df_p.get("first_name", "")
                df_p["Last Name"] = df_p.get("last_name", "")

                df_p["Point"] = ""  # left blank per your spec
                df_p["Reason"] = "$75 Perfect Attendance Bonus"
                df_p["Note"] = ""
                df_p["Point Total"] = pd.to_numeric(df_p.get("point_total"), errors="coerce").fillna(0).round(1)
                df_p["Flag Code"] = df_p.get("flag_code", "")

                out_cols = ["Employee #", "First Name", "Last Name", "Point", "Reason", "Note", "Point Total", "Flag Code"]
                df_out = df_p[out_cols].copy()

                st.dataframe(df_out, use_container_width=True, hide_index=True)
                csv = df_out.to_csv(index=False).encode("utf-8")
                st.download_button("Download CSV", csv, "preview_perfect_attendance.csv", "text/csv", key="dl_preview_pa")

    st.divider()

    # ------------------------------------------------------------
    # 3) DB-changing actions (we will wire the first two after you provide Beta7 logic)
    # ------------------------------------------------------------
    st.markdown("### Actions (Modifies Database)")
    st.caption("These buttons write changes to the database and generate a CSV of what changed.")

    # ---- Perform 2 Month Roll Off ----
    st.markdown("#### Perform 2 Month Roll Off")
    st.caption("Removes any roll-offs due as of today and advances the next roll-off date.")

    st.warning("Not wired yet: I need the ATP_Beta7 roll-off logic/function so we don't guess and miscalculate.")
    st.button("Perform 2 Month Roll Off (Commit)", disabled=True, key="btn_commit_rolloff")

    # ---- Generate Perfect Attendance ----
    st.markdown("#### Generate Perfect Attendance")
    st.caption("Applies perfect attendance updates due as of today and advances the next perfect attendance date.")

    st.warning("Not wired yet: I need the ATP_Beta7 perfect attendance logic/function so we don't guess and miscalculate.")
    st.button("Generate Perfect Attendance (Commit)", disabled=True, key="btn_commit_pa")

    st.divider()

    # ---- Generate YTD Roll Offs (this one exists today via services.apply_ytd_rolloffs) ----
    st.markdown("#### Generate YTD Roll Offs")
    st.caption("Uses the existing YTD roll-off logic and writes entries to the database.")

    run_dt = st.date_input("Run date (rolloff uses the 1st of this month)", value=date.today(), key="roll_run_dt")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Preview YTD Roll Offs", key="btn_preview_ytd"):
            items = services.apply_ytd_rolloffs(conn, run_date=run_dt, dry_run=True)

            # Map into your requested CSV shape
            df = pd.DataFrame(items)
            if df.empty:
                st.info("No YTD roll-offs found.")
            else:
                # Attempt to normalize expected columns from existing service output
                # You may need to adjust these keys based on what apply_ytd_rolloffs returns
                df_out = pd.DataFrame({
                    "Employee #": df.get("employee_id", "").astype(str),
                    "First Name": df.get("first_name", ""),
                    "Last Name": df.get("last_name", ""),
                    "Point": pd.to_numeric(df.get("points_to_rolloff", 0), errors="coerce").fillna(0).round(1),
                    "Point Date": df.get("roll_date", ""),
                    "Reason": "YTD Roll Off",
                    "Note": "",
                    "Point Total": pd.to_numeric(df.get("new_point_total", df.get("point_total", 0)), errors="coerce").fillna(0).round(1),
                    "Flag Code": df.get("flag_code", ""),
                })

                st.dataframe(df_out, use_container_width=True, hide_index=True)
                csv = df_out.to_csv(index=False).encode("utf-8")
                st.download_button("Download CSV", csv, "preview_ytd_rolloffs.csv", "text/csv", key="dl_preview_ytd")

    with col2:
        confirm_apply = st.checkbox("I understand this will write roll-off entries to the database.", key="roll_confirm")

        if st.button("Generate YTD Roll Offs (Commit)", key="btn_commit_ytd") and confirm_apply:
            items = services.apply_ytd_rolloffs(conn, run_date=run_dt, dry_run=False)

            df = pd.DataFrame(items)
            if df.empty:
                st.info("No YTD roll-offs were applied.")
            else:
                df_out = pd.DataFrame({
                    "Employee #": df.get("employee_id", "").astype(str),
                    "First Name": df.get("first_name", ""),
                    "Last Name": df.get("last_name", ""),
                    "Point": pd.to_numeric(df.get("points_rolled", df.get("points_to_rolloff", 0)), errors="coerce").fillna(0).round(1),
                    "Point Date": df.get("roll_date", ""),
                    "Reason": "YTD Roll Off",
                    "Note": "",
                    "Point Total": pd.to_numeric(df.get("new_point_total", df.get("point_total", 0)), errors="coerce").fillna(0).round(1),
                    "Flag Code": df.get("flag_code", ""),
                })

                st.success(f"Applied YTD roll-offs for {len(df_out)} employees.")
                st.dataframe(df_out, use_container_width=True, hide_index=True)
                csv = df_out.to_csv(index=False).encode("utf-8")
                st.download_button("Download CSV", csv, "ytd_rolloffs_applied.csv", "text/csv", key="dl_commit_ytd")

    st.divider()

    # ------------------------------------------------------------
    # 4) Employee Point History PDF (Termination File) — next
    # ------------------------------------------------------------
    st.markdown("### Employee Point History (PDF)")
    st.caption("Generates a PDF of the employee's complete point history for the termination file.")
    st.warning("Next step: wire PDF generation once we confirm the exact Beta7 output format you want.")
