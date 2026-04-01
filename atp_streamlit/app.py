"""Attendance Point Tracker — Streamlit Web App
Full remodel: clean layout, status badges, live countdown, improved workflows.
"""
from __future__ import annotations

import base64
import html
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
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle

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
POINT_BALANCE_REPAIR_VERSION = 2
EMPLOYEE_CACHE_TTL_SECONDS = 60
DASHBOARD_CACHE_TTL_SECONDS = 45
LEDGER_HISTORY_DEFAULT_LIMIT = 500
LEDGER_HISTORY_FULL_LIMIT = 5000


# ── Theme ─────────────────────────────────────────────────────────────────────
def apply_theme() -> None:
    st.markdown(
        """<style>
/* ══════════════════════════════════════════════════════════════
   CONTROL ROOM OS  —  Ultimate Command Interface
   Space Grotesk (UI) + Space Mono (data readouts)
══════════════════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap');

:root {
    /* ── Depth palette ── */
    --bg:        #02060e;
    --bg2:       #040c1a;
    --surface:   rgba(4,12,28,0.82);
    --surface2:  rgba(6,16,36,0.68);

    /* ── Text ── */
    --text:      #b8d0ee;
    --text-hi:   #e4f0ff;
    --muted:     #3d5a7a;
    --faint:     #182840;

    /* ── Accent system ── */
    --blue:      #0078ff;
    --cyan:      #00c8f0;
    --green:     #00e896;
    --amber:     #f0a800;
    --red:       #ff3050;
    --purple:    #8855ee;
    --teal:      #00b8a0;

    /* ── Borders / glows ── */
    --border:    rgba(0,120,255,.14);
    --border-hi: rgba(0,200,240,.50);
    --glow-b:    rgba(0,120,255,.28);
    --glow-c:    rgba(0,200,240,.28);
    --shadow:    0 10px 48px rgba(0,0,0,.75);
}

/* ── System-wide font ── */
html, body, .stApp, button, input, select, textarea, label, p, span, div {
    font-family: 'Space Grotesk', 'Inter', system-ui, -apple-system, sans-serif !important;
}

/* ── Base canvas ── */
.stApp { background: var(--bg) !important; color: var(--text); }
.block-container {
    padding-top: 1.6rem; padding-bottom: 3rem;
    max-width: 1520px;
}
footer, #MainMenu { visibility: hidden; }

/* ── Custom scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #02060e; }
::-webkit-scrollbar-thumb {
    background: rgba(0,120,255,.22); border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(0,200,240,.38); }

/* ══════════════════════════════════════════════════════════════
   ATMOSPHERIC BACKGROUND LAYERS
══════════════════════════════════════════════════════════════ */

/* Aurora glow (injected div) */
@keyframes aurora-drift {
  0%   { background-position: 0% 0%;   opacity: .75; }
  25%  { background-position: 60% 20%; opacity: .92; }
  50%  { background-position: 100% 60%;opacity: .80; }
  75%  { background-position: 40% 100%;opacity: .88; }
  100% { background-position: 0% 0%;   opacity: .75; }
}
.aurora-bg {
    position: fixed; inset: 0;
    background:
        radial-gradient(ellipse 55% 45% at 12% 20%, rgba(0,80,200,.11) 0%, transparent 100%),
        radial-gradient(ellipse 45% 55% at 88% 75%, rgba(0,160,240,.08) 0%, transparent 100%),
        radial-gradient(ellipse 35% 45% at 55% 92%, rgba(80,0,180,.07) 0%, transparent 100%),
        radial-gradient(ellipse 65% 35% at 48% 5%,  rgba(0,40,120,.07) 0%, transparent 100%);
    background-size: 200% 200%;
    animation: aurora-drift 40s ease-in-out infinite;
    pointer-events: none; z-index: 1;
}

/* Tech grid (injected div) */
.tech-grid-overlay {
    position: fixed; inset: 0;
    background-image:
        linear-gradient(rgba(0,120,255,.016) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,120,255,.016) 1px, transparent 1px);
    background-size: 48px 48px;
    pointer-events: none; z-index: 2;
}

/* Corner brackets (HUD decorators) */
.hud-corner {
    position: fixed; width: 22px; height: 22px;
    border-color: rgba(0,200,240,.28); border-style: solid;
    pointer-events: none; z-index: 10;
}
.hud-corner-tl { top: 12px; left: 12px; border-width: 2px 0 0 2px; border-radius: 2px 0 0 0; }
.hud-corner-tr { top: 12px; right: 12px; border-width: 2px 2px 0 0; border-radius: 0 2px 0 0; }
.hud-corner-bl { bottom: 12px; left: 12px; border-width: 0 0 2px 2px; border-radius: 0 0 0 2px; }
.hud-corner-br { bottom: 12px; right: 12px; border-width: 0 2px 2px 0; border-radius: 0 0 2px 0; }

/* ══════════════════════════════════════════════════════════════
   SIDEBAR
══════════════════════════════════════════════════════════════ */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(8,18,42,.84) 0%, rgba(5,13,31,.78) 55%, rgba(4,10,24,.80) 100%) !important;
    border-right: 1px solid rgba(0,200,240,.20) !important;
    width: 272px !important;
    box-shadow: 0 0 0 1px rgba(0,200,240,.06), 6px 0 42px rgba(0,0,0,.62), inset -1px 0 0 rgba(0,200,240,.12), inset 0 1px 0 rgba(255,255,255,.08);
    backdrop-filter: blur(14px) saturate(1.08);
    -webkit-backdrop-filter: blur(14px) saturate(1.08);
    position: relative;
    overflow: hidden;
}
section[data-testid="stSidebar"] > div {
    position: relative;
    z-index: 1;
}
section[data-testid="stSidebar"]::before {
    content: '';
    position: absolute;
    top: 0;
    left: 10%;
    right: 10%;
    height: 2px;
    background: linear-gradient(90deg, transparent 0%, var(--cyan) 52%, transparent 100%);
    animation: sidebar-top-glow 5s ease-in-out infinite;
    pointer-events: none;
    z-index: 2;
}
section[data-testid="stSidebar"]::after {
    content: '';
    position: absolute;
    inset: 0;
    background:
        radial-gradient(80% 36% at 14% 0%, rgba(0,200,240,.10) 0%, transparent 70%),
        radial-gradient(72% 42% at 88% 100%, rgba(255,48,80,.08) 0%, transparent 72%),
        linear-gradient(135deg, rgba(255,255,255,.05) 0%, rgba(255,255,255,0) 45%);
    opacity: .88;
    pointer-events: none;
}
section[data-testid="stSidebar"] * { color: #8bc2dd !important; }

/* Top edge glow on sidebar */
@keyframes sidebar-top-glow {
    0%,100% { opacity: .35; }
    50%      { opacity: .92; box-shadow: 0 0 16px rgba(0,200,240,.55); }
}

/* Sidebar selectbox */
section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background: rgba(0,8,22,.90) !important;
    border: 1px solid rgba(0,120,255,.22) !important;
    color: #88aed0 !important; border-radius: 7px !important;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] input,
section[data-testid="stSidebar"] div[data-baseweb="select"] span,
section[data-testid="stSidebar"] div[data-baseweb="select"] div {
    color: #88aed0 !important; -webkit-text-fill-color: #88aed0 !important;
}

/* Radio nav items */
section[data-testid="stSidebar"] [data-testid="stRadio"] label {
    display: flex !important; align-items: center !important;
    padding: .44rem .80rem !important; border-radius: 7px !important;
    margin: 2px 0 !important; transition: all .20s ease !important;
    border: 1px solid transparent !important;
    font-size: .85rem !important; font-weight: 500 !important;
    letter-spacing: .01em !important; cursor: pointer !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
    background: rgba(0,120,255,.08) !important;
    border-color: rgba(0,120,255,.20) !important;
    color: #6a9ec8 !important;
}

/* ══════════════════════════════════════════════════════════════
   METRIC TILES
══════════════════════════════════════════════════════════════ */
div[data-testid="stMetric"] {
    background: rgba(3,10,26,0.80) !important;
    backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
    border: 1px solid rgba(0,120,255,.18) !important;
    border-top: 2px solid rgba(0,200,240,.60) !important;
    border-radius: 12px;
    padding: 1.1rem 1.3rem .95rem 1.3rem;
    box-shadow: 0 8px 36px rgba(0,0,0,.60), inset 0 1px 0 rgba(255,255,255,.025);
    position: relative; overflow: hidden;
}
/* Corner-cut decoration */
div[data-testid="stMetric"]::before {
    content: ''; position: absolute; inset: 0;
    background: linear-gradient(135deg, rgba(0,120,255,.07) 0%, transparent 50%);
    pointer-events: none;
}
div[data-testid="stMetric"] label {
    color: var(--muted) !important;
    font-size: .66rem !important; font-weight: 700 !important;
    letter-spacing: .16em !important; text-transform: uppercase !important;
    font-family: 'Space Mono', monospace !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: var(--text-hi) !important;
    font-size: 2.05rem !important; font-weight: 700 !important;
    letter-spacing: -.02em !important; font-variant-numeric: tabular-nums;
    font-family: 'Space Mono', monospace !important;
    text-shadow: 0 0 30px rgba(0,200,240,.28);
}
div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
    font-family: 'Space Mono', monospace !important; font-size: .76rem !important;
}

/* ══════════════════════════════════════════════════════════════
   BUTTONS
══════════════════════════════════════════════════════════════ */
.stButton > button {
    border-radius: 7px !important; font-weight: 600 !important;
    font-size: .84rem !important; letter-spacing: .025em !important;
    border: 1px solid rgba(0,120,255,.28) !important;
    background: linear-gradient(135deg, rgba(0,80,200,.12) 0%, rgba(0,120,255,.05) 100%) !important;
    color: #4a9ee8 !important;
    transition: all .22s ease !important;
    position: relative; overflow: hidden;
}
.stButton > button::before {
    content: '';
    position: absolute; inset: 0;
    background: linear-gradient(135deg, rgba(0,200,240,.06) 0%, transparent 60%);
    opacity: 0; transition: opacity .22s ease;
}
.stButton > button:hover {
    border-color: var(--cyan) !important;
    background: rgba(0,120,255,.16) !important;
    box-shadow: 0 0 20px rgba(0,120,255,.22), 0 0 40px rgba(0,120,255,.08),
                inset 0 0 18px rgba(0,120,255,.06) !important;
    color: #7ac8f8 !important;
    transform: translateY(-1px) !important;
}
.stButton > button:active {
    transform: translateY(0) !important;
    box-shadow: 0 0 10px rgba(0,120,255,.18) !important;
}

/* ══════════════════════════════════════════════════════════════
   TABS
══════════════════════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px;
    border-bottom: 1px solid rgba(0,120,255,.12);
    background: rgba(2,6,14,.70);
    border-radius: 10px 10px 0 0;
    padding: 4px 4px 0 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0; border: none !important;
    font-size: .82rem !important; font-weight: 600 !important;
    letter-spacing: .035em !important; color: var(--muted) !important;
    padding: .52rem 1.05rem !important;
    transition: all .18s ease !important; background: transparent !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: var(--text) !important;
    background: rgba(0,120,255,.07) !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: rgba(0,120,255,.11) !important;
    border-bottom: 2px solid var(--cyan) !important;
    color: var(--cyan) !important;
    text-shadow: 0 0 16px rgba(0,200,240,.40);
}

/* ══════════════════════════════════════════════════════════════
   FORM INPUTS
══════════════════════════════════════════════════════════════ */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stDateInput > div > div > input,
.stTextArea textarea {
    background: rgba(2,8,20,.92) !important;
    border: 1px solid rgba(0,120,255,.20) !important;
    border-radius: 7px !important; color: var(--text) !important;
    transition: border-color .18s, box-shadow .18s !important;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus,
.stTextArea textarea:focus {
    border-color: var(--cyan) !important;
    box-shadow: 0 0 0 3px rgba(0,200,240,.10), 0 0 18px rgba(0,200,240,.07) !important;
    outline: none !important;
}
.stSelectbox > div > div,
.stMultiSelect > div > div {
    background: rgba(2,8,20,.92) !important;
    border: 1px solid rgba(0,120,255,.20) !important;
    border-radius: 7px !important; color: var(--text) !important;
}

/* High-contrast text + caret across all editable fields */
.stApp input,
.stApp textarea {
    color: var(--text-hi) !important;
    -webkit-text-fill-color: var(--text-hi) !important;
    caret-color: var(--cyan) !important;
}
.stApp input::placeholder,
.stApp textarea::placeholder {
    color: #6d8db2 !important;
    opacity: 1 !important;
}
.stApp input::selection,
.stApp textarea::selection {
    background: rgba(0,200,240,.35);
    color: #f2f8ff;
}
.stApp input::-moz-selection,
.stApp textarea::-moz-selection {
    background: rgba(0,200,240,.35);
    color: #f2f8ff;
}
.stApp div[data-baseweb="input"] > div {
    background: rgba(2,8,20,.92) !important;
    border-color: rgba(0,120,255,.20) !important;
}
.stApp div[data-baseweb="input"] input {
    background: transparent !important;
    color: var(--text-hi) !important;
    -webkit-text-fill-color: var(--text-hi) !important;
    caret-color: var(--cyan) !important;
}
.stApp div[data-baseweb="input"] input:focus,
.stApp div[data-baseweb="textarea"] textarea:focus,
.stDateInput input:focus {
    color: var(--text-hi) !important;
    -webkit-text-fill-color: var(--text-hi) !important;
    caret-color: var(--cyan) !important;
}

/* ══════════════════════════════════════════════════════════════
   DATA FRAMES & CHARTS
══════════════════════════════════════════════════════════════ */

    border: 1px solid rgba(0,120,255,.15) !important;
    border-radius: 10px !important;
    overflow: hidden;
    box-shadow: none !important;
    background: rgba(2,8,18,.85) !important;
    /* Keep tabular content above atmospheric background layers for readability. */
    position: relative;
    z-index: 4;
}
[data-testid="stDataFrame"] {
    position: relative;
    z-index: 4;

}
[data-testid="stArrowVegaLiteChart"] {
    border-radius: 12px !important; overflow: hidden;
}

/* ══════════════════════════════════════════════════════════════
   TYPOGRAPHY
══════════════════════════════════════════════════════════════ */
h1, h2, h3, h4, h5, h6 { color: var(--text-hi) !important; }
p, label { color: var(--muted) !important; }

/* ── Page heading ── */
.page-heading { margin-bottom: 1.2rem; }
.page-heading h1 {
    font-size: 1.52rem; font-weight: 700; color: var(--text-hi);
    margin: 0 0 .10rem 0; letter-spacing: -.022em;
    text-shadow: 0 0 44px rgba(0,200,240,.22);
}
.page-heading p {
    color: var(--muted); font-size: .82rem; margin: 0; letter-spacing: .01em;
}
.accent-bar {
    width: 38px; height: 2px; border-radius: 99px; margin: .18rem 0 .32rem 0;
    background: linear-gradient(90deg, var(--cyan), var(--blue), var(--purple), var(--cyan));
    background-size: 300% 100%;
}

/* ── Cards ── */
.card {
    background: rgba(3,10,26,0.72);
    backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
    border: 1px solid var(--border); border-radius: 12px;
    padding: 1.2rem 1.4rem;
    box-shadow: 0 8px 32px rgba(0,0,0,.50), inset 0 1px 0 rgba(255,255,255,.025);
    margin-bottom: .85rem; position: relative; overflow: hidden;
}
.card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent 10%, rgba(0,200,240,.16) 50%, transparent 90%);
}
.card-sm {
    background: rgba(3,10,26,0.58);
    backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(0,120,255,.11); border-radius: 10px;
    padding: .8rem 1rem; box-shadow: 0 4px 20px rgba(0,0,0,.40);
}
.card h2 { color: var(--text-hi) !important; }

/* ── Section label ── */
.section-label {
    font-size: .66rem; font-weight: 700; letter-spacing: .16em;
    text-transform: uppercase; color: #4dd8f0; margin: 0 0 .5rem 0;
    font-family: 'Space Mono', monospace;
    text-shadow: 0 0 16px rgba(0,200,240,.70);
}

/* ── Section header (prominent section titles) ── */
.section-header {
    font-size: .82rem; font-weight: 700; letter-spacing: .13em;
    text-transform: uppercase; color: #4dd8f0;
    margin: 0 0 .85rem 0;
    font-family: 'Space Mono', monospace;
    padding: .45rem .8rem;
    border-left: 3px solid #4dd8f0;
    background: rgba(0,200,240,.09);
    border-radius: 0 6px 6px 0;
    text-shadow: 0 0 22px rgba(0,200,240,.80);
}

/* ── Divider ── */
.divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,120,255,.24), transparent);
    margin: 1.2rem 0; box-shadow: 0 0 8px rgba(0,120,255,.05);
}

/* ── Info / warn / danger boxes ── */
.info-box {
    background: rgba(0,120,255,.06); border: 1px solid rgba(0,120,255,.22);
    border-left: 3px solid var(--cyan); border-radius: 8px;
    padding: .75rem 1rem; color: var(--text); font-size: .86rem;
}
.warn-box {
    background: rgba(240,168,0,.06); border: 1px solid rgba(240,168,0,.22);
    border-left: 3px solid var(--amber); border-radius: 8px;
    padding: .75rem 1rem; color: var(--text); font-size: .86rem;
}
.danger-box {
    background: rgba(255,48,80,.06); border: 1px solid rgba(255,48,80,.22);
    border-left: 3px solid var(--red); border-radius: 8px;
    padding: .75rem 1rem; color: var(--text); font-size: .86rem;
}

/* ── List rows ── */
.list-row {
    background: rgba(3,10,26,0.58); border: 1px solid rgba(0,120,255,.10);
    border-radius: 9px; padding: .62rem 1rem; margin-bottom: .36rem;
    transition: border-color .18s ease;
}
.list-row:hover { border-color: rgba(0,120,255,.26); }
/* Dashboard hero + filter chips */
.dashboard-hero {
    background: linear-gradient(120deg, rgba(10, 26, 60, .78), rgba(8, 20, 45, .68));
    border: 1px solid rgba(0, 200, 240, .24);
    border-radius: 14px;
    padding: .95rem 1.05rem;
    margin: .25rem 0 .75rem 0;
    box-shadow: 0 10px 28px rgba(0, 0, 0, .38), inset 0 1px 0 rgba(255,255,255,.04);
}
.dashboard-hero-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: .6rem;
}
.dashboard-hero-stat {
    background: rgba(4, 14, 34, .72);
    border: 1px solid rgba(0, 120, 255, .20);
    border-radius: 11px;
    padding: .62rem .72rem;
}
.dashboard-hero-stat .k {
    font-size: .62rem;
    text-transform: uppercase;
    letter-spacing: .14em;
    color: #66ddf5;
    font-family: 'Space Mono', monospace;
}
.dashboard-hero-stat .v {
    font-size: 1.25rem;
    font-weight: 700;
    color: #e6f1ff;
    margin-top: .22rem;
}
.dashboard-filter-pill {
    display: inline-flex;
    align-items: center;
    gap: .35rem;
    margin-top: .65rem;
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #77d8ee;
    border: 1px solid rgba(0, 200, 240, .32);
    border-radius: 999px;
    padding: .28rem .62rem;
    background: rgba(0, 200, 240, .08);
    font-family: 'Space Mono', monospace;
}

/* Dashboard threshold tiles */
.dashboard-threshold-card {
    margin-bottom: .45rem;
    padding: .74rem .92rem;
    border-radius: 12px;
    border: 1px solid rgba(20, 40, 80, .28);
    background: linear-gradient(145deg, rgba(10,20,52,.76), rgba(7,17,39,.72));
    backdrop-filter: blur(12px);
    box-shadow: 0 4px 14px rgba(15,32,68,.10);
    pointer-events: none;
}
.dashboard-threshold-card .title {
    font-size: .65rem;
    letter-spacing: .10em;
    text-transform: uppercase;
    font-weight: 700;
}
.dashboard-threshold-card .meta {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-top: .18rem;
}
.dashboard-threshold-card .count {
    font-size: 1.95rem;
    font-weight: 800;
    color: #e8f1ff;
    line-height: 1;
}
.dashboard-threshold-card .hint {
    font-size: .67rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .07em;
}

/* ── Sidebar brand ── */
.sidebar-brand {
    padding: .70rem 0 .95rem 0;
    border-bottom: 1px solid rgba(0,120,255,.10); margin-bottom: .9rem;
}
.sidebar-brand .name {
    font-size: 1rem; font-weight: 700; color: #88b0d8 !important;
    letter-spacing: -.01em; text-shadow: 0 0 16px rgba(0,120,255,.22);
}
.sidebar-brand .sub { font-size: .68rem; color: #182840 !important; margin-top: .08rem; }
.sidebar-nav-label {
    font-size: .60rem !important; font-weight: 700 !important;
    letter-spacing: .16em !important; text-transform: uppercase !important;
    color: #182840 !important; margin: .9rem 0 .22rem 0 !important;
    display: block; font-family: 'Space Mono', monospace !important;
}

/* ── Employee spotlight card ── */
section[data-testid="stSidebar"] .sidebar-employee-card {
    margin-top: 1rem; padding: 1rem .9rem .85rem;
    border-radius: 14px; border: 1px solid rgba(0,200,240,.20);
    background: rgba(4,6,18,0.92); backdrop-filter: blur(14px);
    box-shadow: 0 12px 36px rgba(0,0,0,.65), inset 0 1px 0 rgba(255,255,255,.025);
    position: relative; overflow: hidden;
}
section[data-testid="stSidebar"] .sidebar-employee-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #00c8f0, #009ac8, #00e4ff);
    animation: card-top-border-glow 3s ease-in-out infinite;
}
@keyframes card-top-border-glow {
    0%,100% { opacity: .75; }
    50% { opacity: 1; box-shadow: 0 0 16px rgba(0,200,240,.45); }
}
section[data-testid="stSidebar"] .sidebar-employee-title {
    font-size: .65rem; letter-spacing: .18em; text-transform: uppercase; font-weight: 700;
    color: var(--cyan) !important; -webkit-text-fill-color: var(--cyan) !important;
    font-family: 'Space Mono', monospace !important;
    text-shadow: 0 0 10px rgba(0,200,240,.45); margin-bottom: .42rem;
    50% { opacity: 1; box-shadow: 0 0 16px rgba(0,200,240,.45); }
}

section[data-testid="stSidebar"] .sidebar-employee-name {
    font-size: 1.26rem; font-weight: 700;
    color: var(--text-hi) !important; -webkit-text-fill-color: var(--text-hi) !important;
    letter-spacing: -.015em; line-height: 1.2; margin-bottom: .62rem;
    padding-bottom: .52rem; border-bottom: 1px solid rgba(0,120,255,.12);
}
section[data-testid="stSidebar"] .sidebar-employee-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: .30rem;
}
section[data-testid="stSidebar"] .sidebar-employee-item {
    background: rgba(2,4,16,.82); border: 1px solid rgba(0,120,255,.11);
    border-radius: 7px; padding: .35rem .40rem;
}
section[data-testid="stSidebar"] .sidebar-employee-item.full-width { grid-column: 1 / -1; }
section[data-testid="stSidebar"] .sidebar-employee-item .label {
    display: block; font-size: .58rem; letter-spacing: .14em; text-transform: uppercase;
    color: #182840 !important; font-weight: 700;
    font-family: 'Space Mono', monospace !important; margin-bottom: .09rem;
}
section[data-testid="stSidebar"] .sidebar-employee-item .value {
    display: block; font-size: .87rem; font-weight: 600; color: #6090b8 !important;
    letter-spacing: -.01em;
}
section[data-testid="stSidebar"] .sidebar-employee-item .value.highlight {
    color: var(--cyan) !important; -webkit-text-fill-color: var(--cyan) !important;
    font-weight: 800; text-shadow: 0 0 8px rgba(0,200,240,.32);
}

/* ── Live dot ── */
@keyframes live-pulse {
  0%,100% { box-shadow: 0 0 0 0 rgba(0,232,150,.55), 0 0 8px rgba(0,232,150,.40); background: #00e896; }
  50%      { box-shadow: 0 0 0 7px rgba(0,232,150,0), 0 0 18px rgba(0,232,150,.70); background: #00ffaa; }
}
.live-dot {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    background: #00e896; margin-right: 8px; vertical-align: middle;
    animation: live-pulse 1.8s ease-in-out infinite;
}

/* ══════════════════════════════════════════════════════════════
   ANIMATIONS
══════════════════════════════════════════════════════════════ */

/* Metric tiles — top border cycles + lift */
@keyframes tile-breathe {
  0%,100% {
    border-top-color: rgba(0,200,240,.52) !important;
    box-shadow: 0 8px 36px rgba(0,0,0,.60), inset 0 1px 0 rgba(255,255,255,.025);
    transform: translateY(0);
  }
  50% {
    border-top-color: rgba(0,200,240,.98) !important;
    box-shadow: 0 10px 44px rgba(0,0,0,.65), 0 0 28px rgba(0,200,240,.18),
                inset 0 1px 0 rgba(255,255,255,.04);
    transform: translateY(-2px);
  }
}
div[data-testid="stMetric"]              { animation: tile-breathe 6s ease-in-out infinite; }
div[data-testid="stMetric"]:nth-child(1) { animation-delay: 0s;   }
div[data-testid="stMetric"]:nth-child(2) { animation-delay: 1.4s; }
div[data-testid="stMetric"]:nth-child(3) { animation-delay: 2.8s; }
div[data-testid="stMetric"]:nth-child(4) { animation-delay: 4.2s; }
div[data-testid="stMetric"]:nth-child(5) { animation-delay: 2.1s; }
div[data-testid="stMetric"]:nth-child(6) { animation-delay: 3.5s; }

/* Accent bar — continuous sweep */
@keyframes accent-sweep {
  0%   { background-position: 0%   50%; box-shadow: 0 0 10px rgba(0,120,255,.55), 0 0 24px rgba(0,120,255,.18); }
  50%  { background-position: 100% 50%; box-shadow: 0 0 18px rgba(0,200,240,.75), 0 0 36px rgba(0,200,240,.25); }
  100% { background-position: 200% 50%; box-shadow: 0 0 10px rgba(0,120,255,.55), 0 0 24px rgba(0,120,255,.18); }
}
.accent-bar { animation: accent-sweep 3.5s linear infinite; }

/* Cards — border breathe */
@keyframes card-breathe {
  0%,100% { border-color: rgba(0,120,255,.14); box-shadow: 0 8px 32px rgba(0,0,0,.50), inset 0 1px 0 rgba(255,255,255,.025); }
  50%      { border-color: rgba(0,120,255,.28); box-shadow: 0 10px 38px rgba(0,0,0,.55), 0 0 20px rgba(0,120,255,.07), inset 0 1px 0 rgba(255,255,255,.04); }
}
.card    { animation: card-breathe 9s ease-in-out infinite; }
.card-sm { animation: card-breathe 10s ease-in-out infinite; animation-delay: 2.5s; }

/* Section label shimmer */
@keyframes label-shimmer {
  0%,100% { text-shadow: 0 0 10px rgba(0,200,240,.28); opacity: .78; }
  50%      { text-shadow: 0 0 22px rgba(0,200,240,.65); opacity: 1; }
}
.section-label { animation: label-shimmer 4s ease-in-out infinite; }

/* Sidebar top brand border */
@keyframes sidebar-brand-glow {
  0%,100% { border-bottom-color: rgba(0,120,255,.10); }
  50%      { border-bottom-color: rgba(0,120,255,.32); }
}
.sidebar-brand { animation: sidebar-brand-glow 5s ease-in-out infinite; }

/* Box entrance */
@keyframes box-fade-in {
  from { opacity: 0; transform: translateY(5px); }
  to   { opacity: 1; transform: translateY(0); }
}
.info-box, .warn-box, .danger-box { animation: box-fade-in .40s ease-out both; }

/* Page heading entrance */
@keyframes heading-in {
  from { opacity: 0; transform: translateX(-8px); }
  to   { opacity: 1; transform: translateX(0); }
}
.page-heading { animation: heading-in .45s ease-out both; }

/* DataFrame/table visuals: fully static (remove moving line effects) */
.stDataFrame,
[data-testid="stDataFrame"],
[data-testid="stTable"] {
    animation: none !important;
    transition: none !important;
}
.stDataFrame *,
[data-testid="stDataFrame"] *,
[data-testid="stTable"] * {
    animation: none !important;
    transition: none !important;
}

/* Keep chart pulse animation */
@keyframes dataframe-glow {
  0%,100% { box-shadow: 0 0 0 1px rgba(0,120,255,.06); }
  50%      { box-shadow: 0 0 0 1px rgba(0,120,255,.22), 0 0 24px rgba(0,120,255,.06); }
}
[data-testid="stArrowVegaLiteChart"] {
    animation: dataframe-glow 6s ease-in-out infinite;
}

/* Divider breathe */
@keyframes divider-breathe {
  0%,100% { opacity: .40; }
  50%      { opacity: .88; box-shadow: 0 0 14px rgba(0,120,255,.16); }
}
.divider { animation: divider-breathe 5.5s ease-in-out infinite; }

/* List row entrance on hover highlight */
@keyframes row-in {
  from { opacity: 0; transform: translateX(-4px); }
  to   { opacity: 1; transform: translateX(0); }
}
.list-row { animation: row-in .35s ease-out both; }

/* HUD corner bracket pulse */
@keyframes corner-pulse {
  0%,100% { border-color: rgba(0,200,240,.22); }
  50%      { border-color: rgba(0,200,240,.55); }
}
.hud-corner { animation: corner-pulse 4s ease-in-out infinite; }

/* Respect prefers-reduced-motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important; animation-iteration-count: 1 !important;
  }
}
</style>""",
        unsafe_allow_html=True,
    )

