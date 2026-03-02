from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import io
import sys

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Attendance Point Tracker", page_icon="📅", layout="wide")

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import atp_core.db as db
from atp_core.schema import ensure_schema
from atp_core import repo, services
from atp_core.rules import REASON_OPTIONS


BUILDINGS = ["Building A", "Building B", "Building C"]


def get_conn():
    conn = db.connect()
    ensure_schema(conn)
    return conn


def is_pg(conn) -> bool:
    return conn.__class__.__module__.startswith("psycopg2")


def fetchall_sql(conn, sql: str, params=()):
    if is_pg(conn):
        cur = conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        rows = cur.fetchall()
        cur.close()
        return rows
    return conn.execute(sql, params).fetchall()


def exec_sql(conn, sql: str, params=()):
    if is_pg(conn):
        cur = conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        cur.close()
        return
    conn.execute(sql, params)


def fmt_date(val):
    if not val:
        return "—"
    if hasattr(val, "strftime"):
        return val.strftime("%m/%d/%Y")
    try:
        return datetime.strptime(str(val), "%Y-%m-%d").strftime("%m/%d/%Y")
    except ValueError:
        return str(val)


def load_employees(conn, q: str = "", building: str = "All") -> list[dict]:
    rows = [dict(r) for r in repo.search_employees(conn, q=q, limit=3000)]
    if building != "All":
        rows = [r for r in rows if (r.get("location") or "") == building]
    return rows


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def run_export_query(conn, export_type: str, building: str, start_date: date, end_date: date) -> pd.DataFrame:
    if export_type == "30-day point history":
        if is_pg(conn):
            sql = """
            SELECT e.employee_id, e.first_name, e.last_name, COALESCE(e."Location", '') AS location,
                   p.point_date, p.points, p.reason, COALESCE(p.note, '') AS note
              FROM points_history p
              JOIN employees e ON e.employee_id = p.employee_id
             WHERE (p.point_date::date) BETWEEN (%s::date) AND (%s::date)
            """
        else:
            sql = """
            SELECT e.employee_id, e.first_name, e.last_name, COALESCE(e."Location", '') AS location,
                   p.point_date, p.points, p.reason, COALESCE(p.note, '') AS note
              FROM points_history p
              JOIN employees e ON e.employee_id = p.employee_id
             WHERE date(p.point_date) BETWEEN date(?) AND date(?)
            """
        params = [start_date.isoformat(), end_date.isoformat()]

    elif export_type == "upcoming 2-month roll-offs":
        if is_pg(conn):
            sql = """
            SELECT employee_id, first_name, last_name, COALESCE("Location", '') AS location,
                   point_total, rolloff_date
              FROM employees
             WHERE rolloff_date IS NOT NULL
               AND (rolloff_date::date) BETWEEN (%s::date) AND (%s::date)
            """
        else:
            sql = """
            SELECT employee_id, first_name, last_name, COALESCE("Location", '') AS location,
                   point_total, rolloff_date
              FROM employees
             WHERE rolloff_date IS NOT NULL
               AND date(rolloff_date) BETWEEN date(?) AND date(?)
            """
        params = [start_date.isoformat(), end_date.isoformat()]

    elif export_type == "upcoming perfect attendance":
        if is_pg(conn):
            sql = """
            SELECT employee_id, first_name, last_name, COALESCE("Location", '') AS location,
                   point_total, perfect_attendance
              FROM employees
             WHERE perfect_attendance IS NOT NULL
               AND (perfect_attendance::date) BETWEEN (%s::date) AND (%s::date)
            """
        else:
            sql = """
            SELECT employee_id, first_name, last_name, COALESCE("Location", '') AS location,
                   point_total, perfect_attendance
              FROM employees
             WHERE perfect_attendance IS NOT NULL
               AND date(perfect_attendance) BETWEEN date(?) AND date(?)
            """
        params = [start_date.isoformat(), end_date.isoformat()]
    else:
        year_start = date(date.today().year, 1, 1)
        if is_pg(conn):
            sql = """
            SELECT e.employee_id, e.first_name, e.last_name, COALESCE(e."Location", '') AS location,
                   p.point_date, p.points, p.reason, COALESCE(p.note, '') AS note
              FROM points_history p
              JOIN employees e ON e.employee_id = p.employee_id
             WHERE p.reason = 'YTD Roll-Off'
               AND (p.point_date::date) >= (%s::date)
            """
        else:
            sql = """
            SELECT e.employee_id, e.first_name, e.last_name, COALESCE(e."Location", '') AS location,
                   p.point_date, p.points, p.reason, COALESCE(p.note, '') AS note
              FROM points_history p
              JOIN employees e ON e.employee_id = p.employee_id
             WHERE p.reason = 'YTD Roll-Off'
               AND date(p.point_date) >= date(?)
            """
        params = [year_start.isoformat()]

    if building != "All":
        sql += " AND COALESCE(e.\"Location\", '') = ?" if " JOIN employees e" in sql else " AND COALESCE(\"Location\", '') = ?"
        params.append(building)

    sql += " ORDER BY last_name, first_name"
    return pd.DataFrame([dict(r) for r in fetchall_sql(conn, sql, tuple(params))])


