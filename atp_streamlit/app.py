"""Attendance Point Tracker — Streamlit Web App
Entry point: routes to page modules.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Attendance Point Tracker",
    page_icon="\u23f0",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atp_streamlit.constants import BUILDINGS  # noqa: E402
from atp_streamlit.theme import apply_theme  # noqa: E402
from atp_streamlit.shared.auth import ensure_session_defaults, is_authenticated  # noqa: E402
from atp_streamlit.shared.db import get_conn  # noqa: E402

from atp_streamlit.pages.login import login_page  # noqa: E402
from atp_streamlit.pages.dashboard import (  # noqa: E402
    dashboard_page,
    selected_employee_sidebar,
)
from atp_streamlit.pages.pto import pto_page  # noqa: E402
from atp_streamlit.pages.employees import employees_page  # noqa: E402
from atp_streamlit.pages.ledger import points_ledger_page  # noqa: E402
from atp_streamlit.pages.corrective import corrective_action_page  # noqa: E402
from atp_streamlit.pages.manage import manage_employees_page  # noqa: E402
from atp_streamlit.pages.exports import exports_page  # noqa: E402
from atp_streamlit.pages.system_updates import system_updates_page  # noqa: E402


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
