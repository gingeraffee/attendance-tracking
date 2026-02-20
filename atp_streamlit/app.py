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

    # ----------------------------
    # Beta7 helper logic (local)
    # ----------------------------
    from datetime import datetime, timedelta

    def add_months_first(d, months: int):
        """Beta7: first day of the month 'months' after date d."""
        m_total = (d.month - 1) + months
        y = d.year + (m_total // 12)
        m = (m_total % 12) + 1
        return date(y, m, 1)

    def add_months(orig: date, months: int) -> date:
        """Beta7: add calendar months, clamp day if needed."""
        y = orig.year + (orig.month - 1 + months) // 12
        m = (orig.month - 1 + months) % 12 + 1
        if m in (1, 3, 5, 7, 8, 10, 12):
            dim = 31
        elif m in (4, 6, 9, 11):
            dim = 30
        else:
            leap = (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
            dim = 29 if leap else 28
        d = min(orig.day, dim)
        return date(y, m, d)

    def first_of_month(d: date) -> date:
        return date(d.year, d.month, 1)

    def first_of_next_month(d: date) -> date:
        return add_months(first_of_month(d), 1)

    def two_months_then_first(d: date) -> date:
        return first_of_next_month(add_months(d, 2))

    # Beta7 has this (it’s functionally the same as two_months_then_first in that file)
    def three_months_then_first(d: date) -> date:
        return first_of_next_month(add_months(d, 2))

    def step_next_due(current_due: date, perfect_date: date) -> date:
        """Beta7: advance next rolloff due date."""
        if current_due < perfect_date:
            return two_months_then_first(perfect_date)
        return two_months_then_first(current_due)

    today = date.today()
    today_iso = today.isoformat()

    # ============================================================
    # 1) 30-Day Point History (CSV) — true running total (Beta7)
    # ============================================================
    st.markdown("### 30-Day Point History (CSV)")
    st.caption("Exports every point event in the last 30 days with a true running total per employee (Beta7 logic).")

    if st.button("Generate 30-Day Point History CSV", key="btn_30day"):
        cutoff = (today - timedelta(days=30)).isoformat()

        rows = conn.execute(
            """
            WITH recent_emp AS (
                SELECT DISTINCT employee_id
                  FROM points_history
                 WHERE date(point_date) >= date(?)
            ),
            ordered AS (
                SELECT
                    p.id,
                    p.employee_id,
                    e.first_name,
                    e.last_name,
                    p.point_date,
                    COALESCE(p.points, 0.0)   AS points,
                    COALESCE(p.reason, '')    AS reason,
                    COALESCE(p.note, '')      AS note,
                    COALESCE(p.flag_code, '') AS flag_code,
                    SUM(COALESCE(p.points, 0.0)) OVER (
                        PARTITION BY p.employee_id
                        ORDER BY date(p.point_date), p.id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) AS point_total
                FROM points_history p
                JOIN employees e ON e.employee_id = p.employee_id
                WHERE p.employee_id IN (SELECT employee_id FROM recent_emp)
            )
            SELECT
                employee_id, first_name, last_name,
                point_date, points, reason, note, point_total, flag_code
            FROM ordered
            WHERE date(point_date) >= date(?)
            ORDER BY date(point_date) DESC, id DESC;
            """,
            (cutoff, cutoff),
        ).fetchall()

        df = pd.DataFrame([dict(r) for r in rows])
        if df.empty:
            st.info("No point events found in the last 30 days.")
        else:
            df_out = pd.DataFrame({
                "Employee #": df["employee_id"].astype(str),
                "First Name": df["first_name"],
                "Last Name": df["last_name"],
                "Point Date": df["point_date"],
                "Point": pd.to_numeric(df["points"], errors="coerce").fillna(0).round(1),
                "Reason": df["reason"],
                "Note": df["note"],
                "Point Total": pd.to_numeric(df["point_total"], errors="coerce").fillna(0).round(1),
                "Flag Code": df["flag_code"],
            })

            st.dataframe(df_out, use_container_width=True, hide_index=True)
            csv = df_out.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "points_last_30_days.csv", "text/csv", key="dl_30day")

    st.divider()

    # ============================================================
    # 2) Preview Reports (NO DB CHANGES)
    # ============================================================
    st.markdown("### Preview Reports (No Database Changes)")
    st.caption("These exports do not write anything to the database. They are previews only.")

    c1, c2 = st.columns(2)

    # ---- Preview Roll Offs (sorted earliest -> latest, grouped by date) ----
    with c1:
        st.markdown("#### Preview Roll Offs")
        st.caption("Sorted by roll-off date (earliest first): March rolloffs, then April, then May, etc.")

        if st.button("Generate Preview Roll Offs CSV", key="btn_preview_rolloffs"):
            rows_r = conn.execute(
                """
                SELECT employee_id, first_name, last_name, rolloff_date, COALESCE(point_total,0.0) AS pt
                FROM employees
                WHERE rolloff_date IS NOT NULL AND date(rolloff_date) >= date('now')
                ORDER BY date(rolloff_date) ASC, last_name, first_name;
                """
            ).fetchall()

            df_r = pd.DataFrame([dict(r) for r in rows_r])
            if df_r.empty:
                st.info("No upcoming roll-offs found.")
            else:
                df_out = pd.DataFrame({
                    "Employee #": df_r["employee_id"].astype(str),
                    "First Name": df_r["first_name"],
                    "Last Name": df_r["last_name"],
                    "Point": -1.0,
                    "Reason": "2 Month Rolloff",
                    "Note": "",
                    "Point Total": (pd.to_numeric(df_r["pt"], errors="coerce").fillna(0) - 1.0).round(1),
                    "Flag Code": "",
                })

                st.dataframe(df_out, use_container_width=True, hide_index=True)
                csv = df_out.to_csv(index=False).encode("utf-8")
                st.download_button("Download CSV", csv, "preview_rolloffs.csv", "text/csv", key="dl_preview_rolloffs")

    # ---- Preview Perfect Attendance ----
    with c2:
        st.markdown("#### Preview Perfect Attendance")
        st.caption("Upcoming perfect attendance dates (no DB changes).")

        if st.button("Generate Preview Perfect Attendance CSV", key="btn_preview_pa"):
            rows_p = conn.execute(
                """
                SELECT employee_id, first_name, last_name, perfect_attendance AS d, COALESCE(point_total,0.0) AS pt
                FROM employees
                WHERE perfect_attendance IS NOT NULL AND date(perfect_attendance) >= date('now')
                ORDER BY date(perfect_attendance) ASC, last_name, first_name;
                """
            ).fetchall()

            df_p = pd.DataFrame([dict(r) for r in rows_p])
            if df_p.empty:
                st.info("No upcoming perfect attendance dates found.")
            else:
                df_out = pd.DataFrame({
                    "Employee #": df_p["employee_id"].astype(str),
                    "First Name": df_p["first_name"],
                    "Last Name": df_p["last_name"],
                    "Point": "",
                    "Reason": "$75 Perfect Attendance Bonus",
                    "Note": "",
                    "Point Total": pd.to_numeric(df_p["pt"], errors="coerce").fillna(0).round(1),
                    "Flag Code": "",
                })

                st.dataframe(df_out, use_container_width=True, hide_index=True)
                csv = df_out.to_csv(index=False).encode("utf-8")
                st.download_button("Download CSV", csv, "preview_perfect_attendance.csv", "text/csv", key="dl_preview_pa")

    st.divider()

    # ============================================================
    # 3) Actions (Modifies Database)
    # ============================================================
    st.markdown("### Actions (Modifies Database)")
    st.caption("These buttons write changes to the database and generate a CSV of what changed.")

    # ---- Perform 2 Month Roll Off ----
    st.markdown("#### Perform 2 Month Roll Off")
    st.caption("Applies roll-offs only for rolloff dates on or before today. Multiple overdue roll-offs create multiple rows.")

    confirm_roll = st.checkbox("I understand this will write roll-off entries to the database.", key="confirm_2mo_rolloff")

    if st.button("Perform 2 Month Roll Off (Commit)", key="btn_commit_rolloff") and confirm_roll:
        expired = conn.execute(
            """
            SELECT employee_id, first_name, last_name,
                   rolloff_date,
                   COALESCE(point_total,0.0) AS pt,
                   NULLIF(last_point_date,'') AS last_point_iso
            FROM employees
            WHERE rolloff_date IS NOT NULL AND date(rolloff_date) <= date('now');
            """
        ).fetchall()

        log = []

        with conn:
            for rec in expired:
                emp_id = int(rec["employee_id"])
                fn = rec["first_name"]
                ln = rec["last_name"]
                current_total = float(rec["pt"] or 0.0)

                next_roll = datetime.strptime(rec["rolloff_date"], "%Y-%m-%d").date()

                # Beta7 perfect_date anchor
                last_point_iso = rec["last_point_iso"]
                if last_point_iso:
                    anchor = datetime.strptime(last_point_iso, "%Y-%m-%d").date()
                    perfect_date = three_months_then_first(anchor)
                else:
                    perfect_date = date.min

                # Apply due roll-offs, but only while due <= today
                # Create one CSV row AND one history row per event (your requirement)
                while next_roll <= today and current_total > 0:
                    current_total = max(0.0, round(current_total - 1.0, 2))

                    # Write one history entry per roll-off event
                    conn.execute(
                        """
                        INSERT INTO points_history (employee_id, point_date, points, reason, note, flag_code)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (emp_id, next_roll.isoformat(), -1.0, "2 Month Roll Off", "", ""),
                    )

                    # Log row (one per roll-off)
                    log.append({
                        "Employee #": str(emp_id),
                        "First Name": fn,
                        "Last Name": ln,
                        "Point": -1.0,
                        "Point Date": next_roll.isoformat(),
                        "Reason": "2 Month Roll Off",
                        "Note": "",
                        "Point Total": round(current_total, 1),
                        "Flag Code": "",
                    })

                    # Advance to next due date using Beta7 stepping
                    next_roll = step_next_due(next_roll, perfect_date)

                # If the rolloff_date itself is overdue, advance it even if total is already 0
                # (still only changes overdue dates)
                if rec["rolloff_date"] != next_roll.isoformat():
                    conn.execute(
                        "UPDATE employees SET rolloff_date=? WHERE employee_id=?",
                        (next_roll.isoformat(), emp_id),
                    )

                # Update point_total if it changed
                conn.execute(
                    "UPDATE employees SET point_total=? WHERE employee_id=?",
                    (current_total, emp_id),
                )

        df_log = pd.DataFrame(log)
        if df_log.empty:
            st.info("No roll-offs were applied (nothing due today or earlier, or point totals already at 0).")
        else:
            # Sort so most recent roll-off date appears at the top of the audit
            df_log["Point Date"] = pd.to_datetime(df_log["Point Date"], errors="coerce")
            df_log = df_log.sort_values("Point Date", ascending=False).copy()
            df_log["Point Date"] = df_log["Point Date"].dt.strftime("%Y-%m-%d")

            st.success(f"Applied {len(df_log)} roll-off event(s).")
            st.dataframe(df_log, use_container_width=True, hide_index=True)
            csv = df_log.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "apply_2_month_rolloffs.csv", "text/csv", key="dl_apply_rolloffs")

    st.divider()

    # ---- Generate Perfect Attendance (Beta7 logic for advancing dates) ----
    st.markdown("#### Generate Perfect Attendance")
    st.caption("Updates perfect attendance dates that are due as of today, advancing them using Beta7 logic (3-month steps to the 1st).")

    confirm_pa = st.checkbox("I understand this will update perfect attendance dates in the database.", key="confirm_pa")

    if st.button("Generate Perfect Attendance (Commit)", key="btn_commit_pa") and confirm_pa:
        rows = conn.execute(
            """
            SELECT employee_id, first_name, last_name,
                   COALESCE(point_total,0.0) AS pt,
                   NULLIF(perfect_attendance,'') AS d
            FROM employees
            WHERE perfect_attendance IS NOT NULL
              AND date(perfect_attendance) <= date(?)
            ORDER BY last_name, first_name;
            """,
            (today_iso,),
        ).fetchall()

        if not rows:
            st.info("No perfect attendance dates are due as of today.")
        else:
            log = []

            with conn:
                for r in rows:
                    emp_id = int(r["employee_id"])
                    fn = r["first_name"]
                    ln = r["last_name"]
                    pt = float(r["pt"] or 0.0)
                    due_iso = r["d"]

                    due_d = datetime.strptime(due_iso, "%Y-%m-%d").date()

                    # Beta7: advance by 3 months to first-of-month, repeat until in future
                    next_d = add_months_first(due_d, 3)
                    while next_d <= today:
                        next_d = add_months_first(next_d, 3)

                    conn.execute(
                        "UPDATE employees SET perfect_attendance=? WHERE employee_id=?",
                        (next_d.isoformat(), emp_id),
                    )

                    log.append({
                        "Employee #": str(emp_id),
                        "First Name": fn,
                        "Last Name": ln,
                        "Point": 0.0,
                        "Point Date": due_iso,  # date of perfect attendance event
                        "Reason": "$75 Attendance Bonus",
                        "Note": "",
                        "Point Total": round(pt, 1),
                        "Flag Code": "",
                    })

            df_log = pd.DataFrame(log)
            st.success(f"Updated perfect attendance dates for {len(df_log)} employee(s).")
            st.dataframe(df_log, use_container_width=True, hide_index=True)
            csv = df_log.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "apply_perfect_attendance.csv", "text/csv", key="dl_apply_pa")

    st.divider()

    # ============================================================
    # 4) YTD + PDF placeholders (we'll align these next)
    # ============================================================
    st.markdown("### Generate YTD Roll Offs")
    st.caption("Keeping your existing YTD UI here for now — we can align output columns next if needed.")
    st.info("Use the existing YTD section below (unchanged).")
