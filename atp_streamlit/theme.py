"""Dark theme CSS for the Attendance Point Tracker."""
from __future__ import annotations

import streamlit as st


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

