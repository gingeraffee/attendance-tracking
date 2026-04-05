"""Login page."""
from __future__ import annotations

import base64
import html
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = APP_DIR.parent

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import atp_core.db as db
from atp_core import repo, services
from atp_core.rules import REASON_OPTIONS

from atp_streamlit.constants import (
    BUILDINGS,
    DASHBOARD_CACHE_TTL_SECONDS,
    EMPLOYEE_CACHE_TTL_SECONDS,
    EXPORT_LABELS,
    LEDGER_HISTORY_DEFAULT_LIMIT,
    LEDGER_HISTORY_FULL_LIMIT,
)
from atp_streamlit.shared.db import (
    _db_cache_key,
    _fetchall_cached,
    _get_cached_conn,
    _load_employees_cached,
    clear_read_caches,
    exec_sql,
    fetchall,
    first_value,
    get_conn,
    is_pg,
    load_employees,
    _apply_bulk_employee_override,
    _get_history_point_total,
    _normalize_bulk_override_columns,
    _parse_bulk_override_employee_id,
    _parse_bulk_override_point_total,
    _parse_bulk_override_date,
)
from atp_streamlit.shared.formatting import (
    days_badge,
    days_until,
    divider,
    fmt_date,
    info_box,
    page_heading,
    pt_badge,
    section_header,
    section_label,
    to_csv,
    warn_box,
)
from atp_streamlit.shared.hud import render_hr_live_monitor, render_tech_hud


import os
import secrets

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
