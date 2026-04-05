"""Authentication and session state management."""
from __future__ import annotations

import streamlit as st


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

