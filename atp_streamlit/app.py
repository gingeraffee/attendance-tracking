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
import plotly.graph_objects as go
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
    --bg:      #060d1f;
    --bg2:     #090f24;
    --surface: rgba(10,20,52,0.70);
    --surface2:rgba(13,26,64,0.55);
    --border:  rgba(79,142,247,.18);
    --shadow:  0 4px 28px rgba(0,0,0,.55);
    --text:    #d4e1f7;
    --muted:   #6a8ab8;
    --faint:   #384d6e;
    --blue:    #4f8ef7;
    --cyan:    #00d4ff;
    --green:   #00ff9d;
    --amber:   #ffb020;
    --red:     #ff3d56;
    --purple:  #a855f7;
}

/* ── Base ── */
.stApp { background: #060d1f !important; color: var(--text); }
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1440px; }
footer, #MainMenu { visibility: hidden; }

/* ── Aurora background (injected div) ── */
@keyframes aurora-drift {
  0%   { background-position: 0%   0%;  }
  33%  { background-position: 100% 30%; }
  66%  { background-position: 55%  100%;}
  100% { background-position: 0%   0%;  }
}
.aurora-bg {
    position: fixed; inset: 0;
    background:
        radial-gradient(ellipse 65% 55% at 18% 28%, rgba(79,142,247,.10) 0%, transparent 100%),
        radial-gradient(ellipse 55% 65% at 82% 72%, rgba(0,212,255,.08) 0%, transparent 100%),
        radial-gradient(ellipse 45% 55% at 52% 88%, rgba(168,85,247,.06) 0%, transparent 100%);
    background-size: 200% 200%;
    animation: aurora-drift 28s ease-in-out infinite;
    pointer-events: none; z-index: 1;
}

/* ── Tech grid (injected div) ── */
.tech-grid-overlay {
    position: fixed; inset: 0;
    background-image:
        linear-gradient(rgba(79,142,247,.022) 1px, transparent 1px),
        linear-gradient(90deg, rgba(79,142,247,.022) 1px, transparent 1px);
    background-size: 50px 50px;
    pointer-events: none; z-index: 2;
}


/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #030810 0%, #060d1f 100%) !important;
    border-right: 1px solid rgba(79,142,247,.15) !important;
    width: 276px !important;
    box-shadow: 4px 0 28px rgba(0,0,0,.55), inset -1px 0 0 rgba(79,142,247,.06);
}
section[data-testid="stSidebar"] * { color: #7899c8 !important; }
section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background: #0a1428 !important; color: #c9d8f0 !important;
    border: 1px solid rgba(79,142,247,.25) !important;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] input,
section[data-testid="stSidebar"] div[data-baseweb="select"] span,
section[data-testid="stSidebar"] div[data-baseweb="select"] div {
    color: #c9d8f0 !important; -webkit-text-fill-color: #c9d8f0 !important;
}

/* ── Metric tiles ── */
div[data-testid="stMetric"] {
    background: rgba(10,20,52,0.65) !important;
    backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
    border: 1px solid rgba(79,142,247,.20) !important;
    border-top: 2px solid rgba(79,142,247,.70) !important;
    border-radius: 14px;
    padding: 1.1rem 1.25rem .85rem 1.25rem;
    box-shadow: 0 4px 28px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.04);
    position: relative; overflow: hidden;
}
div[data-testid="stMetric"]::before {
    content: ''; position: absolute; inset: 0;
    background: linear-gradient(135deg, rgba(79,142,247,.07) 0%, transparent 55%);
    pointer-events: none;
}
div[data-testid="stMetric"] label {
    color: var(--muted) !important; font-size: .72rem !important;
    font-weight: 700 !important; letter-spacing: .10em !important;
    text-transform: uppercase !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #e8f1ff !important; font-size: 2rem !important;
    font-weight: 800 !important; letter-spacing: -.03em !important;
    font-variant-numeric: tabular-nums;
    text-shadow: 0 0 22px rgba(79,142,247,.38);
}

/* ── Buttons ── */
.stButton > button {
    border-radius: 8px !important; font-weight: 600 !important;
    border: 1px solid rgba(79,142,247,.40) !important;
    background: linear-gradient(135deg, rgba(79,142,247,.13), rgba(79,142,247,.05)) !important;
    color: #7eb3ff !important; transition: all .2s !important;
}
.stButton > button:hover {
    border-color: var(--blue) !important;
    background: rgba(79,142,247,.20) !important;
    box-shadow: 0 0 22px rgba(79,142,247,.32), inset 0 0 14px rgba(79,142,247,.08) !important;
    color: #a8d0ff !important;
}

/* ── DataFrames / Tabs / Inputs ── */
.stDataFrame {
    border: 1px solid rgba(79,142,247,.18) !important;
    border-radius: 12px !important; overflow: hidden;
    box-shadow: 0 0 0 1px rgba(79,142,247,.06) !important;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 4px; border-bottom: 1px solid rgba(79,142,247,.15); background: transparent;
}
.stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; }
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: rgba(79,142,247,.12) !important;
    border-bottom: 2px solid var(--blue) !important;
}
.stTextInput  > div > div > input,
.stNumberInput > div > div > input,
.stDateInput  > div > div > input {
    background: rgba(10,20,52,.85) !important;
    border: 1px solid rgba(79,142,247,.25) !important;
    border-radius: 8px !important; color: var(--text) !important;
}
.stTextInput  > div > div > input:focus,
.stNumberInput > div > div > input:focus {
    border-color: var(--blue) !important;
    box-shadow: 0 0 0 3px rgba(79,142,247,.16) !important;
}
h1,h2,h3,h4,h5,h6 { color: var(--text) !important; }
p, label { color: var(--muted) !important; }

/* ── Page heading ── */
.page-heading { margin-bottom: 1.4rem; }
.page-heading h1 {
    font-size: 1.6rem; font-weight: 800; color: #e8f1ff;
    margin: 0 0 .15rem 0; letter-spacing: -.025em;
    text-shadow: 0 0 32px rgba(79,142,247,.32);
}
.page-heading p { color: var(--muted); font-size: .87rem; margin: 0; }
.accent-bar { width: 44px; height: 3px; border-radius: 99px; margin: .25rem 0 .4rem 0; }

/* ── Cards ── */
.card {
    background: rgba(10,20,52,0.62); backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border: 1px solid rgba(79,142,247,.16); border-radius: 14px;
    padding: 1.2rem 1.4rem;
    box-shadow: 0 4px 24px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.04);
    margin-bottom: .9rem;
}
.card-sm {
    background: rgba(10,20,52,0.55); backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid rgba(79,142,247,.13); border-radius: 10px;
    padding: .8rem 1rem; box-shadow: 0 2px 16px rgba(0,0,0,.32);
}
/* Fix hardcoded dark text inside cards for the dark theme */
.card h2 { color: #d4e1f7 !important; }

/* ── Section label ── */
.section-label {
    font-size: .71rem; font-weight: 700; letter-spacing: .12em;
    text-transform: uppercase; color: var(--blue); margin: 0 0 .55rem 0;
    text-shadow: 0 0 12px rgba(79,142,247,.45);
}

/* ── Divider ── */
.divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(79,142,247,.30), transparent);
    margin: 1.25rem 0; box-shadow: 0 0 8px rgba(79,142,247,.08);
}

/* ── Info / warn / danger boxes ── */
.info-box {
    background: rgba(79,142,247,.07); border: 1px solid rgba(79,142,247,.26);
    border-left: 3px solid var(--blue); border-radius: 8px; padding: .75rem 1rem;
    color: var(--text); font-size: .88rem;
    box-shadow: inset 0 0 20px rgba(79,142,247,.04), 0 0 12px rgba(79,142,247,.05);
}
.warn-box {
    background: rgba(255,176,32,.07); border: 1px solid rgba(255,176,32,.26);
    border-left: 3px solid var(--amber); border-radius: 8px; padding: .75rem 1rem;
    color: var(--text); font-size: .88rem;
    box-shadow: inset 0 0 20px rgba(255,176,32,.04);
}
.danger-box {
    background: rgba(255,61,86,.07); border: 1px solid rgba(255,61,86,.26);
    border-left: 3px solid var(--red); border-radius: 8px; padding: .75rem 1rem;
    color: var(--text); font-size: .88rem;
    box-shadow: inset 0 0 20px rgba(255,61,86,.04);
}

/* ── Upcoming list rows ── */
.list-row {
    background: rgba(10,20,52,0.55); border: 1px solid rgba(79,142,247,.12);
    border-radius: 10px; padding: .65rem 1rem; margin-bottom: .38rem;
}

/* ── Sidebar brand ── */
.sidebar-brand {
    padding: .75rem 0 1rem 0; border-bottom: 1px solid rgba(79,142,247,.12); margin-bottom: 1rem;
}
.sidebar-brand .name {
    font-size: 1.05rem; font-weight: 800; color: #c9d8f0 !important;
    letter-spacing: -.01em; text-shadow: 0 0 14px rgba(79,142,247,.28);
}
.sidebar-brand .sub  { font-size: .72rem; color: #2d4060 !important; margin-top: .1rem; }
.sidebar-nav-label   {
    font-size: .65rem !important; font-weight: 700 !important; letter-spacing: .12em !important;
    text-transform: uppercase !important; color: #2a3e58 !important;
    margin: 1rem 0 .3rem 0 !important; display: block;
}

section[data-testid="stSidebar"] .sidebar-employee-card {
    margin-top: 1.1rem; padding: 1rem .9rem .85rem; border-radius: 16px;
    border: 1px solid rgba(79,142,247,.15);
    background: rgba(8,16,42,0.88); backdrop-filter: blur(10px);
    box-shadow: 0 8px 28px rgba(0,0,0,.55), inset 0 1px 0 rgba(255,255,255,.04);
    position: relative; overflow: hidden;
}
section[data-testid="stSidebar"] .sidebar-employee-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #ff3d56, #cc1c2e, #ff3d56);
    animation: card-top-border-glow 3s ease-in-out infinite;
}
@keyframes card-top-border-glow {
    0%,100% { opacity: .85; box-shadow: none; }
    50% { opacity: 1; box-shadow: 0 0 12px rgba(255,61,86,.5); }
}
section[data-testid="stSidebar"] .sidebar-employee-title {
    font-size: .72rem; letter-spacing: .16em; text-transform: uppercase; font-weight: 700;
    color: #ff3d56 !important; -webkit-text-fill-color: #ff3d56 !important;
    text-shadow: 0 0 10px rgba(255,61,86,.4); margin-bottom: .45rem;
}
section[data-testid="stSidebar"] .sidebar-employee-name {
    font-size: 1.32rem; font-weight: 800;
    color: #d4e1f7 !important; -webkit-text-fill-color: #d4e1f7 !important;
    letter-spacing: -.015em; line-height: 1.2; margin-bottom: .7rem;
    padding-bottom: .6rem; border-bottom: 1px solid rgba(79,142,247,.15);
}
section[data-testid="stSidebar"] .sidebar-employee-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: .35rem;
}
section[data-testid="stSidebar"] .sidebar-employee-item {
    background: rgba(5,10,28,0.75); border: 1px solid rgba(79,142,247,.14);
    border-radius: 8px; padding: .38rem .45rem;
}
section[data-testid="stSidebar"] .sidebar-employee-item.full-width { grid-column: 1 / -1; }
section[data-testid="stSidebar"] .sidebar-employee-item .label {
    display: block; font-size: .62rem; letter-spacing: .10em; text-transform: uppercase;
    color: #2d4465 !important; font-weight: 700; margin-bottom: .12rem;
}
section[data-testid="stSidebar"] .sidebar-employee-item .value {
    display: block; font-size: .9rem; font-weight: 600;
    color: #8aaad4 !important; letter-spacing: -.01em;
}
section[data-testid="stSidebar"] .sidebar-employee-item .value.highlight {
    color: #ff3d56 !important; -webkit-text-fill-color: #ff3d56 !important;
    font-size: .9rem; font-weight: 800; text-shadow: 0 0 8px rgba(255,61,86,.35);
}

