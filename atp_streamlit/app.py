import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import date, datetime
import sys
from pathlib import Path
import io
import os
import time
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

# MUST be the first Streamlit command
st.set_page_config(
    page_title="Point System 2026",
    page_icon="📅",
    layout="wide",
)
    
# ---- Path setup (MUST come before importing atp_core) -------------------------
APP_DIR = Path(__file__).resolve().parent          # .../attendance-tracking/atp_streamlit
REPO_ROOT = APP_DIR.parent                         # .../attendance-tracking
ROOT = REPO_ROOT

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import atp_core.db as db
except Exception as e:
    st.error("Failed to import atp_core.db")
    st.exception(e)
    st.stop()

connect = db.connect
get_db_path = getattr(db, "get_db_path", lambda: "MISSING get_db_path()")
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
    logo_candidates = [
        APP_DIR / "assets" / "logo.png",
        ROOT / "assets" / "logo.png",
    ]
    logo_path = next((path for path in logo_candidates if path.is_file()), None)
    if logo_path:
        st.sidebar.image(str(logo_path), use_container_width=True)

def on_emp_table_select():
    sel = st.session_state.get("emp_table", {}).selection.rows
    if sel:
        idx = sel[0]
        emp_id = int(st.session_state["emp_table_ids"][idx])
        st.session_state["selected_emp_id"] = emp_id
        
def get_conn():
    conn = connect()
    ensure_schema(conn)
    return conn


def _is_pg_conn(conn) -> bool:
    return conn.__class__.__module__.startswith("psycopg2")


def _fetchall_sql(conn, sql: str, params=()):
    if _is_pg_conn(conn):
        cur = conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        rows = cur.fetchall()
        cur.close()
        return rows
    return conn.execute(sql, params).fetchall()


def _exec_sql(conn, sql: str, params=()):
    if _is_pg_conn(conn):
        cur = conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        cur.close()
        return
    conn.execute(sql, params)



def _fetchone_sql(conn, sql: str, params=()):
    if _is_pg_conn(conn):
        cur = conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        row = cur.fetchone()
        cur.close()
        return row
    return conn.execute(sql, params).fetchone()


def _first_workday_of_month(d: date) -> date:
    cur = d.replace(day=1)
    while cur.weekday() >= 5:  # 5=Saturday, 6=Sunday
        cur = cur.replace(day=cur.day + 1)
    return cur

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
try:
    conn = get_conn()
except Exception as e:
    st.error("Database connection failed.")
    st.exception(e)
    st.stop()
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

        # Edit Info toggle button
        if not st.session_state.setdefault("show_edit_info", False):
            if st.sidebar.button("✏️ Edit Info", key="btn_edit_info"):
                st.session_state["show_edit_info"] = True
                st.rerun()
        else:
            st.sidebar.markdown("#### Edit Employee Dates")

            # Parse existing dates for the calendar pickers
            def parse_date_for_picker(val):
                if not val:
                    return None
                if hasattr(val, "date"):
                    return val.date()
                if isinstance(val, date):
                    return val
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
                    try:
                        return datetime.strptime(str(val), fmt).date()
                    except ValueError:
                        pass
                return None

            with st.sidebar.form("edit_info_form"):
                last_point_default = parse_date_for_picker(emp.get("last_point_date"))
                rolloff_default = parse_date_for_picker(emp.get("rolloff_date"))
                perfect_default = parse_date_for_picker(emp.get("perfect_attendance"))

                clear_last_point = st.checkbox(
                    "Clear Last Point Date",
                    value=False,
                    key="clear_last_point_date",
                )
                new_last_point = st.date_input(
                    "Last Point Date",
                    value=last_point_default,
                    format="MM/DD/YYYY",
                    key="edit_last_point_date",
                    disabled=clear_last_point,
                )

                clear_rolloff = st.checkbox(
                    "Clear 2 Month Roll-Off Date",
                    value=False,
                    key="clear_rolloff_date",
                )
                new_rolloff = st.date_input(
                    "2 Month Roll-Off Date",
                    value=rolloff_default,
                    format="MM/DD/YYYY",
                    key="edit_rolloff_date",
                    disabled=clear_rolloff,
                )

                clear_perfect = st.checkbox(
                    "Clear Perfect Attendance Date",
                    value=False,
                    key="clear_perfect_date",
                )
                new_perfect = st.date_input(
                    "Perfect Attendance Date",
                    value=perfect_default,
                    format="MM/DD/YYYY",
                    key="edit_perfect_date",
                    disabled=clear_perfect,
                )

                col_save, col_cancel = st.columns(2)
                with col_save:
                    save_clicked = st.form_submit_button("💾 Save")
                with col_cancel:
                    cancel_clicked = st.form_submit_button("✖ Cancel")

            if save_clicked:
                try:
                    _exec_sql(
                        conn,
                        """
                        UPDATE employees
                           SET last_point_date    = ?,
                               rolloff_date       = ?,
                               perfect_attendance = ?
                         WHERE employee_id = ?
                        """,
                        (
                            None if clear_last_point else (new_last_point.isoformat() if new_last_point else None),
                            None if clear_rolloff else (new_rolloff.isoformat() if new_rolloff else None),
                            None if clear_perfect else (new_perfect.isoformat() if new_perfect else None),
                            int(selected_emp_id),
                        ),
                    )
                    conn.commit()
                    st.session_state["show_edit_info"] = False
                    st.sidebar.success("Dates updated.")
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(str(e))

            if cancel_clicked:
                st.session_state["show_edit_info"] = False
                st.rerun()

    else:
        st.sidebar.info("Employee not found.")
