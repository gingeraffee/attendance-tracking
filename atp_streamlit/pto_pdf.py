"""PTO manager summary PDF generation."""
from __future__ import annotations

import io
import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable, Image, PageBreak, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png")
PAGE_W, PAGE_H = letter
MARGIN = inch
BODY_W = PAGE_W - 2 * MARGIN

_NAVY  = colors.HexColor("#1a3a5c")
_LIGHT = colors.HexColor("#f5f7fa")
_RULE  = colors.HexColor("#cccccc")


def _styles() -> dict:
    return {
        "report_title": ParagraphStyle(
            "rpt_title", fontName="Helvetica-Bold", fontSize=16,
            alignment=TA_CENTER, spaceAfter=6, textColor=_NAVY,
        ),
        "section_title": ParagraphStyle(
            "rpt_section", fontName="Helvetica-Bold", fontSize=13,
            spaceAfter=4, spaceBefore=2, textColor=_NAVY,
        ),
        "meta": ParagraphStyle(
            "rpt_meta", fontName="Helvetica", fontSize=10,
            alignment=TA_CENTER, spaceAfter=4, textColor=colors.black,
        ),
        "label": ParagraphStyle(
            "rpt_label", fontName="Helvetica-Bold", fontSize=10,
            textColor=colors.black, spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "rpt_body", fontName="Helvetica", fontSize=10,
            spaceAfter=4, textColor=colors.black, leading=13,
        ),
        "th": ParagraphStyle(
            "rpt_th", fontName="Helvetica-Bold", fontSize=9,
            textColor=colors.white,
        ),
        "td": ParagraphStyle(
            "rpt_td", fontName="Helvetica", fontSize=9,
            textColor=colors.black,
        ),
        "note": ParagraphStyle(
            "rpt_note", fontName="Helvetica-Oblique", fontSize=9,
            textColor=colors.HexColor("#666666"), spaceAfter=4,
        ),
    }


def _header() -> Table:
    logo = Image(LOGO_PATH, height=50, width=160)
    t = Table([[logo]], colWidths=[BODY_W])
    t.setStyle(TableStyle([
        ("ALIGN",         (0, 0), (0, 0), "CENTER"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _data_table(headers: list[str], rows: list[list], col_widths: list[float], s: dict) -> Table:
    header_row = [Paragraph(h, s["th"]) for h in headers]
    data = [header_row] + [[Paragraph(str(c), s["td"]) for c in row] for row in rows]
    tbl = Table(data, colWidths=[w * inch for w in col_widths])
    row_bgs = [
        ("BACKGROUND", (0, i), (-1, i), colors.white if i % 2 == 1 else _LIGHT)
        for i in range(1, len(data))
    ]
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), _NAVY),
        ("GRID",          (0, 0), (-1, -1), 0.25, _RULE),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("ALIGN",         (1, 0), (-1, -1), "RIGHT"),
    ] + row_bgs))
    return tbl