/* ─────────────────────── ANIMATIONS ─────────────────────── */

/* Metric tiles — neon top-border cycles */
@keyframes tile-neon {
  0%, 100% {
    border-top-color: rgba(79,142,247,.70) !important;
    box-shadow: 0 4px 28px rgba(0,0,0,.45), 0 0 0 1px rgba(79,142,247,.04);
    transform: translateY(0);
  }
  50% {
    border-top-color: rgba(0,212,255,.95) !important;
    box-shadow: 0 6px 34px rgba(0,0,0,.50), 0 0 24px rgba(0,212,255,.22), 0 0 0 1px rgba(0,212,255,.10);
    transform: translateY(-2px);
  }
}
div[data-testid="stMetric"]          { animation: tile-neon 5s ease-in-out infinite; }
div[data-testid="stMetric"]:nth-child(1) { animation-delay: 0s;   }
div[data-testid="stMetric"]:nth-child(2) { animation-delay: 1.1s; }
div[data-testid="stMetric"]:nth-child(3) { animation-delay: 2.2s; }
div[data-testid="stMetric"]:nth-child(4) { animation-delay: 3.3s; }
div[data-testid="stMetric"]:nth-child(5) { animation-delay: 1.6s; }

/* Accent bar — neon gradient sweep */
@keyframes accent-neon {
  0%   { background-position: 0%   50%; box-shadow: 0 0 12px rgba(79,142,247,.60), 0 0 28px rgba(79,142,247,.20); }
  50%  { background-position: 100% 50%; box-shadow: 0 0 20px rgba(0,212,255,.80), 0 0 40px rgba(0,212,255,.28); }
  100% { background-position: 0%   50%; box-shadow: 0 0 12px rgba(79,142,247,.60), 0 0 28px rgba(79,142,247,.20); }
}
.accent-bar {
    background: linear-gradient(90deg, var(--blue), var(--cyan), var(--purple), var(--blue));
    background-size: 300% 300%;
    animation: accent-neon 4s ease-in-out infinite !important;
}

/* Cards — border breathes */
@keyframes card-border-breathe {
  0%, 100% { border-color: rgba(79,142,247,.16); box-shadow: 0 4px 24px rgba(0,0,0,.42); }
  50%       { border-color: rgba(79,142,247,.34); box-shadow: 0 6px 32px rgba(0,0,0,.48), 0 0 16px rgba(79,142,247,.09); }
}
.card, .card-sm { animation: card-border-breathe 7s ease-in-out infinite; }

/* Pulsing LIVE dot */
@keyframes live-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(0,255,157,.6), 0 0 8px rgba(0,255,157,.45); background: #00ff9d; }
  50%       { box-shadow: 0 0 0 9px rgba(0,255,157,0), 0 0 18px rgba(0,255,157,.75); background: #00ffb8; }
}
.live-dot {
    display: inline-block; width: 9px; height: 9px; border-radius: 50%;
    background: #00ff9d; margin-right: 8px; vertical-align: middle;
    animation: live-pulse 1.8s ease-in-out infinite;
}

/* Section labels — neon shimmer */
@keyframes label-neon {
  0%, 100% { text-shadow: 0 0 8px rgba(79,142,247,.32); opacity: .85; }
  50%       { text-shadow: 0 0 18px rgba(79,142,247,.70); opacity: 1; }
}
.section-label { animation: label-neon 4s ease-in-out infinite; }

/* Sidebar brand border */
@keyframes sidebar-brand-glow {
  0%, 100% { border-bottom-color: rgba(79,142,247,.12); }
  50%       { border-bottom-color: rgba(79,142,247,.40); box-shadow: 0 1px 0 rgba(79,142,247,.08); }
}
.sidebar-brand { animation: sidebar-brand-glow 5s ease-in-out infinite; }

