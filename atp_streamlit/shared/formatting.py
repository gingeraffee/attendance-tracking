"""Format and display helper functions."""
from __future__ import annotations

import html
from datetime import date, datetime

import pandas as pd
import streamlit as st


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
