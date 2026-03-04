"""Attendance Point Tracker — Streamlit Web App
Full remodel: clean layout, status badges, live countdown, improved workflows.
"""
from __future__ import annotations

import base64
from io import BytesIO
from datetime import date, datetime, timedelta
import math
import os
from pathlib import Path
import secrets
import sys

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

st.set_page_config(
    page_title="Attendance Point Tracker",
    page_icon="⏰",
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

BUILDINGS = ["APIM", "APIS", "AAP"]


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
section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background: #ffffff !important;
    color: #111827 !important;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] input,
section[data-testid="stSidebar"] div[data-baseweb="select"] span,
section[data-testid="stSidebar"] div[data-baseweb="select"] div {
    color: #111827 !important;
    -webkit-text-fill-color: #111827 !important;
}

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

.sidebar-employee-card {
    margin-top: 1.1rem;
    padding: 1rem .9rem .85rem;
    border-radius: 16px;
    border: 1px solid rgba(100,149,255,.22);
    background: linear-gradient(145deg, rgba(15,28,62,.92) 0%, rgba(9,19,44,.97) 100%);
    box-shadow: 0 8px 32px rgba(4,10,26,.45), inset 0 1px 0 rgba(120,160,255,.12);
    position: relative;
    overflow: hidden;
}
.sidebar-employee-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, #4f8ef7, #00b8e6, #4f8ef7);
    opacity: .85;
}
.sidebar-employee-title {
    font-size: .6rem;
    letter-spacing: .16em;
    text-transform: uppercase;
    font-weight: 700;
    color: #4f8ef7 !important;
    margin-bottom: .45rem;
}
.sidebar-employee-name {
    font-size: 1.05rem;
    font-weight: 800;
    color: #f0f6ff !important;
    letter-spacing: -.015em;
    line-height: 1.2;
    margin-bottom: .7rem;
    padding-bottom: .6rem;
    border-bottom: 1px solid rgba(255,255,255,.07);
}
.sidebar-employee-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: .35rem;
}
.sidebar-employee-item {
    background: rgba(255,255,255,.04);
    border: 1px solid rgba(255,255,255,.06);
    border-radius: 8px;
    padding: .38rem .45rem;
}
.sidebar-employee-item.full-width {
    grid-column: 1 / -1;
}
.sidebar-employee-item .label {
    display: block;
    font-size: .56rem;
    letter-spacing: .10em;
    text-transform: uppercase;
    color: #4a6490 !important;
    font-weight: 700;
    margin-bottom: .12rem;
}
.sidebar-employee-item .value {
    display: block;
    font-size: .78rem;
    font-weight: 600;
    color: #c8d8f4 !important;
    letter-spacing: -.01em;
}
.sidebar-employee-item .value.highlight {
    color: #4f8ef7 !important;
    font-size: .9rem;
    font-weight: 800;
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


def ensure_session_defaults() -> None:
    defaults = {
        "selected_employee_id": None,
        "dashboard_bucket": None,
        "authenticated": False,
        "login_error": False,
        "_auth_token": None,
        "_auth_redirect_pending": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def is_authenticated() -> bool:
    """Auth requires the in-session auth flag plus token validation.

    During login submit, query params can lag one rerun behind session_state.
    To avoid a flash of the login screen, allow a one-rerun grace period while
    the URL token is being written.
    """
    session_token = st.session_state.get("_auth_token")
    url_token = st.query_params.get("_s")
    if not st.session_state.get("authenticated", False) or session_token is None:
        return False

    if session_token == url_token:
        st.session_state["_auth_redirect_pending"] = False
        return True

    if st.session_state.get("_auth_redirect_pending") and not url_token:
        return True

    return False


# ── Login ──────────────────────────────────────────────────────────────────────
def login_page() -> None:
    """Render a centered access-code login screen matching the reference design."""
    # Embed logo as base64 so it renders inside custom HTML
    logo_path = REPO_ROOT / "assets" / "logo.png"
    logo_tag = ""
    if logo_path.exists():
        logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()
        logo_tag = (
            f'<img src="data:image/png;base64,{logo_b64}"'
            ' style="max-height:110px;max-width:100%;object-fit:contain;'
            'margin-bottom:1.1rem;" />'
        )

    st.markdown(
        f"""<style>
        section[data-testid="stSidebar"] {{ display: none !important; }}
        .block-container {{ padding-top: 3rem !important; max-width: 100% !important; }}
        footer, #MainMenu {{ visibility: hidden; }}

        /* Page background */
        [data-testid="stAppViewContainer"] > .main {{
            background: #e8eaed !important;
        }}
        .stApp {{ background: #e8eaed !important; }}

        /* Branding card — logo + title only, red top accent */
        .login-brand-card {{
            background: #ffffff;
            border-radius: 12px;
            border-top: 6px solid #cc2229;
            padding: 2.2rem 2rem 1.8rem 2rem;
            text-align: center;
            margin-bottom: 1.4rem;
            box-shadow: 0 2px 10px rgba(0,0,0,.09);
        }}
        .login-title {{
            font-size: 1.45rem;
            font-weight: 700;
            color: #111827;
            margin: 0;
            letter-spacing: -.01em;
        }}

        /* Field label */
        .login-field-label {{
            display: block;
            font-size: .88rem;
            font-weight: 600;
            color: #111827;
            margin-bottom: .3rem;
            margin-top: 0;
        }}

        /* Inputs */
        div[data-testid="stTextInput"] input {{
            background: #ffffff !important;
            border: 1px solid #d1d5db !important;
            border-radius: 7px !important;
            font-size: .95rem !important;
        }}
        div[data-testid="stTextInput"] input:focus {{
            border-color: #6b7280 !important;
            box-shadow: none !important;
        }}

        /* Start button — dark */
        .stButton > button {{
            background: #111827 !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 7px !important;
            font-size: .97rem !important;
            font-weight: 600 !important;
            width: 100% !important;
            padding: .7rem !important;
            margin-top: .9rem !important;
            letter-spacing: .02em !important;
            transition: background .15s !important;
        }}
        .stButton > button:hover {{
            background: #1f2937 !important;
        }}

        /* Error message */
        .login-error {{
            background: #fee2e2;
            color: #b91c1c;
            border-radius: 7px;
            padding: .5rem .9rem;
            font-size: .84rem;
            font-weight: 600;
            margin-top: .6rem;
        }}
        </style>""",
        unsafe_allow_html=True,
    )

    _, col, _ = st.columns([1, 1.8, 1])
    with col:
        # Branding card
        st.markdown(
            f'<div class="login-brand-card">'
            f'{logo_tag}'
            f'<div class="login-title">Attendance Tracking</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Form below card
        st.markdown("<span class='login-field-label'>Access Code</span>", unsafe_allow_html=True)
        access_code = st.text_input(
            "Access Code",
            type="password",
            placeholder="",
            label_visibility="collapsed",
        )
        start_clicked = st.button("Start", use_container_width=True)

        if start_clicked:
            expected = os.environ.get("ACCESS_CODE", "attendance2024")
            if access_code == expected:
                token = secrets.token_urlsafe(16)
                st.session_state["authenticated"] = True
                st.session_state["_auth_token"] = token
                st.session_state["_auth_redirect_pending"] = True
                st.session_state["login_error"] = False
                st.query_params["_s"] = token
                st.rerun()
            else:
                st.session_state["login_error"] = True

        if st.session_state.get("login_error"):
            st.markdown(
                "<div class='login-error'>Incorrect access code. Please try again.</div>",
                unsafe_allow_html=True,
            )


def build_point_history_pdf(employee: dict, history: list[dict]) -> bytes:
    """Generate a printable attendance point history report as a PDF."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()

    full_name = f"{employee.get('last_name', '')}, {employee.get('first_name', '')}".strip(", ")
    employee_id = employee.get("employee_id", "—")
    location = employee.get("Location") or employee.get("location") or "—"
    generated_on = datetime.now().strftime("%m/%d/%Y %I:%M %p")

    story = [
        Paragraph("Attendance Point History Report", styles["Title"]),
        Spacer(1, 0.1 * inch),
        Paragraph(f"<b>Employee:</b> {full_name}", styles["Normal"]),
        Paragraph(f"<b>Employee #:</b> {employee_id}", styles["Normal"]),
        Paragraph(f"<b>Location:</b> {location}", styles["Normal"]),
        Paragraph(
            f"<b>Current Point Total:</b> {float(employee.get('point_total') or 0):.1f}",
            styles["Normal"],
        ),
        Paragraph(f"<b>Generated:</b> {generated_on}", styles["Normal"]),
        Spacer(1, 0.2 * inch),
    ]

    if history:
        table_rows = [["Date", "Points", "Reason", "Note", "Running Total"]]
        for row in history:
            table_rows.append(
                [
                    fmt_date(row.get("point_date")),
                    f"{float(row.get('points') or 0):.1f}",
                    str(row.get("reason") or "—"),
                    str(row.get("note") or "—"),
                    f"{float(row.get('point_total') or 0):.1f}",
                ]
            )

        table = Table(table_rows, colWidths=[1.1 * inch, 0.8 * inch, 1.4 * inch, 2.9 * inch, 1.0 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f4fa")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1a2744")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfd8e6")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fbff")]),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("No point history entries were found for this employee.", styles["Normal"]))

    doc.build(story)
    return buffer.getvalue()


def selected_employee_sidebar(conn, employee_id: int | None) -> None:
    if not employee_id:
        return

    if is_pg(conn):
        sql = '''
            SELECT e.employee_id,
                   e.first_name,
                   e.last_name,
                   COALESCE(e."Location", '') AS building,
                   GREATEST(0.0, ROUND(COALESCE((
                       SELECT SUM(ph.points) FROM points_history ph WHERE ph.employee_id = e.employee_id
                   ), 0.0), 1)) AS point_total,
                   (
                       SELECT MAX(ph2.point_date::date)
                         FROM points_history ph2
                        WHERE ph2.employee_id = e.employee_id
                          AND COALESCE(ph2.points, 0.0) > 0.0
                   )::text AS last_positive_point_date,
                   e.rolloff_date::text AS rolloff_date,
                   e.perfect_attendance::text AS perfect_attendance
              FROM employees e
             WHERE e.employee_id = %s
             LIMIT 1
        '''
        rows = fetchall(conn, sql, (employee_id,))
    else:
        sql = '''
            SELECT e.employee_id,
                   e.first_name,
                   e.last_name,
                   COALESCE(e."Location", '') AS building,
                   MAX(0.0, ROUND(COALESCE((
                       SELECT SUM(ph.points) FROM points_history ph WHERE ph.employee_id = e.employee_id
                   ), 0.0), 1)) AS point_total,
                   (
                       SELECT MAX(date(ph2.point_date))
                         FROM points_history ph2
                        WHERE ph2.employee_id = e.employee_id
                          AND COALESCE(ph2.points, 0.0) > 0.0
                   ) AS last_positive_point_date,
                   e.rolloff_date,
                   e.perfect_attendance
              FROM employees e
             WHERE e.employee_id = ?
             LIMIT 1
        '''
        rows = fetchall(conn, sql, (employee_id,))

    if not rows:
        return

    emp = dict(rows[0])
    full_name = f"{emp.get('first_name') or ''} {emp.get('last_name') or ''}".strip() or "Unknown Employee"
    st.markdown(
        "<div class='sidebar-employee-card'>"
        "<div class='sidebar-employee-title'>&#9673; Employee Spotlight</div>"
        f"<div class='sidebar-employee-name'>{full_name}</div>"
        "<div class='sidebar-employee-grid'>"
        f"<div class='sidebar-employee-item'><span class='label'>Emp #</span><span class='value'>{emp.get('employee_id') or '—'}</span></div>"
        f"<div class='sidebar-employee-item'><span class='label'>Building</span><span class='value'>{emp.get('building') or '—'}</span></div>"
        f"<div class='sidebar-employee-item full-width'><span class='label'>Point Total</span><span class='value highlight'>{float(emp.get('point_total') or 0):.1f} pts</span></div>"
        f"<div class='sidebar-employee-item'><span class='label'>Last Point</span><span class='value'>{fmt_date(emp.get('last_positive_point_date'))}</span></div>"
        f"<div class='sidebar-employee-item'><span class='label'>Roll Off</span><span class='value'>{fmt_date(emp.get('rolloff_date'))}</span></div>"
        f"<div class='sidebar-employee-item full-width'><span class='label'>Perfect Attendance</span><span class='value'>{fmt_date(emp.get('perfect_attendance'))}</span></div>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def load_employees(conn, q: str = "", building: str = "All") -> list[dict]:
    rows = [dict(r) for r in repo.search_employees(conn, q=q, limit=3000)]
    if building != "All":
        rows = [r for r in rows if (r.get("location") or "") == building]
    return rows


# ── Dashboard ─────────────────────────────────────────────────────────────────
def dashboard_page(conn, building: str) -> None:
    page_heading(
        "Dashboard",
        "Real-time overview of attendance activity, thresholds, and upcoming actions.",
    )

    today = date.today()
    in_30_days = today + timedelta(days=30)
    employees = load_employees(conn, building=building)
    emp_ids = [int(e["employee_id"]) for e in employees]

    if not emp_ids:
        info_box("No employees found for this building filter.")
        return

    ph = ",".join(["?" if not is_pg(conn) else "%s"] * len(emp_ids))

    if is_pg(conn):
        sql_emp_detail = f'''
            SELECT e.employee_id, e.last_name, e.first_name,
                   COALESCE(e."Location",'') AS building,
                   GREATEST(0.0, ROUND(COALESCE(SUM(ph.points), 0.0)::numeric, 1)::float8) AS point_total,
                   e.last_point_date, e.rolloff_date, e.perfect_attendance
              FROM employees e
              LEFT JOIN points_history ph ON ph.employee_id = e.employee_id
             WHERE e.employee_id IN ({ph})
             GROUP BY e.employee_id, e.last_name, e.first_name, e."Location",
                      e.last_point_date, e.rolloff_date, e.perfect_attendance
        '''
        sql_roll_due = f'''
            SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS building,
                   rolloff_date, COALESCE(point_total,0) AS point_total
              FROM employees
             WHERE employee_id IN ({ph})
               AND rolloff_date IS NOT NULL
               AND (rolloff_date::date) >= (%s::date)
               AND (rolloff_date::date) <= (%s::date)
             ORDER BY (rolloff_date::date), lower(last_name), lower(first_name)
        '''
        sql_perf_due = f'''
            SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS building,
                   perfect_attendance, COALESCE(point_total,0) AS point_total
              FROM employees
             WHERE employee_id IN ({ph})
               AND perfect_attendance IS NOT NULL
               AND (perfect_attendance::date) >= (%s::date)
               AND (perfect_attendance::date) <= (%s::date)
             ORDER BY (perfect_attendance::date), lower(last_name), lower(first_name)
        '''
        sql_build_reasons = '''
            SELECT ph.reason, COUNT(*) AS n
              FROM points_history ph
              JOIN employees e ON e.employee_id = ph.employee_id
             WHERE (ph.point_date::date) >= (%s::date)
               AND COALESCE(ph.points, 0.0) > 0.0
               AND COALESCE(e."Location", '') = %s
               AND COALESCE(e.is_active, 1) = 1
               AND COALESCE(ph.reason, '') <> ''
             GROUP BY ph.reason
             ORDER BY n DESC, ph.reason
             LIMIT 1
        '''
        sql_active_emp_points = '''
            SELECT e.employee_id,
                   COALESCE(e."Location", '') AS building,
                   GREATEST(0.0, ROUND(COALESCE(SUM(ph.points), 0.0)::numeric, 1)::float8) AS point_total
              FROM employees e
              LEFT JOIN points_history ph ON ph.employee_id = e.employee_id
             WHERE COALESCE(e.is_active, 1) = 1
             GROUP BY e.employee_id, e."Location"
        '''
        sql_build_points_window = f'''
            SELECT COALESCE(e."Location", '') AS building,
                   ROUND(COALESCE(SUM(ph.points), 0.0)::numeric, 1)::float8 AS pts
              FROM points_history ph
              JOIN employees e ON e.employee_id = ph.employee_id
             WHERE ph.employee_id IN ({ph})
               AND (ph.point_date::date) >= (%s::date)
               AND (ph.point_date::date) < (%s::date)
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY COALESCE(e."Location", '')
        '''
        sql_insights_gt1 = f'''
            SELECT e.employee_id,
                   e.last_name,
                   e.first_name,
                   COALESCE(e."Location", '') AS building,
                   ROUND(COALESCE(SUM(ph.points), 0.0)::numeric, 1)::float8 AS points_30d,
                   MAX(ph.point_date::date)::text AS last_point_date,
                   COALESCE((
                       SELECT ph2.reason
                         FROM points_history ph2
                        WHERE ph2.employee_id = e.employee_id
                          AND (ph2.point_date::date) >= (%s::date)
                          AND EXTRACT(DOW FROM ph2.point_date::date) NOT IN (0, 6)
                          AND COALESCE(ph2.points, 0.0) > 0.0
                          AND COALESCE(ph2.reason, '') <> ''
                        GROUP BY ph2.reason
                        ORDER BY COUNT(*) DESC, MAX(ph2.point_date::date) DESC, ph2.reason
                        LIMIT 1
                   ), '—') AS top_reason
              FROM employees e
              JOIN points_history ph ON ph.employee_id = e.employee_id
             WHERE e.employee_id IN ({ph})
               AND (ph.point_date::date) >= (%s::date)
               AND EXTRACT(DOW FROM ph.point_date::date) NOT IN (0, 6)
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY e.employee_id, e.last_name, e.first_name, e."Location"
            HAVING COALESCE(SUM(ph.points), 0.0) > 1.0
             ORDER BY points_30d DESC, MAX(ph.point_date::date) DESC, lower(e.last_name), lower(e.first_name)
        '''
        sql_points_60d = f'''
            SELECT ph.employee_id,
                   ROUND(COALESCE(SUM(ph.points), 0.0)::numeric, 1)::float8 AS points_60d
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND (ph.point_date::date) >= (%s::date)
               AND EXTRACT(DOW FROM ph.point_date::date) NOT IN (0, 6)
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY ph.employee_id
        '''
        sql_trend_90d = f'''
            SELECT (ph.point_date::date)::text AS point_day,
                   ROUND(COALESCE(SUM(ph.points), 0.0)::numeric, 1)::float8 AS pts
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND (ph.point_date::date) >= (%s::date)
               AND EXTRACT(DOW FROM ph.point_date::date) NOT IN (0, 6)
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY (ph.point_date::date)
             ORDER BY (ph.point_date::date)
        '''
        sql_hotspots_365 = f'''
            SELECT EXTRACT(DOW FROM ph.point_date::date)::int AS dow,
                   ROUND(COALESCE(SUM(ph.points), 0.0)::numeric, 1)::float8 AS total_points,
                   COUNT(*) AS incidents
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND (ph.point_date::date) >= (%s::date)
               AND EXTRACT(DOW FROM ph.point_date::date) NOT IN (0, 6)
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY EXTRACT(DOW FROM ph.point_date::date)
             ORDER BY total_points DESC
        '''
    else:
        sql_emp_detail = f'''
            SELECT e.employee_id, e.last_name, e.first_name,
                   COALESCE(e."Location",'') AS building,
                   MAX(0.0, ROUND(COALESCE((
                       SELECT SUM(ph.points) FROM points_history ph WHERE ph.employee_id = e.employee_id
                   ), 0.0), 1)) AS point_total,
                   e.last_point_date, e.rolloff_date, e.perfect_attendance
              FROM employees e
             WHERE e.employee_id IN ({ph})
        '''
        sql_roll_due = f'''
            SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS building,
                   rolloff_date, COALESCE(point_total,0) AS point_total
              FROM employees
             WHERE employee_id IN ({ph})
               AND rolloff_date IS NOT NULL
               AND date(rolloff_date) >= date(?)
               AND date(rolloff_date) <= date(?)
             ORDER BY date(rolloff_date), lower(last_name), lower(first_name)
        '''
        sql_perf_due = f'''
            SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS building,
                   perfect_attendance, COALESCE(point_total,0) AS point_total
              FROM employees
             WHERE employee_id IN ({ph})
               AND perfect_attendance IS NOT NULL
               AND date(perfect_attendance) >= date(?)
               AND date(perfect_attendance) <= date(?)
             ORDER BY date(perfect_attendance), lower(last_name), lower(first_name)
        '''
        sql_build_reasons = '''
            SELECT ph.reason, COUNT(*) AS n
              FROM points_history ph
              JOIN employees e ON e.employee_id = ph.employee_id
             WHERE date(ph.point_date) >= date(?)
               AND COALESCE(ph.points, 0.0) > 0.0
               AND COALESCE(e."Location", '') = ?
               AND COALESCE(e.is_active, 1) = 1
               AND COALESCE(ph.reason, '') <> ''
             GROUP BY ph.reason
             ORDER BY n DESC, ph.reason
             LIMIT 1
        '''
        sql_active_emp_points = '''
            SELECT e.employee_id,
                   COALESCE(e."Location", '') AS building,
                   MAX(0.0, ROUND(COALESCE((
                       SELECT SUM(ph.points) FROM points_history ph WHERE ph.employee_id = e.employee_id
                   ), 0.0), 1)) AS point_total
              FROM employees e
             WHERE COALESCE(e.is_active, 1) = 1
             GROUP BY e.employee_id, e."Location"
        '''
        sql_build_points_window = f'''
            SELECT COALESCE(e."Location", '') AS building,
                   ROUND(COALESCE(SUM(ph.points), 0.0), 1) AS pts
              FROM points_history ph
              JOIN employees e ON e.employee_id = ph.employee_id
             WHERE ph.employee_id IN ({ph})
               AND date(ph.point_date) >= date(?)
               AND date(ph.point_date) < date(?)
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY COALESCE(e."Location", '')
        '''
        sql_insights_gt1 = f'''
            SELECT e.employee_id,
                   e.last_name,
                   e.first_name,
                   COALESCE(e."Location", '') AS building,
                   ROUND(COALESCE(SUM(ph.points), 0.0), 1) AS points_30d,
                   MAX(date(ph.point_date)) AS last_point_date,
                   COALESCE((
                       SELECT ph2.reason
                         FROM points_history ph2
                        WHERE ph2.employee_id = e.employee_id
                          AND date(ph2.point_date) >= date(?)
                          AND strftime('%w', ph2.point_date) NOT IN ('0', '6')
                          AND COALESCE(ph2.points, 0.0) > 0.0
                          AND COALESCE(ph2.reason, '') <> ''
                        GROUP BY ph2.reason
                        ORDER BY COUNT(*) DESC, MAX(date(ph2.point_date)) DESC, ph2.reason
                        LIMIT 1
                   ), '—') AS top_reason
              FROM employees e
              JOIN points_history ph ON ph.employee_id = e.employee_id
             WHERE e.employee_id IN ({ph})
               AND date(ph.point_date) >= date(?)
               AND strftime('%w', ph.point_date) NOT IN ('0', '6')
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY e.employee_id, e.last_name, e.first_name, e."Location"
            HAVING COALESCE(SUM(ph.points), 0.0) > 1.0
             ORDER BY points_30d DESC, MAX(date(ph.point_date)) DESC, lower(e.last_name), lower(e.first_name)
        '''
        sql_points_60d = f'''
            SELECT ph.employee_id,
                   ROUND(COALESCE(SUM(ph.points), 0.0), 1) AS points_60d
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND date(ph.point_date) >= date(?)
               AND strftime('%w', ph.point_date) NOT IN ('0', '6')
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY ph.employee_id
        '''
        sql_trend_90d = f'''
            SELECT date(ph.point_date) AS point_day,
                   ROUND(COALESCE(SUM(ph.points), 0.0), 1) AS pts
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND date(ph.point_date) >= date(?)
               AND strftime('%w', ph.point_date) NOT IN ('0', '6')
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY date(ph.point_date)
             ORDER BY date(ph.point_date)
        '''
        sql_hotspots_365 = f'''
            SELECT CAST(strftime('%w', ph.point_date) AS INTEGER) AS dow,
                   ROUND(COALESCE(SUM(ph.points), 0.0), 1) AS total_points,
                   COUNT(*) AS incidents
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND date(ph.point_date) >= date(?)
               AND strftime('%w', ph.point_date) NOT IN ('0', '6')
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY CAST(strftime('%w', ph.point_date) AS INTEGER)
             ORDER BY total_points DESC
        '''

    emp_detail_rows = [dict(r) for r in fetchall(conn, sql_emp_detail, tuple(emp_ids))]
    roll_due_rows = [dict(r) for r in fetchall(conn, sql_roll_due, (*emp_ids, today.isoformat(), in_30_days.isoformat()))]
    perf_due_rows = [dict(r) for r in fetchall(conn, sql_perf_due, (*emp_ids, today.isoformat(), in_30_days.isoformat()))]

    bucket_defs = {
        "0": lambda pts: pts == 0,
        "1-4": lambda pts: 1 <= pts <= 4,
        "5-6": lambda pts: 5 <= pts <= 6,
        "7": lambda pts: pts >= 7,
    }
    bucket_counts = {
        key: sum(1 for r in emp_detail_rows if fn(float(r.get("point_total") or 0)))
        for key, fn in bucket_defs.items()
    }


    st.markdown(
        """<style>
        .st-key-dashboard_bucket_all div[data-testid="stButton"],
        .st-key-dashboard_bucket_0 div[data-testid="stButton"],
        .st-key-dashboard_bucket_1-4 div[data-testid="stButton"],
        .st-key-dashboard_bucket_5-6 div[data-testid="stButton"],
        .st-key-dashboard_bucket_7 div[data-testid="stButton"] {
            margin-top: -92px !important;
            position: relative;
            z-index: 30;
        }
        .st-key-dashboard_bucket_all div[data-testid="stButton"] > button,
        .st-key-dashboard_bucket_0 div[data-testid="stButton"] > button,
        .st-key-dashboard_bucket_1-4 div[data-testid="stButton"] > button,
        .st-key-dashboard_bucket_5-6 div[data-testid="stButton"] > button,
        .st-key-dashboard_bucket_7 div[data-testid="stButton"] > button {
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            min-height: 92px !important;
            width: 100% !important;
            padding: 0 !important;
        }
        .st-key-dashboard_bucket_all div[data-testid="stButton"] > button p,
        .st-key-dashboard_bucket_0 div[data-testid="stButton"] > button p,
        .st-key-dashboard_bucket_1-4 div[data-testid="stButton"] > button p,
        .st-key-dashboard_bucket_5-6 div[data-testid="stButton"] > button p,
        .st-key-dashboard_bucket_7 div[data-testid="stButton"] > button p {
            opacity: 0 !important;
            margin: 0 !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    tile_cols = st.columns(5)
    tile_specs = [
        ("all", "All Employees"),
        ("0", "0 Points"),
        ("1-4", "1–4 Pts"),
        ("5-6", "5–6 Pts"),
        ("7", "7+ Pts"),
    ]
    active_bucket = st.session_state.get("dashboard_bucket")
    tile_palette = {
        "all": {"accent": "#5c6f8c", "glow": "rgba(92,111,140,.22)"},
        "0": {"accent": "#00a87a", "glow": "rgba(0,168,122,.25)"},
        "1-4": {"accent": "#4f8ef7", "glow": "rgba(79,142,247,.25)"},
        "5-6": {"accent": "#e6960a", "glow": "rgba(230,150,10,.28)"},
        "7": {"accent": "#e0394a", "glow": "rgba(224,57,74,.32)"},
    }

    for col, (key, label) in zip(tile_cols, tile_specs):
        selected = (active_bucket == key) if key != "all" else (active_bucket not in bucket_defs)
        accent = tile_palette[key]["accent"]
        glow = tile_palette[key]["glow"]
        border = "rgba(26,39,68,.16)" if not selected else accent
        shadow = f"0 0 0 2px {glow}, 0 8px 18px rgba(15,32,68,.12)" if selected else "0 4px 14px rgba(15,32,68,.08)"
        employees_count = len(emp_detail_rows) if key == "all" else bucket_counts[key]

        col.markdown(
            f"<div class='card-sm' style='margin-bottom:.45rem;padding:.72rem .9rem;"
            f"background:#ffffff;border:1px solid {border};box-shadow:{shadow};cursor:pointer;pointer-events:none;'>"
            f"<div style='height:4px;border-radius:999px;background:{accent};margin:-.2rem 0 .6rem 0'></div>"
            f"<div style='font-size:.68rem;letter-spacing:.09em;text-transform:uppercase;color:#5c6f8c;font-weight:700'>{label}</div>"
            f"<div style='display:flex;align-items:baseline;justify-content:space-between;margin-top:.18rem'>"
            f"<span style='font-size:1.95rem;font-weight:800;color:#1a2744;line-height:1'>{employees_count}</span>"
            f"<span style='font-size:.72rem;font-weight:700;color:{accent};text-transform:uppercase;letter-spacing:.05em'>&nbsp;employees</span>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

        if col.button("filter", key=f"dashboard_bucket_{key}", use_container_width=True):
            if key == "all":
                st.session_state.pop("dashboard_bucket", None)
            else:
                st.session_state["dashboard_bucket"] = key
            st.rerun()

    col_left, col_right = st.columns([1.6, 1], gap="large")

    with col_left:
        section_label("Employee Point Overview")
        bucket_key = st.session_state.get("dashboard_bucket")
        source_rows = list(emp_detail_rows)
        if bucket_key in bucket_defs:
            source_rows = [r for r in emp_detail_rows if bucket_defs[bucket_key](float(r.get("point_total") or 0))]
            st.caption(f"Filtered by threshold tile: {bucket_key}")

        source_rows = sorted(
            source_rows,
            key=lambda r: (
                -float(r.get("point_total") or 0),
                str(r.get("last_point_date") or ""),
            ),
        )

        if source_rows:
            df_emps = pd.DataFrame(
                [
                    {
                        "employee_id": int(r["employee_id"]),
                        "Employee #": str(r["employee_id"]),
                        "Name": f"{r['last_name']}, {r['first_name']}",
                        "Building": r.get("building") or "—",
                        "Point Total": f"{float(r.get('point_total') or 0):.1f}",
                        "Last Point Date": fmt_date(r.get("last_point_date")),
                    }
                    for r in source_rows
                ]
            )
            event = st.dataframe(
                df_emps[["Employee #", "Name", "Building", "Point Total", "Last Point Date"]],
                use_container_width=True,
                hide_index=True,
                height=575,
                key="dash_emp_above5_table",
                on_select="rerun",
                selection_mode="single-row",
            )
            selected_rows = (event.selection.get("rows") if event else []) or []
            if selected_rows:
                idx = int(selected_rows[0])
                if 0 <= idx < len(df_emps):
                    st.session_state["selected_employee_id"] = int(df_emps.iloc[idx]["employee_id"])
        else:
            info_box("None 🎉")


    with col_right:
        section_label("Roll Offs Due (Next 30 Days)")
        if roll_due_rows:
            df_roll = pd.DataFrame(
                [
                    {
                        "Employee #": str(r["employee_id"]),
                        "Name": f"{r['last_name']}, {r['first_name']}",
                        "Building": r.get("building") or "—",
                        "Rolloff Date": fmt_date(r.get("rolloff_date")),
                        "Current Points": f"{float(r.get('point_total') or 0):.1f}",
                    }
                    for r in roll_due_rows
                ]
            )
            st.dataframe(df_roll, use_container_width=True, hide_index=True, height=235)
        else:
            info_box("No roll-offs due in the next 30 days.")

        divider()
        section_label("Perfect Attendance Due (Next 30 Days)")
        if perf_due_rows:
            df_perf = pd.DataFrame(
                [
                    {
                        "Employee #": str(r["employee_id"]),
                        "Name": f"{r['last_name']}, {r['first_name']}",
                        "Building": r.get("building") or "—",
                        "Perfect Date": fmt_date(r.get("perfect_attendance")),
                        "Current Points": f"{float(r.get('point_total') or 0):.1f}",
                    }
                    for r in perf_due_rows
                ]
            )
            st.dataframe(df_perf, use_container_width=True, hide_index=True, height=235)
        else:
            info_box("No perfect attendance dates due in the next 30 days.")

    divider()
    section_label("Building Snapshot (Average Points per Employee)")

    active_rows = [
        dict(r)
        for r in fetchall(
            conn,
            """SELECT COALESCE("Location", '') AS building, COUNT(*) AS n FROM employees WHERE COALESCE(is_active,1)=1 GROUP BY COALESCE("Location", '')""",
        )
    ]
    active_by_build = {b: 0 for b in BUILDINGS}
    for r in active_rows:
        if r["building"] in active_by_build:
            active_by_build[r["building"]] = int(r["n"] or 0)

    since_30 = (today - timedelta(days=30)).isoformat()
    since_60 = (today - timedelta(days=60)).isoformat()
    tomorrow = (today + timedelta(days=1)).isoformat()

    current_rows = [dict(r) for r in fetchall(conn, sql_build_points_window, (*emp_ids, since_30, tomorrow))]
    prior_rows = [dict(r) for r in fetchall(conn, sql_build_points_window, (*emp_ids, since_60, since_30))]
    current_points = {r.get("building") or "": float(r.get("pts") or 0.0) for r in current_rows}
    prior_points = {r.get("building") or "": float(r.get("pts") or 0.0) for r in prior_rows}

    snap_rows = []
    for b in BUILDINGS:
        headcount = int(active_by_build.get(b) or 0)
        cur_total = float(current_points.get(b) or 0.0)
        prev_total = float(prior_points.get(b) or 0.0)
        cur_rate = (cur_total / headcount * 100.0) if headcount else 0.0
        prev_rate = (prev_total / headcount * 100.0) if headcount else 0.0
        if prev_rate > 0:
            pct_change = ((cur_rate - prev_rate) / prev_rate) * 100.0
            pct_txt = f"{pct_change:+.1f}%"
        else:
            pct_txt = "—"
        reason_rows = [dict(r) for r in fetchall(conn, sql_build_reasons, (since_30, b))]
        most_common_reason = (reason_rows[0].get("reason") if reason_rows else None) or "—"
        snap_rows.append(
            {
                "Building": b,
                "Active Employees": headcount,
                "Points / 100 Active (30d)": f"{cur_rate:.1f}",
                "% Change vs Prior 30 Days": pct_txt,
                "Most Common Reason (30d)": most_common_reason,
            }
        )

    st.dataframe(pd.DataFrame(snap_rows), use_container_width=True, hide_index=True)

    divider()
    section_label("Insights")

    st.markdown("#### Employees > 1.0 Point (Last 30 Days)")
    gt1_rows = [dict(r) for r in fetchall(conn, sql_insights_gt1, (since_30, *emp_ids, since_30))]
    if gt1_rows:
        df_gt1 = pd.DataFrame(
            [
                {
                    "Employee #": str(r["employee_id"]),
                    "Name": f"{r['last_name']}, {r['first_name']}",
                    "Building": r.get("building") or "—",
                    "Points (30d)": f"{float(r.get('points_30d') or 0.0):.1f}",
                    "Last Point Date": fmt_date(r.get("last_point_date")),
                    "Top Reason": (r.get("top_reason") or "—"),
                }
                for r in gt1_rows
            ]
        )
        st.dataframe(df_gt1.head(25), use_container_width=True, hide_index=True)
        if len(df_gt1) > 25:
            with st.expander(f"Show all ({len(df_gt1)})"):
                st.dataframe(df_gt1, use_container_width=True, hide_index=True)
    else:
        info_box("No employees over 1.0 points in the last 30 days.")

    st.markdown("#### Trending Risk (Heuristic) — On track to exceed 8 points")
    pts60_rows = [dict(r) for r in fetchall(conn, sql_points_60d, (*emp_ids, since_60))]
    points60_by_emp = {int(r.get("employee_id")): float(r.get("points_60d") or 0.0) for r in pts60_rows}
    weekdays_60 = max(len(pd.bdate_range(start=today - timedelta(days=60), end=today)), 1)
    weekdays_30 = len(pd.bdate_range(start=today + timedelta(days=1), end=today + timedelta(days=30)))
    risk_rows = []
    for r in emp_detail_rows:
        emp_id = int(r["employee_id"])
        current_points = float(r.get("point_total") or 0.0)
        points_60d = float(points60_by_emp.get(emp_id) or 0.0)
        projected_30d = (points_60d / weekdays_60) * weekdays_30
        projected_total = current_points + projected_30d
        if projected_total >= 8.0:
            risk_rows.append(
                {
                    "Employee #": str(emp_id),
                    "Name": f"{r['last_name']}, {r['first_name']}",
                    "Building": r.get("building") or "—",
                    "Current Points": f"{current_points:.1f}",
                    "Points (60d)": f"{points_60d:.1f}",
                    "Projected +30d": f"{projected_30d:.1f}",
                    "Projected Total": f"{projected_total:.1f}",
                    "Confidence Note": "Low data" if points_60d < 2.0 else "Based on last 60 days",
                    "_projected_total": projected_total,
                }
            )
    if risk_rows:
        df_risk = pd.DataFrame(risk_rows).sort_values(by="_projected_total", ascending=False).drop(columns=["_projected_total"])
        st.dataframe(df_risk, use_container_width=True, hide_index=True)
    else:
        info_box("No active employees currently trend to 8.0+ points in the next 30 days.")

    st.markdown("#### Absenteeism Trend (Last 90 Days, Weekdays Only)")
    trend_rows = [dict(r) for r in fetchall(conn, sql_trend_90d, (*emp_ids, (today - timedelta(days=90)).isoformat()))]
    all_days = pd.bdate_range(start=today - timedelta(days=90), end=today)
    trend_df = pd.DataFrame({"point_day": all_days, "Total Points": 0.0})
    if trend_rows:
        trend_points = pd.DataFrame(
            {
                "point_day": pd.to_datetime([r.get("point_day") for r in trend_rows]),
                "Total Points": [float(r.get("pts") or 0.0) for r in trend_rows],
            }
        )
        trend_df = trend_df.merge(trend_points, on="point_day", how="left", suffixes=("", "_q"))
        trend_df["Total Points"] = trend_df["Total Points_q"].fillna(trend_df["Total Points"]) 
        trend_df = trend_df.drop(columns=["Total Points_q"])
    trend_df = trend_df.rename(columns={"point_day": "Date"}).set_index("Date")
    st.line_chart(trend_df)

    st.markdown("#### Day-of-Week Hotspots (Last 365 Days, Weekdays Only)")
    dow_rows = [dict(r) for r in fetchall(conn, sql_hotspots_365, (*emp_ids, (today - timedelta(days=365)).isoformat()))]
    dow_map = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}
    if dow_rows:
        df_dow = pd.DataFrame(
            [
                {
                    "Day of Week": dow_map.get(int(r.get("dow") or 0), str(r.get("dow") or "—")),
                    "Total Points": f"{float(r.get('total_points') or 0.0):.1f}",
                    "Incidents": int(r.get("incidents") or 0),
                    "Avg Points/Incident": f"{(float(r.get('total_points') or 0.0) / max(int(r.get('incidents') or 0), 1)):.2f}",
                }
                for r in dow_rows
            ]
        )
        st.dataframe(df_dow, use_container_width=True, hide_index=True)
    else:
        info_box("No point incidents in the last 365 days for this filter.")


# ── Employees ─────────────────────────────────────────────────────────────────
def employees_page(conn, building: str) -> None:
    page_heading("Employees", "Look up employees and review current attendance status.")

    rows = load_employees(conn, building=building)

    if not rows:
        info_box("No matching employees found.")
        return

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
    section_label("Point History (all events)")
    hist = [dict(r) for r in repo.get_points_history(conn, emp_id, limit=5000)]

    pdf_bytes = build_point_history_pdf(emp, hist)
    safe_last = str(emp.get("last_name") or "employee").replace(" ", "_")
    safe_first = str(emp.get("first_name") or "").replace(" ", "_")
    report_date = date.today().strftime("%Y%m%d")
    st.download_button(
        "Download Point History PDF",
        data=pdf_bytes,
        file_name=f"attendance-history-{emp_id}-{safe_last}-{safe_first}-{report_date}.pdf",
        mime="application/pdf",
        use_container_width=False,
    )

    if hist:
        df_h = pd.DataFrame(hist)[["point_date", "points", "reason", "note", "point_total"]]
        df_h["point_date"] = df_h["point_date"].apply(fmt_date)
        df_h["points"] = df_h["points"].apply(lambda v: f"{float(v or 0):.1f}")
        df_h["point_total"] = df_h["point_total"].apply(lambda v: f"{float(v or 0):.1f}")
        df_h.columns = ["Date", "Points", "Reason", "Note", "Running Total"]
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

    # Employee picker (Streamlit selectbox has built-in type-to-search: focus it and start typing)
    # Kept keyboard-friendly: Tab into the dropdown, type a few letters, use arrows + Enter.
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

    # When the employee changes, nudge keyboard focus to the Date field (best-effort).
    prev_focus_emp = st.session_state.get("_focus_emp_id")
    if prev_focus_emp != emp_id:
        st.session_state["_focus_emp_id"] = emp_id
        components.html(
            """<script>
            // best-effort focus: Streamlit renders inputs with aria-labels
            const sel = () => document.querySelector('input[aria-label="Date (MM/DD/YYYY)"]');
            const tryFocus = () => { const el = sel(); if (el) { el.focus(); el.select?.(); return true; } return false; };
            let tries = 0;
            const t = setInterval(() => { tries++; if (tryFocus() || tries > 20) clearInterval(t); }, 100);
            </script>""",
            height=0,
        )
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
        with st.form("ledger_entry", clear_on_submit=False):
            # Keyboard-first entry order (Tab works naturally in this top-to-bottom layout)
            # Date in MM/DD/YYYY (text input is faster than clicking a date picker for batch work)
            date_str = st.text_input(
                "Date (MM/DD/YYYY)",
                value=date.today().strftime("%m/%d/%Y"),
                placeholder="MM/DD/YYYY",
                key="ledger_date_str",
            )

            points = st.selectbox(
                "Points",
                [0.5, 1.0, 1.5],
                index=0,
                key="ledger_points",
            )

            reason = st.selectbox(
                "Reason",
                ["Tardy/Early Leave", "Absence", "No Call/No Show"],
                index=0,
                key="ledger_reason",
            )

            note = st.text_input("Note (optional)", key="ledger_note")
            flag_code = st.text_input("Flag code (optional)", key="ledger_flag")

            submit = st.form_submit_button("Add Point", use_container_width=True)

        if submit:
            # Parse MM/DD/YYYY
            try:
                p_date = datetime.strptime(date_str.strip(), "%m/%d/%Y").date()
            except Exception:
                st.error("Invalid date. Use MM/DD/YYYY (example: 03/02/2026).")
            else:
                if p_date > date.today():
                    st.error("Date cannot be in the future.")
                else:
                    try:
                        preview = services.preview_add_point(emp_id, p_date, float(points), reason, note)
                        services.add_point(conn, preview, flag_code=(flag_code or "").strip() or None)
                        st.success(f"Added {float(points):.1f} pts on {fmt_date(p_date)}.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))


    with col_hist:
        section_label("Transaction History (all events)")
        hist = [dict(r) for r in repo.get_points_history(conn, emp_id, limit=5000)]
        if hist:
            df_h = pd.DataFrame(hist)[["id", "point_date", "points", "reason", "note", "point_total"]]
            df_h["point_date"] = df_h["point_date"].apply(fmt_date)
            df_h["points"] = df_h["points"].apply(lambda v: f"{float(v or 0):.1f}")
            df_h["point_total"] = df_h["point_total"].apply(lambda v: f"{float(v or 0):.1f}")
            df_h.columns = ["ID", "Date", "Pts", "Reason", "Note", "Running Total"]
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
    ensure_session_defaults()
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

        # Placeholder so the spotlight renders AFTER page content updates session state
        spotlight_placeholder = st.empty()

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

    # Render spotlight after page runs so it always reflects the current selection
    with spotlight_placeholder.container():
        selected_employee_sidebar(conn, st.session_state.get("selected_employee_id"))

ensure_session_defaults()
if not is_authenticated():
    login_page()
else:
    main()