def dashboard_page(conn, building: str):
    st.subheader("Dashboard")
    employees = load_employees(conn, building=building)
    emp_ids = [int(e["employee_id"]) for e in employees]

    if not emp_ids:
        st.info("No employees found for this building filter.")
        return

    placeholders = ",".join(["%s" if is_pg(conn) else "?"] * len(emp_ids))

    if is_pg(conn):
        recent_sql = f"""
            SELECT
                COUNT(DISTINCT CASE WHEN (point_date::date) >= (%s::date) THEN employee_id END) AS c7,
                COUNT(DISTINCT CASE WHEN (point_date::date) >= (%s::date) THEN employee_id END) AS c30
            FROM points_history
            WHERE employee_id IN ({placeholders})
              AND points > 0
        """
    else:
        recent_sql = f"""
            SELECT
                COUNT(DISTINCT CASE WHEN date(point_date) >= date(?) THEN employee_id END) AS c7,
                COUNT(DISTINCT CASE WHEN date(point_date) >= date(?) THEN employee_id END) AS c30
            FROM points_history
            WHERE employee_id IN ({placeholders})
              AND points > 0
        """
    recent = dict(fetchall_sql(conn, recent_sql, (date.today() - timedelta(days=7), date.today() - timedelta(days=30), *emp_ids))[0])

    def count_due(col: str, days: int):
        if is_pg(conn):
            sql = f"SELECT COUNT(*) AS c FROM employees WHERE employee_id IN ({placeholders}) AND {col} IS NOT NULL AND ({col}::date) <= (%s::date)"
        else:
            sql = f"SELECT COUNT(*) AS c FROM employees WHERE employee_id IN ({placeholders}) AND {col} IS NOT NULL AND date({col}) <= date(?)"
        return int(fetchall_sql(conn, sql, (*emp_ids, (date.today() + timedelta(days=days)).isoformat()))[0]["c"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Points added (7 days)", int(recent.get("c7") or 0))
    c2.metric("Points added (30 days)", int(recent.get("c30") or 0))
    c3.metric("Roll-offs due ≤ 30 days", count_due("rolloff_date", 30))
    c4.metric("Perfect attendance due ≤ 60 days", count_due("perfect_attendance", 60))

    st.markdown("### Action cards")
    a1, a2, a3 = st.columns(3)
    if a1.button("Open Exports: Roll-offs next 30 days", use_container_width=True):
        st.session_state["page"] = "Exports & Forecasts"
        st.session_state["export_type"] = "upcoming 2-month roll-offs"
        st.rerun()
    if a2.button("Open Ledger", use_container_width=True):
        st.session_state["page"] = "Points Ledger"
        st.rerun()
    if a3.button("Open Maintenance", use_container_width=True):
        st.session_state["page"] = "System Updates"
        st.rerun()


def employees_page(conn, building: str):
    st.subheader("Employees")
    q = st.text_input("Search by employee #, last name, or first name")
    rows = load_employees(conn, q=q, building=building)
    if not rows:
        st.info("No matching employees.")
        return

    df = pd.DataFrame(rows)
    df["employee_id"] = df["employee_id"].astype(int)
    st.dataframe(df[["employee_id", "last_name", "first_name", "location", "is_active"]], use_container_width=True, hide_index=True)

    emp_options = [(int(r["employee_id"]), f"{r['employee_id']} — {r['last_name']}, {r['first_name']}") for r in rows]
    selected = st.selectbox("Select employee", emp_options, format_func=lambda x: x[1])
    emp_id = selected[0]

    emp = dict(repo.get_employee(conn, emp_id))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Point Total", f"{float(emp.get('point_total') or 0):.1f}")
    c2.metric("Next Roll-Off", fmt_date(emp.get("rolloff_date")))
    c3.metric("Perfect Attendance", fmt_date(emp.get("perfect_attendance")))
    c4.metric("Last Point Change", fmt_date(emp.get("last_point_date")))

    hist = pd.DataFrame([dict(r) for r in repo.get_points_history(conn, emp_id, limit=25)])
    st.markdown("#### Recent point history")
    if hist.empty:
        st.caption("No history yet.")
    else:
        st.dataframe(hist[["point_date", "points", "reason", "note", "point_total"]], use_container_width=True, hide_index=True)


def points_ledger_page(conn, building: str):
    st.subheader("Points Ledger")
    employees = load_employees(conn, building=building)
    if not employees:
        st.info("No employees available.")
        return

    opts = [(int(e["employee_id"]), f"{e['employee_id']} — {e['last_name']}, {e['first_name']}") for e in employees]
    selected = st.selectbox("Employee", opts, format_func=lambda x: x[1])
    emp_id = selected[0]

    with st.form("ledger_entry"):
        p_date = st.date_input("Transaction date", value=date.today())
        points = st.number_input("Points (+ add, - remove)", step=0.5, value=0.5)
        reason = st.selectbox("Reason", REASON_OPTIONS)
        note = st.text_input("Reason details")
        submitted = st.form_submit_button("Post transaction")

    if submitted:
        try:
            preview = services.preview_add_point(emp_id, p_date, points, reason, note)
            services.add_point(conn, preview)
            st.success("Ledger entry saved.")
            st.rerun()
        except Exception as e:
            st.error(str(e))

    hist = pd.DataFrame([dict(r) for r in repo.get_points_history(conn, emp_id, limit=100)])
    st.markdown("#### Ledger history")
    if hist.empty:
        st.caption("No ledger history.")
    else:
        st.dataframe(hist[["id", "point_date", "points", "reason", "note", "point_total"]], use_container_width=True, hide_index=True)
        if st.button("Undo last change"):
            try:
                last = hist.iloc[0]
                services.delete_point_history_entry(conn, point_id=int(last["id"]), employee_id=emp_id)
                st.success("Last ledger change was removed.")
                st.rerun()
            except Exception as e:
                st.error(str(e))


def manage_employees_page(conn):
    st.subheader("Manage Employees")
    a, b = st.tabs(["Add", "Edit/Archive"])

    with a:
        with st.form("add_employee"):
            emp_id = st.number_input("Employee #", min_value=1, step=1)
            first = st.text_input("First name")
            last = st.text_input("Last name")
            location = st.selectbox("Building", ["", *BUILDINGS])
            submitted = st.form_submit_button("Add employee")
        if submitted:
            try:
                services.create_employee(conn, int(emp_id), last, first, location)
                conn.commit()
                st.success("Employee added.")
            except Exception as e:
                st.error(str(e))

    with b:
        rows = [dict(r) for r in repo.search_employees(conn, q="", active_only=False, limit=3000)]
        options = [(int(r["employee_id"]), f"{r['employee_id']} — {r['last_name']}, {r['first_name']}") for r in rows]
        selected = st.selectbox("Employee to edit", options, format_func=lambda x: x[1])
        emp = dict(repo.get_employee(conn, selected[0]))

        with st.form("edit_employee"):
            first = st.text_input("First name", value=emp.get("first_name") or "")
            last = st.text_input("Last name", value=emp.get("last_name") or "")
            location = st.selectbox("Building", ["", *BUILDINGS], index=max(["", *BUILDINGS].index(emp.get("location") or "") if (emp.get("location") or "") in ["", *BUILDINGS] else 0, 0))
            active = st.checkbox("Active", value=bool(emp.get("is_active", 1)))
            submitted = st.form_submit_button("Save changes")

        if submitted:
            try:
                exec_sql(conn, "UPDATE employees SET first_name = ?, last_name = ?, \"Location\" = ?, is_active = ? WHERE employee_id = ?", (first.strip(), last.strip(), location or None, 1 if active else 0, selected[0]))
                conn.commit()
                st.success("Employee updated.")
            except Exception as e:
                st.error(str(e))

        st.markdown("---")
        delete_confirm = st.checkbox("I understand delete permanently removes employee and history.")
        if st.button("Delete employee"):
            if not delete_confirm:
                st.error("Check confirmation first.")
            else:
                try:
                    services.delete_employee(conn, selected[0])
                    conn.commit()
                    st.success("Employee deleted.")
                except Exception as e:
                    st.error(str(e))


def exports_page(conn, building: str):
    st.subheader("Exports & Forecasts")
    export_type = st.selectbox(
        "Export type",
        ["30-day point history", "upcoming 2-month roll-offs", "upcoming perfect attendance", "upcoming annual roll-off"],
        key="export_type",
    )
    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Start date", value=date.today() - timedelta(days=30))
    with c2:
        end_date = st.date_input("End date", value=date.today() + timedelta(days=60))

    df = run_export_query(conn, export_type, building, start_date, end_date)
    if df.empty:
        st.info("No rows found for current filters.")
        return

    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Download CSV", data=to_csv_bytes(df), file_name=f"{export_type.replace(' ', '_')}.csv", mime="text/csv")


def system_updates_page(conn):
    st.subheader("System Updates")
    run_date = st.date_input("Run jobs through date", value=date.today())
    dry_run = st.toggle("Dry run", value=True)
    confirm = st.checkbox("I understand this updates the database.")

    if "maintenance_log" not in st.session_state:
        st.session_state["maintenance_log"] = []

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Process roll-offs due through today"):
            if not dry_run and not confirm:
                st.error("You must confirm before running database updates.")
            else:
                rows = services.apply_2mo_rolloffs(conn, run_date=run_date, dry_run=dry_run)
                st.success(f"Processed {len(rows)} employees.")
                st.session_state["maintenance_log"].append({"timestamp": datetime.now().isoformat(timespec="seconds"), "job": "2-month roll-off", "dry_run": dry_run, "count": len(rows)})
                if rows:
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.download_button("Download impacted employees CSV", data=to_csv_bytes(df), file_name="rolloff_impacted.csv", mime="text/csv")

    with c2:
        if st.button("Advance perfect attendance date where eligible"):
            if not dry_run and not confirm:
                st.error("You must confirm before running database updates.")
            else:
                rows = services.advance_due_perfect_attendance_dates(conn, run_date=run_date, dry_run=dry_run)
                st.success(f"Processed {len(rows)} employees.")
                st.session_state["maintenance_log"].append({"timestamp": datetime.now().isoformat(timespec="seconds"), "job": "perfect attendance advance", "dry_run": dry_run, "count": len(rows)})
                if rows:
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.download_button("Download impacted employees CSV", data=to_csv_bytes(df), file_name="perfect_attendance_impacted.csv", mime="text/csv")

    log_df = pd.DataFrame(st.session_state["maintenance_log"])
    st.markdown("#### Run log")
    if log_df.empty:
        st.caption("No jobs run in this session.")
    else:
        st.dataframe(log_df, use_container_width=True, hide_index=True)


def main():
    st.title("Attendance Point Tracker")
    st.caption("Scalable multipage workflow for attendance tracking")

    conn = get_conn()

    st.sidebar.header("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Dashboard", "Employees", "Points Ledger", "Manage Employees", "Exports & Forecasts", "System Updates"],
        key="page",
    )
    building = st.sidebar.selectbox("Building filter", ["All", *BUILDINGS], key="global_building")

    if page == "Dashboard":
        dashboard_page(conn, building)
    elif page == "Employees":
        employees_page(conn, building)
    elif page == "Points Ledger":
        points_ledger_page(conn, building)
    elif page == "Manage Employees":
        manage_employees_page(conn)
    elif page == "Exports & Forecasts":
        exports_page(conn, building)
    else:
        system_updates_page(conn)


if __name__ == "__main__":
    main()
