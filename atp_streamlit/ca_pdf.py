"""Corrective action PDF generation for the attendance tracker."""
from __future__ import annotations

import io
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png")

PAGE_W, PAGE_H = letter
MARGIN = inch
BODY_W = PAGE_W - 2 * MARGIN

TIER_LABELS = {
    "verbal_coaching":  "Coaching Session",
    "verbal_warning":   "Verbal Warning",
    "written_warning":  "Written Warning",
    "termination":      "Termination",
}


def _styles():
    return {
        "title": ParagraphStyle(
            "ca_title", fontName="Helvetica-Bold", fontSize=13,
            alignment=TA_CENTER, spaceAfter=8, textColor=colors.black,
        ),
        "label": ParagraphStyle(
            "ca_label", fontName="Helvetica-Bold", fontSize=10,
            alignment=TA_LEFT, textColor=colors.black,
        ),
        "value": ParagraphStyle(
            "ca_value", fontName="Helvetica", fontSize=10,
            alignment=TA_LEFT, textColor=colors.black,
        ),
        "body": ParagraphStyle(
            "ca_body", fontName="Helvetica", fontSize=10,
            alignment=TA_JUSTIFY, leading=13, spaceAfter=6,
            textColor=colors.black,
        ),
        "bullet": ParagraphStyle(
            "ca_bullet", fontName="Helvetica", fontSize=10,
            leftIndent=20, leading=13, spaceAfter=4, textColor=colors.black,
        ),
        "sig_label": ParagraphStyle(
            "ca_sig_label", fontName="Helvetica", fontSize=9,
            textColor=colors.black,
        ),
        "th": ParagraphStyle(
            "ca_th", fontName="Helvetica-Bold", fontSize=9, textColor=colors.black,
        ),
        "td": ParagraphStyle(
            "ca_td", fontName="Helvetica", fontSize=9, textColor=colors.black,
        ),
    }


def _header():
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


def _info_block(s, employee_name, manager, gen_date, point_total,
                rolloff_2m=None, rolloff_ytd=None):
    rows_data = [
        ("Employee Name:", employee_name),
        ("Manager:",       manager or "—"),
        ("Date:",          gen_date),
        ("Current Point Total:", f"{point_total:.1f}"),
    ]
    if rolloff_2m:
        rows_data.append(("Next 2-Month Roll Off:", rolloff_2m))
    if rolloff_ytd:
        rows_data.append(("Next YTD Roll Off:", rolloff_ytd))

    rows = [[Paragraph(l, s["label"]), Paragraph(v, s["value"])]
            for l, v in rows_data]
    t = Table(rows, colWidths=[BODY_W * 0.38, BODY_W * 0.62])
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _body_standard(s, gen_date, point_total, rolloff_2m, rolloff_ytd):
    pts = f"{point_total:.1f}"
    r2m  = rolloff_2m  or "—"
    rytd = rolloff_ytd or "—"
    elems = []
    elems.append(Paragraph(
        f"As of {gen_date}, your point total is <b>{pts}</b>. Points are given to effectively "
        "control the attendance of employees. As points are acquired, steps are taken to reverse "
        "the trend of unsatisfactory attendance.",
        s["body"],
    ))
    elems.append(Paragraph(
        "As our attendance policy states, corrective action for attendance problems will be "
        "administered according to the following:",
        s["body"],
    ))
    elems.append(Paragraph("<b>Number of Points:</b>", s["body"]))
    for bullet in [
        "Five (5) points within a consecutive twelve (12) month period \u2014 Coaching Session",
        "Six (6) points within a consecutive twelve (12) month period \u2014 Verbal Warning",
        "Seven (7) points within a consecutive twelve (12) month period \u2014 Written Warning",
        "Eight (8) points within a consecutive twelve (12) month period \u2014 Termination",
    ]:
        elems.append(Paragraph(f"\u2022  {bullet}", s["bullet"]))
    elems.append(Spacer(1, 4))
    elems.append(Paragraph(
        "We are taking the appropriate step to control the noticed problem. We feel that you are a "
        "valuable employee; therefore, we hope you will resolve this problem immediately so we will "
        "not have to take any further action. We do understand that absence and tardiness is "
        "sometimes unavoidable.",
        s["body"],
    ))
    elems.append(Paragraph(
        f"Please remember, it is possible to reverse points. Going 2 full consecutive months "
        f"without any tardies or absences will remove 1.0 point. Your first opportunity for this "
        f"roll off is on <b>{r2m}</b>. Points also fall off after one calendar year. "
        f"Your next year-to-date roll off is <b>{rytd}</b>.",
        s["body"],
    ))
    elems.append(Paragraph(
        "Please feel free to discuss with your supervisor or the Human Resources department any "
        "problems or questions you may have regarding the attendance program. API is committed to "
        "maintaining a fair, consistent, reasonable, and flexible program.",
        s["body"],
    ))
    return elems