# ── DB helpers ────────────────────────────────────────────────────────────────
def _db_cache_key() -> str:
    return db.get_db_path()


@st.cache_resource(show_spinner=False)
def _get_cached_conn(db_key: str):
    return db.connect()


@st.cache_resource(show_spinner=False)
def _initialize_database(db_key: str, repair_version: int) -> None:
    conn = _get_cached_conn(db_key)
    ensure_schema(conn)
    try:
        if is_pg(conn):
            exec_sql(conn, "ALTER TABLE employees ADD COLUMN IF NOT EXISTS point_warning_date DATE")
            conn.commit()
        else:
            cols = [r[1] for r in fetchall(conn, "PRAGMA table_info(employees)")]
            if "point_warning_date" not in cols:
                exec_sql(conn, "ALTER TABLE employees ADD COLUMN point_warning_date DATE")
                conn.commit()
    except Exception:
        pass

    bulk_recalc = getattr(services, "recalculate_all_employee_dates", None)
    single_recalc = getattr(services, "recalculate_employee_dates", None)
    if callable(bulk_recalc):
        bulk_recalc(conn)
    elif callable(single_recalc):
        employee_rows = fetchall(conn, "SELECT employee_id FROM employees")
        with db.tx(conn):
            for row in employee_rows:
                single_recalc(conn, int(row["employee_id"]))


@st.cache_data(ttl=EMPLOYEE_CACHE_TTL_SECONDS, show_spinner=False)
def _load_employees_cached(db_key: str, q: str, building: str) -> list[dict]:
    conn = _get_cached_conn(db_key)
    rows = [dict(r) for r in repo.search_employees(conn, q=q, limit=3000)]
    if building != "All":
        rows = [r for r in rows if (r.get("location") or "") == building]
    return rows


@st.cache_data(ttl=DASHBOARD_CACHE_TTL_SECONDS, show_spinner=False)
def _fetchall_cached(db_key: str, sql: str, params: tuple = ()) -> list[dict]:
    conn = _get_cached_conn(db_key)
    return [dict(r) for r in fetchall(conn, sql, params)]


def clear_read_caches() -> None:
    _load_employees_cached.clear()
    _fetchall_cached.clear()


def get_conn():
    db_key = _db_cache_key()
    _initialize_database(db_key, POINT_BALANCE_REPAIR_VERSION)
    return _get_cached_conn(db_key)

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
        return "-"
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
        return f"<span style='{s}color:#8fa0b8'>-</span>"
    if days < 0:
        return f"<span style='{s}color:#e0394a;background:rgba(224,57,74,.09);border:1px solid rgba(224,57,74,.20)'>overdue {abs(days)}d</span>"
    if days == 0:
        return f"<span style='{s}color:#e0394a;background:rgba(224,57,74,.09);border:1px solid rgba(224,57,74,.20)'>today</span>"
    if days <= 14:
        return f"<span style='{s}color:#e6960a;background:rgba(230,150,10,.09);border:1px solid rgba(230,150,10,.20)'>{days}d</span>"
    return f"<span style='{s}color:#7899c8;background:rgba(79,142,247,.08);border:1px solid rgba(79,142,247,.18)'>{days}d</span>"


def info_box(msg: str) -> None:
    st.markdown(f"<div class='info-box'>{_html_inline(msg)}</div>", unsafe_allow_html=True)


def warn_box(msg: str) -> None:
    st.markdown(f"<div class='warn-box'>{_html_inline(msg)}</div>", unsafe_allow_html=True)


def _repair_mojibake(text: object) -> str:
    """Fix double-encoded UTF-8 text (UTF-8 bytes misread as cp1252/latin-1)."""
    if text is None:
        return ""
    s = str(text)
    # Only attempt repair if text contains characters typical of mojibake
    # (latin chars with diacritics followed by special cp1252 chars)
    try:
        raw = s.encode("cp1252", errors="ignore")
        candidate = raw.decode("utf-8", errors="ignore")
        # Accept the repair only if it's shorter (mojibake is always longer)
        if candidate and len(candidate) < len(s):
            return candidate
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return s


def _html_inline(text: object) -> str:
    """Normalize punctuation for Streamlit raw-HTML blocks."""
    repaired = _repair_mojibake(text)
    return (
        html.escape(repaired)
        .replace("\u2014", "&mdash;")
        .replace("\u2013", "&ndash;")
        .replace("\u00b7", "&middot;")
        .replace("\u2022", "&bull;")
        .replace("\u2713", "&#10003;")
        .replace("\u00d7", "&times;")
    )


def page_heading(title: str, sub: str, *, allow_title_html: bool = False) -> None:
    repaired_title = _repair_mojibake(title)
    title_html = repaired_title if allow_title_html else _html_inline(repaired_title)
    st.markdown(
        f"<div class='page-heading'><h1>{title_html}</h1>"
        f"<div class='accent-bar'></div><p>{_html_inline(sub)}</p></div>",
        unsafe_allow_html=True,
    )


def section_label(text: str) -> None:
    st.markdown(f"<div class='section-label'>{_html_inline(text)}</div>", unsafe_allow_html=True)