def generate_manager_pto_pdf(
    df,
    mgr_lookup: dict[int, str],
    mgr_to_employees: dict[str, list[str]],
    shift_hours: dict[str, float],
    date_start: date,
    date_end: date,
    building: str = "All",
) -> bytes:
    """
    df                  — filtered PTO DataFrame (employee_id, employee, pto_type, hours, …)
    mgr_lookup          — {employee_id: manager_name}
    mgr_to_employees    — {manager_name: ["Last, First", …]} for all active employees in scope
    shift_hours         — {"Last, First": 8.0 or 4.0} hours per shift per employee
    date_start/end      — the report period
    building            — location filter label
    """
    import pandas as pd

    buf = io.BytesIO()
    s = _styles()

    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=0.55 * inch, bottomMargin=0.55 * inch,
    )

    df = df.copy()
    if "employee_id" in df.columns:
        df["manager"] = df["employee_id"].apply(
            lambda eid: mgr_lookup.get(int(eid), "Unassigned") if pd.notna(eid) else "Unassigned"
        )
    else:
        df["manager"] = "Unassigned"
    df["manager"] = df["manager"].fillna("Unassigned").str.strip().replace("", "Unassigned")

    def _hours_to_days(emp_name: str, hrs: float) -> float:
        return round(hrs / shift_hours.get(emp_name, 8.0), 1)

    df["days"] = df.apply(
        lambda row: row["hours"] / shift_hours.get(row["employee"], 8.0), axis=1
    )

    period_str = f"{date_start.strftime('%B %d, %Y')} \u2013 {date_end.strftime('%B %d, %Y')}"
    gen_date   = date.today().strftime("%B %d, %Y")

    story = []

    # ── Cover ────────────────────────────────────────────────────────────────
    try:
        story.append(_header())
        story.append(HRFlowable(width=BODY_W, thickness=0.75, color=colors.black,
                                spaceBefore=4, spaceAfter=8))
    except Exception:
        pass

    story.append(Paragraph("PTO Usage Summary Report", s["report_title"]))
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph(f"Period: {period_str}", s["meta"]))
    if building != "All":
        story.append(Paragraph(f"Location: {building}", s["meta"]))
    story.append(Paragraph(f"Generated: {gen_date}", s["meta"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(HRFlowable(width=BODY_W, thickness=0.5, color=_RULE, spaceAfter=8))

    total_hrs  = df["hours"].sum()
    total_days = df["days"].sum()
    total_emps = df["employee"].nunique()
    _unplan = {"absence", "absence (sick)", "absence (covid)", "long term sick leave"}
    _plan   = {"vacation", "floating holiday", "reward pto", "personal"}
    unplan_days = df[df["pto_type"].str.strip().str.lower().isin(_unplan)]["days"].sum()
    plan_days   = df[df["pto_type"].str.strip().str.lower().isin(_plan)]["days"].sum()

    overview = [
        ["Total PTO Hours",      f"{total_hrs:,.0f}"],
        ["Total PTO Days",       f"{total_days:,.1f}"],
        ["Employees Using PTO",  str(total_emps)],
        ["Planned PTO Days",     f"{plan_days:,.1f}"],
        ["Unplanned PTO Days",   f"{unplan_days:,.1f}"],
    ]
    ov_tbl = Table(
        [[Paragraph(k, s["label"]), Paragraph(v, s["body"])] for k, v in overview],
        colWidths=[BODY_W * 0.50, BODY_W * 0.50],
    )
    ov_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(ov_tbl)
    story.append(PageBreak())

    # ── Per-manager pages ────────────────────────────────────────────────────
    for mgr in sorted(df["manager"].unique()):
        mgr_df   = df[df["manager"] == mgr]
        mgr_emps = mgr_df["employee"].nunique()
        mgr_hrs  = mgr_df["hours"].sum()

        story.append(Paragraph(f"Manager: {mgr}", s["section_title"]))
        story.append(HRFlowable(width=BODY_W, thickness=0.5, color=_RULE, spaceAfter=6))
        story.append(Paragraph(
            f"Employees Using PTO: <b>{mgr_emps}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"Total Hours: <b>{mgr_hrs:,.0f}</b>",
            s["body"],
        ))
        story.append(Spacer(1, 0.1 * inch))

        # PTO by type
        type_summary = (
            mgr_df.groupby("pto_type")
            .agg(hours=("hours", "sum"), days=("days", "sum"), events=("hours", "count"))
            .sort_values("days", ascending=False)
            .reset_index()
        )
        story.append(Paragraph("PTO by Type", s["label"]))
        story.append(Spacer(1, 0.04 * inch))
        story.append(_data_table(
            ["PTO Type", "Hours", "Avg Days / Request"],
            [[r["pto_type"], f"{r['hours']:.0f}", f"{r['days'] / r['events']:.1f}"]
             for _, r in type_summary.iterrows()],
            [3.5, 1.25, 1.25],
            s,
        ))
        story.append(Spacer(1, 0.15 * inch))

        # Employee breakdown — days respects PT/FT shift length
        emp_summary = (
            mgr_df.groupby("employee")
            .agg(hours=("hours", "sum"), days=("days", "sum"), events=("hours", "count"))
            .sort_values("days", ascending=False)
            .reset_index()
        )
        story.append(Paragraph("Employee Breakdown", s["label"]))
        story.append(Spacer(1, 0.04 * inch))
        story.append(_data_table(
            ["Employee", "Hours", "Avg Days / Request"],
            [
                [
                    r["employee"],
                    f"{r['hours']:.0f}",
                    f"{r['days'] / r['events']:.1f}",
                ]
                for _, r in emp_summary.iterrows()
            ],
            [3.5, 1.25, 1.25],
            s,
        ))
        story.append(Spacer(1, 0.15 * inch))

        # Zero PTO employees under this manager
        emps_with_pto = set(mgr_df["employee"].str.strip())
        zero_pto = sorted(n for n in mgr_to_employees.get(mgr, []) if n not in emps_with_pto)
        if zero_pto:
            story.append(Paragraph("No PTO Recorded This Period", s["label"]))
            story.append(Spacer(1, 0.04 * inch))
            story.append(_data_table(["Employee"], [[n] for n in zero_pto], [6.0], s))

        story.append(PageBreak())

    doc.build(story)
    return buf.getvalue()