/* Entrance — boxes */
@keyframes box-fade-in {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
.info-box, .warn-box, .danger-box { animation: box-fade-in .45s ease-out both; }

/* Entrance — page heading */
@keyframes heading-in {
  from { opacity: 0; transform: translateX(-10px); }
  to   { opacity: 1; transform: translateX(0); }
}
.page-heading { animation: heading-in .5s ease-out both; }

/* DataFrames — neon frame pulse */
@keyframes dataframe-glow {
  0%, 100% { box-shadow: 0 0 0 1px rgba(79,142,247,.08); }
  50%       { box-shadow: 0 0 0 1px rgba(79,142,247,.28), 0 0 20px rgba(79,142,247,.08); }
}
.stDataFrame, [data-testid="stArrowVegaLiteChart"] {
    animation: dataframe-glow 5s ease-in-out infinite; border-radius: 12px !important;
}

/* Divider breathe */
@keyframes divider-breathe {
  0%, 100% { opacity: .55; }
  50%       { opacity: 1; box-shadow: 0 0 12px rgba(79,142,247,.20); }
}
.divider { animation: divider-breathe 5s ease-in-out infinite; }

/* Respect prefers-reduced-motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important; animation-iteration-count: 1 !important;
  }
}
</style>""",
        unsafe_allow_html=True,
    )
    # Inject fixed-position atmospheric overlays (aurora glow, tech grid)
    st.markdown(
        '<div class="aurora-bg"></div>'
        '<div class="tech-grid-overlay"></div>',
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
    return f"<span style='{s}color:#7899c8;background:rgba(79,142,247,.08);border:1px solid rgba(79,142,247,.18)'>{days}d</span>"


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

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def render_hr_live_monitor(
    *,
    points_24h: int,
    points_7d: int,
    rolloffs_due_7d: int,
    perfect_due_7d: int,
    label: str = "Monitoring attendance activity",
):
    """
    Data-driven 'live monitor' animation.
    - Speed increases with points activity
    - Glow increases with upcoming deadlines (rolloffs/perfect due soon)
    """

    # --- Activity score (0..1): how "busy" things are ---
    # Weighted: last 24h matters most, then 7d.
    activity_raw = (points_24h * 2.5) + (points_7d * 0.6)
    # Log scale so it doesn't go ridiculous on big weeks:
    activity_norm = 1.0 - math.exp(-activity_raw / 12.0)  # ~0..1
    activity_norm = _clamp(activity_norm, 0.0, 1.0)

    # --- Urgency score (0..1): deadlines coming due ---
    urgency_raw = (rolloffs_due_7d * 1.2) + (perfect_due_7d * 1.4)
    urgency_norm = 1.0 - math.exp(-urgency_raw / 10.0)
    urgency_norm = _clamp(urgency_norm, 0.0, 1.0)

    # --- Map scores -> animation + glow ---
    # Sweep duration: 2.6s (calm) down to 0.9s (hot)
    sweep_s = 2.6 - (1.7 * activity_norm)
    sweep_s = _clamp(sweep_s, 0.9, 2.6)

    # Glow opacity: subtle -> bright
    glow = 0.18 + (0.55 * urgency_norm)  # 0.18..0.73
    glow = _clamp(glow, 0.18, 0.75)

    # Base line opacity: slightly responds to activity
    baseline = 0.20 + (0.25 * activity_norm)  # 0.20..0.45
    baseline = _clamp(baseline, 0.18, 0.50)

    # Status text
    if activity_norm < 0.18 and urgency_norm < 0.18:
        status = "Calm"
    elif activity_norm < 0.45 and urgency_norm < 0.35:
        status = "Active"
    elif activity_norm < 0.75 or urgency_norm < 0.65:
        status = "Busy"
    else:
        status = "Hot"

    # Render
    st.markdown(
        f"""
<style>
.hr-monitor-wrap {{
  margin: 6px 0 10px 0;
}}

.hr-monitor-top {{
  display:flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 6px;
}}

.hr-monitor-label {{
  font-size: 0.92rem;
  opacity: 0.92;
}}

.hr-monitor-status {{
  font-size: 0.86rem;
  opacity: 0.75;
  white-space: nowrap;
}}

.hr-live-monitor {{
  position: relative;
  width: 100%;
  height: 14px;
  border-radius: 999px;
  background: rgba(255,255,255,0.10);
  overflow: hidden;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.12);
}}

.hr-live-monitor::before {{
  content:"";
  position:absolute;
  left:0; top:50%;
  transform: translateY(-50%);
  width:100%;
  height:2px;
  background: rgba(120,200,255,{baseline});
}}

.hr-live-monitor::after {{
  content:"";
  position:absolute;
  top:0; left:-30%;
  width:30%;
  height:100%;
  background: linear-gradient(90deg,
    rgba(0,0,0,0),
    rgba(120,200,255,{glow}),
    rgba(120,200,255,{_clamp(glow+0.12, 0.20, 0.90)}),
    rgba(120,200,255,{glow}),
    rgba(0,0,0,0)
  );
  animation: hr_sweep {sweep_s:.2f}s linear infinite;
}}

@keyframes hr_sweep {{
  0%   {{ left: -30%; }}
  100% {{ left: 100%; }}
}}
</style>

<div class="hr-monitor-wrap">
  <div class="hr-monitor-top">
    <div class="hr-monitor-label">{label}</div>
    <div class="hr-monitor-status">{status} · 24h:{points_24h} · 7d:{points_7d} · due7d:{rolloffs_due_7d + perfect_due_7d}</div>
  </div>
  <div class="hr-live-monitor"></div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_tech_hud(building: str) -> None:
    """Live HUD status bar — ticking clock, building, session uptime."""
    components.html(
        f"""<!DOCTYPE html>
<html><head><style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#060d1f; font-family:'SF Mono','Fira Code',ui-monospace,'Cascadia Code','Courier New',monospace; overflow:hidden; }}
  #hud {{
    display:flex; justify-content:space-between; align-items:center;
    padding:8px 16px;
    background:rgba(6,13,31,0.92);
    border:1px solid rgba(79,142,247,.24);
    border-radius:10px;
    font-size:11px; letter-spacing:.07em; color:#3d5a80;
  }}
  .left {{ display:flex; align-items:center; gap:0; }}
  .right {{ display:flex; align-items:center; gap:0; }}
  .seg {{ white-space:nowrap; }}
  .dot {{
    display:inline-block; width:6px; height:6px; border-radius:50%;
    background:#00ff9d; margin-right:5px; vertical-align:middle;
    box-shadow:0 0 5px rgba(0,255,157,.6);
    animation:blink 1.8s ease-in-out infinite;
  }}
  @keyframes blink {{
    0%,100% {{ opacity:1; box-shadow:0 0 4px rgba(0,255,157,.6); }}
    50%      {{ opacity:.4; box-shadow:0 0 10px rgba(0,255,157,.9); }}
  }}
  .val {{ color:#5a8fd4; }}
  .sep {{ color:rgba(79,142,247,.28); padding:0 9px; }}
  #hud-time {{ color:#00d4ff; font-weight:700; letter-spacing:.12em; min-width:68px; text-align:right; }}
</style></head><body>
<div id="hud">
  <div class="left">
    <span class="seg"><span class="dot"></span>SYS&nbsp;<span style="color:#00ff9d">ONLINE</span></span>
    <span class="sep">|</span>
    <span class="seg">BUILDING&nbsp;<span class="val">{building.upper()}</span></span>
    <span class="sep">|</span>
    <span class="seg">SESSION&nbsp;<span class="val" id="uptime">00:00:00</span></span>
  </div>
  <div class="right">
    <span class="seg" id="datestamp"></span>
    <span class="sep">|</span>
    <span id="hud-time">--:--:--</span>
  </div>
</div>
<script>
(function(){{
  var s=Date.now();
  var D=['SUN','MON','TUE','WED','THU','FRI','SAT'];
  var M=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  function p(n){{return n<10?'0'+n:''+n;}}
  function tick(){{
    var d=new Date();
    var t=document.getElementById('hud-time');
    var ds=document.getElementById('datestamp');
    var up=document.getElementById('uptime');
    if(!t)return;
    t.textContent=p(d.getHours())+':'+p(d.getMinutes())+':'+p(d.getSeconds());
    ds.textContent=D[d.getDay()]+' '+p(d.getDate())+' '+M[d.getMonth()]+' '+d.getFullYear();
    var e=Math.floor((Date.now()-s)/1000);
    up.textContent=p(Math.floor(e/3600))+':'+p(Math.floor(e%3600/60))+':'+p(e%60);
  }}
  tick(); setInterval(tick,1000);
}})();
</script>
</body></html>""",
        height=50,
        scrolling=False,
    )


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


def get_employee_spotlight(conn, employee_id: int | None) -> dict | None:
    if not employee_id:
        return None

    if is_pg(conn):
        sql = '''
            SELECT e.employee_id,
                   e.first_name,
                   e.last_name,
                   COALESCE(e."Location", '') AS building,
                   GREATEST(0.0, ROUND(COALESCE((
                       SELECT SUM(ph.points) FROM points_history ph WHERE ph.employee_id = e.employee_id
                   ), 0.0)::numeric, 1)::float8) AS point_total,
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
        return None
    return dict(rows[0])


def selected_employee_sidebar(conn, employee_id: int | None) -> None:
    emp = get_employee_spotlight(conn, employee_id)
    if not emp:
        return
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
    st.markdown(
        """<style>
        .st-key-spotlight_add_point button {
            background: transparent !important;
            border: 1px solid rgba(255,61,86,.35) !important;
            color: rgba(255,61,86,.85) !important;
            font-size: .6rem !important;
            padding: .18rem .5rem !important;
            border-radius: 6px !important;
            font-family: 'SF Mono','Fira Code',monospace !important;
            letter-spacing: .1em !important;
            text-transform: uppercase !important;
            font-weight: 600 !important;
            margin-top: .4rem !important;
            transition: all .15s ease !important;
        }
        .st-key-spotlight_add_point button:hover {
            background: rgba(255,61,86,.08) !important;
            border-color: rgba(255,61,86,.8) !important;
            color: #ff3d56 !important;
            box-shadow: 0 0 10px rgba(255,61,86,.25) !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )
    if st.button("⊕  Add Point to Record", key="spotlight_add_point", use_container_width=True):
        st.session_state["ledger_emp_id"] = int(emp["employee_id"])
        st.session_state["_nav_to"] = "Points Ledger"
        st.rerun()


def load_employees(conn, q: str = "", building: str = "All") -> list[dict]:
    rows = [dict(r) for r in repo.search_employees(conn, q=q, limit=3000)]
    if building != "All":
        rows = [r for r in rows if (r.get("location") or "") == building]
    return rows


# ── Dashboard ─────────────────────────────────────────────────────────────────
def dashboard_page(conn, building: str) -> None:
    page_heading(
        '<span class="live-dot"></span>Dashboard',
        "Real-time overview of attendance activity, thresholds, and upcoming actions.",
    )
    render_tech_hud(building)

    today = date.today()
    in_30_days = today + timedelta(days=30)
    employees = load_employees(conn, building=building)
    emp_ids = [int(e["employee_id"]) for e in employees]

    if not emp_ids:
        info_box("No employees found for this building filter.")
        return
    ph = ",".join(["?" if not is_pg(conn) else "%s"] * len(emp_ids))   
    
    def _scalar_n(conn, sql: str, params: tuple) -> int:
        rows = fetchall(conn, sql, params)
        if not rows:
            return 0
        r0 = dict(rows[0])
        return int(r0.get("n") or 0)
    
    # ── HR Live Monitor (data-driven animation) ───────────────────────────────
    since_24h = (today - timedelta(days=1)).isoformat()
    since_7d = (today - timedelta(days=7)).isoformat()
    due_7d = (today + timedelta(days=7)).isoformat()
    if is_pg(conn):
        sql_points_since = f"""
            SELECT COUNT(*) AS n
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND (ph.point_date::date) >= (%s::date)
               AND COALESCE(ph.points, 0.0) > 0.0
        """
        sql_roll_due_7d = f"""
            SELECT COUNT(*) AS n
              FROM employees
             WHERE employee_id IN ({ph})
               AND rolloff_date IS NOT NULL
               AND (rolloff_date::date) >= (%s::date)
               AND (rolloff_date::date) <= (%s::date)
        """
        sql_perf_due_7d = f"""
            SELECT COUNT(*) AS n
              FROM employees
             WHERE employee_id IN ({ph})
               AND perfect_attendance IS NOT NULL
               AND (perfect_attendance::date) >= (%s::date)
               AND (perfect_attendance::date) <= (%s::date)
        """

        points_24h = _scalar_n(conn, sql_points_since, (*emp_ids, since_24h))
        points_7d = _scalar_n(conn, sql_points_since, (*emp_ids, since_7d))
        rolloffs_due_7d = _scalar_n(conn, sql_roll_due_7d, (*emp_ids, today.isoformat(), due_7d))
        perfect_due_7d = _scalar_n(conn, sql_perf_due_7d, (*emp_ids, today.isoformat(), due_7d))

    else:
        sql_points_since = f"""
            SELECT COUNT(*) AS n
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND date(ph.point_date) >= date(?)
               AND COALESCE(ph.points, 0.0) > 0.0
        """
        sql_roll_due_7d = f"""
            SELECT COUNT(*) AS n
              FROM employees
             WHERE employee_id IN ({ph})
               AND rolloff_date IS NOT NULL
               AND date(rolloff_date) >= date(?)
               AND date(rolloff_date) <= date(?)
        """
        sql_perf_due_7d = f"""
            SELECT COUNT(*) AS n
              FROM employees
             WHERE employee_id IN ({ph})
               AND perfect_attendance IS NOT NULL
               AND date(perfect_attendance) >= date(?)
               AND date(perfect_attendance) <= date(?)
        """

        points_24h = _scalar_n(conn, sql_points_since, (*emp_ids, since_24h))
        points_7d = _scalar_n(conn, sql_points_since, (*emp_ids, since_7d))
        rolloffs_due_7d = _scalar_n(conn, sql_roll_due_7d, (*emp_ids, today.isoformat(), due_7d))
        perfect_due_7d = _scalar_n(conn, sql_perf_due_7d, (*emp_ids, today.isoformat(), due_7d))

    render_hr_live_monitor(
        points_24h=points_24h,
        points_7d=points_7d,
        rolloffs_due_7d=rolloffs_due_7d,
        perfect_due_7d=perfect_due_7d,
        label="Monitoring attendance activity",
    )

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
        sql_weekday_window = f'''
            WITH totals AS (
                SELECT EXTRACT(DOW FROM ph.point_date::date)::int AS dow,
                       ROUND(COALESCE(SUM(ph.points), 0.0)::numeric, 1)::float8 AS total_points,
                       COUNT(*) AS incidents
                  FROM points_history ph
                 WHERE ph.employee_id IN ({ph})
                   AND (ph.point_date::date) >= (%s::date)
                   AND (ph.point_date::date) < (%s::date)
                   AND COALESCE(ph.points, 0.0) > 0.0
                 GROUP BY EXTRACT(DOW FROM ph.point_date::date)
            ),
            emp_counts AS (
                SELECT d.dow,
                       COUNT(*) AS employees_pointed
                  FROM (
                        SELECT EXTRACT(DOW FROM ph.point_date::date)::int AS dow,
                               ph.employee_id,
                               SUM(COALESCE(ph.points, 0.0)) AS employee_points
                          FROM points_history ph
                         WHERE ph.employee_id IN ({ph})
                           AND (ph.point_date::date) >= (%s::date)
                           AND (ph.point_date::date) < (%s::date)
                           AND COALESCE(ph.points, 0.0) > 0.0
                         GROUP BY EXTRACT(DOW FROM ph.point_date::date), ph.employee_id
                        HAVING SUM(COALESCE(ph.points, 0.0)) >= 1.0
                  ) d
                 GROUP BY d.dow
            )
            SELECT t.dow,
                   t.total_points,
                   t.incidents,
                   COALESCE(e.employees_pointed, 0) AS employees_pointed
              FROM totals t
              LEFT JOIN emp_counts e ON e.dow = t.dow
        '''
        sql_weekday_reason = f'''
            SELECT ph.reason, COUNT(*) AS n
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND (ph.point_date::date) >= (%s::date)
               AND (ph.point_date::date) < (%s::date)
               AND EXTRACT(DOW FROM ph.point_date::date)::int = (%s)
               AND COALESCE(ph.points, 0.0) > 0.0
               AND COALESCE(ph.reason, '') <> ''
             GROUP BY ph.reason
             ORDER BY n DESC, ph.reason
             LIMIT 1
        '''
        sql_weekday_employees = f'''
            SELECT e.employee_id,
                   e.last_name || ', ' || e.first_name AS employee,
                   COALESCE(e."Location", '') AS building,
                   COUNT(*) AS incidents,
                   ROUND(COALESCE(SUM(ph.points), 0.0)::numeric, 1)::float8 AS total_points
              FROM points_history ph
              JOIN employees e ON e.employee_id = ph.employee_id
             WHERE ph.employee_id IN ({ph})
               AND (ph.point_date::date) >= (%s::date)
               AND (ph.point_date::date) < (%s::date)
               AND EXTRACT(DOW FROM ph.point_date::date)::int = (%s)
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY e.employee_id, e.last_name, e.first_name, e."Location"
             ORDER BY total_points DESC, lower(e.last_name), lower(e.first_name)
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
        sql_weekday_window = f'''
            WITH totals AS (
                SELECT CAST(strftime('%w', ph.point_date) AS INTEGER) AS dow,
                       ROUND(COALESCE(SUM(ph.points), 0.0), 1) AS total_points,
                       COUNT(*) AS incidents
                  FROM points_history ph
                 WHERE ph.employee_id IN ({ph})
                   AND date(ph.point_date) >= date(?)
                   AND date(ph.point_date) < date(?)
                   AND COALESCE(ph.points, 0.0) > 0.0
                 GROUP BY CAST(strftime('%w', ph.point_date) AS INTEGER)
            ),
            emp_counts AS (
                SELECT d.dow,
                       COUNT(*) AS employees_pointed
                  FROM (
                        SELECT CAST(strftime('%w', ph.point_date) AS INTEGER) AS dow,
                               ph.employee_id,
                               SUM(COALESCE(ph.points, 0.0)) AS employee_points
                          FROM points_history ph
                         WHERE ph.employee_id IN ({ph})
                           AND date(ph.point_date) >= date(?)
                           AND date(ph.point_date) < date(?)
                           AND COALESCE(ph.points, 0.0) > 0.0
                         GROUP BY CAST(strftime('%w', ph.point_date) AS INTEGER), ph.employee_id
                        HAVING SUM(COALESCE(ph.points, 0.0)) >= 1.0
                  ) d
                 GROUP BY d.dow
            )
            SELECT t.dow,
                   t.total_points,
                   t.incidents,
                   COALESCE(e.employees_pointed, 0) AS employees_pointed
              FROM totals t
              LEFT JOIN emp_counts e ON e.dow = t.dow
        '''
        sql_weekday_reason = f'''
            SELECT ph.reason, COUNT(*) AS n
              FROM points_history ph
             WHERE ph.employee_id IN ({ph})
               AND date(ph.point_date) >= date(?)
               AND date(ph.point_date) < date(?)
               AND CAST(strftime('%w', ph.point_date) AS INTEGER) = ?
               AND COALESCE(ph.points, 0.0) > 0.0
               AND COALESCE(ph.reason, '') <> ''
             GROUP BY ph.reason
             ORDER BY n DESC, ph.reason
             LIMIT 1
        '''
        sql_weekday_employees = f'''
            SELECT e.employee_id,
                   e.last_name || ', ' || e.first_name AS employee,
                   COALESCE(e."Location", '') AS building,
                   COUNT(*) AS incidents,
                   ROUND(COALESCE(SUM(ph.points), 0.0), 1) AS total_points
              FROM points_history ph
              JOIN employees e ON e.employee_id = ph.employee_id
             WHERE ph.employee_id IN ({ph})
               AND date(ph.point_date) >= date(?)
               AND date(ph.point_date) < date(?)
               AND CAST(strftime('%w', ph.point_date) AS INTEGER) = ?
               AND COALESCE(ph.points, 0.0) > 0.0
             GROUP BY e.employee_id, e.last_name, e.first_name, e."Location"
             ORDER BY total_points DESC, lower(e.last_name), lower(e.first_name)
        '''

    emp_detail_rows = [dict(r) for r in fetchall(conn, sql_emp_detail, tuple(emp_ids))]
    roll_due_rows = [dict(r) for r in fetchall(conn, sql_roll_due, (*emp_ids, today.isoformat(), in_30_days.isoformat()))]
    perf_due_rows = [dict(r) for r in fetchall(conn, sql_perf_due, (*emp_ids, today.isoformat(), in_30_days.isoformat()))]

    bucket_defs = {
        "0": lambda pts: pts == 0,
        "1-4": lambda pts: 1 <= pts <= 4.5,
        "5-6": lambda pts: 5 <= pts <= 6.5,
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
        ("1-4", "1–4.5 Pts"),
        ("5-6", "5–6.5 Pts"),
        ("7", "7+ Pts"),
    ]
    active_bucket = st.session_state.get("dashboard_bucket")

    for col, (key, label) in zip(tile_cols, tile_specs):
        selected = (active_bucket == key) if key != "all" else (active_bucket not in bucket_defs)
        accent, glow = {
            "all": ("#5c6f8c", "rgba(92,111,140,.22)"),
            "0": ("#00a87a", "rgba(0,168,122,.25)"),
            "1-4": ("#4f8ef7", "rgba(79,142,247,.25)"),
            "5-6": ("#e6960a", "rgba(230,150,10,.28)"),
            "7": ("#e0394a", "rgba(224,57,74,.32)"),
        }.get(key, ("#5c6f8c", "rgba(92,111,140,.22)"))
        # Keep style vars local and explicit to avoid NameError in f-string interpolation.
        card_border = "rgba(26,39,68,.16)" if not selected else accent
        card_shadow = f"0 0 0 2px {glow}, 0 8px 18px rgba(15,32,68,.12)" if selected else "0 4px 14px rgba(15,32,68,.08)"
        employees_count = len(emp_detail_rows) if key == "all" else bucket_counts[key]

        col.markdown(
            f"<div class='card-sm' style='margin-bottom:.45rem;padding:.72rem .9rem;"
            f"background:rgba(10,20,52,0.65);border:1px solid {card_border};box-shadow:{card_shadow};cursor:pointer;pointer-events:none;backdrop-filter:blur(12px);'>"
            f"<div style='height:4px;border-radius:999px;background:{accent};margin:-.2rem 0 .6rem 0'></div>"
            f"<div style='font-size:.68rem;letter-spacing:.09em;text-transform:uppercase;color:{accent};font-weight:700'>{label}</div>"
            f"<div style='display:flex;align-items:baseline;justify-content:space-between;margin-top:.18rem'>"
            f"<span style='font-size:1.95rem;font-weight:800;color:#e8f1ff;line-height:1;text-shadow:0 0 18px rgba(79,142,247,.3)'>{employees_count}</span>"
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
            bucket_label_map = dict(tile_specs)
            st.caption(f"Filtered by threshold tile: {bucket_label_map.get(bucket_key, bucket_key)}")

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
            """SELECT COALESCE("Location", '') AS building, COUNT(*) AS n
               FROM employees
              WHERE COALESCE(is_active,1)=1
              GROUP BY COALESCE("Location", '')""",
        )
    ]
    avg_total_rows = [
        dict(r)
        for r in fetchall(
            conn,
            """SELECT COALESCE("Location", '') AS building,
                      AVG(COALESCE(point_total, 0.0)) AS avg_point_total
               FROM employees
              WHERE COALESCE(is_active,1)=1
              GROUP BY COALESCE("Location", '')""",
        )
    ]
    active_by_build = {b: 0 for b in BUILDINGS}
    avg_total_by_build = {b: 0.0 for b in BUILDINGS}
    for r in active_rows:
        if r["building"] in active_by_build:
            active_by_build[r["building"]] = int(r["n"] or 0)
    for r in avg_total_rows:
        if r["building"] in avg_total_by_build:
            avg_total_by_build[r["building"]] = float(r.get("avg_point_total") or 0.0)

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
        avg_point_total = float(avg_total_by_build.get(b) or 0.0)
        cur_total = float(current_points.get(b) or 0.0)
        prev_total = float(prior_points.get(b) or 0.0)
        cur_avg_30d = (cur_total / headcount) if headcount else 0.0
        prev_avg_30d = (prev_total / headcount) if headcount else 0.0
        if prev_avg_30d > 0:
            pct_change = ((cur_avg_30d - prev_avg_30d) / prev_avg_30d) * 100.0
            pct_txt = f"{pct_change:+.1f}%"
        else:
            pct_txt = "—"
        reason_rows = [dict(r) for r in fetchall(conn, sql_build_reasons, (since_30, b))]
        most_common_reason = (reason_rows[0].get("reason") if reason_rows else None) or "—"
        snap_rows.append(
            {
                "Building": b,
                "Active Employees": headcount,
                "Avg Point Total / Employee": f"{avg_point_total:.2f}",
                "% Change in Avg Points (30d)": pct_txt,
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

    st.markdown("#### Trending Risks  — On track to exceed 8 points")
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

    st.markdown("#### Absenteeism Trend (90 Days)")
    trend_rows = [dict(r) for r in fetchall(conn, sql_trend_90d, (*emp_ids, (today - timedelta(days=90)).isoformat()))]
    # Merge on plain string dates to avoid pandas datetime-resolution mismatches
    # (bdate_range may return datetime64[ns] while pd.to_datetime from SQL strings
    #  returns datetime64[us] in newer pandas, causing silent merge failures).
    all_day_strs = pd.bdate_range(start=today - timedelta(days=90), end=today).strftime("%Y-%m-%d").tolist()
    trend_df = pd.DataFrame({"point_day": all_day_strs, "Total Points": 0.0})
    if trend_rows:
        trend_points = pd.DataFrame(
            {
                "point_day": [str(r.get("point_day") or "")[:10] for r in trend_rows],
                "Total Points": [float(r.get("pts") or 0.0) for r in trend_rows],
            }
        )
        trend_df = trend_df.merge(trend_points, on="point_day", how="left", suffixes=("", "_q"))
        trend_df["Total Points"] = trend_df["Total Points_q"].fillna(trend_df["Total Points"])
        trend_df = trend_df.drop(columns=["Total Points_q"])
    trend_df["point_day"] = pd.to_datetime(trend_df["point_day"])
    trend_df = trend_df.rename(columns={"point_day": "Date"}).set_index("Date")
    st.line_chart(trend_df)

    st.markdown("#### Day-of-Week Trend")
    ctrl_col1, ctrl_col2 = st.columns([1.2, 1])
    with ctrl_col1:
        window_label = st.selectbox(
            "Window",
            ["Last 30 days", "Last 90 days", "Last 12 months"],
            index=1,
            key="dow_window",
        )
    with ctrl_col2:
        metric_choice = st.radio("Metric", ["Count", "Points", "Rate"], index=0, horizontal=True, key="dow_metric")

    window_days = {"Last 30 days": 30, "Last 90 days": 90, "Last 12 months": 365}[window_label]
    window_start = today - timedelta(days=window_days - 1)
    window_end = today + timedelta(days=1)
    prior_start = window_start - timedelta(days=window_days)
    prior_end = window_start

    current_rows = [
        dict(r)
        for r in fetchall(conn, sql_weekday_window, (*emp_ids, window_start.isoformat(), window_end.isoformat(), *emp_ids, window_start.isoformat(), window_end.isoformat()))
    ]
    prior_rows = [
        dict(r)
        for r in fetchall(conn, sql_weekday_window, (*emp_ids, prior_start.isoformat(), prior_end.isoformat(), *emp_ids, prior_start.isoformat(), prior_end.isoformat()))
    ]

    current_by_dow = {
        int(r.get("dow") or 0): {
            "incidents": int(r.get("incidents") or 0),
            "employees_pointed": int(r.get("employees_pointed") or 0),
            "points": float(r.get("total_points") or 0.0),
        }
        for r in current_rows
    }
    prior_by_dow = {
        int(r.get("dow") or 0): {
            "incidents": int(r.get("incidents") or 0),
            "employees_pointed": int(r.get("employees_pointed") or 0),
            "points": float(r.get("total_points") or 0.0),
        }
        for r in prior_rows
    }

    dow_order = [1, 2, 3, 4, 5]
    dow_labels = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}

    denominator_count = max(len(emp_ids), 1)
    if metric_choice == "Rate":
        st.caption("Rate uses approximate active-headcount denominator: incidents ÷ active employees × 100.")

    def metric_value(stats: dict, metric: str) -> float:
        incidents = float(stats.get("incidents") or 0)
        employees_pointed = float(stats.get("employees_pointed") or 0)
        points = float(stats.get("points") or 0)
        if metric == "Count":
            return employees_pointed
        if metric == "Points":
            return points
        return (incidents / denominator_count) * 100.0

    table_rows = []
    metric_values = {}
    for dow in dow_order:
        stats = current_by_dow.get(dow, {"incidents": 0, "employees_pointed": 0, "points": 0.0})
        incidents = int(stats.get("incidents") or 0)
        employees_pointed = int(stats.get("employees_pointed") or 0)
        points = float(stats.get("points") or 0.0)
        selected_val = metric_value(stats, metric_choice)
        metric_values[dow] = selected_val

        weekday_reason_rows = [
            dict(r)
            for r in fetchall(
                conn,
                sql_weekday_reason,
                (*emp_ids, window_start.isoformat(), window_end.isoformat(), dow),
            )
        ]
        top_reason_day = (weekday_reason_rows[0].get("reason") if weekday_reason_rows else None) or "—"

        table_rows.append(
            {
                "Weekday": dow_labels[dow],
                "# of Employees Pointed": employees_pointed,
                "Total Points Issued": round(points, 1),
                "Top Reason": top_reason_day,
            }
        )

    dow_df = pd.DataFrame(table_rows)
    dow_event = st.dataframe(
        dow_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    selected_rows = dow_event.selection.rows
    if selected_rows:
        sel_idx = selected_rows[0]
        sel_dow = dow_order[sel_idx]
        sel_label = dow_labels[sel_dow]
        emp_rows = [
            dict(r)
            for r in fetchall(
                conn,
                sql_weekday_employees,
                (*emp_ids, window_start.isoformat(), window_end.isoformat(), sel_dow),
            )
        ]
        if emp_rows:
            st.markdown(f"**Employees pointed on {sel_label}s** ({window_start.strftime('%b %d')} – {window_end.strftime('%b %d, %Y')})")
            emp_display = pd.DataFrame([
                {
                    "Employee": r["employee"],
                    "Building": r["building"],
                    "Incidents": int(r["incidents"]),
                    "Points": float(r["total_points"]),
                }
                for r in emp_rows
            ])
            st.dataframe(emp_display, use_container_width=True, hide_index=True)
        else:
            st.info(f"No employees pointed on {sel_label}s in this window.")

    worst_dow = max(dow_order, key=lambda d: metric_values.get(d, 0.0))
    worst_label = dow_labels[worst_dow]
    worst_value = metric_values.get(worst_dow, 0.0)
    if metric_choice == "Count":
        worst_value_txt = f"{int(round(worst_value))} employees pointed"
    elif metric_choice == "Points":
        worst_value_txt = f"{worst_value:.1f} points"
    else:
        worst_value_txt = f"{worst_value:.2f} incidents per 100 active"
    st.markdown(f"• Worst weekday ({metric_choice.lower()}): **{worst_label}** — **{worst_value_txt}**")

    delta_rows = []
    for dow in dow_order:
        cur_val = metric_value(current_by_dow.get(dow, {"incidents": 0, "employees_pointed": 0, "points": 0.0}), metric_choice)
        prev_val = metric_value(prior_by_dow.get(dow, {"incidents": 0, "employees_pointed": 0, "points": 0.0}), metric_choice)
        if prev_val > 0:
            pct = ((cur_val - prev_val) / prev_val) * 100.0
            pct_txt = f"{pct:+.1f}%"
        elif cur_val > 0:
            pct_txt = "new activity"
        else:
            pct_txt = "0.0%"
        delta_rows.append((dow, abs(cur_val - prev_val), pct_txt))

    if delta_rows:
        ch_dow, _, pct_txt = max(delta_rows, key=lambda x: x[1])
        st.markdown(f"• Biggest change vs prior matching window: **{dow_labels[ch_dow]}** — **{pct_txt}**")

    reason_rows = [
        dict(r)
        for r in fetchall(
            conn,
            sql_weekday_reason,
            (*emp_ids, window_start.isoformat(), window_end.isoformat(), worst_dow),
        )
    ]
    top_reason = (reason_rows[0].get("reason") if reason_rows else None) or "—"
    if top_reason != "—":
        st.markdown(f"• Most common reason on {worst_label}: **{top_reason}**")



# ── PTO Usage Analysis ────────────────────────────────────────────────────────
_PTO_PALETTE = [
    "#00d4ff", "#7b61ff", "#00e5a0", "#ff6b6b", "#ffa94d",
    "#a9e34b", "#f06595", "#74c0fc", "#e599f7", "#63e6be",
]

_PTO_SAMPLE_CSV = (
    "employee_id,last_name,first_name,building,pto_type,start_date,end_date,hours\n"
    "101,Smith,Jane,APIM,Vacation,2025-01-06,2025-01-10,40\n"
    "102,Jones,Bob,APIS,Sick,2025-01-07,2025-01-07,4\n"
    "103,Davis,Carol,AAP,Personal,2025-01-08,2025-01-08,8\n"
    "104,Wilson,Tom,APIM,FMLA,2025-01-13,2025-01-24,80\n"
    "105,Brown,Alice,APIS,Bereavement,2025-01-13,2025-01-15,24\n"
    "106,Green,Mark,AAP,Vacation,2025-02-03,2025-02-07,40\n"
)


def _pto_metric(label: str, value: str, sub: str = "") -> None:
    sub_html = f"<div style='font-size:.75rem;color:#6b8cba;margin-top:.2rem'>{sub}</div>" if sub else ""
    st.markdown(
        f"<div style='background:#0d1b2e;border:1px solid #1a3a5c;border-radius:10px;"
        f"padding:1rem 1.25rem;text-align:center'>"
        f"<div style='font-size:.78rem;color:#4a7fa5;text-transform:uppercase;letter-spacing:.08em'>{label}</div>"
        f"<div style='font-size:1.8rem;font-weight:700;color:#e8f4fd;line-height:1.2;margin-top:.3rem'>{value}</div>"
        f"{sub_html}</div>",
        unsafe_allow_html=True,
    )


def pto_page(conn, building: str) -> None:
    page_heading("PTO Usage Analysis", "Upload a CSV export to analyze PTO patterns by type, building, and employee.")

    # ── Active employee roster from DB (active_only=True by default) ────────
    active_db = load_employees(conn, building="All")
    active_ids: set[int] = {int(e["employee_id"]) for e in active_db}
    active_names: set[str] = {
        f"{e['last_name'].strip().lower()}, {e['first_name'].strip().lower()}"
        for e in active_db
    }
    # For utilization denominator: active headcount scoped to the building filter
    if building != "All":
        active_count_in_scope = sum(1 for e in active_db if (e.get("location") or "") == building)
    else:
        active_count_in_scope = len(active_db)

    # ── CSV upload ──────────────────────────────────────────────────────────
    with st.expander("Upload PTO Data", expanded="pto_df" not in st.session_state):
        st.markdown(
            "Upload a CSV with columns: `employee_id` *(optional)*, `last_name`, `first_name`, "
            "`building`, `pto_type`, `start_date` *(YYYY-MM-DD)*, `end_date` *(YYYY-MM-DD)*, `hours` *(total for the period)*  \n"
            "Single-day entries: set `start_date` and `end_date` to the same date. "
            "The legacy single-`date` format is also accepted."
        )
        col_up, col_dl = st.columns([3, 1])
        with col_up:
            uploaded = st.file_uploader("Choose CSV file", type="csv", label_visibility="collapsed")
        with col_dl:
            st.download_button(
                "Download template",
                data=_PTO_SAMPLE_CSV,
                file_name="pto_template.csv",
                mime="text/csv",
                use_container_width=True,
            )

        if uploaded is not None:
            try:
                raw = pd.read_csv(uploaded)
                raw.columns = [c.strip().lower().replace(" ", "_") for c in raw.columns]
                cols = set(raw.columns)

                def _normalize_and_filter(df: pd.DataFrame) -> pd.DataFrame:
                    """Shared cleanup + DB active-employee filter applied after parsing."""
                    df["hours"] = pd.to_numeric(df["hours"], errors="coerce").fillna(0)
                    df["building"] = df["building"].astype(str).str.strip()
                    df["pto_type"] = df["pto_type"].astype(str).str.strip()
                    df["employee"] = df["last_name"].str.strip() + ", " + df["first_name"].str.strip()
                    df["days"] = (df["hours"] / 8).round(2)

                    # Build name→id lookup from DB for reliable export
                    _name_to_id: dict = {
                        f"{e['last_name'].strip().lower()}, {e['first_name'].strip().lower()}": int(e["employee_id"])
                        for e in active_db
                    }

                    # Match against active DB employees
                    def _is_active(row):
                        if "employee_id" in df.columns:
                            try:
                                if int(row["employee_id"]) in active_ids:
                                    return True
                            except (ValueError, TypeError):
                                pass
                        name_key = f"{str(row['last_name']).strip().lower()}, {str(row['first_name']).strip().lower()}"
                        return name_key in active_names

                    mask = df.apply(_is_active, axis=1)
                    excluded = (~mask).sum()
                    if excluded:
                        removed_names = sorted(df.loc[~mask, "employee"].unique())
                        st.warning(
                            f"{excluded} row(s) excluded — employee(s) not found in the active database: "
                            + ", ".join(removed_names)
                        )
                    df = df[mask].copy()

                    # Always resolve a canonical employee_id from the DB (covers CSVs without it)
                    def _resolve_id(row):
                        name_key = f"{str(row['last_name']).strip().lower()}, {str(row['first_name']).strip().lower()}"
                        if name_key in _name_to_id:
                            return _name_to_id[name_key]
                        try:
                            return int(row["employee_id"])
                        except (KeyError, ValueError, TypeError):
                            return None

                    df["employee_id"] = df.apply(_resolve_id, axis=1)
                    return df

                # Detect format: range (start_date/end_date) or legacy (date)
                if "start_date" in cols and "end_date" in cols:
                    required = {"last_name", "first_name", "building", "pto_type", "start_date", "end_date", "hours"}
                    missing = required - cols
                    if missing:
                        st.error(f"CSV is missing required columns: {', '.join(sorted(missing))}")
                    else:
                        raw["start_date"] = pd.to_datetime(raw["start_date"], errors="coerce")
                        raw["end_date"] = pd.to_datetime(raw["end_date"], errors="coerce")
                        raw = raw.dropna(subset=["start_date", "end_date"])
                        raw = _normalize_and_filter(raw)
                        st.session_state["pto_df"] = raw
                        st.session_state.pop("pto_type_toggles", None)
                        st.success(f"Loaded {len(raw):,} PTO records for active employees.")
                elif "date" in cols:
                    # Legacy single-day format — convert to range format
                    required = {"last_name", "first_name", "building", "pto_type", "date", "hours"}
                    missing = required - cols
                    if missing:
                        st.error(f"CSV is missing required columns: {', '.join(sorted(missing))}")
                    else:
                        raw["start_date"] = pd.to_datetime(raw["date"], errors="coerce")
                        raw["end_date"] = raw["start_date"]
                        raw = raw.dropna(subset=["start_date"])
                        raw = _normalize_and_filter(raw)
                        st.session_state["pto_df"] = raw
                        st.session_state.pop("pto_type_toggles", None)
                        st.success(f"Loaded {len(raw):,} PTO records for active employees (legacy format).")
                else:
                    st.error("CSV must contain either `start_date`/`end_date` columns or a `date` column.")
            except Exception as exc:
                st.error(f"Could not parse CSV: {exc}")

    if "pto_df" not in st.session_state:
        st.info("Upload a PTO CSV above to begin analysis.")
        return

    df_all: pd.DataFrame = st.session_state["pto_df"].copy()

    # ── Filters ─────────────────────────────────────────────────────────────
    import re as _re
    divider()
    section_label("Filters")
    fc1, fc2, fc3 = st.columns(3)

    date_min = df_all["start_date"].min().date()
    date_max = df_all["end_date"].max().date()
    with fc1:
        date_start = st.date_input("From", value=date_min, min_value=date_min, max_value=date_max, key="pto_from")
    with fc2:
        date_end = st.date_input("To", value=date_max, min_value=date_min, max_value=date_max, key="pto_to")

    all_buildings = sorted(df_all["building"].dropna().unique())
    bldg_opts = ["All"] + all_buildings
    default_bldg = building if building in all_buildings else "All"
    with fc3:
        sel_building = st.selectbox("Building", bldg_opts, index=bldg_opts.index(default_bldg), key="pto_bldg")

    all_types = sorted(df_all["pto_type"].dropna().unique())

    # ── PTO type toggle chips ────────────────────────────────────────────────
    def _tkey(t: str) -> str:
        return "pto_toggle_" + _re.sub(r"[^a-z0-9]", "_", t.lower())

    # Reset toggle state if the type list has changed (new CSV loaded)
    if set(st.session_state.get("pto_type_toggles", {}).keys()) != set(all_types):
        st.session_state["pto_type_toggles"] = {t: True for t in all_types}
    toggles: dict = st.session_state["pto_type_toggles"]

    active_sel   = [f".st-key-{_tkey(t)} button" for t in all_types if     toggles.get(t, True)]
    inactive_sel = [f".st-key-{_tkey(t)} button" for t in all_types if not toggles.get(t, True)]

    # Inject pill CSS globally (applies in sidebar too)
    st.markdown(
        f"""<style>
        div[class*="st-key-pto_toggle_"] button {{
            padding: 0.12rem 0.5rem !important;
            font-size: 0.6rem !important;
            border-radius: 999px !important;
            font-family: 'SF Mono','Fira Code',monospace !important;
            letter-spacing: 0.04em !important;
            text-transform: uppercase !important;
            min-height: 26px !important;
            line-height: 1.15 !important;
            font-weight: 600 !important;
            transition: all 0.15s ease !important;
        }}
        {(', '.join(active_sel) or '.pto-na') + ' { background: rgba(0,212,255,.1) !important; border: 1px solid rgba(0,212,255,.7) !important; color: #00d4ff !important; box-shadow: 0 0 10px rgba(0,212,255,.2), inset 0 0 6px rgba(0,212,255,.05) !important; }'}
        {(', '.join(inactive_sel) or '.pto-na') + ' { background: rgba(6,13,31,.6) !important; border: 1px solid #1a3050 !important; color: #2d4a6a !important; box-shadow: none !important; }'}
        </style>""",
        unsafe_allow_html=True,
    )

    # Render type filter pills in the sidebar
    with st.sidebar:
        st.markdown("<span class='sidebar-nav-label'>PTO Type Filter</span>", unsafe_allow_html=True)
        for _pt in all_types:
            if st.button(_pt, key=_tkey(_pt), use_container_width=True):
                st.session_state["pto_type_toggles"][_pt] = not toggles.get(_pt, True)
                st.rerun()

    sel_types = [t for t in all_types if st.session_state["pto_type_toggles"].get(t, True)]

    # Apply filters — include any PTO event that overlaps the selected date range
    df = df_all[
        (df_all["start_date"].dt.date <= date_end)
        & (df_all["end_date"].dt.date >= date_start)
    ]
    if sel_building != "All":
        df = df[df["building"] == sel_building]
    if sel_types:
        df = df[df["pto_type"].isin(sel_types)]

    if df.empty:
        info_box("No PTO records match the current filters.")
        return

    # ── KPI tiles ───────────────────────────────────────────────────────────
    divider()
    section_label("Summary")
    k1, k2, k3, k4 = st.columns(4)
    total_hours = df["hours"].sum()
    total_days = total_hours / 8
    unique_emps = df["employee"].nunique()
    # Denominator is active DB headcount for the selected building — not the CSV
    denom = active_count_in_scope if sel_building == building else (
        sum(1 for e in active_db if (e.get("location") or "") == sel_building)
        if sel_building != "All" else len(active_db)
    )
    utilization_pct = (unique_emps / denom * 100) if denom else 0
    top_type = df.groupby("pto_type")["hours"].sum().idxmax() if not df.empty else "—"
    avg_hours = total_hours / unique_emps if unique_emps else 0

    with k1:
        _pto_metric("Total PTO Days", f"{total_days:,.1f}", f"{total_hours:,.0f} hours")
    with k2:
        _pto_metric("Employees Used PTO", str(unique_emps), f"{utilization_pct:.0f}% utilization")
    with k3:
        _pto_metric("Top PTO Type", top_type)
    with k4:
        _pto_metric("Avg Days / Employee", f"{avg_hours / 8:.1f}", f"{avg_hours:.0f} hrs avg")

    # ── Donut chart + Monthly trend ─────────────────────────────────────────
    divider()
    chart_col, trend_col = st.columns(2)

    type_totals = df.groupby("pto_type")["hours"].sum().sort_values(ascending=False)
    type_colors = {t: _PTO_PALETTE[i % len(_PTO_PALETTE)] for i, t in enumerate(type_totals.index)}

    # Top-5 + "Other" for the donut
    _top5 = type_totals.head(5)
    _other_sum = type_totals.iloc[5:].sum()
    if _other_sum > 0:
        import pandas as _pd
        donut_totals = _pd.concat([_top5, _pd.Series({"Other": _other_sum})])
        _top5_types = set(_top5.index)
    else:
        donut_totals = _top5
        _top5_types = set(_top5.index)
    donut_colors = [type_colors.get(t, "#4a5568") for t in donut_totals.index]

    with chart_col:
        section_label("PTO by Type — click a slice to see employees")
        donut_fig = go.Figure(go.Pie(
            labels=donut_totals.index.tolist(),
            values=donut_totals.values.tolist(),
            hole=0.52,
            marker=dict(colors=donut_colors, line=dict(color="#060d1f", width=2)),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>%{value:.0f} hrs (%{percent})<extra></extra>",
        ))
        donut_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            margin=dict(t=10, b=10, l=10, r=10),
            font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
        )
        donut_event = st.plotly_chart(
            donut_fig,
            use_container_width=True,
            on_select="rerun",
            key="pto_donut",
        )

    with trend_col:
        section_label("Monthly PTO Trend (hours)")
        df_trend = df.copy()
        df_trend["month"] = df_trend["start_date"].dt.to_period("M").dt.to_timestamp()
        monthly = df_trend.groupby(["month", "pto_type"])["hours"].sum().reset_index()
        trend_fig = go.Figure()
        for pto_type in monthly["pto_type"].unique():
            sub = monthly[monthly["pto_type"] == pto_type]
            trend_fig.add_trace(go.Scatter(
                x=sub["month"], y=sub["hours"], name=pto_type, mode="lines+markers",
                line=dict(color=type_colors.get(pto_type, "#00d4ff"), width=2),
                marker=dict(size=5),
                hovertemplate=f"<b>{pto_type}</b><br>%{{x|%b %Y}}: %{{y:.0f}} hrs<extra></extra>",
            ))
        trend_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
            xaxis=dict(showgrid=False, color="#4a7fa5"),
            yaxis=dict(showgrid=True, gridcolor="#0d1b2e", color="#4a7fa5"),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
            margin=dict(t=10, b=10, l=10, r=10),
            hovermode="x unified",
        )
        st.plotly_chart(trend_fig, use_container_width=True, key="pto_trend")

    # ── Donut drill-down ────────────────────────────────────────────────────
    selected_points = donut_event.selection.get("points", []) if donut_event.selection else []
    if selected_points:
        sel_type = selected_points[0].get("label")
        if sel_type:
            divider()
            section_label(f"Employees — {sel_type}")
            if sel_type == "Other":
                drill_src = df[~df["pto_type"].isin(_top5_types)].copy()
            else:
                drill_src = df[df["pto_type"] == sel_type].copy()
            drill_src["start_date"] = drill_src["start_date"].dt.strftime("%Y-%m-%d")
            drill_src["end_date"] = drill_src["end_date"].dt.strftime("%Y-%m-%d")
            drill = (
                drill_src[["employee", "building", "start_date", "end_date", "hours", "days"]]
                .rename(columns={"employee": "Employee", "building": "Building",
                                 "start_date": "Start", "end_date": "End",
                                 "hours": "Hours", "days": "Days"})
                .sort_values("Hours", ascending=False)
            )
            drill["Hours"] = drill["Hours"].round(1)
            drill["Days"] = drill["Days"].round(1)
            st.dataframe(drill, use_container_width=True, hide_index=True)

    # ── Building comparison ─────────────────────────────────────────────────
    divider()
    bc1, bc2 = st.columns(2)

    with bc1:
        section_label("PTO Hours by Building")
        bldg_totals = df.groupby("building")["hours"].sum().sort_values(ascending=False).reset_index()
        bar_fig = go.Figure(go.Bar(
            x=bldg_totals["building"],
            y=bldg_totals["hours"],
            marker=dict(color=_PTO_PALETTE[:len(bldg_totals)], line=dict(color="#060d1f", width=1)),
            hovertemplate="<b>%{x}</b>: %{y:.0f} hrs<extra></extra>",
            text=(bldg_totals["hours"] / 8).round(1).astype(str) + "d",
            textposition="outside",
        ))
        bar_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
            xaxis=dict(showgrid=False, color="#4a7fa5"),
            yaxis=dict(showgrid=True, gridcolor="#0d1b2e", color="#4a7fa5", title="Hours"),
            margin=dict(t=10, b=10, l=10, r=10),
        )
        st.plotly_chart(bar_fig, use_container_width=True, key="pto_bldg_bar")

    with bc2:
        section_label("Most Popular Days of Week for PTO")
        dow_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
        df_dow = df.copy()
        df_dow["dow"] = df_dow["start_date"].dt.dayofweek
        df_dow["dow_label"] = df_dow["dow"].map(dow_map)
        dow_order = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        dow_totals = (
            df_dow[df_dow["dow_label"].isin(dow_order)]
            .groupby("dow_label")["hours"]
            .sum()
            .reindex(dow_order)
            .fillna(0)
            .reset_index()
        )
        dow_fig = go.Figure(go.Bar(
            x=dow_totals["dow_label"],
            y=dow_totals["hours"],
            marker=dict(color="#7b61ff", line=dict(color="#060d1f", width=1)),
            hovertemplate="<b>%{x}</b>: %{y:.0f} hrs<extra></extra>",
        ))
        dow_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
            xaxis=dict(showgrid=False, color="#4a7fa5"),
            yaxis=dict(showgrid=True, gridcolor="#0d1b2e", color="#4a7fa5", title="Hours"),
            margin=dict(t=10, b=10, l=10, r=10),
        )
        st.plotly_chart(dow_fig, use_container_width=True, key="pto_dow_bar")

    # ── Top PTO users ───────────────────────────────────────────────────────
    divider()
    tu1, tu2 = st.columns([3, 2])

    with tu1:
        section_label("Top PTO Users")
        top_users = (
            df.groupby(["employee", "building"])["hours"]
            .sum()
            .reset_index()
            .sort_values("hours", ascending=False)
            .head(15)
        )
        top_users["Days"] = (top_users["hours"] / 8).round(1)
        top_users = top_users.rename(columns={"employee": "Employee", "building": "Building", "hours": "Hours"})
        top_users["Hours"] = top_users["Hours"].round(1)
        st.dataframe(top_users[["Employee", "Building", "Days", "Hours"]], use_container_width=True, hide_index=True)

    with tu2:
        section_label("Zero PTO — No Usage Recorded")
        emps_with_pto = set(df["employee"].unique())
        # Use the DB roster as the reference — not the CSV
        scoped_active = [
            e for e in active_db
            if sel_building == "All" or (e.get("location") or "") == sel_building
        ]
        all_active_names = {
            f"{e['last_name'].strip()}, {e['first_name'].strip()}"
            for e in scoped_active
        }
        no_pto = sorted(all_active_names - emps_with_pto)
        if no_pto:
            no_pto_df = pd.DataFrame({"Employee": no_pto})
            st.dataframe(no_pto_df, use_container_width=True, hide_index=True)
        else:
            info_box("All active employees have PTO recorded in this period.")

    # ── Module 1: Planned vs Unplanned ──────────────────────────────────────
    divider()
    section_label("Planned vs Unplanned PTO")

    _PLANNED_TYPES   = {"vacation", "personal", "floating holiday", "reward pto"}
    _UNPLANNED_TYPES = {"absence", "absence (sick)", "absence (covid)", "long term sick leave"}
    _PROTECTED_TYPES = {"jury duty", "bereavement", "fmla"}

    def _classify_pto(t: str) -> str:
        tl = t.strip().lower()
        if tl in _PLANNED_TYPES:   return "Planned"
        if tl in _UNPLANNED_TYPES: return "Unplanned"
        if tl in _PROTECTED_TYPES: return "Protected / Neutral"
        return "Other"

    def _drill_table(source_df: pd.DataFrame, label: str) -> None:
        section_label(f"Employees — {label}")
        d = source_df.copy()
        d["start_date"] = d["start_date"].dt.strftime("%Y-%m-%d")
        d["end_date"]   = d["end_date"].dt.strftime("%Y-%m-%d")
        d["Hours"] = d["hours"].round(1)
        d["Days"]  = (d["hours"] / 8).round(1)
        d = (
            d.rename(columns={"employee": "Employee", "building": "Building",
                               "pto_type": "PTO Type", "start_date": "Start", "end_date": "End"})
            [["Employee", "Building", "PTO Type", "Start", "End", "Hours", "Days"]]
            .sort_values(["Employee", "Start"])
        )
        st.dataframe(d, use_container_width=True, hide_index=True)

    df_cls = df.copy()
    df_cls["category"] = df_cls["pto_type"].apply(_classify_pto)
    cat_hrs = df_cls.groupby("category")["hours"].sum()
    total_cls_h = cat_hrs.sum()
    plan_h = cat_hrs.get("Planned", 0)
    unpl_h = cat_hrs.get("Unplanned", 0)
    prot_h = cat_hrs.get("Protected / Neutral", 0)

    pv1, pv2, pv3, pv4 = st.columns(4)
    _pct = lambda h: f"{h / total_cls_h * 100:.0f}%" if total_cls_h else "—"
    with pv1:
        _pto_metric("Planned", _pct(plan_h), f"{plan_h / 8:.1f} days")
    with pv2:
        _pto_metric("Unplanned", _pct(unpl_h), f"{unpl_h / 8:.1f} days")
    with pv3:
        _pto_metric("Protected / Neutral", _pct(prot_h), f"{prot_h / 8:.1f} days")
    with pv4:
        ratio_str = f"{plan_h / unpl_h:.1f}×" if unpl_h else "N/A"
        _pto_metric("Plan : Unplan Ratio", ratio_str, "higher = more predictable")

    df_cls["month"] = df_cls["start_date"].dt.to_period("M").dt.to_timestamp()
    mcat = (
        df_cls[df_cls["category"].isin(["Planned", "Unplanned"])]
        .groupby(["month", "category"])["hours"].sum().reset_index()
    )
    pv_l, pv_r = st.columns([2, 1])
    pu_event = None
    _pu_trace_cats: list[str] = []
    with pv_l:
        if not mcat.empty:
            _CAT_CLR = {"Planned": "#00e5a0", "Unplanned": "#ff6b6b"}
            pu_fig = go.Figure()
            for cat in ["Planned", "Unplanned"]:
                sub = mcat[mcat["category"] == cat]
                if not sub.empty:
                    _pu_trace_cats.append(cat)
                    pu_fig.add_trace(go.Bar(
                        x=sub["month"], y=sub["hours"], name=cat,
                        marker=dict(color=_CAT_CLR[cat], line=dict(color="#060d1f", width=1)),
                        hovertemplate=f"<b>{cat}</b><br>%{{x|%b %Y}}: %{{y:.0f}} hrs<extra></extra>",
                    ))
            pu_fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
                xaxis=dict(showgrid=False, color="#4a7fa5"),
                yaxis=dict(showgrid=True, gridcolor="#0d1b2e", color="#4a7fa5", title="Hours"),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
                margin=dict(t=10, b=10, l=10, r=10),
                barmode="group",
            )
            pu_event = st.plotly_chart(pu_fig, use_container_width=True, on_select="rerun", key="pto_pu_trend")
        else:
            info_box("Not enough monthly data for trend.")
    with pv_r:
        section_label("Type \u2192 Category Map")
        cls_tbl = (
            df_cls.groupby(["pto_type", "category"])["hours"].sum()
            .reset_index()
            .rename(columns={"pto_type": "Type", "category": "Category", "hours": "Hours"})
            .sort_values("Hours", ascending=False)
        )
        cls_tbl["Hours"] = cls_tbl["Hours"].round(1)
        st.dataframe(cls_tbl, use_container_width=True, hide_index=True, height=300)

    # Trend drilldown — rendered outside columns at full width
    pu_pts = pu_event.selection.get("points", []) if (pu_event and pu_event.selection) else []
    if pu_pts:
        pt = pu_pts[0]
        cn = pt.get("curve_number", 0)
        sel_cat = _pu_trace_cats[cn] if cn < len(_pu_trace_cats) else None
        x_raw = pt.get("x") or pt.get("label") or ""
        if sel_cat and x_raw:
            try:
                sel_period = pd.to_datetime(x_raw).to_period("M")
                drill_pu = df_cls[
                    (df_cls["category"] == sel_cat) &
                    (df_cls["start_date"].dt.to_period("M") == sel_period)
                ]
                if not drill_pu.empty:
                    divider()
                    _drill_table(drill_pu, f"{sel_cat} \u2014 {sel_period.strftime('%b %Y')}")
            except Exception:
                pass

    # ── Module 2: Concentration ──────────────────────────────────────
    divider()
    section_label("PTO Concentration \u2014 Who's Driving Usage?")

    emp_hrs = df.groupby("employee")["hours"].sum().sort_values(ascending=False).reset_index()
    n_total_emp = len(emp_hrs)
    top10_n = max(1, round(n_total_emp * 0.10))
    total_emp_hrs = emp_hrs["hours"].sum()
    top10_pct_hrs = emp_hrs.head(top10_n)["hours"].sum() / total_emp_hrs * 100 if total_emp_hrs else 0
    concentration_label = "High" if top10_pct_hrs > 50 else ("Moderate" if top10_pct_hrs > 33 else "Even")

    cn1, cn2, cn3 = st.columns(3)
    with cn1:
        _pto_metric("Employees with PTO", str(n_total_emp), "in selected period")
    with cn2:
        _pto_metric(f"Top 10% ({top10_n} people)", f"{top10_pct_hrs:.0f}% of hours", "concentration signal")
    with cn3:
        _pto_metric("Distribution", concentration_label, "of PTO across team")

    # Pre-compute histogram bins before column block so they're accessible for drilldown
    import numpy as _np
    _max_h = max(float(emp_hrs["hours"].max()), 1.0)
    _bin_edges = list(_np.linspace(0, _max_h, 11))
    _bin_labels = [f"{int(_bin_edges[i])}\u2013{int(_bin_edges[i+1])}h" for i in range(10)]
    _emp_hrs_b = emp_hrs.copy()
    _emp_hrs_b["bin"] = pd.cut(_emp_hrs_b["hours"], bins=_bin_edges, labels=_bin_labels, include_lowest=True)
    _bin_counts = _emp_hrs_b.groupby("bin", observed=False)["hours"].count().reindex(_bin_labels).fillna(0)

    top10_hrs_sum = emp_hrs.head(10)["hours"].sum()
    rest_hrs_sum = emp_hrs.iloc[10:]["hours"].sum() if n_total_emp > 10 else 0

    conc_event = None
    hist_event = None
    cc1, cc2 = st.columns(2)
    with cc1:
        conc_fig = go.Figure(go.Bar(
            y=["Top 10 Users", "Rest of Team"],
            x=[top10_hrs_sum, rest_hrs_sum],
            orientation="h",
            marker=dict(color=["#00d4ff", "#1a3a5c"], line=dict(color="#060d1f", width=1)),
            text=[f"{top10_hrs_sum / 8:.0f}d", f"{rest_hrs_sum / 8:.0f}d"],
            textposition="inside",
            textfont=dict(color="#e8f4fd"),
            hovertemplate="<b>%{y}</b>: %{x:.0f} hrs<extra></extra>",
        ))
        conc_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
            xaxis=dict(showgrid=True, gridcolor="#0d1b2e", color="#4a7fa5", title="Hours"),
            yaxis=dict(showgrid=False, color="#4a7fa5"),
            margin=dict(t=10, b=10, l=10, r=10),
            height=180,
        )
        conc_event = st.plotly_chart(conc_fig, use_container_width=True, on_select="rerun", key="pto_conc_bar")
    with cc2:
        hist_fig = go.Figure(go.Bar(
            x=_bin_labels,
            y=_bin_counts.values,
            marker=dict(color="#7b61ff", line=dict(color="#060d1f", width=1)),
            hovertemplate="<b>%{x}</b>: %{y} employees<extra></extra>",
        ))
        hist_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
            xaxis=dict(showgrid=False, color="#4a7fa5", title="Total Hours Used", tickangle=-30),
            yaxis=dict(showgrid=True, gridcolor="#0d1b2e", color="#4a7fa5", title="# Employees"),
            margin=dict(t=10, b=10, l=10, r=10),
            height=180,
            bargap=0.05,
        )
        hist_event = st.plotly_chart(hist_fig, use_container_width=True, on_select="rerun", key="pto_dist_hist")

    # Concentration drilldowns — rendered outside columns at full width
    conc_pts = conc_event.selection.get("points", []) if (conc_event and conc_event.selection) else []
    if conc_pts:
        bar_label = conc_pts[0].get("y") or conc_pts[0].get("label") or ""
        if bar_label in ("Top 10 Users", "Rest of Team"):
            _group = emp_hrs.head(10) if bar_label == "Top 10 Users" else emp_hrs.iloc[10:]
            _grp_names = set(_group["employee"])
            _grp_df = df[df["employee"].isin(_grp_names)]
            _grp_agg = (
                _grp_df.groupby("pto_type")["hours"].sum()
                .reset_index()
                .rename(columns={"pto_type": "PTO Type", "hours": "Hours"})
                .sort_values("Hours", ascending=False)
            )
            _grp_agg["Hours"] = _grp_agg["Hours"].round(1)
            _grp_agg["Days"] = (_grp_agg["Hours"] / 8).round(1)
            divider()
            section_label(f"PTO Breakdown — {bar_label}")
            st.dataframe(_grp_agg, use_container_width=True, hide_index=True)

    hist_pts = hist_event.selection.get("points", []) if (hist_event and hist_event.selection) else []
    if hist_pts:
        bin_sel = hist_pts[0].get("x") or hist_pts[0].get("label") or ""
        if bin_sel in _bin_labels:
            bi = _bin_labels.index(bin_sel)
            lo, hi = _bin_edges[bi], _bin_edges[bi + 1]
            names_in_bin = set(_emp_hrs_b[(_emp_hrs_b["hours"] >= lo) & (_emp_hrs_b["hours"] <= hi)]["employee"])
            if names_in_bin:
                _hist_df = df[df["employee"].isin(names_in_bin)]
                _hist_agg = (
                    _hist_df.groupby(["employee", "building", "pto_type"])["hours"].sum()
                    .reset_index()
                    .rename(columns={"employee": "Employee", "building": "Building",
                                     "pto_type": "PTO Type", "hours": "Hours"})
                    .sort_values(["Employee", "Hours"], ascending=[True, False])
                )
                _hist_agg["Hours"] = _hist_agg["Hours"].round(1)
                _hist_agg["Days"] = (_hist_agg["Hours"] / 8).round(1)
                divider()
                section_label(f"Employees Using {bin_sel} — by PTO Type")
                st.dataframe(_hist_agg, use_container_width=True, hide_index=True)

    # ── Module 3: Burnout & Retention Risk ──────────────────────────────────
    divider()
    section_label("Burnout & Retention Risk")

    low10_n = max(1, round(n_total_emp * 0.10))
    low_users = emp_hrs.tail(low10_n).copy() if n_total_emp >= 5 else pd.DataFrame()
    low_avg_days = low_users["hours"].mean() / 8 if not low_users.empty else 0
    no_pto_count = len(no_pto)
    no_pto_rate = no_pto_count / max(1, len(all_active_names)) * 100

    br1, br2, br3 = st.columns(3)
    with br1:
        _pto_metric("No PTO Recorded", str(no_pto_count), "employees — 0 hrs")
    with br2:
        _pto_metric("Zero-PTO Rate", f"{no_pto_rate:.0f}%", "of active headcount")
    with br3:
        _pto_metric("Lowest 10% Avg", f"{low_avg_days:.1f} days", "potential burnout flag")

    brl, brr = st.columns(2)
    with brl:
        section_label("No PTO — Burnout / Safety Risk")
        if no_pto:
            st.dataframe(pd.DataFrame({"Employee": no_pto}), use_container_width=True, hide_index=True)
        else:
            info_box("All active employees have PTO recorded. ✓")
    with brr:
        section_label(f"Lowest Usage — Bottom 10% ({low10_n} employees)")
        if not low_users.empty:
            low_users["Days"] = (low_users["hours"] / 8).round(1)
            low_users = low_users.rename(columns={"employee": "Employee", "hours": "Hours"})
            low_users["Hours"] = low_users["Hours"].round(1)
            st.dataframe(low_users[["Employee", "Hours", "Days"]], use_container_width=True, hide_index=True)
        else:
            info_box("Not enough data for bottom 10% analysis.")

    # ── Module 4: Pace & Seasonality ────────────────────────────────────────
    divider()
    section_label("PTO Pace & Seasonality")

    from datetime import timedelta as _td
    period_days = max(1, (date_end - date_start).days + 1)
    annualized_total = total_days / period_days * 365
    annualized_per_emp = avg_hours / 8 / period_days * 365 if unique_emps else 0

    mid = date_start + _td(days=period_days // 2)
    fh_hrs = df[df["start_date"].dt.date < mid]["hours"].sum()
    sh_hrs = df[df["start_date"].dt.date >= mid]["hours"].sum()
    fh_rate = fh_hrs / max(1, period_days // 2)
    sh_rate = sh_hrs / max(1, period_days - period_days // 2)
    delta_pct = (sh_rate - fh_rate) / fh_rate * 100 if fh_rate else 0
    trend_arrow = "▲" if delta_pct > 5 else ("▼" if delta_pct < -5 else "→")

    ps1, ps2, ps3 = st.columns(3)
    with ps1:
        _pto_metric("Annualized PTO Days", f"{annualized_total:,.0f}", "at current pace — total")
    with ps2:
        _pto_metric("Days / Employee (ann.)", f"{annualized_per_emp:.1f}", "per active employee")
    with ps3:
        _pto_metric("Usage Trend", f"{trend_arrow} {abs(delta_pct):.0f}%", "2nd vs 1st half of period")

    _MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    df_season = df_all.copy()
    if sel_building != "All":
        df_season = df_season[df_season["building"] == sel_building]
    df_season["cal_month"] = df_season["start_date"].dt.month
    season = (
        df_season.groupby("cal_month")["hours"].sum()
        .reindex(range(1, 13)).fillna(0).reset_index()
    )
    season["label"] = [_MONTH_LABELS[m - 1] for m in season["cal_month"]]
    season_fig = go.Figure(go.Bar(
        x=season["label"],
        y=season["hours"],
        marker=dict(
            color=season["hours"],
            colorscale=[[0, "#0d1b2e"], [0.5, "#7b61ff"], [1, "#00d4ff"]],
            line=dict(color="#060d1f", width=1),
        ),
        text=(season["hours"] / 8).round(0).astype(int).astype(str) + "d",
        textposition="outside",
        hovertemplate="<b>%{x}</b>: %{y:.0f} total hrs<extra></extra>",
    ))
    season_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
        xaxis=dict(showgrid=False, color="#4a7fa5"),
        yaxis=dict(showgrid=True, gridcolor="#0d1b2e", color="#4a7fa5", title="Total Hours"),
        margin=dict(t=30, b=10, l=10, r=10),
    )
    season_event = st.plotly_chart(season_fig, use_container_width=True, on_select="rerun", key="pto_seasonality")
    season_pts = season_event.selection.get("points", []) if (season_event and season_event.selection) else []
    if season_pts:
        sel_mon_label = season_pts[0].get("x") or season_pts[0].get("label") or ""
        if sel_mon_label in _MONTH_LABELS:
            sel_mon_num = _MONTH_LABELS.index(sel_mon_label) + 1
            df_mon = df.copy()
            df_mon["cal_month"] = df_mon["start_date"].dt.month
            drill_mon = df_mon[df_mon["cal_month"] == sel_mon_num]
            if not drill_mon.empty:
                divider()
                _drill_table(drill_mon, f"PTO in {sel_mon_label}")

    # ── Export ──────────────────────────────────────────────────────────────
    divider()
    section_label("Export Filtered Data")
    exp_cols = ["employee_id", "employee", "building", "pto_type", "start_date", "end_date", "hours", "days"]
    exp_df = df[[c for c in exp_cols if c in df.columns]].copy()
    exp_df["start_date"] = exp_df["start_date"].dt.strftime("%Y-%m-%d")
    exp_df["end_date"] = exp_df["end_date"].dt.strftime("%Y-%m-%d")
    st.download_button(
        "Download filtered PTO as CSV",
        data=to_csv(exp_df),
        file_name=f"pto_export_{date_start}_{date_end}.csv",
        mime="text/csv",
    )

    # ── Clear data ──────────────────────────────────────────────────────────
    divider()
    st.markdown(
        "<p style='color:#6a8ab8;font-size:.8rem;margin-bottom:.4rem'>"
        "Clear the loaded CSV data to start over with a new file.</p>",
        unsafe_allow_html=True,
    )
    if st.button("Clear PTO Data", type="secondary", use_container_width=False):
        st.session_state.pop("pto_df", None)
        st.session_state.pop("pto_type_toggles", None)
        st.rerun()


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
        "color:#6a8ab8;background:rgba(79,142,247,.08);border:1px solid rgba(79,142,247,.22)'>Inactive</span>"
    )
    st.markdown(
        f"<div class='card'>"
        f"<div style='display:flex;justify-content:space-between;align-items:flex-start'>"
        f"<div><h2 style='margin:0;font-size:1.3rem;font-weight:800;color:#d4e1f7'>"
        f"{emp.get('last_name')}, {emp.get('first_name')}</h2>"
        f"<div style='color:#6a8ab8;font-size:.85rem;margin-top:.2rem'>"
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
        f"color:#6a8ab8;margin-bottom:.3rem'>Points</div>{pt_badge(pts)}</div>"
        f"<div class='card-sm'>"
        f"<div style='font-size:.67rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;"
        f"color:#6a8ab8;margin-bottom:.3rem'>Next Roll-off</div>"
        f"<div style='font-size:.9rem;font-weight:700;color:#d4e1f7'>{fmt_date(emp.get('rolloff_date'))}</div></div>"
        f"<div class='card-sm'>"
        f"<div style='font-size:.67rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;"
        f"color:#6a8ab8;margin-bottom:.3rem'>Perfect Att.</div>"
        f"<div style='font-size:.9rem;font-weight:700;color:#d4e1f7'>{fmt_date(emp.get('perfect_attendance'))}</div></div>"
        f"<div class='card-sm'>"
        f"<div style='font-size:.67rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;"
        f"color:#6a8ab8;margin-bottom:.3rem'>Last Entry</div>"
        f"<div style='font-size:.9rem;font-weight:700;color:#d4e1f7'>{fmt_date(emp.get('last_point_date'))}</div></div>"
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

    # Resolve any deferred navigation request (e.g. from spotlight button)
    # Must happen before the radio widget renders so the new value is respected.
    _nav_to = st.session_state.pop("_nav_to", None)
    if _nav_to:
        st.session_state["page"] = _nav_to

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
            ["Dashboard", "PTO Usage Analysis", "Employees", "Points Ledger", "Manage Employees", "Exports & Forecasts", "System Updates"],
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
    elif page == "PTO Usage Analysis":
        pto_page(conn, building)
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

    # Render spotlight only on Dashboard (after page runs so it reflects current selection)
    with spotlight_placeholder.container():
        if page == "Dashboard":
            selected_employee_sidebar(conn, st.session_state.get("selected_employee_id"))

ensure_session_defaults()
if not is_authenticated():
    login_page()
else:
    main()