def section_header(text: str) -> None:
    st.markdown(f"<div class='section-header'>{_html_inline(text)}</div>", unsafe_allow_html=True)


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
    To avoid a flash of the login screen, trust the in-session auth state while
    the URL token handoff is still in progress.
    """
    session_token = st.session_state.get("_auth_token")
    if not st.session_state.get("authenticated", False) or session_token is None:
        return False

    # Keep the post-login transition seamless even if URL params lag by a rerun.
    if st.query_params.get("_s") != session_token:
        st.query_params["_s"] = session_token
    if st.session_state.get("_auth_redirect_pending"):
        st.session_state["_auth_redirect_pending"] = False
    return True

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def render_hr_live_monitor(
    *,
    points_24h: int,
    points_7d: int,
    rolloffs_due_7d: int,
    perfect_due_7d: int,
    label: str = "At a glance",
    pto_utilization_pct: float | None = None,
):
    """
    Data-driven 'live monitor' animation bar.

    Normal mode (pto_utilization_pct is None):
      - Speed driven by recent points activity
      - Glow driven by upcoming rolloff/perfect-attendance deadlines
      - Color always cyan

    PTO mode (pto_utilization_pct provided):
      - Cyan  : utilization <= 50 %
      - Amber : 51–80 %
      - Red   : 81 %+  (pulsing)
    """
    # ── PTO color override ────────────────────────────────────────────────────
    safe_label = _html_inline(label)

    if pto_utilization_pct is not None:
        p = pto_utilization_pct
        if p <= 50.0:
            r, g, b = 0, 200, 240          # cyan
            pulse = False
            status = f"PTO Utilization {p:.0f}% — Normal"
        elif p <= 80.0:
            r, g, b = 240, 168, 0          # amber
            pulse = False
            status = f"PTO Utilization {p:.0f}% — Elevated"
        else:
            r, g, b = 255, 48, 80          # red
            pulse = True
            status = f"PTO Utilization {p:.0f}% — High"

        sweep_s   = 1.4
        glow      = 0.72
        baseline  = 0.35
        pulse_css = """
  animation: hr_pulse 0.9s ease-in-out infinite;
}
@keyframes hr_pulse {
  0%,100% { opacity: 0.65; }
  50%      { opacity: 1.0;  }
""" if pulse else ""
        safe_status = _html_inline(status)

        st.markdown(
            f"""<style>
.hr-monitor-wrap {{ margin: 6px 0 10px 0; }}
.hr-monitor-top  {{ display:flex; justify-content:space-between; align-items:baseline; gap:10px; margin-bottom:6px; }}
.hr-monitor-label  {{ font-size:0.92rem; opacity:0.92; }}
.hr-monitor-status {{ font-size:0.86rem; opacity:0.75; white-space:nowrap; color:rgb({r},{g},{b}); font-weight:600; }}
.hr-live-monitor {{
  position:relative; width:100%; height:14px; border-radius:999px;
  background:rgba(255,255,255,0.10); overflow:hidden;
  box-shadow:inset 0 0 0 1px rgba(255,255,255,0.12);
  {pulse_css}
}}
.hr-live-monitor::before {{
  content:""; position:absolute; left:0; top:50%; transform:translateY(-50%);
  width:100%; height:2px; background:rgba({r},{g},{b},{baseline});
}}
.hr-live-monitor::after {{
  content:""; position:absolute; top:0; left:-30%; width:30%; height:100%;
  background:linear-gradient(90deg,
    rgba(0,0,0,0),
    rgba({r},{g},{b},{glow}),
    rgba({r},{g},{b},{min(glow+0.12,0.90):.2f}),
    rgba({r},{g},{b},{glow}),
    rgba(0,0,0,0)
  );
  animation:hr_sweep {sweep_s:.2f}s linear infinite;
}}
@keyframes hr_sweep {{ 0% {{ left:-30%; }} 100% {{ left:100%; }} }}
</style>
<div class="hr-monitor-wrap">
  <div class="hr-monitor-top">
    <div class="hr-monitor-label">{safe_label}</div>
    <div class="hr-monitor-status">{safe_status}</div>
  </div>
  <div class="hr-live-monitor"></div>
</div>""",
            unsafe_allow_html=True,
        )
        return

    # ── Standard attendance mode ───────────────────────────────────────────────
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
    safe_status = _html_inline(status)

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
    <div class="hr-monitor-label">{safe_label}</div>
    <div class="hr-monitor-status">{safe_status} &middot; 24h:{points_24h} &middot; 7d:{points_7d} &middot; due7d:{rolloffs_due_7d + perfect_due_7d}</div>
  </div>
  <div class="hr-live-monitor"></div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_tech_hud(
    building: str,
    *,
    at_risk_5plus: int = 0,
    total_employees: int = 1,
) -> None:
    """Live HUD status bar with reactive colors based on employees at 5+ points.

    ACTIVITY label + bar/border color:
      Cyan  (< 10 % at 5+ pts)  — Normal
      Amber (10–24 %)            — Elevated
      Red   (25 %+)              — Critical
    """
    pct = (at_risk_5plus / max(total_employees, 1)) * 100.0

    if pct < 10.0:
        act_label   = "NORMAL"
        act_rgb     = "0,200,240"      # cyan
        bar_speed   = "1.4s"
        border_rgba = "rgba(0,120,255,.22)"
        sweep_rgba  = "rgba(0,200,240,.04)"
        top_rgba    = "rgba(0,200,240,.30)"
    elif pct < 25.0:
        act_label   = "ELEVATED"
        act_rgb     = "240,168,0"      # amber
        bar_speed   = "0.9s"
        border_rgba = "rgba(240,168,0,.45)"
        sweep_rgba  = "rgba(240,168,0,.06)"
        top_rgba    = "rgba(240,168,0,.50)"
    else:
        act_label   = "CRITICAL"
        act_rgb     = "255,48,80"      # red
        bar_speed   = "0.55s"
        border_rgba = "rgba(255,48,80,.55)"
        sweep_rgba  = "rgba(255,48,80,.07)"
        top_rgba    = "rgba(255,48,80,.60)"

    components.html(
        f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  background: transparent;
  font-family: 'Space Mono','SF Mono','Fira Code',ui-monospace,'Cascadia Code','Courier New',monospace;
  overflow: hidden;
}}
#hud {{
  display: flex; justify-content: space-between; align-items: center;
  padding: 7px 14px;
  background: rgba(2,8,22,0.94);
  border: 1px solid {border_rgba};
  border-radius: 10px;
  font-size: 10.5px; letter-spacing: .08em; color: #2d4860;
  box-shadow: 0 0 0 1px rgba(0,200,240,.04), 0 4px 24px rgba(0,0,0,.60),
              inset 0 1px 0 rgba(255,255,255,.025);
  position: relative; overflow: hidden;
}}
#hud::after {{
  content: '';
  position: absolute; top: 0; left: -80%; width: 40%; height: 100%;
  background: linear-gradient(90deg, transparent, {sweep_rgba}, transparent);
  animation: hud-sweep 7s linear infinite;
  pointer-events: none;
}}
@keyframes hud-sweep {{ 0% {{ left:-80%; }} 100% {{ left:160%; }} }}
#hud::before {{
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent 5%, {top_rgba} 50%, transparent 95%);
  animation: hud-top 5s ease-in-out infinite;
}}
@keyframes hud-top {{ 0%,100% {{ opacity:.40; }} 50% {{ opacity:.90; }} }}
.hud-left  {{ display:flex; align-items:center; gap:0; flex-wrap:nowrap; }}
.hud-right {{ display:flex; align-items:center; gap:0; flex-wrap:nowrap; }}
.seg {{ white-space:nowrap; }}
.dot {{
  display:inline-block; width:6px; height:6px; border-radius:50%;
  background:#00e896; margin-right:6px; vertical-align:middle;
  box-shadow:0 0 6px rgba(0,232,150,.70);
  animation:dot-blink 1.8s ease-in-out infinite;
}}
@keyframes dot-blink {{
  0%,100% {{ opacity:1;   box-shadow:0 0 4px  rgba(0,232,150,.65); }}
  50%      {{ opacity:.45; box-shadow:0 0 12px rgba(0,232,150,.95); }}
}}
.bars {{ display:inline-flex; align-items:flex-end; gap:2px; height:12px; margin:0 4px; vertical-align:middle; }}
.bar  {{ width:3px; border-radius:1px; }}
.bar:nth-child(1) {{ animation:bar-bounce {bar_speed} ease-in-out infinite 0.00s; }}
.bar:nth-child(2) {{ animation:bar-bounce {bar_speed} ease-in-out infinite 0.15s; }}
.bar:nth-child(3) {{ animation:bar-bounce {bar_speed} ease-in-out infinite 0.30s; }}
@keyframes bar-bounce {{
  0%,100% {{ height:3px;  background:rgba({act_rgb},.30); }}
  50%      {{ height:11px; background:rgba({act_rgb},.90); box-shadow:0 0 6px rgba({act_rgb},.50); }}
}}
.act-val {{ color:rgba({act_rgb},1); font-weight:700; }}
.signal {{ display:inline-flex; align-items:center; gap:3px; margin:0 4px; vertical-align:middle; }}
.sig-dot {{ width:4px; height:4px; border-radius:50%; }}
.sig-dot:nth-child(1) {{ background:rgba({act_rgb},.90); box-shadow:0 0 4px rgba({act_rgb},.50); animation:sig-pulse 2.4s ease-in-out infinite 0.0s; }}
.sig-dot:nth-child(2) {{ background:rgba({act_rgb},.65); animation:sig-pulse 2.4s ease-in-out infinite 0.6s; }}
.sig-dot:nth-child(3) {{ background:rgba({act_rgb},.35); animation:sig-pulse 2.4s ease-in-out infinite 1.2s; }}
@keyframes sig-pulse {{ 0%,100%{{opacity:.50;}} 50%{{opacity:1;}} }}
.val  {{ color:#4a88c0; }}
.hi   {{ color:#00c8f0; font-weight:700; }}
.green{{ color:#00e896; font-weight:700; }}
.sep  {{ color:rgba(0,120,255,.22); padding:0 10px; }}
#hud-time {{ color:#00c8f0; font-weight:700; letter-spacing:.14em; min-width:72px; text-align:right; }}
#hud-date {{ color:#2d4860; }}
</style></head><body>
<div id="hud">
  <div class="hud-left">
    <span class="seg"><span class="dot"></span>SYS&nbsp;<span class="green">ONLINE</span></span>
    <span class="sep">|</span>
    <span class="seg">
      <span class="bars"><span class="bar"></span><span class="bar"></span><span class="bar"></span></span>
      ACTIVITY&nbsp;<span class="act-val">{act_label}</span>
    </span>
    <span class="sep">|</span>
    <span class="seg">BUILDING&nbsp;<span class="val">{building.upper()}</span></span>
    <span class="sep">|</span>
    <span class="seg">SESSION&nbsp;<span class="hi" id="uptime">00:00:00</span></span>
    <span class="sep">|</span>
    <span class="seg">SIGNAL: Strong <span class="signal"><span class="sig-dot"></span><span class="sig-dot"></span><span class="sig-dot"></span></span></span>
  </div>
  <div class="hud-right">
    <span class="seg" id="hud-date"></span>
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
    var d=new Date(),ht=document.getElementById('hud-time'),
        hd=document.getElementById('hud-date'),up=document.getElementById('uptime');
    if(!ht)return;
    ht.textContent=p(d.getHours())+':'+p(d.getMinutes())+':'+p(d.getSeconds());
    hd.textContent=D[d.getDay()]+' '+p(d.getDate())+' '+M[d.getMonth()]+' '+d.getFullYear();
    var e=Math.floor((Date.now()-s)/1000);
    up.textContent=p(Math.floor(e/3600))+':'+p(Math.floor(e%3600/60))+':'+p(e%60);
  }}
  tick();setInterval(tick,1000);
}})();
</script>
</body></html>""",
        height=46,
        scrolling=False,
    )


