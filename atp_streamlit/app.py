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
            --bg: #f2f5fb;
            --surface: #ffffff;
            --surface-soft: #f8faff;
            --line: #d9e2f0;
            --text: #15243d;
            --muted: #5f7395;
            --navy-1: #0f1f3d;
            --navy-2: #1b2f54;
            --primary: #3f6fe8;
            --accent: #1dc8b0;
        }

        .stApp {
            background: radial-gradient(1000px 420px at 8% -8%, rgba(63,111,232,.08), transparent 42%), var(--bg);
            color: var(--text);
        }

        .block-container { max-width: 1500px; padding-top: 1.1rem; }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, var(--navy-1) 0%, var(--navy-2) 100%);
            border-right: 1px solid #304a79;
            width: 320px !important;
        }
        section[data-testid="stSidebar"] * { color: #eaf1ff !important; }

        /* make sidebar controls stand out */
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div,
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"],
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] input {
            background: #f3f7ff !important;
            color: #1a2943 !important;
            border-radius: 10px !important;
            border: 2px solid #5f8dff !important;
            box-shadow: 0 0 0 2px rgba(95,141,255,.18);
        }

        .hero {
            background: linear-gradient(120deg, #ecf3ff, #f4fbff);
            border: 1px solid #c9daf8;
            border-left: 5px solid var(--primary);
            border-radius: 16px;
            padding: 1.15rem 1.3rem;
            box-shadow: 0 8px 22px rgba(28,54,102,.08);
            margin-bottom: .95rem;
        }

        .cool-card {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: .95rem 1rem;
            box-shadow: 0 8px 20px rgba(17,41,84,.06);
            margin-bottom: .75rem;
        }

        .dash-card {
            background: linear-gradient(180deg, #ffffff, #f8fbff);
            border: 1px solid #d4e0f5;
            border-radius: 14px;
            padding: .9rem 1rem;
            margin-bottom: .65rem;
            box-shadow: 0 8px 18px rgba(17,41,84,.06);
        }

        div[data-testid="stMetric"] {
            background: #fff;
            border: 1px solid #d9e3f4;
            border-top: 3px solid var(--primary);
            border-radius: 12px;
            padding: 12px 12px;
        }
        div[data-testid="stMetricLabel"] { color: var(--muted); }
        div[data-testid="stMetricValue"] { color: var(--text); }

        .stButton>button {
            border-radius: 10px;
            border: 1px solid #4f74db;
            background: linear-gradient(120deg, #3d67dd, #39b9ad);
            color: #fff;
            font-weight: 600;
        }
        .stButton>button:hover { filter: brightness(1.05); }

        .stDataFrame, .stTabs [data-baseweb="tab-panel"] {
            border: 1px solid var(--line);
            border-radius: 12px;
            background: var(--surface);
        }

        h1,h2,h3,h4,h5 { color: var(--text) !important; }
        p,label,.stCaption { color: var(--muted) !important; }
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

    st.markdown(
        """
        <div class='hero'>
            <h2 style='margin:0 0 .35rem 0; color:#142647'>Attendance Ops Dashboard</h2>
            <div style='color:#4f6488'>Interactive command center for activity trends, upcoming deadlines, and one-click actions.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    controls = st.columns([1.25, 1, 1], gap="small")
    with controls[0]:
        window_label = st.selectbox("Activity window", ["7 days", "14 days", "30 days", "60 days"], index=2)
    with controls[1]:
        show_only_flagged = st.toggle("Only flagged (≥2 points)", value=False)
    with controls[2]:
        top_n = st.slider("Leaderboard size", min_value=5, max_value=25, value=10, step=5)

    days = int(window_label.split()[0])
    start_date = date.today() - timedelta(days=days)
    placeholders = ",".join(["%s" if is_pg(conn) else "?"] * len(emp_ids))

    # KPI counts
    if is_pg(conn):
        sql_recent = f"""
            SELECT COUNT(DISTINCT employee_id) AS active
            FROM points_history
            WHERE employee_id IN ({placeholders})
              AND points > 0
              AND (point_date::date) >= (%s::date)
        """
    else:
        sql_recent = f"""
            SELECT COUNT(DISTINCT employee_id) AS active
            FROM points_history
            WHERE employee_id IN ({placeholders})
              AND points > 0
              AND date(point_date) >= date(?)
        """

    active_recent = int(fetchall_sql(conn, sql_recent, (*emp_ids, start_date.isoformat()))[0]["active"] or 0)

    def count_due(col: str, days_out: int):
        due_date = (date.today() + timedelta(days=days_out)).isoformat()
        if is_pg(conn):
            sql = f"SELECT COUNT(*) AS c FROM employees WHERE employee_id IN ({placeholders}) AND {col} IS NOT NULL AND ({col}::date) <= (%s::date)"
        else:
            sql = f"SELECT COUNT(*) AS c FROM employees WHERE employee_id IN ({placeholders}) AND {col} IS NOT NULL AND date({col}) <= date(?)"
        return int(fetchall_sql(conn, sql, (*emp_ids, due_date))[0]["c"] or 0)

    roll30 = count_due("rolloff_date", 30)
    perf60 = count_due("perfect_attendance", 60)

    if is_pg(conn):
        trend_sql = f"""
            SELECT (point_date::date)::text AS d, COUNT(*) AS events
            FROM points_history
            WHERE employee_id IN ({placeholders})
              AND (point_date::date) >= (%s::date)
            GROUP BY (point_date::date)
            ORDER BY (point_date::date)
        """
    else:
        trend_sql = f"""
            SELECT date(point_date) AS d, COUNT(*) AS events
            FROM points_history
            WHERE employee_id IN ({placeholders})
              AND date(point_date) >= date(?)
            GROUP BY date(point_date)
            ORDER BY date(point_date)
        """
    trend_df = pd.DataFrame([dict(r) for r in fetchall_sql(conn, trend_sql, (*emp_ids, start_date.isoformat()))])

    # leaderboard
    if is_pg(conn):
        leader_sql = f"""
            SELECT e.employee_id, e.first_name, e.last_name, COALESCE(e."Location", '') AS location,
                   COALESCE(e.point_total,0) AS point_total
            FROM employees e
            WHERE e.employee_id IN ({placeholders})
            ORDER BY COALESCE(e.point_total,0) DESC, e.last_name, e.first_name
            LIMIT %s
        """
        leader_params = (*emp_ids, int(top_n))
    else:
        leader_sql = f"""
            SELECT e.employee_id, e.first_name, e.last_name, COALESCE(e."Location", '') AS location,
                   COALESCE(e.point_total,0) AS point_total
            FROM employees e
            WHERE e.employee_id IN ({placeholders})
            ORDER BY COALESCE(e.point_total,0) DESC, e.last_name, e.first_name
            LIMIT ?
        """
        leader_params = (*emp_ids, int(top_n))

    leaders = pd.DataFrame([dict(r) for r in fetchall_sql(conn, leader_sql, leader_params)])
    if show_only_flagged and not leaders.empty:
        leaders = leaders[pd.to_numeric(leaders["point_total"], errors="coerce").fillna(0) >= 2]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"Active in {days} days", active_recent)
    m2.metric("Roll-offs due ≤30d", roll30)
    m3.metric("Perfect attendance ≤60d", perf60)
    m4.metric("Total employees", len(emp_ids))

    left, right = st.columns([1.65, 1], gap="large")
    with left:
        st.markdown("#### Activity trend")
        if trend_df.empty:
            st.caption("No activity for selected window.")
        else:
            trend_df["d"] = pd.to_datetime(trend_df["d"], errors="coerce")
            trend_df = trend_df.sort_values("d")
            st.line_chart(trend_df.set_index("d")["events"], color="#4f7dff", height=270)

        st.markdown("#### Top employees by points")
        if leaders.empty:
            st.caption("No employees match current filters.")
        else:
            display = leaders.copy()
            display["employee"] = display["last_name"].astype(str) + ", " + display["first_name"].astype(str)
            display = display[["employee_id", "employee", "location", "point_total"]]
            display.columns = ["Employee #", "Employee", "Building", "Point Total"]
            st.dataframe(display, use_container_width=True, hide_index=True)

    with right:
        st.markdown("#### Quick actions")
        st.markdown("<div class='dash-card'><b>Review roll-offs now</b><br><span style='color:#a8b8d8'>Jump to reports with roll-off preset.</span></div>", unsafe_allow_html=True)
        if st.button("Open roll-off exports", use_container_width=True, key="dash_export"):
            st.session_state["page"] = "Exports & Forecasts"
            st.session_state["export_type"] = "upcoming 2-month roll-offs"
            st.rerun()

        st.markdown("<div class='dash-card'><b>Record attendance event</b><br><span style='color:#a8b8d8'>Launch ledger entry workflow.</span></div>", unsafe_allow_html=True)
        if st.button("Open points ledger", use_container_width=True, key="dash_ledger"):
            st.session_state["page"] = "Points Ledger"
            st.rerun()

        st.markdown("<div class='dash-card'><b>Run maintenance jobs</b><br><span style='color:#a8b8d8'>Use dry-run and commit controls.</span></div>", unsafe_allow_html=True)
        if st.button("Open system updates", use_container_width=True, key="dash_sys"):
            st.session_state["page"] = "System Updates"
            st.rerun()



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
    st.caption("Professional attendance operations workspace")

    conn = get_conn()

    st.sidebar.subheader("Navigation")
    page = st.sidebar.radio(
        "Navigation menu",
        ["Dashboard", "Employees", "Points Ledger", "Manage Employees", "Exports & Forecasts", "System Updates"],
        key="page",
        label_visibility="collapsed",
    )
    st.sidebar.markdown("### Building filter")
    building = st.sidebar.selectbox("Building filter", ["All", *BUILDINGS], key="global_building", label_visibility="collapsed")

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
