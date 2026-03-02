from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
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


def apply_theme():
    st.markdown(
        """
        <style>
        :root {
            --bg: #eef1f6;
            --sidebar-top: #0a1631;
            --sidebar-bot: #1f355b;
            --navy: #14284b;
            --navy-2: #253f66;
            --ink: #172338;
            --muted: #5e6f8e;
            --line: #d6dbe7;
            --accent: #c6203d;
            --blue: #3b7ddb;
            --card: #ffffff;
        }

        .stApp {
            background: var(--bg);
            color: var(--ink);
        }

        .block-container {
            padding-top: 1.0rem;
            max-width: 1460px;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, var(--sidebar-top) 0%, var(--sidebar-bot) 100%);
            border-right: 2px solid #c92542;
            width: 295px !important;
        }
        section[data-testid="stSidebar"] * {
            color: #ecf1fa !important;
        }

        .sidebar-profile {
            background: rgba(255,255,255,0.95);
            color: #1f2b40 !important;
            border-radius: 14px;
            padding: .85rem;
            border: 1px solid rgba(0,0,0,.08);
            box-shadow: 0 8px 24px rgba(0,0,0,.18);
            margin-bottom: .8rem;
        }
        .sidebar-profile .name {
            margin-top: .45rem;
            color: #b21934;
            font-weight: 700;
        }

        .hero {
            padding: 1.45rem 1.5rem;
            border-radius: 16px;
            background: linear-gradient(90deg, #081a38 0%, #29436a 100%);
            border-left: 6px solid var(--accent);
            color: #f5f8ff;
            box-shadow: 0 12px 30px rgba(8,19,43,.18);
            margin: .35rem 0 1.15rem 0;
        }

        .section-title {
            color: #1a2740;
            font-size: 2.35rem;
            font-weight: 700;
            margin-bottom: .2rem;
            font-family: Georgia, "Times New Roman", serif;
        }

        .underline-red {
            border-bottom: 3px solid var(--accent);
            margin: .2rem 0 .7rem 0;
        }

        .module-card {
            background: var(--card);
            border: 1px solid var(--line);
            border-left: 5px solid var(--accent);
            border-radius: 14px;
            padding: 1rem 1rem .9rem 1rem;
            box-shadow: 0 6px 16px rgba(26,41,68,.08);
            margin-bottom: .65rem;
        }
        .module-title {
            color: #1d2a40;
            font-size: 1.9rem;
            font-weight: 700;
            font-family: Georgia, "Times New Roman", serif;
            margin-bottom: .35rem;
        }

        .pill {
            display: inline-block;
            padding: .2rem .6rem;
            border-radius: 999px;
            background: #c6203d;
            color: #fff;
            font-size: .74rem;
            font-weight: 700;
            margin-left: .45rem;
        }

        .progress-card {
            background: #ffffff;
            border-radius: 14px;
            border-top: 3px solid var(--accent);
            padding: 1.6rem .9rem;
            box-shadow: 0 6px 16px rgba(26,41,68,.08);
            text-align: center;
            margin-bottom: .7rem;
        }

        div[data-testid="stMetric"] {
            background: #fff;
            border: 1px solid var(--line);
            border-left: 5px solid var(--blue);
            border-radius: 12px;
            padding: 10px 12px;
            box-shadow: 0 4px 12px rgba(26,41,68,.06);
        }
        div[data-testid="stMetricLabel"] { color: #4f607f; }
        div[data-testid="stMetricValue"] { color: #18263f; }

        .stButton > button {
            border-radius: 8px;
            border: 1px solid #bd203c;
            background: #fff;
            color: #bd203c;
            font-weight: 600;
        }
        .stButton > button:hover {
            border-color: #9f1630;
            color: #9f1630;
            background: #fff6f8;
        }

        .stDataFrame {
            background: #fff;
            border: 1px solid var(--line);
            border-radius: 12px;
        }

        [data-testid="stSidebarNav"] { display:none; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_hero(title: str, subtitle: str):
    st.markdown(
        f"""
        <div class='hero'>
            <h3 style='margin:.1rem 0 .35rem 0; color:#ffffff'>{title}</h3>
            <div style='color:#d7e2ff; font-size:.96rem'>{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card_start():
    st.markdown("<div class='cool-card'>", unsafe_allow_html=True)


def card_end():
    st.markdown("</div>", unsafe_allow_html=True)


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

    recent = dict(
        fetchall_sql(
            conn,
            recent_sql,
            (date.today() - timedelta(days=7), date.today() - timedelta(days=30), *emp_ids),
        )[0]
    )

    def count_due(col: str, days: int):
        if is_pg(conn):
            sql = f"SELECT COUNT(*) AS c FROM employees WHERE employee_id IN ({placeholders}) AND {col} IS NOT NULL AND ({col}::date) <= (%s::date)"
        else:
            sql = f"SELECT COUNT(*) AS c FROM employees WHERE employee_id IN ({placeholders}) AND {col} IS NOT NULL AND date({col}) <= date(?)"
        return int(fetchall_sql(conn, sql, (*emp_ids, (date.today() + timedelta(days=days)).isoformat()))[0]["c"])

    c7 = int(recent.get("c7") or 0)
    c30 = int(recent.get("c30") or 0)
    roll30 = count_due("rolloff_date", 30)
    perf60 = count_due("perfect_attendance", 60)

    completed_pct = int(round((c30 / max(1, len(emp_ids))) * 100))
    completed_pct = min(100, completed_pct)

    st.markdown(
        """
        <div class='hero'>
            <h2 style='margin:0 0 .4rem 0; color:#f8fbff; font-family:Georgia,Times New Roman,serif;'>
                Welcome back to Attendance Command Center
            </h2>
            <div style='color:#d9e2f6; font-size:1.04rem;'>
                Monitor workforce attendance activity across buildings, act on due roll-offs, and keep your records current.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.9, 1], gap="large")

    with left:
        st.markdown("<div class='module-title'>Your Priority Modules</div>", unsafe_allow_html=True)
        st.markdown("<div class='underline-red'></div>", unsafe_allow_html=True)

        st.markdown(
            f"""
            <div class='module-card'><b>📊 Weekly Attendance Activity</b> <span class='pill'>{c7} employees</span><br>
            <span style='color:#596a88'>Employees with points posted in the last 7 days.</span></div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Go to Points Ledger →", key="go_ledger"):
            st.session_state["page"] = "Points Ledger"
            st.rerun()

        st.markdown(
            f"""
            <div class='module-card'><b>🗓️ Upcoming 2-Month Roll-Offs</b> <span class='pill'>{roll30} due</span><br>
            <span style='color:#596a88'>Employees due for roll-off action within 30 days.</span></div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Go to Exports & Forecasts →", key="go_export"):
            st.session_state["page"] = "Exports & Forecasts"
            st.session_state["export_type"] = "upcoming 2-month roll-offs"
            st.rerun()

        st.markdown(
            f"""
            <div class='module-card'><b>✅ Perfect Attendance Milestones</b> <span class='pill'>{perf60} upcoming</span><br>
            <span style='color:#596a88'>Milestones expected in the next 60 days.</span></div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Go to System Updates →", key="go_system"):
            st.session_state["page"] = "System Updates"
            st.rerun()

    with right:
        st.markdown("<div class='module-title'>Your Progress</div>", unsafe_allow_html=True)
        st.markdown("<div class='underline-red'></div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class='progress-card'>
                <div style='font-size:3rem; color:#c6203d; font-weight:700; line-height:1.1;'>{completed_pct}%</div>
                <div style='color:#536482'>Current attendance activity completion signal</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.caption("Operational indicators")
        st.progress(min(100, int((c7 / max(1, len(emp_ids))) * 100)), text=f"7-day activity: {c7}")
        st.progress(min(100, int((roll30 / max(1, len(emp_ids))) * 100)), text=f"Roll-offs due (30d): {roll30}")
        st.progress(min(100, int((perf60 / max(1, len(emp_ids))) * 100)), text=f"Perfect attendance due (60d): {perf60}")
        st.progress(min(100, int((c30 / max(1, len(emp_ids))) * 100)), text=f"30-day activity: {c30}")



def employees_page(conn, building: str):
    page_hero("Employees", "Lookup people quickly and view status without accidental edits.")
    card_start()
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
    card_end()


def points_ledger_page(conn, building: str):
    page_hero("Points Ledger", "Record attendance transactions with clean, auditable history.")
    card_start()
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
    card_end()


def manage_employees_page(conn):
    page_hero("Manage Employees", "HR maintenance tools for onboarding, edits, archive, and cleanup.")
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
    page_hero("Exports & Forecasts", "Generate operational files and forward-looking attendance lists.")
    card_start()
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
    card_end()


def system_updates_page(conn):
    page_hero("System Updates", "Run controlled maintenance jobs with dry-run and confirmation guardrails.")
    card_start()
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
    card_end()


def main():
    apply_theme()
    st.title("Attendance Point Tracker")
    st.caption("Attendance operations workspace")

    conn = get_conn()

    logo_path = REPO_ROOT / "assets" / "logo.png"
    sidebar_logo = f"<img src='file://{logo_path}' style='max-width:190px; width:100%; display:block; margin:auto;'>" if logo_path.exists() else "<div style='font-size:1.6rem; font-weight:700;'>ATP</div>"
    st.sidebar.markdown(
        f"""
        <div class='sidebar-profile'>
            {sidebar_logo}
            <div style='text-align:center; margin-top:.35rem; font-size:.74rem; letter-spacing:.08em; color:#4e5d77;'>ATTENDANCE ADMIN</div>
            <div class='name' style='text-align:center;'>👤 HR Team</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    rows_all = load_employees(conn, building="All")
    active_count = sum(1 for r in rows_all if int(r.get("is_active", 1)) == 1)
    pct = min(100, int((active_count / max(1, len(rows_all))) * 100))
    st.sidebar.markdown(f"**PROGRESS · {pct}%**")
    st.sidebar.progress(pct)
    st.sidebar.divider()

    st.sidebar.header("Navigation")
    page = st.sidebar.radio(
        "Navigation menu",
        ["Dashboard", "Employees", "Points Ledger", "Manage Employees", "Exports & Forecasts", "System Updates"],
        key="page",
        label_visibility="collapsed",
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