# ── Login ──────────────────────────────────────────────────────────────────────
def login_page() -> None:
    """Render a centered access-code login screen matching the reference design."""
    def _handle_login_submit() -> None:
        expected = os.environ.get("ACCESS_CODE", "attendance2024")
        access_code = st.session_state.get("access_code_input", "")
        if access_code == expected:
            token = secrets.token_urlsafe(16)
            st.session_state["authenticated"] = True
            st.session_state["_auth_token"] = token
            st.session_state["_auth_redirect_pending"] = True
            st.session_state["login_error"] = False
            st.query_params["_s"] = token
        else:
            st.session_state["login_error"] = True
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
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');

        section[data-testid="stSidebar"] {{ display: none !important; }}
        footer, #MainMenu {{ visibility: hidden; }}

        /* ── Full-screen dark canvas ── */
        .stApp {{
            background: #02060e !important;
            font-family: 'Space Grotesk', system-ui, sans-serif !important;
        }}

        /* ── Atmospheric grid ── */
        .stApp::before {{
            content: '';
            position: fixed; inset: 0;
            background-image:
                linear-gradient(rgba(0,120,255,.015) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0,120,255,.015) 1px, transparent 1px);
            background-size: 48px 48px;
            pointer-events: none; z-index: 0;
        }}

        /* ── Aurora glow behind card ── */
        .stApp::after {{
            content: '';
            position: fixed; inset: 0;
            background:
                radial-gradient(ellipse 60% 50% at 50% 55%, rgba(0,80,200,.10) 0%, transparent 100%),
                radial-gradient(ellipse 40% 60% at 20% 20%, rgba(0,160,240,.06) 0%, transparent 100%),
                radial-gradient(ellipse 35% 45% at 80% 80%, rgba(80,0,180,.05) 0%, transparent 100%);
            pointer-events: none; z-index: 0;
        }}

        /* ── Vertical centering via top padding ── */
        .block-container {{
            padding-top: 12vh !important;
            padding-bottom: 4rem !important;
            max-width: 100% !important;
        }}

        /* ── Center the card within its column ── */
        .login-card {{
            margin: 0 auto !important;
        }}

        /* ── Status bar (top-of-card) ── */
        .login-status-bar {{
            display: flex; align-items: center; gap: 8px;
            font-family: 'Space Mono', monospace;
            font-size: .65rem; font-weight: 700;
            letter-spacing: .18em; text-transform: uppercase;
            color: #3d5a7a; margin-bottom: 1.8rem;
        }}
        .login-status-dot {{
            width: 7px; height: 7px; border-radius: 50%;
            background: #00e896;
            box-shadow: 0 0 8px rgba(0,232,150,.70);
            animation: login-dot-pulse 1.8s ease-in-out infinite;
        }}
        @keyframes login-dot-pulse {{
            0%,100% {{ box-shadow: 0 0 5px rgba(0,232,150,.60); }}
            50%      {{ box-shadow: 0 0 14px rgba(0,232,150,.90); }}
        }}

        /* ── Main login card ── */
        .login-card {{
            background: rgba(3,10,26,0.88);
            backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(0,120,255,.22);
            border-radius: 16px;
            width: 100%; max-width: 400px;
            padding: 0;
            box-shadow: 0 24px 80px rgba(0,0,0,.80),
                        0 0 0 1px rgba(0,200,240,.05),
                        inset 0 1px 0 rgba(255,255,255,.04);
            position: relative; overflow: hidden;
        }}
        /* Animated top border */
        .login-card::before {{
            content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent 0%, #00c8f0 40%, #0078ff 60%, transparent 100%);
            animation: login-top-glow 4s ease-in-out infinite;
        }}
        @keyframes login-top-glow {{
            0%,100% {{ opacity: .55; box-shadow: 0 0 10px rgba(0,200,240,.20); }}
            50%      {{ opacity: 1;   box-shadow: 0 0 24px rgba(0,200,240,.55); }}
        }}
        /* Corner decorators */
        .login-card::after {{
            content: ''; position: absolute;
            bottom: -1px; right: -1px;
            width: 20px; height: 20px;
            border-bottom: 2px solid rgba(0,200,240,.30);
            border-right:  2px solid rgba(0,200,240,.30);
            border-radius: 0 0 16px 0;
        }}

        /* ── Card header band ── */
        .login-card-header {{
            padding: 1.8rem 2rem 1.4rem;
            border-bottom: 1px solid rgba(0,120,255,.12);
            text-align: center;
        }}
        .login-card-body {{
            padding: 1.6rem 2rem 2rem;
        }}

        /* ── Title & subtitle ── */
        .login-system-tag {{
            font-family: 'Space Mono', monospace;
            font-size: .60rem; font-weight: 700;
            letter-spacing: .20em; text-transform: uppercase;
            color: #00c8f0; margin-bottom: .7rem;
            text-shadow: 0 0 14px rgba(0,200,240,.40);
        }}
        .login-title {{
            font-size: 1.28rem; font-weight: 700;
            color: #d8ecff; margin: .4rem 0 0 0;
            letter-spacing: -.015em;
            text-shadow: 0 0 30px rgba(0,200,240,.18);
        }}

        /* ── Field label ── */
        .login-field-label {{
            display: block;
            font-family: 'Space Mono', monospace;
            font-size: .62rem; font-weight: 700;
            letter-spacing: .14em; text-transform: uppercase;
            color: #3d5a7a;
            margin-bottom: .4rem; margin-top: 0;
        }}

        /* ── Input ── */
        div[data-testid="stTextInput"] input {{
            background: rgba(0,6,20,.92) !important;
            border: 1px solid rgba(0,120,255,.25) !important;
            border-radius: 8px !important;
            color: #b8d0ee !important;
            font-family: 'Space Mono', monospace !important;
            font-size: .92rem !important;
            letter-spacing: .08em !important;
            transition: border-color .18s, box-shadow .18s !important;
        }}
        div[data-testid="stTextInput"] input:focus {{
            border-color: #00c8f0 !important;
            box-shadow: 0 0 0 3px rgba(0,200,240,.12), 0 0 18px rgba(0,200,240,.07) !important;
        }}

        /* ── Authorize button ── */
        .stButton > button {{
            background: linear-gradient(135deg, rgba(0,80,200,.20) 0%, rgba(0,120,255,.10) 100%) !important;
            border: 1px solid rgba(0,200,240,.40) !important;
            border-radius: 8px !important;
            color: #00c8f0 !important;
            font-family: 'Space Grotesk', sans-serif !important;
            font-size: .90rem !important; font-weight: 700 !important;
            letter-spacing: .08em !important; text-transform: uppercase !important;
            width: 100% !important; padding: .72rem !important;
            margin-top: 1.1rem !important;
            transition: all .22s ease !important;
            box-shadow: 0 0 20px rgba(0,120,255,.10) !important;
        }}
        .stButton > button:hover {{
            background: rgba(0,120,255,.20) !important;
            border-color: #00c8f0 !important;
            box-shadow: 0 0 28px rgba(0,200,240,.28), 0 0 56px rgba(0,120,255,.12) !important;
            color: #40e0ff !important;
            transform: translateY(-1px) !important;
        }}
        .stButton > button:active {{ transform: translateY(0) !important; }}

        /* ── Error message ── */
        .login-error {{
            background: rgba(255,48,80,.08);
            border: 1px solid rgba(255,48,80,.28);
            border-left: 3px solid #ff3050;
            border-radius: 7px;
            padding: .55rem .9rem;
            color: #ff8090;
            font-family: 'Space Mono', monospace;
            font-size: .75rem; font-weight: 400;
            margin-top: .65rem; letter-spacing: .02em;
        }}

        /* ── Footer tagline ── */
        .login-footer {{
            font-family: 'Space Mono', monospace;
            font-size: .58rem; letter-spacing: .14em;
            color: #182840; text-align: center;
            margin-top: 1.6rem; text-transform: uppercase;
        }}
        </style>""",
        unsafe_allow_html=True,
    )

    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        # Status bar above card
        st.markdown(
            "<div class='login-status-bar'>"
            "<span class='login-status-dot'></span>"
            "SYSTEM ONLINE &nbsp;·&nbsp;"
            "</div>",
            unsafe_allow_html=True,
        )

        # Card header (pure HTML — logo, system tag, title)
        st.markdown(
            f"<div class='login-card'>"
            f"  <div class='login-card-header'>"
            f"    <div class='login-system-tag'>Status: ●Online</div>"
            f"    {logo_tag}"
            f"    <div class='login-title'>Attendance Tracking</div>"
            f"  </div>"
            f"  <div class='login-card-body'>",
            unsafe_allow_html=True,
        )

        st.markdown("<span class='login-field-label'>Access Code</span>", unsafe_allow_html=True)
        st.text_input(
            "Access Code",
            type="password",
            placeholder="Enter authorization code",
            label_visibility="collapsed",
            key="access_code_input",
        )
        st.button("Begin Tracking", use_container_width=True, on_click=_handle_login_submit)
        if st.session_state.get("login_error"):
            st.markdown(
                "<div class='login-error'>ACCESS DENIED — Incorrect authorization code.</div>",
                unsafe_allow_html=True,
            )

        st.markdown("</div></div>", unsafe_allow_html=True)

        st.markdown(
            "<div class='login-footer'>AUTHORIZED PERSONNEL ONLY</div>",
            unsafe_allow_html=True,
        )


def build_point_history_pdf(employee: dict, history: list[dict]) -> bytes:
    """Generate a premium minimalist attendance point history PDF with company branding."""
    from reportlab.platypus import Image
    from reportlab.lib.enums import TA_CENTER

    buffer = BytesIO()

    # ── Brand palette ─────────────────────────────────────────────────────────
    C_NAVY    = colors.HexColor("#0D2461")   # AAP deep navy
    C_RED     = colors.HexColor("#CC1F2D")   # AAP brand red (borders/accents only)
    C_TEXT    = colors.HexColor("#0D1117")   # near-black body text
    C_MUTED   = colors.HexColor("#64748B")   # secondary text
    C_DIVIDER = colors.HexColor("#E2E8F0")   # subtle border
    C_ROW_ALT = colors.HexColor("#F5F7FF")   # alternating row tint
    C_STAT_BG = colors.HexColor("#F8FAFC")   # empty-state table background
    C_WHITE   = colors.white

    # ── Page geometry ─────────────────────────────────────────────────────────
    PW, PH = letter
    LM = RM = 0.5 * inch
    HEADER_H = 0.82 * inch   # height of drawn header zone
    TM = HEADER_H + 0.18 * inch
    BM = 0.48 * inch
    CW = PW - LM - RM        # 7.5 inch content width

    # ── Employee data ─────────────────────────────────────────────────────────
    full_name   = f"{employee.get('last_name', '')}, {employee.get('first_name', '')}".strip(", ")
    emp_id      = str(employee.get("employee_id", "—"))
    location    = str(employee.get("Location") or employee.get("location") or "—")
    cur_pts     = float(employee.get("point_total") or 0)
    gen_on      = datetime.now().strftime("%m/%d/%Y  %I:%M %p")

    # ── Styles ────────────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    def S(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    lbl_s    = S("PDFLbl",   fontName="Helvetica-Bold", fontSize=7,   textColor=C_MUTED, spaceAfter=2)
    val_s    = S("PDFVal",   fontName="Helvetica-Bold", fontSize=12,  textColor=C_TEXT)
    note_s   = S("PDFNote",  fontName="Helvetica",      fontSize=8,   leading=10,  textColor=C_TEXT)
    reason_s = S("PDFRsn",   fontName="Helvetica",      fontSize=8.5, leading=10.5, textColor=C_TEXT)
    date_s   = S("PDFDt",    fontName="Helvetica",      fontSize=8.5, textColor=C_TEXT)
    hdr_s    = S("PDFHdr",   fontName="Helvetica-Bold", fontSize=8,   textColor=C_WHITE)
    hdr_r_s  = S("PDFHdrR",  fontName="Helvetica-Bold", fontSize=8,   textColor=C_WHITE, alignment=TA_RIGHT)
    pts_r_s  = S("PDFPtsR",  fontName="Helvetica-Bold", fontSize=8.5, textColor=C_TEXT,  alignment=TA_RIGHT)
    empty_s  = S("PDFEmpty", fontName="Helvetica",      fontSize=10,  leading=14, textColor=C_MUTED)

    # ── Logo / asset path ─────────────────────────────────────────────────────
    LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.png"

    # ── Per-page header + footer via canvas callback ───────────────────────────
    def draw_page(canvas, doc):
        canvas.saveState()

        # ── Header: two accent stripes at the bottom edge of header zone ──────
        stripe_y = PH - HEADER_H
        canvas.setFillColor(C_NAVY)
        canvas.rect(0, stripe_y - 3.5, PW, 3.5, fill=1, stroke=0)
        canvas.setFillColor(C_RED)
        canvas.rect(0, stripe_y - 6.0, PW, 2.5, fill=1, stroke=0)

        # ── Logo ──────────────────────────────────────────────────────────────
        logo_h = 0.52 * inch
        logo_y = (PH - HEADER_H) + (HEADER_H - logo_h) / 2
        if LOGO_PATH.exists():
            try:
                canvas.drawImage(
                    str(LOGO_PATH), LM, logo_y,
                    height=logo_h, width=2.6 * inch,
                    preserveAspectRatio=True, mask="auto",
                )
            except Exception:
                pass

        # ── Title block (right-aligned) ────────────────────────────────────────
        mid_y = PH - HEADER_H / 2
        canvas.setFillColor(C_MUTED)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(PW - RM, mid_y + 15, "AMERICAN ASSOCIATED PHARMACIES")
        canvas.setFillColor(C_NAVY)
        canvas.setFont("Helvetica-Bold", 17)
        canvas.drawRightString(PW - RM, mid_y - 1, "ATTENDANCE POINT HISTORY")
        canvas.setFillColor(C_MUTED)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(PW - RM, mid_y - 15, f"Generated  {gen_on}")

        # ── Footer ────────────────────────────────────────────────────────────
        foot_y = BM - 6
        canvas.setStrokeColor(C_DIVIDER)
        canvas.setLineWidth(0.5)
        canvas.line(LM, foot_y, PW - RM, foot_y)
        canvas.setFillColor(C_MUTED)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(LM, foot_y - 11, "CONFIDENTIAL — FOR INTERNAL USE ONLY")
        canvas.drawCentredString(PW / 2, foot_y - 11, full_name)
        canvas.drawRightString(PW - RM, foot_y - 11, f"Page {doc.page}")

        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=LM,
        rightMargin=RM,
        topMargin=TM,
        bottomMargin=BM,
    )

    story = []

    # ── Employee info card ────────────────────────────────────────────────────
    # col widths: 3.0 + 1.3 + 1.3 + 1.9 = 7.5
    emp_col_w = [3.0 * inch, 1.3 * inch, 1.3 * inch, 1.9 * inch]
    pts_val_s = S("PDFPtsV", fontName="Helvetica-Bold", fontSize=18, textColor=C_TEXT)

    emp_table = Table(
        [
            [
                Paragraph("EMPLOYEE NAME", lbl_s),
                Paragraph("EMPLOYEE #", lbl_s),
                Paragraph("LOCATION", lbl_s),
                Paragraph("CURRENT POINTS", lbl_s),
            ],
            [
                Paragraph(full_name or "—", val_s),
                Paragraph(emp_id, val_s),
                Paragraph(location, val_s),
                Paragraph(f"{cur_pts:.1f}", pts_val_s),
            ],
        ],
        colWidths=emp_col_w,
    )
    emp_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#EEF2FF")),
        ("BACKGROUND",   (0, 1), (-1, 1), C_WHITE),
        ("LINEABOVE",    (0, 0), (-1, 0), 3,   C_NAVY),
        ("LINEBEFORE",   (0, 0), (0, -1), 3,   C_RED),
        ("LINEBELOW",    (0, 1), (-1, 1), 0.5, C_DIVIDER),
        ("LINEAFTER",    (-1, 0), (-1, -1), 0.5, C_DIVIDER),
        ("INNERGRID",    (0, 0), (-1, -1), 0.4, C_DIVIDER),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING",(0, 0), (-1, 0), 4),
        ("TOPPADDING",   (0, 1), (-1, 1), 6),
        ("BOTTOMPADDING",(0, 1), (-1, 1), 8),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(emp_table)
    story.append(Spacer(1, 0.11 * inch))

    # ── Section label ─────────────────────────────────────────────────────────
    sec_lbl = Table(
        [[Paragraph("POINT HISTORY", S("SecLbl", fontName="Helvetica-Bold", fontSize=7.5, textColor=C_NAVY))]],
        colWidths=[CW],
    )
    sec_lbl.setStyle(TableStyle([
        ("LINEABOVE",    (0, 0), (-1, -1), 2,   C_NAVY),
        ("LINEBELOW",    (0, 0), (-1, -1), 0.5, C_DIVIDER),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]))
    story.append(sec_lbl)

    # ── History table ─────────────────────────────────────────────────────────
    # col widths: 0.88 + 0.62 + 1.6 + 3.52 + 0.88 = 7.5 inch
    col_w = [0.88 * inch, 0.62 * inch, 1.6 * inch, 3.52 * inch, 0.88 * inch]

    if history:
        table_rows = [[
            Paragraph("DATE",    hdr_s),
            Paragraph("PTS",     hdr_r_s),
            Paragraph("REASON",  hdr_s),
            Paragraph("NOTE",    hdr_s),
            Paragraph("BALANCE", hdr_r_s),
        ]]
        ts_cmds = [
            ("BACKGROUND",   (0, 0), (-1, 0),  C_NAVY),
            ("LINEBELOW",    (0, 0), (-1, 0),  2,   C_RED),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_WHITE, C_ROW_ALT]),
            ("INNERGRID",    (0, 0), (-1, -1), 0.35, C_DIVIDER),
            ("BOX",          (0, 0), (-1, -1), 0.5,  C_DIVIDER),
            ("FONTSIZE",     (0, 0), (-1, -1), 8.5),
            ("LEFTPADDING",  (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING",   (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
            ("TOPPADDING",   (0, 0), (-1, 0),  6),
            ("BOTTOMPADDING",(0, 0), (-1, 0),  6),
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ]

        for i, row in enumerate(history):
            pt  = float(row.get("points")      or 0)
            tot = float(row.get("point_total") or 0)
            table_rows.append([
                Paragraph(fmt_date(row.get("point_date")), date_s),
                Paragraph(f"{pt:+.1f}",  pts_r_s),
                Paragraph(str(row.get("reason") or "—"), reason_s),
                Paragraph(str(row.get("note")   or "—"), note_s),
                Paragraph(f"{tot:.1f}",  pts_r_s),
            ])

        tbl = Table(table_rows, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle(ts_cmds))
        story.append(tbl)
    else:
        empty_tbl = Table(
            [[Paragraph("No point history entries were found for this employee.", empty_s)]],
            colWidths=[CW],
        )
        empty_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), C_STAT_BG),
            ("BOX",          (0, 0), (-1, -1), 0.5, C_DIVIDER),
            ("LEFTPADDING",  (0, 0), (-1, -1), 16),
            ("TOPPADDING",   (0, 0), (-1, -1), 16),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 16),
        ]))
        story.append(empty_tbl)

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
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
                   COALESCE(e.point_total, 0.0) AS point_total,
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
                   COALESCE(e.point_total, 0.0) AS point_total,
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
    full_name_html = _html_inline(full_name)
    emp_id_html = _html_inline(emp.get("employee_id") or "�")
    building_html = _html_inline(emp.get("building") or "�")
    last_point_html = _html_inline(fmt_date(emp.get("last_positive_point_date")))
    roll_off_html = _html_inline(fmt_date(emp.get("rolloff_date")))
    perfect_attendance_html = _html_inline(fmt_date(emp.get("perfect_attendance")))
    st.markdown(
        "<div class='sidebar-employee-card'>"
        "<div class='sidebar-employee-title'>&#9673; Employee Spotlight</div>"
        f"<div class='sidebar-employee-name'>{full_name_html}</div>"
        "<div class='sidebar-employee-grid'>"
        f"<div class='sidebar-employee-item'><span class='label'>Emp #</span><span class='value'>{emp_id_html}</span></div>"
        f"<div class='sidebar-employee-item'><span class='label'>Building</span><span class='value'>{building_html}</span></div>"
        f"<div class='sidebar-employee-item full-width'><span class='label'>Point Total</span><span class='value highlight'>{float(emp.get('point_total') or 0):.1f} pts</span></div>"
        f"<div class='sidebar-employee-item'><span class='label'>Last Point</span><span class='value'>{last_point_html}</span></div>"
        f"<div class='sidebar-employee-item'><span class='label'>Roll Off</span><span class='value'>{roll_off_html}</span></div>"
        f"<div class='sidebar-employee-item full-width'><span class='label'>Perfect Attendance</span><span class='value'>{perfect_attendance_html}</span></div>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        """<style>
        .st-key-spotlight_add_point button {
            background: transparent !important;
            border: 1px solid rgba(0,200,240,.45) !important;
            color: rgba(0,200,240,.95) !important;
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
            background: rgba(0,200,240,.10) !important;
            border-color: rgba(0,200,240,.9) !important;
            color: #00c8f0 !important;
            box-shadow: 0 0 10px rgba(0,200,240,.28) !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )
    if st.button("⊕  Add Point to Record", key="spotlight_add_point", use_container_width=True):
        st.session_state["ledger_emp_id"] = int(emp["employee_id"])
        st.session_state["_nav_to"] = "Points Ledger"
        st.rerun()


def load_employees(conn, q: str = "", building: str = "All") -> list[dict]:
    return _load_employees_cached(_db_cache_key(), q, building)