def _body_termination(s, gen_date, point_total, point_history):
    pts = f"{point_total:.1f}"
    elems = []
    elems.append(Paragraph(
        f"As of {gen_date}, your point total is <b>{pts}</b>.",
        s["body"],
    ))
    elems.append(Paragraph(
        "API maintains an Attendance Points Policy to manage employee attendance. Points are "
        "assessed for absences, tardiness, and related attendance issues. As outlined in our "
        "policy, corrective action is taken as employees accumulate points:",
        s["body"],
    ))
    for bullet in [
        "Five (5) points within a consecutive twelve (12) month period \u2014 Coaching Session",
        "Six (6) points within a consecutive twelve (12) month period \u2014 Verbal Warning",
        "Seven (7) points within a consecutive twelve (12) month period \u2014 Written Warning",
        "Eight (8) points within a consecutive twelve (12) month period \u2014 Termination",
    ]:
        elems.append(Paragraph(f"\u2022  {bullet}", s["bullet"]))
    elems.append(Spacer(1, 4))
    elems.append(Paragraph(
        f"Your attendance record has reached <b>{pts}</b> points, which meets the threshold for "
        f"termination of employment. As a result, your employment with API is terminated "
        f"effective <b>{gen_date}</b>.",
        s["body"],
    ))
    elems.append(Paragraph(
        "Below is a summary of your attendance point history for the current year:",
        s["body"],
    ))

    hist = point_history or []
    table_data = [[
        Paragraph("<b>Date</b>",   s["th"]),
        Paragraph("<b>Reason</b>", s["th"]),
        Paragraph("<b>Points</b>", s["th"]),
    ]]
    for row in hist:
        table_data.append([
            Paragraph(str(row.get("point_date", "")),  s["td"]),
            Paragraph(str(row.get("reason", "")),      s["td"]),
            Paragraph(str(row.get("points", "")),      s["td"]),
        ])
    col_w = [BODY_W * 0.28, BODY_W * 0.52, BODY_W * 0.20]
    ht = Table(table_data, colWidths=col_w)
    ht.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#dddddd")),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    elems.append(ht)
    elems.append(Spacer(1, 6))
    elems.append(Paragraph(
        "If you have any questions regarding this decision, please contact the Human Resources department.",
        s["body"],
    ))
    return elems


def _signatures(s, include_hr=False):
    sig_line  = "_" * 38
    date_line = "_" * 18
    roles = ["Employee", "Manager"] + (["HR"] if include_hr else [])

    rows = []
    for role in roles:
        rows.append([
            Paragraph(f"{role} Signature:", s["sig_label"]),
            Paragraph(sig_line,             s["sig_label"]),
            Paragraph("Date:",              s["sig_label"]),
            Paragraph(date_line,            s["sig_label"]),
        ])
        rows.append([Paragraph("", s["sig_label"])] * 4)

    col_w = [BODY_W * 0.22, BODY_W * 0.46, BODY_W * 0.10, BODY_W * 0.22]
    t = Table(rows, colWidths=col_w)
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return KeepTogether([
        HRFlowable(width=BODY_W, thickness=0.5, color=colors.black,
                   spaceAfter=6, spaceBefore=8),
        Paragraph("<b>Signatures</b>", s["label"]),
        Spacer(1, 5),
        t,
    ])


def generate_ca_pdf(
    tier_key: str,
    employee_name: str,
    manager: str,
    gen_date: str,
    point_total: float,
    rolloff_2m: str | None = None,
    rolloff_ytd: str | None = None,
    point_history: list[dict] | None = None,
) -> bytes:
    """Generate a corrective action PDF and return the raw bytes.

    tier_key: 'verbal_coaching' | 'verbal_warning' | 'written_warning' | 'termination'
    gen_date: already-formatted date string, e.g. "04/25/2026"
    rolloff_2m / rolloff_ytd: formatted date strings or None
    point_history: list of dicts with keys point_date, reason, points (termination only)
    """
    buf = io.BytesIO()
    s = _styles()
    include_hr = tier_key in ("written_warning", "termination")
    title_label = TIER_LABELS.get(tier_key, tier_key.replace("_", " ").title())

    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=0.55 * inch, bottomMargin=0.55 * inch,
    )

    story = []
    story.append(_header())
    story.append(HRFlowable(width=BODY_W, thickness=0.75, color=colors.black,
                             spaceBefore=4, spaceAfter=6))
    story.append(Paragraph(f"Attendance Corrective Action \u2014 {title_label}", s["title"]))
    story.append(Spacer(1, 4))

    show_rolloffs = tier_key != "termination"
    story.append(_info_block(
        s, employee_name, manager, gen_date, point_total,
        rolloff_2m  if show_rolloffs else None,
        rolloff_ytd if show_rolloffs else None,
    ))
    story.append(HRFlowable(width=BODY_W, thickness=0.5, color=colors.black,
                             spaceBefore=6, spaceAfter=8))

    if tier_key == "termination":
        story.extend(_body_termination(s, gen_date, point_total, point_history))
    else:
        story.extend(_body_standard(s, gen_date, point_total, rolloff_2m, rolloff_ytd))

    story.append(Spacer(1, 0.4 * inch))
    story.append(_signatures(s, include_hr=include_hr))

    doc.build(story)
    return buf.getvalue()
