"""Employee detail page."""
from __future__ import annotations

import html
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

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


from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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