# ── Dashboard ─────────────────────────────────────────────────────────────────
def dashboard_page(conn, building: str) -> None:
    page_heading(
        '<span class="live-dot"></span>Active',
        "Track attendance momentum, risk thresholds, and next actions in one polished workspace.",
        allow_title_html=True,
    )

    today = date.today()
    in_30_days = today + timedelta(days=30)
    employees = load_employees(conn, building=building)
    emp_ids = [int(e["employee_id"]) for e in employees]

    if not emp_ids:
        render_tech_hud(building)
        info_box("No employees found for this building filter.")
        return
    ph = ",".join(["?" if not is_pg(conn) else "%s"] * len(emp_ids))
    db_key = _db_cache_key()

    def _read_rows(sql: str, params: tuple) -> list[dict]:
        return _fetchall_cached(db_key, sql, tuple(params))

    def _scalar_n(sql: str, params: tuple) -> int:
        rows = _read_rows(sql, params)
        if not rows:
            return 0
        return int(rows[0].get("n") or 0)

    # ── HR Live Monitor data ──────────────────────────────────────────────────
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
               AND COALESCE(point_total, 0.0) >= 0.5
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

        points_24h = _scalar_n(sql_points_since, (*emp_ids, since_24h))
        points_7d = _scalar_n(sql_points_since, (*emp_ids, since_7d))
        rolloffs_due_7d = _scalar_n(sql_roll_due_7d, (*emp_ids, today.isoformat(), due_7d))
        perfect_due_7d = _scalar_n(sql_perf_due_7d, (*emp_ids, today.isoformat(), due_7d))

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
               AND COALESCE(point_total, 0.0) >= 0.5
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

        points_24h = _scalar_n(sql_points_since, (*emp_ids, since_24h))
        points_7d = _scalar_n(sql_points_since, (*emp_ids, since_7d))
        rolloffs_due_7d = _scalar_n(sql_roll_due_7d, (*emp_ids, today.isoformat(), due_7d))
        perfect_due_7d = _scalar_n(sql_perf_due_7d, (*emp_ids, today.isoformat(), due_7d))

    if is_pg(conn):
        sql_emp_detail = f'''
            SELECT e.employee_id, e.last_name, e.first_name,
                   COALESCE(e."Location",'') AS building,
                   COALESCE(e.point_total, 0.0) AS point_total,
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
               AND COALESCE(point_total, 0.0) >= 0.5
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
                   COALESCE(e.point_total, 0.0) AS point_total
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
                   ), '�') AS top_reason
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
                   COALESCE(e.point_total, 0.0) AS point_total,
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
               AND COALESCE(point_total, 0.0) >= 0.5
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
                   COALESCE(e.point_total, 0.0) AS point_total
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
                   ), '�') AS top_reason
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

    emp_detail_rows = _read_rows(sql_emp_detail, tuple(emp_ids))
    roll_due_rows = _read_rows(sql_roll_due, (*emp_ids, today.isoformat(), in_30_days.isoformat()))
    perf_due_rows = _read_rows(sql_perf_due, (*emp_ids, today.isoformat(), in_30_days.isoformat()))

    bucket_defs = {
        "gt1": lambda pts: pts > 1.0,
        "1-4": lambda pts: 1.0 <= pts <= 4.5,
        "5-6": lambda pts: 5.0 <= pts <= 6.5,
        "7": lambda pts: pts >= 7.0,
    }
    bucket_counts = {
        key: sum(1 for r in emp_detail_rows if fn(float(r.get("point_total") or 0)))
        for key, fn in bucket_defs.items()
    }

    # ── Now that we have real data, fill the top-of-page widgets ─────────────
    at_risk_5plus = bucket_counts.get("5-6", 0) + bucket_counts.get("7", 0)
    total_active  = len(emp_detail_rows)

    render_tech_hud(
        building,
        at_risk_5plus=at_risk_5plus,
        total_employees=total_active,
    )

    active_bucket_label = "All Employees"
    _bucket_label_map = {
        "gt1": ">1.0 Point",
        "1-4": "1.0-4.5 Pts",
        "5-6": "5.0-6.5 Pts",
        "7": "7.0+ Pts",
    }
    if st.session_state.get("dashboard_bucket") in _bucket_label_map:
        active_bucket_label = _bucket_label_map[st.session_state["dashboard_bucket"]]

    st.markdown(
        f"""<div class='dashboard-hero'>
                <div class='dashboard-hero-grid'>
                    <div class='dashboard-hero-stat'><div class='k'>Active Employees</div><div class='v'>{total_active}</div></div>
                    <div class='dashboard-hero-stat'><div class='k'>At Risk (5+)</div><div class='v'>{at_risk_5plus}</div></div>
                    <div class='dashboard-hero-stat'><div class='k'>Rolloffs Due 7d</div><div class='v'>{rolloffs_due_7d}</div></div>
                    <div class='dashboard-hero-stat'><div class='k'>Perfect Due 7d</div><div class='v'>{perfect_due_7d}</div></div>
                </div>
                <div class='dashboard-filter-pill'>Active threshold view: {active_bucket_label}</div>
            </div>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """<style>
        .st-key-dashboard_bucket_all div[data-testid="stButton"],
        .st-key-dashboard_bucket_gt1 div[data-testid="stButton"],
        .st-key-dashboard_bucket_1-4 div[data-testid="stButton"],
        .st-key-dashboard_bucket_5-6 div[data-testid="stButton"],
        .st-key-dashboard_bucket_7 div[data-testid="stButton"] {
            margin-top: -92px !important;
            position: relative;
            z-index: 30;
        }
        .st-key-dashboard_bucket_all div[data-testid="stButton"] > button,
        .st-key-dashboard_bucket_gt1 div[data-testid="stButton"] > button,
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
        .st-key-dashboard_bucket_gt1 div[data-testid="stButton"] > button p,
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
        ("gt1", ">1.0 Point"),
        ("1-4", "1.0-4.5 Pts"),
        ("5-6", "5.0-6.5 Pts"),
        ("7", "7.0+ Pts"),
    ]
    active_bucket = st.session_state.get("dashboard_bucket")

    for col, (key, label) in zip(tile_cols, tile_specs):
        selected = (active_bucket == key) if key != "all" else (active_bucket not in bucket_defs)
        accent, glow = {
            "all": ("#87a4c6", "rgba(135,164,198,.22)"),
            "gt1": ("#00d4ff", "rgba(0,212,255,.24)"),
            "1-4": ("#2da8e8", "rgba(45,168,232,.24)"),
            "5-6": ("#ff6a7f", "rgba(255,106,127,.30)"),
            "7": ("#ff304f", "rgba(255,48,79,.34)"),
        }.get(key, ("#87a4c6", "rgba(135,164,198,.22)"))
        card_border = "rgba(24,49,92,.22)" if not selected else accent
        card_shadow = f"0 0 0 2px {glow}, 0 10px 20px rgba(8,22,52,.22)" if selected else "0 6px 14px rgba(8,22,52,.18)"
        employees_count = len(emp_detail_rows) if key == "all" else bucket_counts[key]
        hint = "selected" if selected else "tap to filter"

        col.markdown(
            f"<div class='dashboard-threshold-card' style='border-color:{card_border};box-shadow:{card_shadow};'>"
            f"<div style='height:4px;border-radius:999px;background:{accent};margin:-.2rem 0 .55rem 0;'></div>"
            f"<div class='title' style='color:{accent}'>{label}</div>"
            f"<div class='meta'>"
            f"<span class='count'>{employees_count}</span>"
            f"<span class='hint' style='color:{accent};'>{hint}</span>"
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
                        "Building": r.get("building") or "�",
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
            info_box("No employees match the selected threshold.")


    with col_right:
        section_label("Roll Offs Due (Next 30 Days)")
        if roll_due_rows:
            df_roll = pd.DataFrame(
                [
                    {
                        "Employee #": str(r["employee_id"]),
                        "Name": f"{r['last_name']}, {r['first_name']}",
                        "Building": r.get("building") or "�",
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
                        "Building": r.get("building") or "�",
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

    active_rows = _read_rows(
        """SELECT COALESCE("Location", '') AS building, COUNT(*) AS n
           FROM employees
          WHERE COALESCE(is_active,1)=1
          GROUP BY COALESCE("Location", '')""",
        (),
    )
    avg_total_rows = _read_rows(
        """SELECT COALESCE("Location", '') AS building,
                  AVG(COALESCE(point_total, 0.0)) AS avg_point_total
           FROM employees
          WHERE COALESCE(is_active,1)=1
          GROUP BY COALESCE("Location", '')""",
        (),
    )
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

    current_rows = _read_rows(sql_build_points_window, (*emp_ids, since_30, tomorrow))
    prior_rows = _read_rows(sql_build_points_window, (*emp_ids, since_60, since_30))
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
            pct_txt = "�"
        reason_rows = _read_rows(sql_build_reasons, (since_30, b))
        most_common_reason = (reason_rows[0].get("reason") if reason_rows else None) or "�"
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
    section_label("Forecasting")

    st.markdown("#### Employees > 1.0 Point (Last 30 Days)")
    gt1_rows = _read_rows(sql_insights_gt1, (since_30, *emp_ids, since_30))
    if gt1_rows:
        df_gt1 = pd.DataFrame(
            [
                {
                    "Employee #": str(r["employee_id"]),
                    "Name": f"{r['last_name']}, {r['first_name']}",
                    "Building": r.get("building") or "�",
                    "Points (30d)": f"{float(r.get('points_30d') or 0.0):.1f}",
                    "Last Point Date": fmt_date(r.get("last_point_date")),
                    "Top Reason": (r.get("top_reason") or "�"),
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

    st.markdown("#### Trending Risks  � On track to exceed 8 points")
    pts60_rows = _read_rows(sql_points_60d, (*emp_ids, since_60))
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
                    "Building": r.get("building") or "�",
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
    trend_rows = _read_rows(sql_trend_90d, (*emp_ids, (today - timedelta(days=90)).isoformat()))
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
        for r in _read_rows(sql_weekday_window, (*emp_ids, window_start.isoformat(), window_end.isoformat(), *emp_ids, window_start.isoformat(), window_end.isoformat()))
    ]
    prior_rows = [
        dict(r)
        for r in _read_rows(sql_weekday_window, (*emp_ids, prior_start.isoformat(), prior_end.isoformat(), *emp_ids, prior_start.isoformat(), prior_end.isoformat()))
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
        st.caption("Rate uses approximate active-headcount denominator: incidents � active employees � 100.")

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

        weekday_reason_rows = _read_rows(
            sql_weekday_reason,
            (*emp_ids, window_start.isoformat(), window_end.isoformat(), dow),
        )
        top_reason_day = (weekday_reason_rows[0].get("reason") if weekday_reason_rows else None) or "�"

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
        emp_rows = _read_rows(
            sql_weekday_employees,
            (*emp_ids, window_start.isoformat(), window_end.isoformat(), sel_dow),
        )
        if emp_rows:
            st.markdown(f"**Employees pointed on {sel_label}s** ({window_start.strftime('%b %d')} � {window_end.strftime('%b %d, %Y')})")
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
    st.markdown(f"� Worst weekday ({metric_choice.lower()}): **{worst_label}** � **{worst_value_txt}**")

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
        st.markdown(f"� Biggest change vs prior matching window: **{dow_labels[ch_dow]}** � **{pct_txt}**")

    reason_rows = _read_rows(
        sql_weekday_reason,
        (*emp_ids, window_start.isoformat(), window_end.isoformat(), worst_dow),
    )
    top_reason = (reason_rows[0].get("reason") if reason_rows else None) or "�"
    if top_reason != "�":
        st.markdown(f"� Most common reason on {worst_label}: **{top_reason}**")



# ── PTO Usage Analytics ────────────────────────────────────────────────────────
_PTO_PALETTE = [
    "#00d4ff", "#7b61ff", "#00e5a0", "#ff6b6b", "#ffa94d",
    "#a9e34b", "#f06595", "#74c0fc", "#e599f7", "#63e6be",
]

# Fixed colors for canonical PTO types — override palette-assigned colors
_PTO_TYPE_COLORS = {
    "Vacation": "#00d4ff",  # light blue
    "Personal": "#7b61ff",  # purple
    "Absence":  "#ff6b6b",  # red
    "Other":    "#6b7280",  # dark gray
}

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
    sub_html = (
        f"<div style='font-size:.75rem;color:#6b8cba;margin-top:.2rem'>{_html_inline(sub)}</div>"
        if sub
        else ""
    )
    st.markdown(
        f"<div style='background:#0d1b2e;border:1px solid #1a3a5c;border-radius:10px;"
        f"padding:1rem 1.25rem;text-align:center'>"
        f"<div style='font-size:.78rem;color:#4a7fa5;text-transform:uppercase;letter-spacing:.08em'>{_html_inline(label)}</div>"
        f"<div style='font-size:1.8rem;font-weight:700;color:#e8f4fd;line-height:1.2;margin-top:.3rem'>{_html_inline(value)}</div>"
        f"{sub_html}</div>",
        unsafe_allow_html=True,
    )


def _weekday_date_range(start_val, end_val):
    """Inclusive weekday-only date range (Mon-Fri) for a PTO interval."""
    if pd.isna(start_val) or pd.isna(end_val):
        return []
    start_ts = pd.Timestamp(start_val).normalize()
    end_ts = pd.Timestamp(end_val).normalize()
    if end_ts < start_ts:
        start_ts, end_ts = end_ts, start_ts
    return pd.bdate_range(start=start_ts, end=end_ts)


def pto_page(conn, building: str) -> None:
    page_heading("PTO Usage Analytics", "Upload a CSV export to analyze PTO patterns by type, building, and employee.")

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

    # ── Load persisted PTO data from DB into session state if not already loaded ──
    def _set_session_pto_df(rows: list[dict]) -> bool:
        if not rows:
            return False
        _df = pd.DataFrame([dict(r) for r in rows])
        _df["start_date"] = pd.to_datetime(_df["start_date"], errors="coerce")
        _df["end_date"] = pd.to_datetime(_df["end_date"], errors="coerce")
        _df["hours"] = pd.to_numeric(_df["hours"], errors="coerce").fillna(0)
        _df["building"] = _df["building"].astype(str).str.strip()
        _df["pto_type"] = _df["pto_type"].astype(str).str.strip()
        _df["employee"] = _df["last_name"].str.strip() + ", " + _df["first_name"].str.strip()
        _df["days"] = (_df["hours"] / 8).round(2)
        st.session_state["pto_df"] = _df
        return True

    if "pto_df" not in st.session_state:
        try:
            _set_session_pto_df(repo.load_pto_data(conn))
        except Exception:
            pass  # No persisted data or schema not yet migrated

    # ── CSV upload ──────────────────────────────────────────────────────────
    with st.expander("Upload PTO Data", expanded="pto_df" not in st.session_state):
        st.markdown(
            "Upload a completed template to upload employee PTO data and see trends and analytics."
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
                raw = pd.read_csv(uploaded, encoding="utf-8-sig")
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
                        try:
                            with db.tx(conn):
                                stats = repo.save_pto_data(conn, raw.to_dict("records"))
                            _set_session_pto_df(repo.load_pto_data(conn))
                            st.session_state.pop("pto_type_toggles", None)
                            st.success(
                                f"Imported {stats['inserted']:,} new PTO record(s), skipped {stats['duplicate']:,} exact duplicate(s). "
                                f"Total stored: {stats['total']:,}."
                            )
                        except Exception as _save_err:
                            st.warning(f"PTO data parsed but could not be saved to database: {_save_err}")
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
                        try:
                            with db.tx(conn):
                                stats = repo.save_pto_data(conn, raw.to_dict("records"))
                            _set_session_pto_df(repo.load_pto_data(conn))
                            st.session_state.pop("pto_type_toggles", None)
                            st.success(
                                f"Imported {stats['inserted']:,} new PTO record(s), skipped {stats['duplicate']:,} exact duplicate(s). "
                                f"Total stored: {stats['total']:,} (legacy format upload)."
                            )
                        except Exception as _save_err:
                            st.warning(f"PTO data parsed but could not be saved to database: {_save_err}")
                else:
                    st.error("CSV must contain either `start_date`/`end_date` columns or a `date` column.")
            except Exception as exc:
                st.error(f"Could not parse CSV: {exc}")

    if "pto_df" not in st.session_state:
        st.info("Upload a PTO CSV above to begin analysis.")
        return

    df_all: pd.DataFrame = st.session_state["pto_df"].copy()

    # ── 30-day PTO utilization for the At a Glance bar ───────────────────────
    _now = date.today()
    _since_30 = pd.Timestamp(_now - timedelta(days=30))
    _df_30 = df_all[
        (df_all["start_date"] >= _since_30) | (df_all["end_date"] >= _since_30)
    ]
    if building != "All":
        _scope_count = sum(1 for e in active_db if (e.get("location") or e.get("Location") or "") == building)
        _df_30 = _df_30[_df_30["building"] == building] if "building" in _df_30.columns else _df_30
    else:
        _scope_count = len(active_db)
    _emps_30 = _df_30["employee"].nunique() if not _df_30.empty else 0
    _util_30 = (_emps_30 / max(_scope_count, 1)) * 100.0

    render_hr_live_monitor(
        points_24h=0,
        points_7d=0,
        rolloffs_due_7d=0,
        perfect_due_7d=0,
        label="At a glance — PTO (Last 30 Days)",
        pto_utilization_pct=_util_30,
    )

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
    section_header("Summary")
    k1, k2, k3, k4 = st.columns(4)
    total_hours = df["hours"].sum()
    # Count distinct weekday dates (Mon-Fri) where ANY employee had PTO.
    # Expand every record's start_date..end_date into business days,
    # union across all employees, then count unique dates.
    _pto_date_set: set = set()
    for _sd, _ed in zip(df["start_date"], df["end_date"]):
        for _d in _weekday_date_range(_sd, _ed):
            _pto_date_set.add(pd.Timestamp(_d).normalize())
    total_dates_impacted = len(_pto_date_set)
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
        _pto_metric("Days Impacted", f"{total_dates_impacted:,}", f"{total_hours:,.0f} total hours")
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
    type_colors = {t: _PTO_TYPE_COLORS.get(t, _PTO_PALETTE[i % len(_PTO_PALETTE)]) for i, t in enumerate(type_totals.index)}

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
        section_header("PTO by Type")
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
            # Required: makes single clicks on pie slices fire selection events
            clickmode="event+select",
        )
        donut_event = st.plotly_chart(
            donut_fig,
            use_container_width=True,
            on_select="rerun",
            key="pto_donut",
        )

    with trend_col:
        section_header("Monthly PTO Trend (hours)")
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
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#4a7fa5")),
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

            # Aggregate per employee + PTO type:
            #   Hours Used   = sum of all hours for that employee+type
            #   Days Impacted = unique weekdays touched by PTO ranges (Mon-Fri only)
            hours_agg = (
                drill_src.groupby(["employee", "pto_type", "building"])["hours"]
                .sum()
                .reset_index(name="hours_used")
            )
            days_src = drill_src[["employee", "pto_type", "building", "start_date", "end_date"]].copy()
            days_src["impact_date"] = days_src.apply(
                lambda r: _weekday_date_range(r["start_date"], r["end_date"]),
                axis=1,
            )
            days_src = days_src.explode("impact_date")
            days_agg = (
                days_src.groupby(["employee", "pto_type", "building"])["impact_date"]
                .nunique()
                .reset_index(name="days_impacted")
            )

            drill = (
                hours_agg.merge(days_agg, on=["employee", "pto_type", "building"], how="left")
                .fillna({"days_impacted": 0})
                .sort_values("hours_used", ascending=False)
                .rename(columns={
                    "employee":      "Employee",
                    "pto_type":      "PTO Type",
                    "building":      "Building",
                    "hours_used":    "Hours Used",
                    "days_impacted": "Days Impacted",
                })
            )
            drill["Hours Used"] = drill["Hours Used"].round(1)
            drill["Days Impacted"] = drill["Days Impacted"].astype(int)

            col_order = ["Employee", "PTO Type", "Hours Used", "Days Impacted", "Building"]
            st.dataframe(drill[col_order], use_container_width=True, hide_index=True)

    # ── Building comparison ─────────────────────────────────────────────────
    divider()
    bc1, bc2 = st.columns(2)

    with bc1:
        section_header("PTO Hours by Location")
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
        section_header("Day of the Week PTO Trends")
        dow_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
        df_dow = df.copy()
        df_dow["dow"] = df_dow["start_date"].dt.dayofweek
        df_dow["dow_label"] = df_dow["dow"].map(dow_map)
        dow_order = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        _DOW_FOCUS = {"Personal", "Vacation", "Absence"}
        _DOW_COLORS = {"Vacation": "#00d4ff", "Personal": "#7b61ff", "Absence": "#ff6b6b", "Other": "#6b7280"}
        df_dow_filtered = df_dow[df_dow["dow_label"].isin(dow_order)].copy()
        df_dow_filtered["dow_category"] = df_dow_filtered["pto_type"].apply(
            lambda t: t if t in _DOW_FOCUS else "Other"
        )
        dow_pivot = (
            df_dow_filtered
            .groupby(["dow_label", "dow_category"])["hours"]
            .sum()
            .reset_index()
        )
        dow_cat_order = ["Vacation", "Personal", "Absence", "Other"]
        dow_cat_order = [c for c in dow_cat_order if c in dow_pivot["dow_category"].unique()]
        dow_traces = []
        for pt in dow_cat_order:
            subset = (
                dow_pivot[dow_pivot["dow_category"] == pt]
                .set_index("dow_label")
                .reindex(dow_order)["hours"]
                .fillna(0)
            )
            dow_traces.append(go.Bar(
                name=pt,
                x=dow_order,
                y=subset.values,
                marker=dict(color=_DOW_COLORS.get(pt, "#7b61ff"), line=dict(color="#060d1f", width=1)),
                hovertemplate=f"<b>%{{x}}</b> — {pt}: %{{y:.0f}} hrs<extra></extra>",
            ))
        dow_fig = go.Figure(data=dow_traces)
        dow_fig.update_layout(
            barmode="stack",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#c8dff0", family="SF Mono, Fira Code, monospace"),
            xaxis=dict(showgrid=False, color="#4a7fa5"),
            yaxis=dict(showgrid=True, gridcolor="#0d1b2e", color="#4a7fa5", title="Hours"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10, color="#4a7fa5")),
            margin=dict(t=30, b=10, l=10, r=10),
        )
        st.plotly_chart(dow_fig, use_container_width=True, key="pto_dow_bar")

    # ── Top PTO users ───────────────────────────────────────────────────────
    divider()
    tu1, tu2 = st.columns([3, 2])

    with tu1:
        section_header("Top PTO Users")
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
        section_header("Zero PTO — No Usage Recorded")
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
    section_header("Planned vs Unplanned PTO")

    _PLANNED_TYPES   = {"vacation", "floating holiday", "reward pto"}
    _UNPLANNED_TYPES = {"personal", "absence", "absence (sick)", "absence (covid)", "long term sick leave"}
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
            _CAT_CLR = {"Planned": "#2684F0", "Unplanned": "#26F0DA"}
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
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#4a7fa5")),
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
    section_header("PTO Concentration \u2014 Who's Driving Usage?")

    emp_hrs = df.groupby("employee")["hours"].sum().sort_values(ascending=False).reset_index()
    n_total_emp = len(emp_hrs)
    top10_n = max(1, round(n_total_emp * 0.10))
    total_emp_hrs = emp_hrs["hours"].sum()
    top10_pct_hrs = emp_hrs.head(top10_n)["hours"].sum() / total_emp_hrs * 100 if total_emp_hrs else 0
    concentration_label = "High" if top10_pct_hrs > 50 else ("Moderate" if top10_pct_hrs > 33 else "Even")

    cn1, cn2, cn3 = st.columns(3)
    with cn1:
        _pto_metric("Employees using PTO", str(n_total_emp), "in selected period")
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

            if {"first_name", "last_name"}.issubset(_grp_df.columns):
                _grp_df = _grp_df.copy()
                _grp_df["First Name"] = _grp_df["first_name"].astype(str).str.strip()
                _grp_df["Last Name"] = _grp_df["last_name"].astype(str).str.strip()
            else:
                _grp_df = _grp_df.copy()
                _name_split = _grp_df["employee"].astype(str).str.split(",", n=1, expand=True)
                _grp_df["Last Name"] = _name_split[0].fillna("").str.strip()
                _grp_df["First Name"] = _name_split[1].fillna("").str.strip()

            _hours_agg = (
                _grp_df.groupby(["First Name", "Last Name", "pto_type"], as_index=False)["hours"]
                .sum()
                .rename(columns={"pto_type": "PTO Type", "hours": "Total Hours"})
            )

            _days_df = _grp_df[["First Name", "Last Name", "pto_type", "start_date", "end_date"]].copy()
            _days_df["impact_date"] = _days_df.apply(
                lambda r: _weekday_date_range(r["start_date"], r["end_date"]),
                axis=1,
            )
            _days_df = _days_df.explode("impact_date")
            _days_agg = (
                _days_df.groupby(["First Name", "Last Name", "pto_type"])["impact_date"]
                .nunique()
                .reset_index(name="Days Impacted")
                .rename(columns={"pto_type": "PTO Type"})
            )

            _grp_agg = _hours_agg.merge(
                _days_agg,
                on=["First Name", "Last Name", "PTO Type"],
                how="left",
            )
            _grp_agg["Total Hours"] = _grp_agg["Total Hours"].round(1)
            _grp_agg["Days Impacted"] = _grp_agg["Days Impacted"].fillna(0).astype(int)
            _grp_agg = _grp_agg.sort_values(
                ["Total Hours", "Last Name", "First Name", "PTO Type"],
                ascending=[False, True, True, True],
            )
            divider()
            section_label(f"PTO Breakdown - {bar_label}")
            st.dataframe(
                _grp_agg[["First Name", "Last Name", "PTO Type", "Total Hours", "Days Impacted"]],
                use_container_width=True,
                hide_index=True,
            )

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
    section_header("Burnout & Retention Risk")

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
        section_label("No PTO Usage — Burnout Risk")
        if no_pto:
            st.dataframe(pd.DataFrame({"Employee": no_pto}), use_container_width=True, hide_index=True)
        else:
            info_box("All active employees have PTO recorded. ✓")
    with brr:
        section_label(f"Bottom 10% of Users({low10_n} employees)")
        if not low_users.empty:
            low_users["Days"] = (low_users["hours"] / 8).round(1)
            low_users = low_users.rename(columns={"employee": "Employee", "hours": "Hours"})
            low_users["Hours"] = low_users["Hours"].round(1)
            st.dataframe(low_users[["Employee", "Hours", "Days"]], use_container_width=True, hide_index=True)
        else:
            info_box("Not enough data for bottom 10% analysis.")

    # ── Module 4: Pace & Seasonality ────────────────────────────────────────
    divider()
    section_header("PTO Pace & Seasonality")

    from datetime import timedelta as _td
    period_days = max(1, (date_end - date_start).days + 1)
    total_days = total_hours / 8
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
    def _clear_pto_data() -> None:
        st.session_state.pop("pto_df", None)
        st.session_state.pop("pto_type_toggles", None)
        try:
            with db.tx(conn):
                repo.clear_pto_data(conn)
        except Exception:
            pass
        st.rerun()
    if st.button("Clear PTO Data", key="pto_clear_btn_export"):
        _clear_pto_data()

    # ── Clear data ──────────────────────────────────────────────────────────
    divider()
    st.markdown(
        "<p style='color:#6a8ab8;font-size:.8rem;margin-bottom:.4rem'>"
        "Clear the loaded CSV data to start over with a new file.</p>",
        unsafe_allow_html=True,
    )
    if st.button("Clear PTO Data", key="pto_clear_btn_footer"):
        _clear_pto_data()

# ── Employees ─────────────────────────────────────────────────────────────────
def employees_page(conn, building: str) -> None:
    page_heading("Employees", "Look up employees and review current attendance status.")

    rows = load_employees(conn, building=building)

    if not rows:
        info_box("No matching employees found.")
        return

    # Detail view
    opts = [
        (int(r["employee_id"]), f"#{r['employee_id']} - {r['last_name']}, {r['first_name']}")
        for r in rows
    ]
    selected = st.selectbox("View details for", opts, format_func=lambda x: x[1], label_visibility="collapsed")
    emp_id = selected[0]
    emp = dict(repo.get_employee(conn, emp_id))

    pts = float(emp.get("point_total") or 0)
    loc = emp.get("Location") or emp.get("location") or "-"
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
        f"Employee #{emp_id} &nbsp;&middot;&nbsp; {loc}</div></div>"
        f"<div style='display:flex;gap:.4rem;align-items:center'>{pt_badge(pts)} {active_badge}</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Point Total", f"{pts:.1f}")
    c2.metric("Next Roll-off", fmt_date(emp.get("rolloff_date")))
    c3.metric("Perfect Attendance", fmt_date(emp.get("perfect_attendance")))
    c4.metric("Last Point Entry", fmt_date(emp.get("last_point_date")))

    # --- Override Point Total ---
    with st.expander("Override Point Total"):
        st.caption("Manually set the point total. Use this to correct totals affected by prior calculation errors. "
                   "This inserts an adjustment entry in the point history.")
        ov_col1, ov_col2 = st.columns([1, 2])
        with ov_col1:
            new_total = st.number_input("New Point Total", min_value=0.0, step=0.5, value=pts, key=f"override_pts_{emp_id}")
        with ov_col2:
            override_note = st.text_input("Reason for override", value="Manual correction — prior roll-off calculation error", key=f"override_note_{emp_id}")
        if st.button("Apply Override", key=f"override_btn_{emp_id}"):
            adjustment = round(new_total - pts, 3)
            if abs(adjustment) < 0.001:
                st.warning("New total is the same as the current total.")
            else:
                try:
                    with db.tx(conn):
                        repo.insert_points_history(
                            conn,
                            employee_id=emp_id,
                            point_date=date.today(),
                            points=adjustment,
                            reason="Manual Adjustment",
                            note=override_note or "Manual point total override",
                            flag_code="MANUAL",
                        )
                        services.recalculate_employee_dates(conn, emp_id)
                    conn.commit()
                    clear_read_caches()
                    st.success(f"Point total adjusted by {adjustment:+.1f} → new total: {new_total:.1f}")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

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

    notice = st.session_state.pop("ledger_notice", None)
    if notice:
        st.success(notice)

    employees = load_employees(conn, building=building)
    if not employees:
        warn_box("No active employees found for this building filter.")
        return

    opts = [
        (int(e["employee_id"]), f"#{e['employee_id']} - {e['last_name']}, {e['first_name']}")
        for e in employees
    ]

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

    ledger_date_key = f"ledger_date_str_{emp_id}"
    ledger_points_key = f"ledger_points_{emp_id}"
    ledger_reason_key = f"ledger_reason_{emp_id}"
    ledger_note_key = f"ledger_note_{emp_id}"
    ledger_flag_key = f"ledger_flag_{emp_id}"

    def focus_ledger_date_field() -> None:
        components.html(
            """<script>
            const rootDoc = (window.parent && window.parent.document) ? window.parent.document : document;
            const selectors = [
              'input[aria-label="Date (MM/DD/YYYY)"]',
              'input[placeholder="MM/DD/YYYY"]',
              'div[data-testid="stTextInput"] input'
            ];
            const sel = () => {
              for (const s of selectors) {
                const el = rootDoc.querySelector(s);
                if (el && !el.disabled) return el;
              }
              return null;
            };
            const tryFocus = () => {
              const el = sel();
              if (!el) return false;
              el.focus({ preventScroll: true });
              if (typeof el.select === "function") el.select();
              return true;
            };
            let tries = 0;
            if (!tryFocus()) {
              const t = setInterval(() => {
                tries += 1;
                if (tryFocus() || tries > 40) clearInterval(t);
              }, 75);
            }
            </script>""",
            height=0,
        )

    def set_ledger_notice(message: str) -> None:
        st.session_state["ledger_notice"] = message

    def parse_mdy(value: str) -> date:
        return datetime.strptime(value.strip(), "%m/%d/%Y").date()

    def format_mdy(value: str | None) -> str:
        if not value:
            return date.today().strftime("%m/%d/%Y")
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime("%m/%d/%Y")

    prev_focus_emp = st.session_state.get("_focus_emp_id")
    if prev_focus_emp != emp_id:
        st.session_state["_focus_emp_id"] = emp_id
        focus_ledger_date_field()

    emp = dict(repo.get_employee(conn, emp_id))
    pts = float(emp.get("point_total") or 0)

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
            date_str = st.text_input(
                "Date (MM/DD/YYYY)",
                value=date.today().strftime("%m/%d/%Y"),
                placeholder="MM/DD/YYYY",
                key=ledger_date_key,
            )

            points = st.selectbox(
                "Points",
                [0.5, 1.0, 1.5],
                index=0,
                key=ledger_points_key,
            )

            reason = st.selectbox(
                "Reason",
                REASON_OPTIONS,
                index=0,
                key=ledger_reason_key,
            )

            note = st.text_input("Note (optional)", key=ledger_note_key)
            flag_code = st.text_input("Flag code (optional)", key=ledger_flag_key)

            submit = st.form_submit_button("Add Point", use_container_width=True)

        if submit:
            try:
                p_date = parse_mdy(date_str)
            except Exception:
                st.error("Invalid date. Use MM/DD/YYYY (example: 03/02/2026).")
            else:
                if p_date > date.today():
                    st.error("Date cannot be in the future.")
                else:
                    try:
                        preview = services.preview_add_point(emp_id, p_date, float(points), reason, note)
                        services.add_point(conn, preview, flag_code=(flag_code or "").strip() or None)
                        clear_read_caches()
                        set_ledger_notice(f"Added {float(points):.1f} pts on {fmt_date(p_date)}.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

        section_label("Repair Totals")
        st.caption("Employee totals are calculated from transaction history. Recalculate after correcting a bad roll-off or manual entry.")
        repair_col1, repair_col2 = st.columns(2)
        with repair_col1:
            if st.button("Recalculate Employee", key=f"repair_emp_{emp_id}", use_container_width=True):
                try:
                    with db.tx(conn):
                        services.recalculate_employee_dates(conn, emp_id)
                    clear_read_caches()
                    set_ledger_notice(f"Recalculated point totals for employee #{emp_id}.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        with repair_col2:
            if st.button("Recalculate Everyone", key="repair_all_employees", use_container_width=True):
                try:
                    services.recalculate_all_employee_dates(conn)
                    clear_read_caches()
                    set_ledger_notice("Recalculated point totals for all employees.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with col_hist:
        section_label("Transaction History (all events)")
        history_limit_key = f"ledger_history_limit_{emp_id}"
        current_history_limit = int(st.session_state.get(history_limit_key, LEDGER_HISTORY_DEFAULT_LIMIT))
        hist = [dict(r) for r in repo.get_points_history(conn, emp_id, limit=current_history_limit)]
        if hist:
            df_h = pd.DataFrame(hist)[["id", "point_date", "points", "reason", "note", "point_total"]]
            df_h["point_date"] = df_h["point_date"].apply(fmt_date)
            df_h["points"] = df_h["points"].apply(lambda v: f"{float(v or 0):.1f}")
            df_h["point_total"] = df_h["point_total"].apply(lambda v: f"{float(v or 0):.1f}")
            df_h.columns = ["ID", "Date", "Pts", "Reason", "Note", "Running Total"]
            st.dataframe(df_h.drop(columns=["ID"]), use_container_width=True, hide_index=True, height=430)

            if len(hist) >= current_history_limit and current_history_limit < LEDGER_HISTORY_FULL_LIMIT:
                if st.button("Load Full History", key=f"load_full_history_{emp_id}"):
                    st.session_state[history_limit_key] = LEDGER_HISTORY_FULL_LIMIT
                    st.rerun()

            if st.button("Undo Last Entry", key="undo_last"):
                try:
                    services.delete_point_history_entry(conn, point_id=int(df_h.iloc[0]["ID"]), employee_id=emp_id)
                    clear_read_caches()
                    set_ledger_notice("Last entry removed.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

            section_label("Edit Transaction")
            entry_options = [
                (
                    int(row["id"]),
                    f"{fmt_date(row.get('point_date'))} | {float(row.get('points') or 0):+.1f} | {row.get('reason') or 'No reason'}",
                )
                for row in hist
            ]
            selected_entry = st.selectbox(
                "Select transaction",
                entry_options,
                format_func=lambda x: x[1],
                key=f"ledger_edit_entry_{emp_id}",
            )
            selected_point_id = int(selected_entry[0])
            selected_row = next(row for row in hist if int(row["id"]) == selected_point_id)

            with st.form(f"ledger_edit_form_{emp_id}_{selected_point_id}", clear_on_submit=False):
                edit_date_str = st.text_input(
                    "Date (MM/DD/YYYY)",
                    value=format_mdy(selected_row.get("point_date")),
                    key=f"ledger_edit_date_{selected_point_id}",
                )
                edit_points = st.number_input(
                    "Points",
                    value=float(selected_row.get("points") or 0.0),
                    step=0.5,
                    format="%.1f",
                    key=f"ledger_edit_points_{selected_point_id}",
                )
                edit_reason = st.text_input(
                    "Reason",
                    value=str(selected_row.get("reason") or ""),
                    key=f"ledger_edit_reason_{selected_point_id}",
                )
                edit_note = st.text_input(
                    "Note",
                    value=str(selected_row.get("note") or ""),
                    key=f"ledger_edit_note_{selected_point_id}",
                )
                edit_flag_code = st.text_input(
                    "Flag code",
                    value=str(selected_row.get("flag_code") or ""),
                    key=f"ledger_edit_flag_{selected_point_id}",
                )

                save_col, delete_col = st.columns(2)
                save_entry = save_col.form_submit_button("Save Entry", use_container_width=True)
                delete_entry = delete_col.form_submit_button("Delete Entry", use_container_width=True)

            st.caption(f"Running total after this entry: {float(selected_row.get('point_total') or 0):.1f} pts")

            if save_entry:
                try:
                    edit_date = parse_mdy(edit_date_str)
                except Exception:
                    st.error("Invalid date. Use MM/DD/YYYY (example: 03/02/2026).")
                else:
                    if edit_date > date.today():
                        st.error("Date cannot be in the future.")
                    else:
                        try:
                            services.update_point_history_entry(
                                conn,
                                point_id=selected_point_id,
                                employee_id=emp_id,
                                point_date=edit_date,
                                points=float(edit_points),
                                reason=edit_reason,
                                note=edit_note,
                                flag_code=(edit_flag_code or "").strip() or None,
                            )
                            clear_read_caches()
                            set_ledger_notice(f"Updated transaction #{selected_point_id}.")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

            if delete_entry:
                try:
                    services.delete_point_history_entry(conn, point_id=selected_point_id, employee_id=emp_id)
                    clear_read_caches()
                    set_ledger_notice(f"Deleted transaction #{selected_point_id}.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        else:
            info_box("No history entries for this employee yet.")



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
                emp_id     = st.number_input("Employee #", min_value=1, step=1)
                first      = st.text_input("First Name")
                last       = st.text_input("Last Name")
                start_date = st.date_input("Hire / Start Date", value=date.today())
                location   = st.selectbox("Building", BLDG_OPTS)
                added      = st.form_submit_button("Add Employee", use_container_width=True)

            if added:
                if not first.strip() or not last.strip():
                    st.error("First and last name are required.")
                else:
                    try:
                        services.create_employee(
                            conn,
                            int(emp_id),
                            last.strip(),
                            first.strip(),
                            start_date,
                            location or None,
                        )
                        conn.commit()
                        clear_read_caches()
                        st.success(f"Employee #{int(emp_id)} — {last}, {first} added.")
                    except Exception as exc:
                        st.error(str(exc))

        with col_info:
            st.markdown("<div style='height:2.5rem'></div>", unsafe_allow_html=True)
            st.markdown(
                "<div class='info-box'><b>New employee checklist</b><br>"
                "&bull; Employee # must be unique across all locations<br>"
                "&bull; Building can be set now or updated later via the Edit tab<br>"
                "&bull; All policy dates are blank until the first point entry is posted</div>",
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
                f"#{r['employee_id']} - {r['last_name']}, {r['first_name']}"
                + (" (inactive)" if not r.get("is_active", 1) else ""),
            )
            for r in all_rows
        ]
        sel = st.selectbox("Select employee", opts, format_func=lambda x: x[1], label_visibility="collapsed")
        emp = dict(repo.get_employee(conn, sel[0]))
        loc_val = emp.get("Location") or emp.get("location") or ""
        loc_idx = BLDG_OPTS.index(loc_val) if loc_val in BLDG_OPTS else 0
        start_raw = str(emp.get("start_date") or "")[:10]
        rolloff_raw = str(emp.get("rolloff_date") or "")[:10]
        perfect_raw = str(emp.get("perfect_attendance") or "")[:10]
        try:
            start_val = date.fromisoformat(start_raw) if start_raw else date.today()
        except ValueError:
            start_val = date.today()

        col_edit, col_del = st.columns([1, 1], gap="large")

        with col_edit:
            section_label("Edit Details")
            with st.form("edit_employee"):
                first_e = st.text_input("First Name", value=emp.get("first_name") or "")
                last_e  = st.text_input("Last Name",  value=emp.get("last_name") or "")
                start_e = st.date_input("Hire / Start Date", value=start_val)
                bldg_e  = st.selectbox("Building", BLDG_OPTS, index=loc_idx)
                act_e   = st.checkbox("Active", value=bool(emp.get("is_active", 1)))
                rolloff_e = st.text_input(
                    "2-Month Roll-off Date (MM/DD/YYYY)",
                    value=(datetime.strptime(rolloff_raw, "%Y-%m-%d").strftime("%m/%d/%Y") if rolloff_raw else ""),
                )
                perfect_e = st.text_input(
                    "Perfect Attendance Date (MM/DD/YYYY)",
                    value=(datetime.strptime(perfect_raw, "%Y-%m-%d").strftime("%m/%d/%Y") if perfect_raw else ""),
                )
                st.caption("Leave either date blank to clear it.")
                saved   = st.form_submit_button("Save Changes", use_container_width=True)

            if saved:
                try:
                    rolloff_clean = (rolloff_e or "").strip()
                    perfect_clean = (perfect_e or "").strip()
                    rolloff_new_iso = datetime.strptime(rolloff_clean, "%m/%d/%Y").date().isoformat() if rolloff_clean else None
                    perfect_new_iso = datetime.strptime(perfect_clean, "%m/%d/%Y").date().isoformat() if perfect_clean else None
                    manual_dates_changed = (
                        (rolloff_new_iso != (rolloff_raw or None))
                        or (perfect_new_iso != (perfect_raw or None))
                    )
                    exec_sql(
                        conn,
                        'UPDATE employees SET first_name=?, last_name=?, start_date=?, "Location"=?, is_active=?, rolloff_date=?, perfect_attendance=? WHERE employee_id=?',
                        (
                            first_e.strip(),
                            last_e.strip(),
                            start_e.isoformat(),
                            bldg_e or None,
                            1 if act_e else 0,
                            rolloff_new_iso,
                            perfect_new_iso,
                            sel[0],
                        ),
                    )
                    if (start_raw != start_e.isoformat()) and not manual_dates_changed:
                        exec_sql(conn, 'UPDATE employees SET perfect_attendance=NULL WHERE employee_id=?', (sel[0],))
                    if not manual_dates_changed:
                        services.recalculate_employee_dates(conn, sel[0])
                    conn.commit()
                    clear_read_caches()
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
                        clear_read_caches()
                        st.success(f"Employee #{sel[0]} deleted.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))


# ── Exports & Forecasts ───────────────────────────────────────────────────────
EXPORT_LABELS = {
    "employee audit":             "Employee Audit",
    "30-day point history":        "30-Day Point History",
    "upcoming 2-month roll-offs":  "Upcoming 2-Month Roll-offs",
    "upcoming perfect attendance": "Upcoming Perfect Attendance",
    "pending ytd roll-offs":       "Pending YTD Roll-offs",
    "applied ytd roll-off history": "Applied YTD Roll-off History",
}


def run_export_query(conn, export_type: str, building: str, start_date: date, end_date: date) -> pd.DataFrame:
    pg = is_pg(conn)

    if export_type == "employee audit":
        if pg:
            sql = """SELECT employee_id   AS "Employee #",
                            last_name     AS "Last Name",
                            first_name    AS "First Name",
                            COALESCE(point_total, 0.0) AS "Point Total",
                            rolloff_date  AS "2 Month Roll Off Date",
                            perfect_attendance AS "Perfect Attendance Date"
                       FROM employees
                      WHERE is_active = 1"""
        else:
            sql = """SELECT employee_id   AS "Employee #",
                            last_name     AS "Last Name",
                            first_name    AS "First Name",
                            COALESCE(point_total, 0.0) AS "Point Total",
                            rolloff_date  AS "2 Month Roll Off Date",
                            perfect_attendance AS "Perfect Attendance Date"
                       FROM employees
                      WHERE is_active = 1"""
        params = []
        if building != "All":
            sql += ' AND COALESCE("Location",\'\') = ?'
            params.append(building)
        sql += " ORDER BY last_name, first_name"
        df = pd.DataFrame([dict(r) for r in fetchall(conn, sql, tuple(params))])
        return df

    elif export_type == "30-day point history":
        if pg:
            sql = """
                SELECT e.employee_id AS "Employee #",
                       e.last_name AS "Last Name",
                       e.first_name AS "First Name",
                       COALESCE(e."Location", '') AS "Location",
                       ph.id AS "_History ID",
                       ph.point_date AS "Point Date",
                       ph.points AS "Point",
                       ph.reason AS "Reason",
                       COALESCE(ph.note, '') AS "Note"
                  FROM points_history ph
                  JOIN employees e ON e.employee_id = ph.employee_id
            """
        else:
            sql = """
                SELECT e.employee_id AS "Employee #",
                       e.last_name AS "Last Name",
                       e.first_name AS "First Name",
                       COALESCE(e."Location", '') AS "Location",
                       ph.id AS "_History ID",
                       ph.point_date AS "Point Date",
                       ph.points AS "Point",
                       ph.reason AS "Reason",
                       COALESCE(ph.note, '') AS "Note"
                  FROM points_history ph
                  JOIN employees e ON e.employee_id = ph.employee_id
            """
        params = []
        if building != "All":
            sql += " WHERE COALESCE(e.\"Location\", '') = ?"
            params.append(building)
        if pg:
            sql += ' ORDER BY "Employee #", (ph.point_date::date), "_History ID"'
        else:
            sql += ' ORDER BY "Employee #", date(ph.point_date), "_History ID"'

        rows = [dict(r) for r in fetchall(conn, sql, tuple(params))]
        running_by_employee: dict[int, float] = {}
        export_rows: list[dict] = []
        start_iso = start_date.isoformat()
        end_iso = end_date.isoformat()

        for row in rows:
            employee_id = int(row["Employee #"])
            running_total = running_by_employee.get(employee_id, 0.0)
            running_total = max(0.0, round(running_total + float(row.get("Point") or 0.0), 3))
            running_by_employee[employee_id] = running_total

            point_day = str(row.get("Point Date") or "")[:10]
            if start_iso <= point_day <= end_iso:
                row["Point Total"] = round(running_total, 1)
                row.pop("_History ID", None)
                export_rows.append(row)

        df = pd.DataFrame(export_rows)
        if not df.empty:
            if "Point" in df.columns:
                df["Point"] = pd.to_numeric(df["Point"], errors="coerce").map(
                    lambda v: f"{v:.1f}" if pd.notna(v) else ""
                )
            if "Point Total" in df.columns:
                df["Point Total"] = pd.to_numeric(df["Point Total"], errors="coerce").map(
                    lambda v: f"{v:.1f}" if pd.notna(v) else ""
                )
        return df

    elif export_type == "upcoming 2-month roll-offs":
        if pg:
            sql = """SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS location,
                            point_total, rolloff_date
                       FROM employees WHERE rolloff_date IS NOT NULL
                         AND COALESCE(point_total, 0.0) >= 0.5
                         AND (rolloff_date::date) BETWEEN (%s::date) AND (%s::date)"""
        else:
            sql = """SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS location,
                            point_total, rolloff_date
                       FROM employees WHERE rolloff_date IS NOT NULL
                         AND COALESCE(point_total, 0.0) >= 0.5
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

    elif export_type == "pending ytd roll-offs":
        # Show pending YTD roll-offs for the current month (not yet applied)
        pending = services.preview_ytd_rolloffs(conn, run_date=date.today(), exclude_applied=True)
        rows_out = []
        for employee_id, net_points, roll_date, label in pending:
            emp = repo.get_employee(conn, int(employee_id))
            if not emp:
                continue
            emp = dict(emp)
            loc = (emp.get("Location") or "")
            if building != "All" and loc != building:
                continue
            current_total = round(float(emp.get("point_total", 0) or 0), 1)
            if current_total <= 0.0:
                continue
            rows_out.append({
                "Employee ID": int(employee_id),
                "First Name": emp.get("first_name", ""),
                "Last Name": emp.get("last_name", ""),
                "Point Total": round(float(emp.get("point_total", 0) or 0), 1),
                "Points": round(float(net_points), 1),
                "Point Date": roll_date.isoformat(),
                "Note": "YTD Roll Off",
                "Notes": "",
            })
        if rows_out:
            return pd.DataFrame(rows_out)
        return pd.DataFrame(columns=["Employee ID", "First Name", "Last Name", "Point Total", "Points", "Point Date", "Note", "Notes"])

    else:  # applied ytd roll-off history
        year_start = date(date.today().year, 1, 1)
        if pg:
            sql = """SELECT e.employee_id AS "Employee ID",
                            e.first_name  AS "First Name",
                            e.last_name   AS "Last Name",
                            COALESCE(e.point_total, 0.0) AS "Point Total",
                            p.points      AS "Points",
                            p.point_date  AS "Point Date",
                            'YTD Roll Off' AS "Note",
                            COALESCE(p.note,'') AS "Notes"
                       FROM points_history p JOIN employees e ON e.employee_id=p.employee_id
                      WHERE p.reason='YTD Roll-Off' AND p.flag_code='AUTO'
                        AND (p.point_date::date) >= (%s::date)"""
        else:
            sql = """SELECT e.employee_id AS "Employee ID",
                            e.first_name  AS "First Name",
                            e.last_name   AS "Last Name",
                            COALESCE(e.point_total, 0.0) AS "Point Total",
                            p.points      AS "Points",
                            p.point_date  AS "Point Date",
                            'YTD Roll Off' AS "Note",
                            COALESCE(p.note,'') AS "Notes"
                       FROM points_history p JOIN employees e ON e.employee_id=p.employee_id
                      WHERE p.reason='YTD Roll-Off' AND p.flag_code='AUTO'
                        AND date(p.point_date) >= date(?)"""
        params = [year_start.isoformat()]

    if building != "All":
        e_ref = 'e."Location"' if " JOIN employees e" in sql else '"Location"'
        sql += f" AND COALESCE({e_ref},'') = ?"
        params.append(building)

    sql += " ORDER BY e.last_name, e.first_name" if export_type == "applied ytd roll-off history" else " ORDER BY last_name, first_name"
    df = pd.DataFrame([dict(r) for r in fetchall(conn, sql, tuple(params))])

    if export_type == "30-day point history" and not df.empty:
        if "Point" in df.columns:
            df["Point"] = pd.to_numeric(df["Point"], errors="coerce").map(
                lambda v: f"{v:.1f}" if pd.notna(v) else ""
            )
        if "Point Total" in df.columns:
            df["Point Total"] = pd.to_numeric(df["Point Total"], errors="coerce").map(
                lambda v: f"{v:.1f}" if pd.notna(v) else ""
            )

    return df


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
def _build_full_backup_excel(conn) -> bytes:
    """Build an Excel workbook with Employees and Point History sheets."""
    import io
    buf = io.BytesIO()
    emp_df = pd.DataFrame([dict(r) for r in fetchall(conn,
        'SELECT employee_id, last_name, first_name, COALESCE("Location",\'\') AS "Location", '
        'start_date, point_total, last_point_date, rolloff_date, perfect_attendance, '
        'point_warning_date, is_active FROM employees ORDER BY last_name, first_name'
    )])
    hist_df = pd.DataFrame([dict(r) for r in fetchall(conn,
        'SELECT id, employee_id, point_date, points, reason, note, flag_code '
        'FROM points_history ORDER BY employee_id, point_date, id'
    )])
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        emp_df.to_excel(writer, sheet_name="Employees", index=False)
        hist_df.to_excel(writer, sheet_name="Point History", index=False)
    return buf.getvalue()


def system_updates_page(conn) -> None:
    page_heading(
        "System Updates",
        "Run automated maintenance jobs: 2-month roll-offs, perfect attendance advancement, and YTD roll-offs.",
    )

    if "maintenance_log" not in st.session_state:
        st.session_state["maintenance_log"] = []

    # ── Database Backup ──────────────────────────────────────────────────
    section_label("Database Backup")
    st.caption("Download a full snapshot of all employees and point history as an Excel file. "
               "Always download a backup before running bulk operations.")
    bk_col1, bk_col2 = st.columns([1, 2])
    with bk_col1:
        if st.button("Generate Backup", use_container_width=True, key="gen_backup"):
            with st.spinner("Building backup..."):
                st.session_state["_backup_bytes"] = _build_full_backup_excel(conn)
                st.session_state["_backup_downloaded"] = True
    with bk_col2:
        if st.session_state.get("_backup_bytes"):
            st.download_button(
                "Download Full Backup (Excel)",
                data=st.session_state["_backup_bytes"],
                file_name=f"atp_full_backup_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dl_backup",
            )

    divider()

    # ── Recalculate All ──────────────────────────────────────────────────
    section_label("Recalculate All Employee Totals")
    st.caption("Recomputes every employee's point total, roll-off date, and perfect attendance date "
               "from their full point history. Use this after fixing calculation bugs.")
    backup_done = st.session_state.get("_backup_downloaded", False)
    if not backup_done:
        st.markdown("<div class='warn-box'>You must generate a backup above before recalculating.</div>", unsafe_allow_html=True)
    recalc_confirm = st.checkbox("I confirm — recalculate all employee totals", disabled=not backup_done, key="recalc_confirm")
    if st.button("Recalculate All", disabled=not (backup_done and recalc_confirm), use_container_width=False, key="btn_recalc_all"):
        try:
            with st.spinner("Recalculating all employees..."):
                emp_rows = fetchall(conn, "SELECT employee_id FROM employees ORDER BY employee_id")
                count = 0
                with db.tx(conn):
                    for row in emp_rows:
                        services.recalculate_employee_dates(conn, int(row["employee_id"]))
                        count += 1
                conn.commit()
                clear_read_caches()
            st.success(f"Recalculated {count} employee(s). Point totals and dates are now recomputed from history.")
        except Exception as exc:
            st.error(str(exc))

    divider()

    # ── Bulk Employee Override ─────────────────────────────────────────
    if "bulk_override_msg" in st.session_state:
        st.success(st.session_state.pop("bulk_override_msg"))
    section_label("Bulk Employee Override")
    st.caption("Upload a CSV with corrected employee data. Required column: **Employee #**. "
               "Optional columns: **Point Total**, **2 Month Roll Off Date**, **Perfect Attendance Date**. "
               "Point adjustments are inserted as history entries; dates are set directly.")
    uploaded = st.file_uploader("Upload corrections CSV", type=["csv"], key="bulk_override_csv")
    if uploaded is not None:
        try:
            csv_df = pd.read_csv(uploaded)
            if "Employee #" not in csv_df.columns:
                st.error("CSV must contain an 'Employee #' column.")
            else:
                has_points = "Point Total" in csv_df.columns
                has_rolloff = "2 Month Roll Off Date" in csv_df.columns
                has_perfect = "Perfect Attendance Date" in csv_df.columns
                if not (has_points or has_rolloff or has_perfect):
                    st.error("CSV must contain at least one of: 'Point Total', '2 Month Roll Off Date', 'Perfect Attendance Date'.")
                else:
                    changes = []
                    for _, row in csv_df.iterrows():
                        eid = int(row["Employee #"])
                        emp = repo.get_employee(conn, eid)
                        if not emp:
                            continue
                        emp = dict(emp)
                        change = {
                            "Employee #": eid,
                            "Last Name": emp.get("last_name", ""),
                            "First Name": emp.get("first_name", ""),
                        }
                        changed = False

                        # -- Point Total --
                        if has_points:
                            val = row["Point Total"]
                            new_total = round(float(val), 1) if pd.notna(val) and str(val).strip() != "" else 0.0
                            current = round(float(emp.get("point_total", 0) or 0), 1)
                            diff = round(new_total - current, 3)
                            change["Current Points"] = current
                            change["New Points"] = new_total
                            change["Pt Adjustment"] = round(diff, 1)
                            if abs(diff) >= 0.05:
                                changed = True

                        # -- Roll-off Date --
                        if has_rolloff:
                            val = row["2 Month Roll Off Date"]
                            new_ro = None
                            if pd.notna(val) and str(val).strip() != "":
                                try:
                                    new_ro = pd.to_datetime(str(val)).date()
                                except Exception:
                                    new_ro = None
                            cur_ro_raw = emp.get("rolloff_date")
                            cur_ro = date.fromisoformat(str(cur_ro_raw)) if cur_ro_raw else None
                            change["Current Roll-off"] = str(cur_ro) if cur_ro else ""
                            change["New Roll-off"] = str(new_ro) if new_ro else ""
                            if new_ro != cur_ro:
                                changed = True

                        # -- Perfect Attendance Date --
                        if has_perfect:
                            val = row["Perfect Attendance Date"]
                            new_pa = None
                            if pd.notna(val) and str(val).strip() != "":
                                try:
                                    new_pa = pd.to_datetime(str(val)).date()
                                except Exception:
                                    new_pa = None
                            cur_pa_raw = emp.get("perfect_attendance")
                            cur_pa = date.fromisoformat(str(cur_pa_raw)) if cur_pa_raw else None
                            change["Current Perfect Att."] = str(cur_pa) if cur_pa else ""
                            change["New Perfect Att."] = str(new_pa) if new_pa else ""
                            if new_pa != cur_pa:
                                changed = True

                        if changed:
                            changes.append(change)

                    if not changes:
                        info_box("No changes needed — all values match.")
                    else:
                        # Store changes in session so they survive reruns
                        st.session_state["bulk_override_changes"] = changes
                        st.session_state["bulk_override_flags"] = {
                            "has_points": has_points, "has_rolloff": has_rolloff, "has_perfect": has_perfect,
                        }
                        chg_df = pd.DataFrame(changes)
                        st.dataframe(chg_df, use_container_width=True, hide_index=True)
                        st.markdown(f"**{len(changes)}** employee(s) will be updated.")
        except Exception as exc:
            st.error(f"Error reading CSV: {exc}")

    # --- Apply step (outside file-upload block so button survives reruns) ---
    if "bulk_override_changes" in st.session_state:
        changes = st.session_state["bulk_override_changes"]
        flags = st.session_state["bulk_override_flags"]
        bulk_confirm = st.checkbox("I confirm — apply these overrides", key="bulk_override_confirm")
        if st.button("Apply Bulk Overrides", disabled=not bulk_confirm, key="btn_bulk_override"):
            _pg = is_pg(conn)
            errors = []
            applied = 0
            for chg in changes:
                eid = int(chg["Employee #"])
                try:
                    # Point total: insert adjustment history, then force exact total
                    if flags["has_points"] and abs(chg.get("Pt Adjustment", 0)) >= 0.05:
                        sql = ("INSERT INTO points_history (employee_id, point_date, points, reason, note, flag_code) "
                               "VALUES (?, ?, ?, ?, ?, ?)")
                        params = (eid, date.today().isoformat(), float(chg["Pt Adjustment"]),
                                  "Manual Adjustment", "Bulk override — prior calculation correction", "MANUAL")
                        if _pg:
                            cur = conn.cursor()
                            cur.execute(sql.replace("?", "%s"), params)
                            cur.close()
                        else:
                            conn.execute(sql, params)
                    # Force exact point total directly
                    if flags["has_points"]:
                        sql = "UPDATE employees SET point_total = ? WHERE employee_id = ?"
                        params = (float(chg["New Points"]), eid)
                        if _pg:
                            cur = conn.cursor()
                            cur.execute(sql.replace("?", "%s"), params)
                            cur.close()
                        else:
                            conn.execute(sql, params)
                    # Direct date overrides
                    if flags["has_rolloff"]:
                        ro_val = chg.get("New Roll-off", "") or None
                        sql = "UPDATE employees SET rolloff_date = ? WHERE employee_id = ?"
                        params = (ro_val, eid)
                        if _pg:
                            cur = conn.cursor()
                            cur.execute(sql.replace("?", "%s"), params)
                            cur.close()
                        else:
                            conn.execute(sql, params)
                    if flags["has_perfect"]:
                        pa_val = chg.get("New Perfect Att.", "") or None
                        sql = "UPDATE employees SET perfect_attendance = ? WHERE employee_id = ?"
                        params = (pa_val, eid)
                        if _pg:
                            cur = conn.cursor()
                            cur.execute(sql.replace("?", "%s"), params)
                            cur.close()
                        else:
                            conn.execute(sql, params)
                    applied += 1
                except Exception as exc:
                    errors.append(f"Employee {eid}: {exc}")
            conn.commit()
            clear_read_caches()
            del st.session_state["bulk_override_changes"]
            del st.session_state["bulk_override_flags"]
            if errors:
                st.session_state["bulk_override_msg"] = f"⚠️ Applied {applied} override(s) with {len(errors)} error(s): {'; '.join(errors)}"
            else:
                st.session_state["bulk_override_msg"] = f"✅ Applied {applied} override(s) successfully."
            st.rerun()

    divider()

    # ── Automated Jobs ───────────────────────────────────────────────────
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
                if not dry_run:
                    clear_read_caches()
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
                if not dry_run:
                    clear_read_caches()
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
                if not dry_run:
                    clear_read_caches()
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


# ── Corrective Action ─────────────────────────────────────────────────────────
def corrective_action_page(conn, building: str) -> None:
    page_heading(
        "Corrective Action",
        "Employees at disciplinary point thresholds. Tap a row to log a corrective action date.",
    )

    today = date.today()
    employees = load_employees(conn, building=building)
    emp_ids = [int(e["employee_id"]) for e in employees]
    if not emp_ids:
        info_box("No employees found for this building filter.")
        return

    ph = ",".join(["%s" if is_pg(conn) else "?"] * len(emp_ids))

    if is_pg(conn):
        sql_ca = f"""
            SELECT e.employee_id,
                   e.last_name,
                   e.first_name,
                   COALESCE(e."Location", '') AS building,
                   COALESCE(e.point_total, 0.0) AS point_total,
                   (
                       SELECT MAX(ph3.point_date::date)::text
                         FROM points_history ph3
                        WHERE ph3.employee_id = e.employee_id
                          AND COALESCE(ph3.points, 0.0) > 0.0
                   ) AS last_point_date,
                   e.point_warning_date::text AS point_warning_date
              FROM employees e
             WHERE e.employee_id IN ({ph})
               AND COALESCE(e.is_active, 1) = 1
               AND COALESCE(e.point_total, 0.0) >= 5.0
             ORDER BY COALESCE(e.point_total, 0.0) DESC,
                      lower(e.last_name), lower(e.first_name)
        """
    else:
        sql_ca = f"""
            SELECT employee_id, last_name, first_name, building, point_total,
                   last_point_date, point_warning_date
              FROM (
                SELECT e.employee_id, e.last_name, e.first_name,
                       COALESCE(e."Location", '') AS building,
                       COALESCE(e.point_total, 0.0) AS point_total,
                       (SELECT MAX(date(ph3.point_date)) FROM points_history ph3
                         WHERE ph3.employee_id = e.employee_id
                           AND COALESCE(ph3.points,0.0) > 0.0
                       ) AS last_point_date,
                       e.point_warning_date
                  FROM employees e
                 WHERE e.employee_id IN ({ph})
                   AND COALESCE(e.is_active, 1) = 1
              ) sub
             WHERE point_total >= 5.0
             ORDER BY point_total DESC, lower(last_name), lower(first_name)
        """

    ca_rows = [dict(r) for r in fetchall(conn, sql_ca, tuple(emp_ids))]

    def parse_iso_date(value):
        if not value:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except Exception:
            return None

    def needs_new_warning(row: dict) -> bool:
        warning_dt = parse_iso_date(row.get("point_warning_date"))
        if warning_dt is None:
            return True
        last_positive_dt = parse_iso_date(row.get("last_point_date"))
        return last_positive_dt is not None and last_positive_dt > warning_dt

    needs_warning_rows = [row for row in ca_rows if needs_new_warning(row)]
    already_warned_rows = [row for row in ca_rows if not needs_new_warning(row)]

    # (key, label, range_str, predicate, hex, r, g, b)
    tiers = [
        ("termination",     "Termination",    "7.6 +",     lambda p: p > 7.5,         "#ff3b30", 255, 59,  48),
        ("written_warning", "Written Warning", "7.0 - 7.5", lambda p: 7.0 <= p <= 7.5, "#bf5af2", 191, 90, 242),
        ("verbal_warning",  "Verbal Warning",  "6.0 - 6.5", lambda p: 6.0 <= p <= 6.5, "#ffd60a", 255, 214, 10),
        ("verbal_coaching", "Verbal Coaching", "5.0 - 5.5", lambda p: 5.0 <= p <= 5.5, "#32ade6", 50, 173, 230),
    ]

    def tier_for(pts):
        for key, lbl, rng, fn, col, r, g, b in tiers:
            if fn(pts):
                return key, lbl, rng, col, r, g, b
        return "none", "-", "-", "#8e8e93", 142, 142, 147

    if not ca_rows:
        info_box("No active employees are currently at or above the 5.0 point threshold.")
        return

    # ── Shared CSS injected once ──────────────────────────────────────────────
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

.ca-wrap { font-family: -apple-system, 'Inter', BlinkMacSystemFont, sans-serif; }

/* Summary pills row */
.ca-pills {
  display: flex;
  gap: .55rem;
  flex-wrap: wrap;
  margin-bottom: 1.4rem;
}
.ca-pill {
  display: flex;
  align-items: center;
  gap: .45rem;
  padding: .38rem .85rem;
  border-radius: 999px;
  border: 1px solid;
  font-size: .72rem;
  font-weight: 600;
  letter-spacing: .02em;
  white-space: nowrap;
  cursor: default;
}
.ca-pill-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* Section label */
.ca-section {
  font-size: .68rem;
  font-weight: 600;
  letter-spacing: .10em;
  text-transform: uppercase;
  color: #636366;
  margin: 1.6rem 0 .55rem 0;
  padding-bottom: .35rem;
  border-bottom: 1px solid rgba(255,255,255,.06);
}

/* Employee row */
.ca-row {
  display: flex;
  align-items: center;
  padding: .72rem 1rem;
  border-radius: 12px;
  margin-bottom: .4rem;
  border: 1px solid rgba(255,255,255,.07);
  background: rgba(28,28,30,.55);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  transition: border-color .15s, background .15s;
  gap: .8rem;
}
.ca-row:hover {
  background: rgba(44,44,46,.70);
  border-color: rgba(255,255,255,.13);
}
.ca-row-active {
  border-color: rgba(255,255,255,.18) !important;
  background: rgba(44,44,46,.85) !important;
}

/* Left color strip */
.ca-strip {
  width: 3px;
  border-radius: 999px;
  align-self: stretch;
  min-height: 36px;
  flex-shrink: 0;
}

/* Name + meta block */
.ca-name {
  font-size: .93rem;
  font-weight: 600;
  color: #f2f2f7;
  line-height: 1.25;
}
.ca-meta {
  font-size: .72rem;
  color: #8e8e93;
  margin-top: .1rem;
}

/* Points badge */
.ca-pts {
  font-size: 1.15rem;
  font-weight: 700;
  line-height: 1;
  flex-shrink: 0;
  min-width: 2.8rem;
  text-align: right;
}

/* Date chips */
.ca-dates {
  display: flex;
  flex-direction: column;
  gap: .22rem;
  margin-left: auto;
  flex-shrink: 0;
  text-align: right;
}
.ca-date-chip {
  font-size: .67rem;
  padding: .15rem .55rem;
  border-radius: 999px;
  background: rgba(255,255,255,.05);
  color: #aeaeb2;
  white-space: nowrap;
}
.ca-date-chip span { color: #f2f2f7; font-weight: 500; }

/* Edit panel */
.ca-edit-panel {
  border-radius: 14px;
  padding: 1rem 1.2rem;
  margin-bottom: 1rem;
  border: 1px solid;
  background: rgba(28,28,30,.80);
  backdrop-filter: blur(20px);
}
.ca-edit-title {
  font-size: .68rem;
  font-weight: 600;
  letter-spacing: .09em;
  text-transform: uppercase;
  margin-bottom: .55rem;
}
.ca-edit-name {
  font-size: 1.05rem;
  font-weight: 600;
  color: #f2f2f7;
}
.ca-edit-sub {
  font-size: .78rem;
  color: #8e8e93;
  margin-top: .15rem;
  margin-bottom: .7rem;
}
</style>
<div class="ca-wrap">
""", unsafe_allow_html=True)

    # ── Summary pills ─────────────────────────────────────────────────────────
    pills_html = '<div class="ca-pills">'
    pills_html += (
        "<div class='ca-pill' style='color:#ff9f0a;border-color:rgba(255,159,10,.30);"
        "background:rgba(255,159,10,.09)'>"
        "<div class='ca-pill-dot' style='background:#ff9f0a'></div>"
        f"{len(needs_warning_rows)} need warning</div>"
    )
    pills_html += (
        "<div class='ca-pill' style='color:#8e8e93;border-color:rgba(142,142,147,.30);"
        "background:rgba(142,142,147,.08)'>"
        "<div class='ca-pill-dot' style='background:#8e8e93'></div>"
        f"{len(already_warned_rows)} already warned</div>"
    )
    for key, lbl, rng, fn, col, r, g, b in tiers:
        n = sum(1 for row in needs_warning_rows if fn(float(row.get("point_total") or 0)))
        if n == 0:
            continue
        pills_html += (
            f"<div class='ca-pill' style='color:{col};"
            f"border-color:rgba({r},{g},{b},.30);"
            f"background:rgba({r},{g},{b},.08)'>"
            f"<div class='ca-pill-dot' style='background:{col}'></div>"
            f"{n} {lbl}</div>"
        )
    pills_html += "</div>"
    st.markdown(pills_html, unsafe_allow_html=True)

    # ── Inline edit panel ─────────────────────────────────────────────────────
    if "ca_edit_id" not in st.session_state:
        st.session_state["ca_edit_id"] = None
    editing_id = st.session_state.get("ca_edit_id")

    if editing_id is not None:
        edit_row = next((r for r in ca_rows if int(r["employee_id"]) == editing_id), None)
        if edit_row:
            pts_e = float(edit_row.get("point_total") or 0)
            _, lbl_e, _, col_e, r_e, g_e, b_e = tier_for(pts_e)
            st.markdown(
                f"<div class='ca-edit-panel' style='border-color:rgba({r_e},{g_e},{b_e},.35)'>"
                f"<div class='ca-edit-title' style='color:{col_e}'>Edit warning date</div>"
                f"<div class='ca-edit-name'>{edit_row['last_name']}, {edit_row['first_name']}</div>"
                f"<div class='ca-edit-sub'>Emp #{edit_row['employee_id']} &nbsp;&middot;&nbsp; "
                f"{pts_e:.1f} pts &nbsp;&middot;&nbsp; {lbl_e}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            existing = edit_row.get("point_warning_date")
            try:
                default_val = date.fromisoformat(str(existing)[:10]) if existing else today
            except Exception:
                default_val = today
            ec1, ec2, ec3 = st.columns([2, 1, 1])
            with ec1:
                new_date = st.date_input("Warning date", value=default_val,
                                         key=f"ca_date_{editing_id}",
                                         label_visibility="collapsed")
            with ec2:
                if st.button("Save", key="ca_save", use_container_width=True):
                    try:
                        sym = "%s" if is_pg(conn) else "?"
                        exec_sql(conn,
                            f"UPDATE employees SET point_warning_date={sym} WHERE employee_id={sym}",
                            (new_date.isoformat(), editing_id))
                        conn.commit()
                        st.session_state["ca_edit_id"] = None
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            with ec3:
                if st.button("Cancel", key="ca_cancel", use_container_width=True):
                    st.session_state["ca_edit_id"] = None
                    st.rerun()

    # ── Tier sections ─────────────────────────────────────────────────────────
    def render_ca_group(group_label: str, group_key: str, rows: list[dict], empty_text: str) -> None:
        st.markdown(
            f"<div class='ca-section'>"
            f"<span>{group_label}</span>"
            f"<span style='color:#3a3a3c;margin:0 .4rem'>&middot;</span>"
            f"{len(rows)} {'employee' if len(rows) == 1 else 'employees'}"
            f"</div>",
            unsafe_allow_html=True,
        )
        if not rows:
            info_box(empty_text)
            return

        for key, label, rng, fn, col, r, g, b in tiers:
            tier_rows = [row for row in rows if fn(float(row.get("point_total") or 0))]
            if not tier_rows:
                continue

            st.markdown(
                f"<div class='ca-section'>"
                f"<span style='color:{col}'>{label}</span>"
                f"<span style='color:#3a3a3c;margin:0 .4rem'>&middot;</span>"
                f"<span>{rng} pts</span>"
                f"<span style='color:#3a3a3c;margin:0 .4rem'>&middot;</span>"
                f"{len(tier_rows)} {'employee' if len(tier_rows)==1 else 'employees'}"
                f"</div>",
                unsafe_allow_html=True,
            )

            for row in tier_rows:
                eid = int(row["employee_id"])
                pts = float(row.get("point_total") or 0)
                name = f"{row['last_name']}, {row['first_name']}"
                bldg = row.get("building") or "-"
                lpd = fmt_date(row.get("last_point_date"))
                pwd = fmt_date(row.get("point_warning_date"))
                is_ed = (editing_id == eid)

                active_cls = "ca-row-active" if is_ed else ""
                warn_color = col if pwd != "-" else "#48484a"
                warn_label = pwd if pwd != "-" else "Not logged"

                st.markdown(
                    f"<div class='ca-row {active_cls}'>"
                    f"<div class='ca-strip' style='background:{col}'></div>"
                    f"<div style='flex:1;min-width:0'>"
                    f"  <div class='ca-name'>{name}</div>"
                    f"  <div class='ca-meta'>#{eid} &nbsp;&middot;&nbsp; {bldg}</div>"
                    f"</div>"
                    f"<div class='ca-pts' style='color:{col}'>{pts:.1f}</div>"
                    f"<div class='ca-dates'>"
                    f"  <div class='ca-date-chip'>Last point &nbsp;<span>{lpd}</span></div>"
                    f"  <div class='ca-date-chip' style='color:{warn_color}'>"
                    f"    Warning &nbsp;<span style='color:{warn_color}'>{warn_label}</span></div>"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if st.button("Set date", key=f"ca_edit_{group_key}_{eid}", use_container_width=False):
                    st.session_state["ca_edit_id"] = eid
                    st.rerun()

    render_ca_group(
        "Needs Corrective Action",
        "needs",
        needs_warning_rows,
        "No employees currently need a new warning.",
    )
    with st.expander("Threshold Met - Warning Up To Date", expanded=False):
        render_ca_group(
            "Threshold Met - Warning Up To Date",
            "up_to_date",
            already_warned_rows,
            "No employees are currently in the already-warned group.",
        )

    st.markdown("</div>", unsafe_allow_html=True)

    divider()
    df_ca = pd.DataFrame([
        {
            "Employee #":         str(int(r["employee_id"])),
            "Name":               f"{r['last_name']}, {r['first_name']}",
            "Building":           r.get("building") or "—",
            "Point Total":        f"{float(r.get('point_total') or 0):.1f}",
            "Last Point Date":    fmt_date(r.get("last_point_date")),
            "Point Warning Date": fmt_date(r.get("point_warning_date")),
            "Tier":               tier_for(float(r.get("point_total") or 0))[1],
            "Status":             "Needs Warning" if needs_new_warning(r) else "Warning Up To Date",
        }
        for r in ca_rows
    ])
    st.download_button(
        "Download Corrective Action List",
        data=to_csv(df_ca),
        file_name=f"corrective_action_{today}.csv",
        mime="text/csv",
        key="dl_ca",
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
            "",
            ["Dashboard", "PTO Usage Analytics", "Employees", "Points Ledger", "Corrective Action", "Manage Employees", "Exports & Forecasts", "System Updates"],
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
    elif page == "PTO Usage Analytics":
        pto_page(conn, building)
    elif page == "Employees":
        employees_page(conn, building)
    elif page == "Points Ledger":
        points_ledger_page(conn, building)
    elif page == "Corrective Action":
        corrective_action_page(conn, building)
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
