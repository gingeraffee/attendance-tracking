"""Attendance Point Tracker — Streamlit Web App
Full remodel: clean layout, status badges, live countdown, improved workflows.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Attendance Point Tracker",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import atp_core.db as db
from atp_core.schema import ensure_schema
from atp_core import repo, services
from atp_core.rules import REASON_OPTIONS

BUILDINGS = ["Building A", "Building B", "Building C"]


# ── Theme ─────────────────────────────────────────────────────────────────────
def apply_theme() -> None:
    st.markdown(
        """<style>
:root {
    --bg:       #f0f4fa;
    --surface:  #ffffff;
    --surface2: #f4f7fd;
    --border:   rgba(0,0,0,.07);
    --shadow:   0 2px 16px rgba(15,32,68,.07);
    --text:     #1a2744;
    --muted:    #5c6f8c;
    --faint:    #8fa0b8;
    --blue:     #4f8ef7;
    --cyan:     #00b8e6;
    --green:    #00a87a;
    --amber:    #e6960a;
    --red:      #e0394a;
}

/* ── Base ── */
.stApp { background: var(--bg); color: var(--text); }
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1440px; }
footer, #MainMenu { visibility: hidden; }

/* ── Sidebar (stays dark) ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1b3a 0%, #0f2044 100%) !important;
    border-right: 1px solid rgba(255,255,255,.06);
    width: 276px !important;
}
section[data-testid="stSidebar"] * { color: #bfcde6 !important; }

/* ── Metric tiles ── */
div[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.1rem 1.25rem .85rem 1.25rem;
    box-shadow: var(--shadow);
}
div[data-testid="stMetric"] label {
    color: var(--muted) !important;
    font-size: .72rem !important;
    font-weight: 700 !important;
    letter-spacing: .08em !important;
    text-transform: uppercase !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: var(--text) !important;
    font-size: 2rem !important;
    font-weight: 800 !important;
    letter-spacing: -.03em !important;
}

/* ── Buttons ── */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    border: 1px solid rgba(79,142,247,.35) !important;
    background: linear-gradient(135deg, rgba(79,142,247,.09), rgba(79,142,247,.04)) !important;
    color: var(--blue) !important;
    transition: all .18s !important;
}
.stButton > button:hover {
    border-color: var(--blue) !important;
    background: rgba(79,142,247,.14) !important;
    box-shadow: 0 0 14px rgba(79,142,247,.18) !important;
}

/* ── DataFrames / Tabs / Inputs ── */
.stDataFrame { border: 1px solid var(--border) !important; border-radius: 12px !important; overflow: hidden; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--border); background: transparent; }
.stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; }
.stTextInput  > div > div > input,
.stNumberInput > div > div > input,
.stDateInput  > div > div > input {
    background: var(--surface2) !important;
    border-color: var(--border) !important;
    border-radius: 8px !important;
    color: var(--text) !important;
}
h1,h2,h3,h4,h5,h6 { color: var(--text) !important; }
p, label { color: var(--muted) !important; }

/* ── Page heading ── */
.page-heading { margin-bottom: 1.4rem; }
.page-heading h1 {
    font-size: 1.6rem; font-weight: 800; color: var(--text);
    margin: 0 0 .15rem 0; letter-spacing: -.025em;
}
.page-heading p { color: var(--muted); font-size: .87rem; margin: 0; }
.accent-bar {
    width: 44px; height: 3px; border-radius: 99px;
    background: linear-gradient(90deg, var(--blue), var(--cyan));
    margin: .25rem 0 .4rem 0;
    box-shadow: 0 0 10px rgba(79,142,247,.30);
}

/* ── Cards ── */
.card    { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 1.2rem 1.4rem; box-shadow: var(--shadow); margin-bottom: .9rem; }
.card-sm { background: var(--surface); border: 1px solid var(--border); border-radius: 10px;  padding: .8rem 1rem;   box-shadow: var(--shadow); }

/* ── Section label ── */
.section-label {
    font-size: .71rem; font-weight: 700; letter-spacing: .10em;
    text-transform: uppercase; color: var(--muted); margin: 0 0 .55rem 0;
}

/* ── Divider ── */
.divider { height: 1px; background: var(--border); margin: 1.25rem 0; }

/* ── Info / warn / danger boxes ── */
.info-box   { background: rgba(79,142,247,.06);  border:1px solid rgba(79,142,247,.18);  border-left:3px solid var(--blue);  border-radius:8px; padding:.75rem 1rem; color:var(--text); font-size:.88rem; }
.warn-box   { background: rgba(230,150,10,.06);  border:1px solid rgba(230,150,10,.18);  border-left:3px solid var(--amber); border-radius:8px; padding:.75rem 1rem; color:var(--text); font-size:.88rem; }
.danger-box { background: rgba(224,57,74,.06);   border:1px solid rgba(224,57,74,.18);   border-left:3px solid var(--red);   border-radius:8px; padding:.75rem 1rem; color:var(--text); font-size:.88rem; }