else:
    st.sidebar.caption("Select an employee from the Employees tab.")
    if st.session_state.get("show_edit_info"):
        st.session_state["show_edit_info"] = False


st.sidebar.divider()
st.sidebar.subheader("Employee Management")

with st.sidebar.expander("Add employee", expanded=False):
    with st.form("add_employee_form", clear_on_submit=True):
        new_emp_id = st.number_input("Employee #", min_value=1, step=1, format="%d")
        new_last_name = st.text_input("Last name")
        new_first_name = st.text_input("First name")
        new_location = st.text_input("Location (optional)")
        add_emp_submit = st.form_submit_button("Add Employee")

    if add_emp_submit:
        try:
            services.create_employee(
                conn,
                employee_id=int(new_emp_id),
                last_name=new_last_name,
                first_name=new_first_name,
                location=new_location,
            )
            st.sidebar.success("Employee added.")
            st.rerun()
        except Exception as e:
            st.sidebar.error(str(e))

with st.sidebar.expander("Delete employee", expanded=False):
    selected_emp_id = st.session_state.get("selected_emp_id")
    if selected_emp_id:
        st.caption(f"Selected Employee #: {selected_emp_id}")
    st.warning("Deleting an employee also deletes all of their point history.")
    with st.form("delete_employee_form"):
        delete_emp_id = st.number_input(
            "Employee # to delete",
            min_value=1,
            step=1,
            format="%d",
            value=int(selected_emp_id) if selected_emp_id else 1,
        )
        confirm_delete = st.checkbox("I understand this action cannot be undone.")
        delete_emp_submit = st.form_submit_button("Delete Employee")

    if delete_emp_submit:
        if not confirm_delete:
            st.sidebar.error("Please confirm deletion before continuing.")
        else:
            try:
                services.delete_employee(conn, int(delete_emp_id))
                if st.session_state.get("selected_emp_id") == int(delete_emp_id):
                    st.session_state.pop("selected_emp_id", None)
                st.sidebar.success("Employee deleted.")
                st.rerun()
            except Exception as e:
                st.sidebar.error(str(e))

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
            "_employee_id": df["employee_id"],
            "Employee #": df["employee_id"].astype("string"),
            "Last Name": df.get("last_name", ""),
            "First Name": df.get("first_name", ""),
            # Keep this as text so it aligns left like the other columns.
            "Point Total": pd.to_numeric(df.get("point_total", 0), errors="coerce").fillna(0).map(lambda v: f"{v:.1f}"),
        }).copy()
        
        # Store row->id mapping for the callback
        st.session_state["emp_table_ids"] = display["_employee_id"].tolist()

        st.dataframe(
            display.drop(columns=["_employee_id"]),
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row",
            key="emp_table",
            on_select=on_emp_table_select,
        )

        # Fallback: dropdown (optional)
        emp_id = None
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
                else pd.DataFrame(columns=["id", "point_date", "points", "reason", "note", "flag_code", "point_total"])
            )

            if not hdf.empty:
                hdf.loc[:, "point_date"] = pd.to_datetime(hdf["point_date"], errors="coerce")
                hdf.loc[:, "points"] = pd.to_numeric(hdf["points"], errors="coerce").round(1)

                edited_hdf = st.data_editor(
                    hdf,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed",
                    column_config={
                        "id": None,
                        "point_date": st.column_config.DateColumn("Point Date", format="MM/DD/YYYY", required=True),
                        "points": st.column_config.NumberColumn("Points", step=0.5, format="%.1f"),
                        "reason": st.column_config.TextColumn("Reason"),
                        "note": st.column_config.TextColumn("Note"),
                        "flag_code": st.column_config.TextColumn("Flag Code"),
                        "point_total": st.column_config.NumberColumn("Point Total", format="%.1f"),
                    },
                    disabled=["id"],
                    key=f"points_history_editor_{emp_id}",
                )

                c_save, c_delete = st.columns(2)

                with c_save:
                    if st.button("Save history edits", key=f"save_history_{emp_id}"):
                        try:
                            for _, row in edited_hdf.iterrows():
                                point_date_value = row.get("point_date")
                                if pd.isna(point_date_value):
                                    raise ValueError("Point date is required.")

                                if hasattr(point_date_value, "to_pydatetime"):
                                    point_date_value = point_date_value.to_pydatetime().date()
                                elif hasattr(point_date_value, "date"):
                                    point_date_value = point_date_value.date()

                                services.update_point_history_entry(
                                    conn,
                                    point_id=int(row["id"]),
                                    employee_id=int(emp_id),
                                    point_date=point_date_value,
                                    points=float(row["points"]),
                                    reason=str(row["reason"]),
                                    note=("" if pd.isna(row.get("note")) else str(row.get("note"))),
                                    flag_code=("" if pd.isna(row.get("flag_code")) else str(row.get("flag_code"))),
                                )
                            st.success("Point history updated.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

                with c_delete:
                    delete_options = [
                        (
                            int(r["id"]),
                            f"{pd.to_datetime(r['point_date'], errors='coerce').strftime('%m/%d/%Y') if pd.notna(pd.to_datetime(r['point_date'], errors='coerce')) else r['point_date']} • {float(r.get('points') or 0):.1f} • {r.get('reason') or ''}"
                        )
                        for r in hdf.to_dict(orient="records")
                    ]
                    selected_delete = st.selectbox(
                        "Select point to delete",
                        options=delete_options,
                        format_func=lambda x: x[1],
                        key=f"delete_point_select_{emp_id}",
                    )
                    confirm_delete_point = st.checkbox(
                        "I understand this point will be permanently deleted.",
                        key=f"confirm_delete_point_{emp_id}",
                    )
                    if st.button("Delete selected point", key=f"delete_point_btn_{emp_id}"):
                        if not confirm_delete_point:
                            st.error("Please confirm deletion before continuing.")
                        else:
                            try:
                                services.delete_point_history_entry(
                                    conn,
                                    point_id=int(selected_delete[0]),
                                    employee_id=int(emp_id),
                                )
                                st.success("Point deleted.")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
            else:
                st.info("No point history found for this employee.")

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

            components.html(
                """
                <script>
                const setupDateField = () => {
                  const doc = window.parent.document;
                  const input = doc.querySelector('input[aria-label="Point date (MM/DD/YYYY)"]');
                  if (!input || input.dataset.autoclearBound === "1") return;
                  input.dataset.autoclearBound = "1";
                  input.addEventListener("focus", () => { input.dataset.autoclearOnType = "1"; });
                  input.addEventListener("keydown", (ev) => {
                    if (input.dataset.autoclearOnType !== "1") return;
                    if (ev.key.length === 1 || ev.key === "Backspace" || ev.key === "Delete") {
                      input.value = "";
                      input.dataset.autoclearOnType = "0";
                      input.dispatchEvent(new Event("input", { bubbles: true }));
                    }
                  });
                };
                setupDateField();
                setTimeout(setupDateField, 250);
                </script>
                """,
                height=0,
            )

            with st.form("add_point_form", clear_on_submit=False):
                pdate = st.date_input("Point date (MM/DD/YYYY)", value=date.today(), format="MM/DD/YYYY")
                points = st.selectbox("Points", [0.5, 1.0, 1.5], index=0)
                reason = st.selectbox("Reason", REASON_OPTIONS, index=0)
                flag_code = st.text_input("Flag Code (optional)", value="")
                note = st.text_area("Note (optional)", placeholder="Leave blank unless needed")
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
                            "date": preview.point_date.strftime("%m/%d/%Y"),
                            "points": preview.points,
                            "reason": preview.reason,
                            "flag_code": (flag_code or "").strip(),
                            "note": preview.note,
                        }
                    )
                    st.info(f"Point Total: {before_total:.1f}  →  {after_total:.1f}")

                    if confirm:
                        services.add_point(conn, preview, flag_code=(flag_code or "").strip() or None)
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

    from datetime import datetime, timedelta
    from atp_core.rules import (
        add_months,
        first_of_month,
        first_of_next_month,
        two_months_then_first,
        three_months_then_first,
        step_next_rolloff,
    )

    today = date.today()
    today_iso = today.isoformat()

    # ============================================================
    # 1) 30-Day Point History (CSV)
    # ============================================================
    st.markdown("### 30-Day Point History (CSV)")
    st.caption("Exports every point event in the last 30 days with a true running total per employee.")

    if st.button("Generate 30-Day Point History CSV", key="btn_30day"):
        cutoff = (today - timedelta(days=30)).isoformat()

        if _is_pg_conn(conn):
            rows = _fetchall_sql(
                conn,
                """
                WITH recent_emp AS (
                    SELECT DISTINCT employee_id
                      FROM points_history
                     WHERE (point_date::date) >= (%s::date)
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
                            ORDER BY (p.point_date::date), p.id
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
                WHERE (point_date::date) >= (%s::date)
                ORDER BY (point_date::date) DESC, id DESC;
                """,
                (cutoff, cutoff),
            )
        else:
            rows = _fetchall_sql(
                conn,
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
            )

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

    with c1:
        st.markdown("#### Preview Roll Offs")
        st.caption("Shows missed/due and upcoming roll-off dates.")

        # Intentionally no "future-only" date filter here:
        # this report must include missed/due roll-offs as well as upcoming ones.
        if _is_pg_conn(conn):
            rows_r = _fetchall_sql(
                conn,
                """
                SELECT employee_id, first_name, last_name, rolloff_date,
                       COALESCE(point_total, 0.0) AS pt
                  FROM employees
                 WHERE rolloff_date IS NOT NULL
                   AND COALESCE(point_total, 0.0) > 0
                 ORDER BY (rolloff_date::date) ASC, last_name, first_name;
                """,
            )
        else:
            rows_r = _fetchall_sql(
                conn,
                """
                SELECT employee_id, first_name, last_name, rolloff_date,
                       COALESCE(point_total, 0.0) AS pt
                  FROM employees
                 WHERE rolloff_date IS NOT NULL
                   AND COALESCE(point_total, 0.0) > 0
                 ORDER BY date(rolloff_date) ASC, last_name, first_name;
                """,
            )

        df_r = pd.DataFrame([dict(r) for r in rows_r])
        if df_r.empty:
            st.info("No missed/due or upcoming roll-offs found.")
        else:
            raw_dates = pd.to_datetime(df_r["rolloff_date"], errors="coerce")
            df_r["rolloff_date"] = raw_dates.dt.strftime("%m/%d/%Y")
            df_r["status"] = raw_dates.apply(
                lambda d: "Missed / Due" if pd.notna(d) and d.date() <= today else "Upcoming"
            )

            df_out_r = pd.DataFrame({
                "Employee #": df_r["employee_id"].astype(str),
                "First Name": df_r["first_name"],
                "Last Name": df_r["last_name"],
                "Roll-Off Date": df_r["rolloff_date"],
                "Status": df_r["status"],
                "Points": df_r["pt"].apply(lambda v: f"-{float(v):.1f}"),
                "Reason": "2 Month Roll Off",
                "Note": "",
                "Point Total After": 0.0,
                "Flag Code": "AUTO",
            })

            st.dataframe(df_out_r, use_container_width=True, hide_index=True)
            csv = df_out_r.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download CSV", csv, "preview_rolloffs.csv",
                "text/csv", key="dl_preview_rolloffs",
            )

    with c2:
        st.markdown("#### Preview Perfect Attendance")
        st.caption("Employees with an upcoming perfect attendance bonus date.")

        # Intentionally no "future-only" date filter here:
        # this report must include missed/due perfect-attendance dates as well as upcoming ones.
        if _is_pg_conn(conn):
            rows_p = _fetchall_sql(
                conn,
                """
                SELECT employee_id, first_name, last_name,
                       perfect_attendance AS pa_date,
                       COALESCE(point_total, 0.0) AS pt
                  FROM employees
                 WHERE perfect_attendance IS NOT NULL
                 ORDER BY (perfect_attendance::date) ASC, last_name, first_name;
                """,
            )
        else:
            rows_p = _fetchall_sql(
                conn,
                """
                SELECT employee_id, first_name, last_name,
                       perfect_attendance AS pa_date,
                       COALESCE(point_total, 0.0) AS pt
                  FROM employees
                 WHERE perfect_attendance IS NOT NULL
                 ORDER BY date(perfect_attendance) ASC, last_name, first_name;
                """,
            )

        df_p = pd.DataFrame([dict(r) for r in rows_p])
        if df_p.empty:
            st.info("No missed/due or upcoming perfect attendance dates found.")
        else:
            df_p = df_p.copy()
            raw_pa = pd.to_datetime(df_p["pa_date"], errors="coerce")
            df_p["pa_date"] = raw_pa
            df_p["status"] = raw_pa.apply(
                lambda d: "Missed / Due" if pd.notna(d) and d.date() <= today else "Upcoming"
            )

            df_out_p = pd.DataFrame({
                "Employee #": df_p["employee_id"].astype("string"),
                "First Name": df_p["first_name"],
                "Last Name": df_p["last_name"],
                "Perfect Attendance Date": df_p["pa_date"].dt.strftime("%m/%d/%Y"),
                "Status": df_p["status"],
                "Point": "",
                "Reason": "$75 Perfect Attendance Bonus",
                "Note": "",
                "Point Total": pd.to_numeric(df_p["pt"], errors="coerce").fillna(0).round(1),
                "Flag Code": "",
            })

            st.dataframe(df_out_p, use_container_width=True, hide_index=True)
            csv = df_out_p.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download CSV", csv, "preview_perfect_attendance.csv",
                "text/csv", key="dl_preview_pa",
            )

    st.markdown("#### Preview YTD Roll Offs")
    st.caption("Shows missed/due and upcoming YTD roll-off opportunities by monthly cycle.")

    month_offsets = [-2, -1, 0, 1]
    ytd_preview_rows = []

    for offset in month_offsets:
        y = today.year + ((today.month - 1 + offset) // 12)
        m = ((today.month - 1 + offset) % 12) + 1
        cycle_month = date(y, m, 1)
        cycle_run_date = _first_workday_of_month(cycle_month)

        cycle_items = services.preview_ytd_rolloffs(conn, run_date=cycle_run_date)
        for employee_id, net_points, roll_date, label in cycle_items:
            already = _fetchone_sql(
                conn,
                """
                SELECT 1
                  FROM points_history
                 WHERE employee_id = ?
                   AND point_date = ?
                   AND reason = 'YTD Roll-Off'
                   AND note LIKE ?
                 LIMIT 1;
                """,
                (int(employee_id), roll_date.isoformat(), f"%{label}%"),
            )
            status = "Applied" if already else ("Missed / Due" if cycle_run_date <= today else "Upcoming")
            ytd_preview_rows.append(
                {
                    "Employee #": str(employee_id),
                    "Cycle Month": cycle_month.strftime("%b %Y"),
                    "Run Date": cycle_run_date.strftime("%m/%d/%Y"),
                    "Roll-Off Date": roll_date.strftime("%m/%d/%Y"),
                    "Status": status,
                    "Points": f"-{float(net_points):.1f}",
                    "Reason": "YTD Roll-Off",
                    "Note": f"YTD roll-off for {label}",
                    "Flag Code": "AUTO",
                }
            )

    if not ytd_preview_rows:
        st.info("No missed/due or upcoming YTD roll-offs found for recent cycles.")
    else:
        df_ytd_preview = pd.DataFrame(ytd_preview_rows)
        st.dataframe(df_ytd_preview, use_container_width=True, hide_index=True)
        st.download_button(
            "Download CSV",
            df_ytd_preview.to_csv(index=False).encode("utf-8"),
            "preview_ytd_rolloffs_all_statuses.csv",
            "text/csv",
            key="dl_preview_ytd_all_statuses",
        )

    st.divider()

    # ============================================================
    # 3) Actions (Modifies Database)
    # ============================================================
    st.markdown("### Actions (Modifies Database)")
    st.caption("These buttons write changes to the database and generate a CSV of what changed.")

    monthly_run_default = _first_workday_of_month(today)
    monthly_run_date = st.date_input(
        "Monthly update run date (first work day)",
        value=monthly_run_default,
        format="MM/DD/YYYY",
        key="monthly_run_date",
        help="Use the first work day of the month (Mon-Fri).",
    )

    # ---- Perform 2 Month Roll Off ----
    st.markdown("#### Perform 2 Month Roll Off")
    st.caption(
        "Applies all points due for roll-off as of today. "
        "ALL remaining points roll off at once per employee. "
        "Roll-off resets the roll-off clock. YTD entries are excluded from the clock."
    )

    confirm_roll = st.checkbox(
        "I understand this will write roll-off entries to the database.",
        key="confirm_2mo_rolloff",
    )

    if st.button("Perform 2 Month Roll Off (Commit)", key="btn_commit_rolloff") and confirm_roll:
        applied = services.apply_2mo_rolloffs(conn, run_date=monthly_run_date, dry_run=False)

        if not applied:
            st.info("No roll-offs were applied (nothing due today or earlier, or point totals already at 0).")
        else:
            log = [
                {
                    "Employee #": str(r["employee_id"]),
                    "First Name": r["first_name"],
                    "Last Name": r["last_name"],
                    "Roll-Off Date": monthly_run_date.strftime("%Y-%m-%d"),
                    "Points Removed": r["points_removed"],
                    "New Total": r["new_total"],
                    "Reason": "2 Month Roll Off",
                    "Flag Code": "AUTO",
                }
                for r in applied
            ]
            df_log = pd.DataFrame(log)
            st.success(f"Applied roll-offs for {len(df_log)} employee(s).")
            st.dataframe(df_log, use_container_width=True, hide_index=True)
            csv = df_log.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download CSV", csv, "apply_2_month_rolloffs.csv",
                "text/csv", key="dl_apply_rolloffs",
            )

    st.divider()

    # ---- Annual (YTD) Roll Off ----
    st.markdown("#### Annual Roll Off (YTD)")
    st.caption(
        "Shows employees with net-positive points in last year's same month window "
        "that are due for YTD roll-off now (including missed/due if not yet applied)."
    )

    ytd_items = services.preview_ytd_rolloffs(conn, run_date=monthly_run_date)
    if not ytd_items:
        st.info("No annual (YTD) roll-offs are due.")
    else:
        ytd_rows = []
        for employee_id, net_points, roll_date, label in ytd_items:
            ytd_rows.append(
                {
                    "Employee #": str(employee_id),
                    "Roll-Off Date": roll_date.strftime("%m/%d/%Y"),
                    "Points": f"-{float(net_points):.1f}",
                    "Reason": "YTD Roll-Off",
                    "Note": f"YTD roll-off for {label}",
                    "Flag Code": "AUTO",
                }
            )
        df_ytd = pd.DataFrame(ytd_rows)
        st.dataframe(df_ytd, use_container_width=True, hide_index=True)
        st.download_button(
            "Download CSV",
            df_ytd.to_csv(index=False).encode("utf-8"),
            "preview_ytd_rolloffs.csv",
            "text/csv",
            key="dl_preview_ytd_rolloffs",
        )

    confirm_ytd = st.checkbox(
        "I understand this will write annual (YTD) roll-off entries to the database.",
        key="confirm_ytd_rolloff",
    )
    if st.button("Perform Annual Roll Off (Commit)", key="btn_commit_ytd_rolloff") and confirm_ytd:
        applied_ytd = services.apply_ytd_rolloffs(conn, run_date=monthly_run_date, dry_run=False)
        if not applied_ytd:
            st.info("No annual (YTD) roll-offs were applied.")
        else:
            df_applied_ytd = pd.DataFrame(
                [
                    {
                        "Employee #": str(employee_id),
                        "Points Removed": f"-{float(net_points):.1f}",
                        "Roll-Off Date": roll_date.strftime("%m/%d/%Y"),
                        "Label": label,
                    }
                    for employee_id, net_points, roll_date, label in applied_ytd
                ]
            )
            st.success(f"Applied annual (YTD) roll-offs for {len(df_applied_ytd)} employee(s).")
            st.dataframe(df_applied_ytd, use_container_width=True, hide_index=True)
            st.download_button(
                "Download CSV",
                df_applied_ytd.to_csv(index=False).encode("utf-8"),
                "apply_ytd_rolloffs.csv",
                "text/csv",
                key="dl_apply_ytd_rolloffs",
            )

    st.divider()

    # ---- Perfect Attendance Status ----
    st.markdown("#### Perfect Attendance Status")
    st.caption(
        "Perfect attendance dates are maintained automatically by the system whenever "
        "a point is added, edited, or deleted. This section shows employees whose "
        "perfect attendance bonus is due on or before today."
    )

    if _is_pg_conn(conn):
        due_pa = _fetchall_sql(
            conn,
            """
            SELECT employee_id, first_name, last_name,
                   perfect_attendance AS pa_date,
                   COALESCE(point_total, 0.0) AS pt
              FROM employees
             WHERE perfect_attendance IS NOT NULL
               AND (perfect_attendance::date) <= CURRENT_DATE
             ORDER BY (perfect_attendance::date) ASC, last_name, first_name;
            """,
        )
    else:
        due_pa = _fetchall_sql(
            conn,
            """
            SELECT employee_id, first_name, last_name,
                   perfect_attendance AS pa_date,
                   COALESCE(point_total, 0.0) AS pt
              FROM employees
             WHERE perfect_attendance IS NOT NULL
               AND date(perfect_attendance) <= date('now')
             ORDER BY date(perfect_attendance) ASC, last_name, first_name;
            """,
        )

    if not due_pa:
        st.info("No perfect attendance bonuses are due as of today.")
    else:
        df_due = pd.DataFrame([dict(r) for r in due_pa])
        df_due["pa_date"] = pd.to_datetime(df_due["pa_date"], errors="coerce").dt.strftime("%m/%d/%Y")
        st.warning(
            f"{len(df_due)} employee(s) have a perfect attendance date on or before today. "
            "After processing payroll, use the button below to advance due dates."
        )
        df_display = pd.DataFrame({
            "Employee #": df_due["employee_id"].astype(str),
            "First Name": df_due["first_name"],
            "Last Name": df_due["last_name"],
            "Perfect Attendance Date": df_due["pa_date"],
            "Point Total": df_due["pt"].apply(lambda v: f"{float(v):.1f}"),
        })
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        csv = df_display.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV", csv, "perfect_attendance_due.csv",
            "text/csv", key="dl_pa_due",
        )

        if st.button("Advance Due Perfect Attendance Dates", key="btn_adv_pa_due"):
            advanced = services.advance_due_perfect_attendance_dates(conn, run_date=monthly_run_date, dry_run=False)
            if not advanced:
                st.info("No perfect attendance dates were advanced.")
            else:
                df_adv = pd.DataFrame([
                    {
                        "Employee #": str(r["employee_id"]),
                        "First Name": r["first_name"],
                        "Last Name": r["last_name"],
                        "Old Perfect Date": r["old_perfect_attendance"],
                        "New Perfect Date": r["new_perfect_attendance"],
                        "Months Advanced": int(r["months_advanced"]),
                    }
                    for r in advanced
                ])
                st.success(f"Advanced perfect attendance dates for {len(df_adv)} employee(s).")
                st.dataframe(df_adv, use_container_width=True, hide_index=True)
                st.download_button(
                    "Download Advance Log CSV",
                    df_adv.to_csv(index=False).encode("utf-8"),
                    "perfect_attendance_advance_log.csv",
                    "text/csv",
                    key="dl_pa_advance_log",
                )

    st.divider()

    # ============================================================
    # 4) Employee Point History PDF
    # ============================================================
    st.markdown("### Employee Point History PDF")
    st.caption("Generate a PDF of an employee's full point history for personnel records.")

    all_emp_rows = repo.search_employees(conn, q="", active_only=False, limit=5000)
    all_employees = [dict(r) for r in all_emp_rows]

    if not all_employees:
        st.info("No employees found.")
    else:
        pdf_options = [
            (
                str(e["employee_id"]),
                f'{e["employee_id"]} — {e.get("last_name", "")}, '
                f'{e.get("first_name", "")} ({e.get("location", "")})'
            )
            for e in all_employees
        ]

        default_pdf_index = 0
        selected_emp_id_pdf = st.session_state.get("selected_emp_id")
        if selected_emp_id_pdf is not None:
            sel_str = str(selected_emp_id_pdf)
            for i, opt in enumerate(pdf_options):
                if opt[0] == sel_str:
                    default_pdf_index = i
                    break

        selected_pdf_emp = st.selectbox(
            "Select employee for PDF",
            pdf_options,
            format_func=lambda x: x[1],
            index=default_pdf_index,
            key="report_pdf_employee",
        )

        if selected_pdf_emp:
            report_emp_id = int(selected_pdf_emp[0])
            emp_row = repo.get_employee(conn, report_emp_id)
            emp = dict(emp_row) if emp_row else None

            if emp:
                if _is_pg_conn(conn):
                    history_rows = _fetchall_sql(
                        conn,
                        """
                        SELECT point_date, points, reason, note, flag_code
                          FROM points_history
                         WHERE employee_id = %s
                         ORDER BY (point_date::date), id;
                        """,
                        (report_emp_id,),
                    )
                else:
                    history_rows = _fetchall_sql(
                        conn,
                        """
                        SELECT point_date, points, reason, note, flag_code
                          FROM points_history
                         WHERE employee_id = ?
                         ORDER BY date(point_date), id;
                        """,
                        (report_emp_id,),
                    )
                history_list = [dict(r) for r in history_rows]

                pdf_bytes = build_point_history_pdf(emp, history_list)
                file_name = f"employee_{report_emp_id}_point_history.pdf"

                st.write(f"History entries included: **{len(history_list)}**")
                st.download_button(
                    "Download Employee Point History PDF",
                    data=pdf_bytes,
                    file_name=file_name,
                    mime="application/pdf",
                    key="dl_employee_point_history_pdf",
                )
            else:
                st.warning("Selected employee could not be loaded.")