/* ── Upcoming list rows ── */
.list-row {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: .65rem 1rem; margin-bottom: .38rem;
}

/* ── Sidebar brand ── */
.sidebar-brand { padding: .75rem 0 1rem 0; border-bottom: 1px solid rgba(255,255,255,.07); margin-bottom: 1rem; }
.sidebar-brand .name { font-size: 1.05rem; font-weight: 800; color: #e2e8f4 !important; letter-spacing: -.01em; }
.sidebar-brand .sub  { font-size: .72rem; color: #4a5f80 !important; margin-top: .1rem; }
.sidebar-nav-label   {
    font-size: .65rem !important; font-weight: 700 !important; letter-spacing: .12em !important;
    text-transform: uppercase !important; color: #3d5270 !important;
    margin: 1rem 0 .3rem 0 !important; display: block;
}
</style>""",
        unsafe_allow_html=True,
    )


# ── DB helpers ────────────────────────────────────────────────────────────────
def get_conn():
    conn = db.connect()
    ensure_schema(conn)
    return conn


def is_pg(conn) -> bool:
    return conn.__class__.__module__.startswith("psycopg2")


def fetchall(conn, sql: str, params=()):
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
    else:
        conn.execute(sql, params)


def first_value(rows, default=0):
    """Return the first scalar value from a query result for tuple/dict-like rows."""
    if not rows:
        return default

    row = rows[0]
    if isinstance(row, dict):
        return next(iter(row.values()), default)

    try:
        return row[0]
    except Exception:
        return default


# ── Format helpers ────────────────────────────────────────────────────────────
def fmt_date(val) -> str:
    if not val:
        return "—"
    if hasattr(val, "strftime"):
        return val.strftime("%m/%d/%Y")
    try:
        return datetime.strptime(str(val), "%Y-%m-%d").strftime("%m/%d/%Y")
    except ValueError:
        return str(val)


def days_until(val) -> int | None:
    if not val:
        return None
    try:
        d = val if hasattr(val, "toordinal") else date.fromisoformat(str(val))
        return (d - date.today()).days
    except Exception:
        return None


def pt_badge(pts) -> str:
    """Colored HTML pill for a point total."""
    pts = float(pts or 0)
    if pts == 0:
        c, bg, b, lbl = "#00a87a", "rgba(0,168,122,.10)",  "rgba(0,168,122,.25)",  "0 pts"
    elif pts < 2:
        c, bg, b, lbl = "#e6960a", "rgba(230,150,10,.10)", "rgba(230,150,10,.25)", f"{pts:.1f} pts"
    else:
        c, bg, b, lbl = "#e0394a", "rgba(224,57,74,.10)",  "rgba(224,57,74,.25)",  f"{pts:.1f} pts"
    return (
        f"<span style='display:inline-block;padding:2px 10px;border-radius:99px;"
        f"font-size:.78rem;font-weight:700;color:{c};background:{bg};"
        f"border:1px solid {b}'>{lbl}</span>"
    )


def days_badge(days) -> str:
    """Colored HTML pill for days countdown."""
    s = "display:inline-block;padding:2px 8px;border-radius:6px;font-size:.78rem;font-weight:700;"
    if days is None:
        return f"<span style='{s}color:#8fa0b8'>—</span>"
    if days < 0:
        return f"<span style='{s}color:#e0394a;background:rgba(224,57,74,.09);border:1px solid rgba(224,57,74,.20)'>overdue {abs(days)}d</span>"
    if days == 0:
        return f"<span style='{s}color:#e0394a;background:rgba(224,57,74,.09);border:1px solid rgba(224,57,74,.20)'>today</span>"
    if days <= 14:
        return f"<span style='{s}color:#e6960a;background:rgba(230,150,10,.09);border:1px solid rgba(230,150,10,.20)'>{days}d</span>"
    return f"<span style='{s}color:#5c6f8c;background:rgba(92,111,140,.07);border:1px solid rgba(92,111,140,.17)'>{days}d</span>"


def info_box(msg: str) -> None:
    st.markdown(f"<div class='info-box'>{msg}</div>", unsafe_allow_html=True)


def warn_box(msg: str) -> None:
    st.markdown(f"<div class='warn-box'>{msg}</div>", unsafe_allow_html=True)


def page_heading(title: str, sub: str) -> None:
    st.markdown(
        f"<div class='page-heading'><h1>{title}</h1>"
        f"<div class='accent-bar'></div><p>{sub}</p></div>",
        unsafe_allow_html=True,
    )


def section_label(text: str) -> None:
    st.markdown(f"<div class='section-label'>{text}</div>", unsafe_allow_html=True)


def divider() -> None:
    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)


def to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def load_employees(conn, q: str = "", building: str = "All") -> list[dict]:
    rows = [dict(r) for r in repo.search_employees(conn, q=q, limit=3000)]
    if building != "All":
        rows = [r for r in rows if (r.get("location") or "") == building]
    return rows


# ── Dashboard ─────────────────────────────────────────────────────────────────
def dashboard_page(conn, building: str) -> None:
    page_heading(
        "Dashboard",
        "Real-time overview of attendance activity, upcoming actions, and point leaders.",
    )

    today = date.today()
    employees = load_employees(conn, building=building)
    emp_ids = [int(e["employee_id"]) for e in employees]

    if not emp_ids:
        info_box("No employees found for this building filter.")
        return

    ph = ",".join(["?" if not is_pg(conn) else "%s"] * len(emp_ids))

    # ── Window selector ──────────────────────────────────────────────────────
    win_label = st.selectbox(
        "Activity window",
        ["7 days", "14 days", "30 days", "60 days"],
        index=2,
        label_visibility="collapsed",
        key="dash_win",
    )
    win_days = int(win_label.split()[0])
    since = (today - timedelta(days=win_days)).isoformat()

    # ── KPI queries — always use AS aliases so dict rows work ────────────────
    if is_pg(conn):
        sql_active  = f"SELECT COUNT(DISTINCT employee_id) AS cnt FROM points_history WHERE employee_id IN ({ph}) AND points > 0 AND (point_date::date) >= (%s::date)"
        sql_roll30  = f"SELECT COUNT(*) AS cnt FROM employees WHERE employee_id IN ({ph}) AND rolloff_date IS NOT NULL AND (rolloff_date::date) <= (%s::date) AND point_total > 0"
        sql_perf60  = f"SELECT COUNT(*) AS cnt FROM employees WHERE employee_id IN ({ph}) AND perfect_attendance IS NOT NULL AND (perfect_attendance::date) <= (%s::date)"
        sql_trend   = f"SELECT (point_date::date)::text AS d, COUNT(*) AS n FROM points_history WHERE employee_id IN ({ph}) AND points > 0 AND (point_date::date) >= (%s::date) GROUP BY 1 ORDER BY 1"
        sql_leaders = f"SELECT employee_id, last_name, first_name, COALESCE(\"Location\",'') AS loc, COALESCE(point_total,0) AS pts FROM employees WHERE employee_id IN ({ph}) ORDER BY pts DESC, last_name LIMIT %s"
        sql_rolloffs= f"SELECT employee_id, last_name, first_name, rolloff_date, point_total FROM employees WHERE employee_id IN ({ph}) AND rolloff_date IS NOT NULL AND point_total > 0 AND (rolloff_date::date) >= (%s::date) ORDER BY rolloff_date LIMIT 12"
        sql_perfect = f"SELECT employee_id, last_name, first_name, perfect_attendance FROM employees WHERE employee_id IN ({ph}) AND perfect_attendance IS NOT NULL AND (perfect_attendance::date) <= (%s::date) ORDER BY perfect_attendance LIMIT 10"
    else:
        sql_active  = f"SELECT COUNT(DISTINCT employee_id) AS cnt FROM points_history WHERE employee_id IN ({ph}) AND points > 0 AND date(point_date) >= date(?)"
        sql_roll30  = f"SELECT COUNT(*) AS cnt FROM employees WHERE employee_id IN ({ph}) AND rolloff_date IS NOT NULL AND date(rolloff_date) <= date(?) AND point_total > 0"
        sql_perf60  = f"SELECT COUNT(*) AS cnt FROM employees WHERE employee_id IN ({ph}) AND perfect_attendance IS NOT NULL AND date(perfect_attendance) <= date(?)"
        sql_trend   = f"SELECT date(point_date) AS d, COUNT(*) AS n FROM points_history WHERE employee_id IN ({ph}) AND points > 0 AND date(point_date) >= date(?) GROUP BY 1 ORDER BY 1"
        sql_leaders = f"SELECT employee_id, last_name, first_name, COALESCE(\"Location\",'') AS loc, COALESCE(point_total,0) AS pts FROM employees WHERE employee_id IN ({ph}) ORDER BY pts DESC, last_name LIMIT ?"
        sql_rolloffs= f"SELECT employee_id, last_name, first_name, rolloff_date, point_total FROM employees WHERE employee_id IN ({ph}) AND rolloff_date IS NOT NULL AND point_total > 0 AND date(rolloff_date) >= date(?) ORDER BY rolloff_date LIMIT 12"
        sql_perfect = f"SELECT employee_id, last_name, first_name, perfect_attendance FROM employees WHERE employee_id IN ({ph}) AND perfect_attendance IS NOT NULL AND date(perfect_attendance) <= date(?) ORDER BY perfect_attendance LIMIT 10"

    # Access scalars by column name (works for both sqlite3.Row and pg dict rows)
    active_n  = dict(fetchall(conn, sql_active,  (*emp_ids, since))[0]).get("cnt") or 0
    rolloff_n = dict(fetchall(conn, sql_roll30,  (*emp_ids, (today + timedelta(30)).isoformat()))[0]).get("cnt") or 0
    perf_n    = dict(fetchall(conn, sql_perf60,  (*emp_ids, (today + timedelta(60)).isoformat()))[0]).get("cnt") or 0

    # ── KPI row ──────────────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"Incidents ({win_days}d)", int(active_n))
    m2.metric("Roll-offs Due ≤30d", int(rolloff_n))
    m3.metric("Perfect Att. Due ≤60d", int(perf_n))
    m4.metric("Total Employees", len(emp_ids))

    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)

    col_left, col_right = st.columns([1.6, 1], gap="large")

    # ── Trend chart + leaderboard ────────────────────────────────────────────
    with col_left:
        section_label(f"Incident Trend — last {win_days} days")
        # Convert to dicts so field access works for both SQLite and PostgreSQL
        trend = [dict(r) for r in fetchall(conn, sql_trend, (*emp_ids, since))]
        if trend:
            df_t = pd.DataFrame(trend).rename(columns={"d": "Date", "n": "Incidents"})
            df_t["Date"] = pd.to_datetime(df_t["Date"])
            st.line_chart(df_t.set_index("Date")["Incidents"], color="#4f8ef7", height=220)
        else:
            info_box("No incidents recorded in the selected window.")

        st.markdown("<div style='height:.65rem'></div>", unsafe_allow_html=True)

        lbl_col, n_col = st.columns([3, 1])
        with lbl_col:
            section_label("Top Employees by Point Total")
        with n_col:
            top_n = st.slider("Top", 5, 25, 10, step=5, label_visibility="collapsed", key="dash_n")

        leaders = [dict(r) for r in fetchall(conn, sql_leaders, (*emp_ids, top_n))]
        if leaders:
            df_l = pd.DataFrame(
                [{"Emp #": str(r["employee_id"]), "Name": f"{r['last_name']}, {r['first_name']}",
                  "Building": r["loc"] or "—", "Points": float(r["pts"] or 0)}
                 for r in leaders]
            )
            st.dataframe(df_l, use_container_width=True, hide_index=True)
        else:
            info_box("No employees currently have outstanding points.")

    # ── Upcoming roll-offs + perfect attendance ───────────────────────────────
    with col_right:
        section_label("Upcoming Roll-offs")

        # 2-month roll-offs — only future dates (rolloff_date >= today)
        rolloffs_2mo = [dict(r) for r in fetchall(conn, sql_rolloffs, (*emp_ids, today.isoformat()))]

        # YTD roll-off previews — amount varies by prior-year month points
        emp_set    = set(emp_ids)
        emp_lookup = {int(e["employee_id"]): e for e in employees}
        ytd_entries: list[dict] = []
        try:
            for p in services.preview_ytd_rolloffs(conn, run_date=date.today()):
                eid = int(p[0])
                if eid not in emp_set:
                    continue
                roll_date_str = str(p[2]) if len(p) > 2 else ""
                # Skip overdue YTD entries — past dates need System Updates, not this list
                if roll_date_str and roll_date_str < today.isoformat():
                    continue
                e = emp_lookup.get(eid, {})
                ytd_entries.append({
                    "employee_id": eid,
                    "last_name":   e.get("last_name", ""),
                    "first_name":  e.get("first_name", ""),
                    "point_total": e.get("point_total", 0),
                    "rolloff_date": roll_date_str,
                    "type":   "YTD Roll-Off",
                    "amount": float(p[1] or 0),
                })
        except Exception:
            pass

        # Combine: tag 2-mo entries then append YTD entries; sort by date
        all_upcoming = [{**r, "type": "2-Mo Roll-Off", "amount": -1.0} for r in rolloffs_2mo]
        all_upcoming += ytd_entries
        all_upcoming.sort(key=lambda x: str(x.get("rolloff_date") or "9999"))

        if all_upcoming:
            html = []
            for r in all_upcoming:
                days   = days_until(r["rolloff_date"])
                is_ytd = r["type"] == "YTD Roll-Off"
                tc = "#00b8e6" if is_ytd else "#4f8ef7"
                tb = "rgba(0,184,230,.10)" if is_ytd else "rgba(79,142,247,.10)"
                tbr= "rgba(0,184,230,.25)" if is_ytd else "rgba(79,142,247,.25)"
                type_badge = (
                    f"<span style='display:inline-block;padding:2px 8px;border-radius:6px;"
                    f"font-size:.74rem;font-weight:700;color:{tc};background:{tb};"
                    f"border:1px solid {tbr}'>{r['type']}</span>"
                )
                amt = float(r.get("amount") or 0)
                html.append(
                    f"<div class='list-row'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:center'>"
                    f"<div><span style='font-weight:600;font-size:.9rem;color:#1a2744'>{r['last_name']}, {r['first_name']}</span>"
                    f"<span style='color:#8fa0b8;font-size:.78rem;margin-left:.4rem'>#{r['employee_id']}</span></div>"
                    f"<div style='display:flex;gap:.3rem;align-items:center'>{type_badge}{days_badge(days)}</div>"
                    f"</div>"
                    f"<div style='display:flex;justify-content:space-between;margin-top:.22rem'>"
                    f"<span style='font-size:.75rem;color:#8fa0b8'>Due {fmt_date(r['rolloff_date'])}</span>"
                    f"<span style='font-size:.78rem;font-weight:700;color:#e0394a'>{amt:.1f} pts</span>"
                    f"</div>"
                    f"</div>"
                )
            st.markdown("".join(html), unsafe_allow_html=True)
        else:
            info_box("No roll-offs are currently pending.")

        divider()

        section_label("Perfect Attendance Due ≤60 Days")
        perfects = [dict(r) for r in fetchall(conn, sql_perfect, (*emp_ids, (today + timedelta(60)).isoformat()))]
        if perfects:
            html = []
            for r in perfects:
                days = days_until(r["perfect_attendance"])
                html.append(
                    f"<div class='list-row'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:center'>"
                    f"<span style='font-weight:600;font-size:.9rem;color:#1a2744'>{r['last_name']}, {r['first_name']}</span>"
                    f"{days_badge(days)}"
                    f"</div>"
                    f"<div style='font-size:.75rem;color:#8fa0b8;margin-top:.18rem'>Eligible {fmt_date(r['perfect_attendance'])}</div>"
                    f"</div>"
                )
            st.markdown("".join(html), unsafe_allow_html=True)
        else:
            info_box("No perfect attendance milestones in the next 60 days.")


# ── Employees ─────────────────────────────────────────────────────────────────
def employees_page(conn, building: str) -> None:
    page_heading("Employees", "Look up employees and review current attendance status.")

    q = st.text_input(
        "Search", placeholder="Name or employee # …", label_visibility="collapsed"
    )
    rows = load_employees(conn, q=q, building=building)

    if not rows:
        info_box("No matching employees found.")
        return

    # Results table
    df = pd.DataFrame(rows)[["employee_id", "last_name", "first_name", "location", "is_active"]]
    df.columns = ["Emp #", "Last Name", "First Name", "Building", "Active"]
    df["Emp #"] = df["Emp #"].astype(str)
    st.dataframe(df, use_container_width=True, hide_index=True)

    divider()

    # Detail view
    opts = [
        (int(r["employee_id"]), f"#{r['employee_id']} — {r['last_name']}, {r['first_name']}")
        for r in rows
    ]
    selected = st.selectbox("View details for", opts, format_func=lambda x: x[1], label_visibility="collapsed")
    emp_id = selected[0]
    emp = dict(repo.get_employee(conn, emp_id))

    pts = float(emp.get("point_total") or 0)
    loc = emp.get("Location") or emp.get("location") or "—"
    active_flag = emp.get("is_active", 1)

    active_badge = (
        "<span style='display:inline-block;padding:2px 9px;border-radius:99px;font-size:.78rem;font-weight:700;"
        "color:#00a87a;background:rgba(0,168,122,.10);border:1px solid rgba(0,168,122,.25)'>Active</span>"
        if active_flag else
        "<span style='display:inline-block;padding:2px 9px;border-radius:99px;font-size:.78rem;font-weight:700;"
        "color:#8fa0b8;background:rgba(143,160,184,.10);border:1px solid rgba(143,160,184,.25)'>Inactive</span>"
    )
    st.markdown(
        f"<div class='card'>"
        f"<div style='display:flex;justify-content:space-between;align-items:flex-start'>"
        f"<div><h2 style='margin:0;font-size:1.3rem;font-weight:800;color:#1a2744'>"
        f"{emp.get('last_name')}, {emp.get('first_name')}</h2>"
        f"<div style='color:#5c6f8c;font-size:.85rem;margin-top:.2rem'>"
        f"Employee #{emp_id} &nbsp;·&nbsp; {loc}</div></div>"
        f"<div style='display:flex;gap:.4rem;align-items:center'>{pt_badge(pts)} {active_badge}</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Point Total", f"{pts:.1f}")
    c2.metric("Next Roll-off", fmt_date(emp.get("rolloff_date")))
    c3.metric("Perfect Attendance", fmt_date(emp.get("perfect_attendance")))
    c4.metric("Last Point Entry", fmt_date(emp.get("last_point_date")))

    divider()
    section_label("Point History (last 50 entries)")
    hist = [dict(r) for r in repo.get_points_history(conn, emp_id, limit=50)]
    if hist:
        df_h = pd.DataFrame(hist)[["point_date", "points", "reason", "note", "point_total"]]
        df_h.columns = ["Date", "Points", "Reason", "Note", "Running Total"]
        df_h["Date"] = df_h["Date"].apply(fmt_date)
        st.dataframe(df_h, use_container_width=True, hide_index=True)
    else:
        info_box("No history entries yet for this employee.")


# ── Points Ledger ─────────────────────────────────────────────────────────────
def points_ledger_page(conn, building: str) -> None:
    page_heading("Points Ledger", "Record attendance transactions and maintain a complete audit trail.")

    employees = load_employees(conn, building=building)
    if not employees:
        warn_box("No active employees found for this building filter.")
        return

    opts = [
        (int(e["employee_id"]), f"#{e['employee_id']} — {e['last_name']}, {e['first_name']}")
        for e in employees
    ]
    selected = st.selectbox("Employee", opts, format_func=lambda x: x[1])
    emp_id = selected[0]
    emp = dict(repo.get_employee(conn, emp_id))
    pts = float(emp.get("point_total") or 0)

    # Status strip
    st.markdown(
        f"<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin:.55rem 0 1.2rem 0'>"
        f"<div class='card-sm'>"
        f"<div style='font-size:.67rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;"
        f"color:#5c6f8c;margin-bottom:.3rem'>Points</div>{pt_badge(pts)}</div>"
        f"<div class='card-sm'>"
        f"<div style='font-size:.67rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;"
        f"color:#5c6f8c;margin-bottom:.3rem'>Next Roll-off</div>"
        f"<div style='font-size:.9rem;font-weight:700;color:#1a2744'>{fmt_date(emp.get('rolloff_date'))}</div></div>"
        f"<div class='card-sm'>"
        f"<div style='font-size:.67rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;"
        f"color:#5c6f8c;margin-bottom:.3rem'>Perfect Att.</div>"
        f"<div style='font-size:.9rem;font-weight:700;color:#1a2744'>{fmt_date(emp.get('perfect_attendance'))}</div></div>"
        f"<div class='card-sm'>"
        f"<div style='font-size:.67rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;"
        f"color:#5c6f8c;margin-bottom:.3rem'>Last Entry</div>"
        f"<div style='font-size:.9rem;font-weight:700;color:#1a2744'>{fmt_date(emp.get('last_point_date'))}</div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    col_form, col_hist = st.columns([1, 2], gap="large")

    with col_form:
        section_label("New Transaction")
        with st.form("ledger_entry", clear_on_submit=True):
            p_date  = st.date_input("Date", value=date.today())
            points  = st.number_input("Points (+ add / − remove)", step=0.5, value=0.5, min_value=-20.0, max_value=20.0)
            reason  = st.selectbox("Reason", REASON_OPTIONS)
            note    = st.text_input("Note (optional)")
            submit  = st.form_submit_button("Post Transaction", use_container_width=True)

        if submit:
            if p_date > date.today():
                st.error("Date cannot be in the future.")
            else:
                try:
                    preview = services.preview_add_point(emp_id, p_date, points, reason, note)
                    services.add_point(conn, preview)
                    st.success(f"Posted {points:+.1f} pts on {fmt_date(p_date)}.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with col_hist:
        section_label("Transaction History")
        hist = [dict(r) for r in repo.get_points_history(conn, emp_id, limit=100)]
        if hist:
            df_h = pd.DataFrame(hist)[["id", "point_date", "points", "reason", "note", "point_total"]]
            df_h.columns = ["ID", "Date", "Pts", "Reason", "Note", "Running Total"]
            df_h["Date"] = df_h["Date"].apply(fmt_date)
            st.dataframe(df_h.drop(columns=["ID"]), use_container_width=True, hide_index=True, height=430)
            if st.button("Undo Last Entry", key="undo_last"):
                try:
                    services.delete_point_history_entry(conn, point_id=int(df_h.iloc[0]["ID"]), employee_id=emp_id)
                    st.success("Last entry removed.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        else:
            info_box("No history entries for this employee yet.")


# ── Manage Employees ──────────────────────────────────────────────────────────
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
                emp_id   = st.number_input("Employee #", min_value=1, step=1)
                first    = st.text_input("First Name")
                last     = st.text_input("Last Name")
                location = st.selectbox("Building", BLDG_OPTS)
                added    = st.form_submit_button("Add Employee", use_container_width=True)

            if added:
                if not first.strip() or not last.strip():
                    st.error("First and last name are required.")
                else:
                    try:
                        services.create_employee(conn, int(emp_id), last.strip(), first.strip(), location or None)
                        conn.commit()
                        st.success(f"Employee #{int(emp_id)} — {last}, {first} added.")
                    except Exception as exc:
                        st.error(str(exc))

        with col_info:
            st.markdown("<div style='height:2.5rem'></div>", unsafe_allow_html=True)
            st.markdown(
                "<div class='info-box'><b>New employee checklist</b><br>"
                "• Employee # must be unique across all locations<br>"
                "• Building can be set now or updated later via the Edit tab<br>"
                "• All policy dates are blank until the first point entry is posted</div>",
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
                f"#{r['employee_id']} — {r['last_name']}, {r['first_name']}"
                + (" (inactive)" if not r.get("is_active", 1) else ""),
            )
            for r in all_rows
        ]
        sel = st.selectbox("Select employee", opts, format_func=lambda x: x[1], label_visibility="collapsed")
        emp = dict(repo.get_employee(conn, sel[0]))
        loc_val = emp.get("Location") or emp.get("location") or ""
        loc_idx = BLDG_OPTS.index(loc_val) if loc_val in BLDG_OPTS else 0

        col_edit, col_del = st.columns([1, 1], gap="large")

        with col_edit:
            section_label("Edit Details")
            with st.form("edit_employee"):
                first_e = st.text_input("First Name", value=emp.get("first_name") or "")
                last_e  = st.text_input("Last Name",  value=emp.get("last_name") or "")
                bldg_e  = st.selectbox("Building", BLDG_OPTS, index=loc_idx)
                act_e   = st.checkbox("Active", value=bool(emp.get("is_active", 1)))
                saved   = st.form_submit_button("Save Changes", use_container_width=True)

            if saved:
                try:
                    exec_sql(
                        conn,
                        'UPDATE employees SET first_name=?, last_name=?, "Location"=?, is_active=? WHERE employee_id=?',
                        (first_e.strip(), last_e.strip(), bldg_e or None, 1 if act_e else 0, sel[0]),
                    )
                    conn.commit()
                    st.success("Changes saved.")
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
                        st.success(f"Employee #{sel[0]} deleted.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))


# ── Exports & Forecasts ───────────────────────────────────────────────────────
EXPORT_LABELS = {
    "30-day point history":        "30-Day Point History",
    "upcoming 2-month roll-offs":  "Upcoming 2-Month Roll-offs",
    "upcoming perfect attendance": "Upcoming Perfect Attendance",
    "upcoming annual roll-off":    "Annual YTD Roll-off Entries",
}


def run_export_query(conn, export_type: str, building: str, start_date: date, end_date: date) -> pd.DataFrame:
    pg = is_pg(conn)

    if export_type == "30-day point history":
        if pg:
            sql = """SELECT e.employee_id, e.last_name, e.first_name, COALESCE(e."Location",'') AS location,
                            p.point_date, p.points, p.reason, COALESCE(p.note,'') AS note
                       FROM points_history p JOIN employees e ON e.employee_id=p.employee_id
                      WHERE (p.point_date::date) BETWEEN (%s::date) AND (%s::date)"""
        else:
            sql = """SELECT e.employee_id, e.last_name, e.first_name, COALESCE(e."Location",'') AS location,
                            p.point_date, p.points, p.reason, COALESCE(p.note,'') AS note
                       FROM points_history p JOIN employees e ON e.employee_id=p.employee_id
                      WHERE date(p.point_date) BETWEEN date(?) AND date(?)"""
        params = [start_date.isoformat(), end_date.isoformat()]

    elif export_type == "upcoming 2-month roll-offs":
        if pg:
            sql = """SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS location,
                            point_total, rolloff_date
                       FROM employees WHERE rolloff_date IS NOT NULL
                         AND (rolloff_date::date) BETWEEN (%s::date) AND (%s::date)"""
        else:
            sql = """SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS location,
                            point_total, rolloff_date
                       FROM employees WHERE rolloff_date IS NOT NULL
                         AND date(rolloff_date) BETWEEN date(?) AND date(?)"""
        params = [start_date.isoformat(), end_date.isoformat()]

    elif export_type == "upcoming perfect attendance":
        if pg:
            sql = """SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS location,
                            point_total, perfect_attendance
                       FROM employees WHERE perfect_attendance IS NOT NULL
                         AND (perfect_attendance::date) BETWEEN (%s::date) AND (%s::date)"""
        else:
            sql = """SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS location,
                            point_total, perfect_attendance
                       FROM employees WHERE perfect_attendance IS NOT NULL
                         AND date(perfect_attendance) BETWEEN date(?) AND date(?)"""
        params = [start_date.isoformat(), end_date.isoformat()]

    else:  # annual roll-off
        year_start = date(date.today().year, 1, 1)
        if pg:
            sql = """SELECT e.employee_id, e.last_name, e.first_name, COALESCE(e."Location",'') AS location,
                            p.point_date, p.points, p.reason, COALESCE(p.note,'') AS note
                       FROM points_history p JOIN employees e ON e.employee_id=p.employee_id
                      WHERE p.reason='YTD Roll-Off' AND p.flag_code='AUTO'
                        AND (p.point_date::date) >= (%s::date)"""
        else:
            sql = """SELECT e.employee_id, e.last_name, e.first_name, COALESCE(e."Location",'') AS location,
                            p.point_date, p.points, p.reason, COALESCE(p.note,'') AS note
                       FROM points_history p JOIN employees e ON e.employee_id=p.employee_id
                      WHERE p.reason='YTD Roll-Off' AND p.flag_code='AUTO'
                        AND date(p.point_date) >= date(?)"""
        params = [year_start.isoformat()]

    if building != "All":
        e_ref = 'e."Location"' if " JOIN employees e" in sql else '"Location"'
        sql += f" AND COALESCE({e_ref},'') = ?"
        params.append(building)

    sql += " ORDER BY last_name, first_name"
    return pd.DataFrame([dict(r) for r in fetchall(conn, sql, tuple(params))])


def exports_page(conn, building: str) -> None:
    page_heading(
        "Exports & Forecasts",
        "Generate and download operational reports for roll-offs, perfect attendance, and point history.",
    )

    col_ctrl, col_data = st.columns([1, 2.8], gap="large")

    with col_ctrl:
        section_label("Report Settings")
        export_type = st.radio(
            "Report type",
            list(EXPORT_LABELS.keys()),
            format_func=lambda k: EXPORT_LABELS[k],
            key="export_type",
            label_visibility="collapsed",
        )
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        start_date = st.date_input("From", value=date.today() - timedelta(days=30))
        end_date   = st.date_input("To",   value=date.today() + timedelta(days=60))
        run = st.button("Run Report", use_container_width=True)

    with col_data:
        if run:
            df = run_export_query(conn, export_type, building, start_date, end_date)
            st.session_state["last_export"] = (export_type, df)

        if "last_export" in st.session_state:
            label, df = st.session_state["last_export"]
            section_label(EXPORT_LABELS.get(label, label))
            if df.empty:
                info_box("No records found for the selected date range and building filter.")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True, height=500)
                st.download_button(
                    "Download CSV",
                    data=to_csv(df),
                    file_name=f"atp_{label.replace(' ', '_')}_{date.today()}.csv",
                    mime="text/csv",
                )
        else:
            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
            info_box("Choose a report type and date range, then click <b>Run Report</b>.")


# ── System Updates ────────────────────────────────────────────────────────────
def system_updates_page(conn) -> None:
    page_heading(
        "System Updates",
        "Run automated maintenance jobs: 2-month roll-offs, perfect attendance advancement, and YTD roll-offs.",
    )

    if "maintenance_log" not in st.session_state:
        st.session_state["maintenance_log"] = []

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
            "<div style='margin-top:.9rem;font-size:.79rem;color:#8fa0b8'>"
            "<b style='color:#5c6f8c'>2-Month Roll-offs</b> — removes 1 pt per overdue period, "
            "advances the roll-off date.<br><br>"
            "<b style='color:#5c6f8c'>Perfect Attendance</b> — advances eligible milestone dates "
            "by one month per overdue period. No points are removed.<br><br>"
            "<b style='color:#5c6f8c'>YTD Roll-offs</b> — applies a rolling 12-month net point "
            "reduction. Does not move roll-off or perfect attendance anchors.</div>",
            unsafe_allow_html=True,
        )

    with col_results:
        if btn_roll and ok:
            try:
                rows = services.apply_2mo_rolloffs(conn, run_date=run_date, dry_run=dry_run)
                st.session_state["maintenance_log"].append({
                    "Time": datetime.now().strftime("%H:%M:%S"),
                    "Job": "2-Month Roll-offs",
                    "Dry Run": dry_run,
                    "Affected": len(rows),
                })
                if rows:
                    df = pd.DataFrame(rows)
                    st.success(f"{'Preview:' if dry_run else 'Applied:'} {len(rows)} employee(s) affected.")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.download_button("Download CSV", to_csv(df), file_name=f"rolloffs_{run_date}.csv", mime="text/csv", key="dl_roll")
                else:
                    info_box("No 2-month roll-offs are due as of the selected date.")
            except Exception as exc:
                st.error(str(exc))

        if btn_perf and ok:
            try:
                rows = services.advance_due_perfect_attendance_dates(conn, run_date=run_date, dry_run=dry_run)
                st.session_state["maintenance_log"].append({
                    "Time": datetime.now().strftime("%H:%M:%S"),
                    "Job": "Perfect Attendance",
                    "Dry Run": dry_run,
                    "Affected": len(rows),
                })
                if rows:
                    df = pd.DataFrame(rows)
                    st.success(f"{'Preview:' if dry_run else 'Applied:'} {len(rows)} employee(s) affected.")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.download_button("Download CSV", to_csv(df), file_name=f"perfect_att_{run_date}.csv", mime="text/csv", key="dl_perf")
                else:
                    info_box("No perfect attendance dates are due for advancement.")
            except Exception as exc:
                st.error(str(exc))

        if btn_ytd and ok:
            try:
                rows = services.apply_ytd_rolloffs(conn, run_date=run_date, dry_run=dry_run)
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
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.download_button("Download CSV", to_csv(df), file_name=f"ytd_rolloffs_{run_date}.csv", mime="text/csv", key="dl_ytd")
                else:
                    info_box("No YTD roll-offs are applicable for the selected date.")
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


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    apply_theme()
    conn = get_conn()

    logo_path = REPO_ROOT / "assets" / "logo.png"

    with st.sidebar:
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)
        else:
            st.markdown(
                "<div class='sidebar-brand'>"
                "<div class='name'>Attendance Tracker</div>"
                "<div class='sub'>Point Management System</div>"
                "</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<span class='sidebar-nav-label'>Navigation</span>", unsafe_allow_html=True)
        page = st.radio(
            "nav",
            ["Dashboard", "Employees", "Points Ledger", "Manage Employees", "Exports & Forecasts", "System Updates"],
            key="page",
            label_visibility="collapsed",
        )

        st.markdown("<span class='sidebar-nav-label'>Building Filter</span>", unsafe_allow_html=True)
        building = st.selectbox(
            "building",
            ["All", *BUILDINGS],
            key="global_building",
            label_visibility="collapsed",
        )

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
