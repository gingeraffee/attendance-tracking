from __future__ import annotations

from csv import DictWriter
from datetime import date, datetime
from io import BytesIO, StringIO
from pathlib import Path
import sys
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from atp_core import repo  # noqa: E402
from backend.app.services import attendance  # noqa: E402

REPORT_LABELS = {
    'point_history': 'Point History',
    'upcoming_rolloffs': 'Upcoming 2-Month Roll-offs',
    'upcoming_perfect_attendance': 'Upcoming Perfect Attendance',
    'annual_rolloffs': 'Annual Roll-offs',
}

PDF_NAVY = colors.HexColor('#081a2d')
PDF_NAVY_ALT = colors.HexColor('#102b48')
PDF_CYAN = colors.HexColor('#45d7ff')
PDF_RED = colors.HexColor('#f24f64')
PDF_INK = colors.HexColor('#16324a')
PDF_MUTED = colors.HexColor('#5d7b94')
PDF_SURFACE = colors.HexColor('#f6fbff')
PDF_LINE = colors.HexColor('#d5e7f2')
PDF_CHIP = colors.HexColor('#e9f8ff')
LOGO_PATH = repo_root / 'assets' / 'logo.png'


def _fmt_date(raw: Any) -> str:
    if not raw:
        return '-'
    try:
        return datetime.strptime(str(raw)[:10], '%Y-%m-%d').strftime('%b %d, %Y')
    except ValueError:
        return str(raw)


def _normalize_value(value: Any) -> str:
    if value in (None, ''):
        return '-'
    if isinstance(value, float):
        return f'{value:.1f}'
    return str(value)


def _make_filename(report_type: str, ext: str) -> str:
    stamp = date.today().isoformat()
    return f'attendance_{report_type}_{stamp}.{ext}'


def _report_subtitle(building: str, start_date: date, end_date: date) -> str:
    scope = 'All locations' if building == 'All' else building
    return f'{scope} | {start_date.isoformat()} to {end_date.isoformat()}'


def _employee_rows(building: str, conn) -> list[dict]:
    return attendance.list_employees(conn, building=building)


def _query_point_history(conn, building: str, start_date: date, end_date: date) -> tuple[list[str], list[dict[str, Any]]]:
    columns = ['Employee #', 'Last Name', 'First Name', 'Location', 'Point Date', 'Point', 'Reason', 'Note', 'Running Total']
    rows: list[dict[str, Any]] = []

    employees = _employee_rows(building, conn)
    for employee in employees:
        employee_id = int(employee['employee_id'])
        history = repo.with_running_point_totals(repo.get_points_history_ordered(conn, employee_id))
        for item in history:
            point_day = str(item.get('point_date') or '')[:10]
            if not point_day:
                continue
            point_date = date.fromisoformat(point_day)
            if point_date < start_date or point_date > end_date:
                continue
            rows.append(
                {
                    'Employee #': employee_id,
                    'Last Name': employee['last_name'],
                    'First Name': employee['first_name'],
                    'Location': employee.get('location') or '-',
                    'Point Date': point_day,
                    'Point': round(float(item.get('points') or 0.0), 1),
                    'Reason': item.get('reason') or '-',
                    'Note': item.get('note') or '-',
                    'Running Total': round(float(item.get('point_total') or 0.0), 1),
                }
            )

    rows.sort(key=lambda row: (row['Last Name'].lower(), row['First Name'].lower(), row['Point Date']))
    return columns, rows


def _query_upcoming_rolloffs(conn, building: str, start_date: date, end_date: date) -> tuple[list[str], list[dict[str, Any]]]:
    columns = ['Employee #', 'Last Name', 'First Name', 'Location', 'Point Total', 'Rolloff Date']
    rows = []
    for employee in _employee_rows(building, conn):
        raw = employee.get('rolloff_date')
        if not raw:
            continue
        due = date.fromisoformat(str(raw)[:10])
        if start_date <= due <= end_date:
            rows.append(
                {
                    'Employee #': employee['employee_id'],
                    'Last Name': employee['last_name'],
                    'First Name': employee['first_name'],
                    'Location': employee.get('location') or '-',
                    'Point Total': round(float(employee.get('point_total') or 0.0), 1),
                    'Rolloff Date': str(raw)[:10],
                }
            )
    rows.sort(key=lambda row: (row['Rolloff Date'], row['Last Name'].lower(), row['First Name'].lower()))
    return columns, rows


def _query_upcoming_perfect_attendance(conn, building: str, start_date: date, end_date: date) -> tuple[list[str], list[dict[str, Any]]]:
    columns = ['Employee #', 'Last Name', 'First Name', 'Location', 'Point Total', 'Perfect Attendance Date']
    rows = []
    for employee in _employee_rows(building, conn):
        raw = employee.get('perfect_attendance')
        if not raw:
            continue
        due = date.fromisoformat(str(raw)[:10])
        if start_date <= due <= end_date:
            rows.append(
                {
                    'Employee #': employee['employee_id'],
                    'Last Name': employee['last_name'],
                    'First Name': employee['first_name'],
                    'Location': employee.get('location') or '-',
                    'Point Total': round(float(employee.get('point_total') or 0.0), 1),
                    'Perfect Attendance Date': str(raw)[:10],
                }
            )
    rows.sort(key=lambda row: (row['Perfect Attendance Date'], row['Last Name'].lower(), row['First Name'].lower()))
    return columns, rows


def _query_annual_rolloffs(conn, building: str, start_date: date, end_date: date) -> tuple[list[str], list[dict[str, Any]]]:
    if repo._is_pg(conn):
        sql = """
            SELECT e.employee_id,
                   e.last_name,
                   e.first_name,
                   COALESCE(e."Location", '') AS location,
                   p.point_date,
                   p.points,
                   p.reason,
                   COALESCE(p.note, '') AS note
              FROM points_history p
              JOIN employees e ON e.employee_id = p.employee_id
             WHERE p.reason = 'YTD Roll-Off'
               AND p.flag_code = 'AUTO'
               AND (p.point_date::date) >= (%s::date)
               AND (p.point_date::date) <= (%s::date)
        """
        params: list[Any] = [start_date.isoformat(), end_date.isoformat()]
        if building != 'All':
            sql += " AND COALESCE(e.\"Location\", '') = %s"
            params.append(building)
    else:
        sql = """
            SELECT e.employee_id,
                   e.last_name,
                   e.first_name,
                   COALESCE(e."Location", '') AS location,
                   p.point_date,
                   p.points,
                   p.reason,
                   COALESCE(p.note, '') AS note
              FROM points_history p
              JOIN employees e ON e.employee_id = p.employee_id
             WHERE p.reason = 'YTD Roll-Off'
               AND p.flag_code = 'AUTO'
               AND date(p.point_date) >= date(?)
               AND date(p.point_date) <= date(?)
        """
        params = [start_date.isoformat(), end_date.isoformat()]
        if building != 'All':
            sql += ' AND COALESCE(e."Location", \'\') = ?'
            params.append(building)

    sql += ' ORDER BY e.last_name, e.first_name, p.point_date'
    rows = [dict(row) for row in repo._fetchall(conn, sql, tuple(params))]
    columns = ['Employee #', 'Last Name', 'First Name', 'Location', 'Point Date', 'Point', 'Reason', 'Note']
    return (
        columns,
        [
            {
                'Employee #': int(row['employee_id']),
                'Last Name': row.get('last_name') or '',
                'First Name': row.get('first_name') or '',
                'Location': row.get('location') or '-',
                'Point Date': str(row.get('point_date') or '')[:10],
                'Point': round(float(row.get('points') or 0.0), 1),
                'Reason': row.get('reason') or '-',
                'Note': row.get('note') or '-',
            }
            for row in rows
        ],
    )


def build_export_preview(conn, report_type: str, building: str, start_date: date, end_date: date) -> dict:
    if report_type == 'point_history':
        columns, rows = _query_point_history(conn, building, start_date, end_date)
    elif report_type == 'upcoming_rolloffs':
        columns, rows = _query_upcoming_rolloffs(conn, building, start_date, end_date)
    elif report_type == 'upcoming_perfect_attendance':
        columns, rows = _query_upcoming_perfect_attendance(conn, building, start_date, end_date)
    elif report_type == 'annual_rolloffs':
        columns, rows = _query_annual_rolloffs(conn, building, start_date, end_date)
    else:
        raise ValueError('Unsupported report type.')

    return {
        'report_type': report_type,
        'title': REPORT_LABELS[report_type],
        'subtitle': _report_subtitle(building, start_date, end_date),
        'columns': columns,
        'rows': rows,
        'row_count': len(rows),
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'building': building,
    }


def build_csv_bytes(preview: dict) -> bytes:
    buffer = StringIO()
    writer = DictWriter(buffer, fieldnames=preview['columns'])
    writer.writeheader()
    for row in preview['rows']:
        writer.writerow({column: _normalize_value(row.get(column)) for column in preview['columns']})
    return buffer.getvalue().encode('utf-8-sig')


def _build_page_decorator(report_title: str, report_subtitle: str):
    def _page_decor(canvas, doc) -> None:
        canvas.saveState()
        page_width, page_height = doc.pagesize
        header_height = 1.08 * inch

        canvas.setFillColor(PDF_NAVY)
        canvas.rect(0, page_height - header_height, page_width, header_height, fill=1, stroke=0)
        canvas.setFillColor(PDF_CYAN)
        canvas.rect(0, page_height - 0.13 * inch, page_width, 0.13 * inch, fill=1, stroke=0)

        logo_x = doc.leftMargin
        logo_y = page_height - 0.82 * inch
        if LOGO_PATH.exists():
            try:
                canvas.drawImage(ImageReader(str(LOGO_PATH)), logo_x, logo_y, width=0.52 * inch, height=0.52 * inch, preserveAspectRatio=True, mask='auto')
            except Exception:
                canvas.setFillColor(PDF_RED)
                canvas.circle(logo_x + 0.18 * inch, logo_y + 0.18 * inch, 0.14 * inch, fill=1, stroke=0)
        else:
            canvas.setFillColor(PDF_RED)
            canvas.circle(logo_x + 0.18 * inch, logo_y + 0.18 * inch, 0.14 * inch, fill=1, stroke=0)

        text_x = doc.leftMargin + 0.68 * inch
        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 15)
        canvas.drawString(text_x, page_height - 0.48 * inch, 'Attendance Tracking')
        canvas.setFillColor(colors.HexColor('#c8e9fb'))
        canvas.setFont('Helvetica', 9.5)
        canvas.drawString(text_x, page_height - 0.68 * inch, report_title)
        canvas.setFont('Helvetica', 8.5)
        canvas.drawString(text_x, page_height - 0.84 * inch, report_subtitle)

        chip_width = 1.48 * inch
        chip_height = 0.3 * inch
        chip_x = page_width - doc.rightMargin - chip_width
        chip_y = page_height - 0.68 * inch
        canvas.setFillColor(colors.white)
        canvas.roundRect(chip_x, chip_y, chip_width, chip_height, 0.12 * inch, fill=1, stroke=0)
        canvas.setFillColor(PDF_NAVY_ALT)
        canvas.setFont('Helvetica-Bold', 8.5)
        canvas.drawCentredString(chip_x + chip_width / 2, chip_y + 0.11 * inch, 'Premium export')

        canvas.setStrokeColor(PDF_LINE)
        canvas.line(doc.leftMargin, 0.55 * inch, page_width - doc.rightMargin, 0.55 * inch)
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(PDF_MUTED)
        canvas.drawString(doc.leftMargin, 0.32 * inch, 'Attendance Tracking Export')
        canvas.drawRightString(page_width - doc.rightMargin, 0.32 * inch, f'Page {doc.page}')
        canvas.restoreState()

    return _page_decor


def _metadata_table(preview: dict, style: ParagraphStyle) -> Table:
    generated_on = datetime.now().strftime('%b %d, %Y %I:%M %p')
    cards = [
        ('Scope', 'All locations' if preview['building'] == 'All' else preview['building']),
        ('Window', f"{_fmt_date(preview['start_date'])} to {_fmt_date(preview['end_date'])}"),
        ('Rows', str(preview['row_count'])),
        ('Generated', generated_on),
    ]
    body = []
    pair: list[Paragraph] = []
    for index, (label, value) in enumerate(cards, start=1):
        pair.append(Paragraph(f'<font color="#5d7b94">{label}</font><br/><b>{value}</b>', style))
        if index % 2 == 0:
            body.append(pair)
            pair = []

    table = Table(body, colWidths=[3.8 * inch, 3.8 * inch])
    table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), PDF_SURFACE),
                ('BOX', (0, 0), (-1, -1), 1, PDF_LINE),
                ('INNERGRID', (0, 0), (-1, -1), 0.75, PDF_LINE),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]
        )
    )
    return table


def _table_widths(columns: list[str], available_width: float) -> list[float]:
    weights = []
    for column in columns:
        lowered = column.lower()
        if 'note' in lowered:
            weights.append(2.4)
        elif 'reason' in lowered:
            weights.append(1.8)
        elif 'name' in lowered or 'location' in lowered:
            weights.append(1.4)
        elif 'date' in lowered:
            weights.append(1.2)
        else:
            weights.append(1.0)
    total = sum(weights)
    return [available_width * (weight / total) for weight in weights]


def build_pdf_bytes(preview: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=1.35 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ExportTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=PDF_NAVY,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        'ExportSubtitle',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=PDF_MUTED,
        spaceAfter=18,
    )
    meta_style = ParagraphStyle(
        'Meta',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=PDF_INK,
    )
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=PDF_INK,
    )

    story = [
        Paragraph(preview['title'], title_style),
        Paragraph(preview['subtitle'], subtitle_style),
        _metadata_table(preview, meta_style),
        Spacer(1, 0.18 * inch),
    ]

    if preview['rows']:
        table_rows = [[Paragraph(f'<b>{column}</b>', cell_style) for column in preview['columns']]]
        for row in preview['rows']:
            table_rows.append([Paragraph(_normalize_value(row.get(column)), cell_style) for column in preview['columns']])
        table = Table(table_rows, colWidths=_table_widths(preview['columns'], doc.width), repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, 0), PDF_NAVY_ALT),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PDF_SURFACE]),
                    ('GRID', (0, 0), (-1, -1), 0.6, PDF_LINE),
                    ('BOX', (0, 0), (-1, -1), 0.8, PDF_LINE),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 7),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
                    ('LINEBELOW', (0, 0), (-1, 0), 1.2, PDF_CYAN),
                ]
            )
        )
        story.append(table)
    else:
        empty_style = ParagraphStyle(
            'Empty',
            parent=styles['BodyText'],
            fontName='Helvetica',
            fontSize=11,
            leading=15,
            textColor=PDF_MUTED,
        )
        story.append(Paragraph('No records matched this export window. Try widening the date range or changing the location filter.', empty_style))

    page_decor = _build_page_decorator(preview['title'], preview['subtitle'])
    doc.build(story, onFirstPage=page_decor, onLaterPages=page_decor)
    return buffer.getvalue()


def build_employee_history_pdf(conn, employee_id: int) -> tuple[bytes, str]:
    employee = attendance.get_employee_detail(conn, int(employee_id))
    if not employee:
        raise ValueError('Employee not found.')

    history = repo.with_running_point_totals(repo.get_points_history_ordered(conn, int(employee_id)))
    employee_name = f"{employee['last_name']}, {employee['first_name']}"
    safe_name = f"{employee['last_name']}_{employee['first_name']}".replace(' ', '_')

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=1.35 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'EmployeeHistoryTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=PDF_NAVY,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        'EmployeeHistorySubtitle',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=PDF_MUTED,
        spaceAfter=18,
    )
    meta_style = ParagraphStyle(
        'EmployeeHistoryMeta',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=PDF_INK,
    )
    cell_style = ParagraphStyle(
        'EmployeeHistoryCell',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=PDF_INK,
    )

    generated_on = datetime.now().strftime('%b %d, %Y %I:%M %p')
    metadata_cards = [
        ('Employee #', str(employee['employee_id'])),
        ('Location', employee.get('location') or '-'),
        ('Current points', f"{float(employee.get('point_total') or 0.0):.1f}"),
        ('Last point', _fmt_date(employee.get('last_point_date'))),
        ('Roll-off', _fmt_date(employee.get('rolloff_date'))),
        ('Perfect attendance', _fmt_date(employee.get('perfect_attendance'))),
        ('History rows', str(len(history))),
        ('Generated', generated_on),
    ]
    meta_rows = []
    pair = []
    for index, (label, value) in enumerate(metadata_cards, start=1):
        pair.append(Paragraph(f'<font color="#5d7b94">{label}</font><br/><b>{value}</b>', meta_style))
        if index % 2 == 0:
            meta_rows.append(pair)
            pair = []

    meta_table = Table(meta_rows, colWidths=[1.95 * inch, 1.95 * inch, 1.95 * inch, 1.95 * inch])
    meta_table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), PDF_SURFACE),
                ('BOX', (0, 0), (-1, -1), 1, PDF_LINE),
                ('INNERGRID', (0, 0), (-1, -1), 0.75, PDF_LINE),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]
        )
    )

    story = [
        Paragraph('Attendance Point History', title_style),
        Paragraph(employee_name, subtitle_style),
        meta_table,
        Spacer(1, 0.18 * inch),
    ]

    if history:
        columns = ['Point Date', 'Points', 'Reason', 'Note', 'Running Total']
        table_rows = [[Paragraph(f'<b>{column}</b>', cell_style) for column in columns]]
        for row in history:
            table_rows.append(
                [
                    Paragraph(_normalize_value(_fmt_date(row.get('point_date'))), cell_style),
                    Paragraph(_normalize_value(round(float(row.get('points') or 0.0), 1)), cell_style),
                    Paragraph(_normalize_value(row.get('reason')), cell_style),
                    Paragraph(_normalize_value(row.get('note')), cell_style),
                    Paragraph(_normalize_value(round(float(row.get('point_total') or 0.0), 1)), cell_style),
                ]
            )
        table = Table(table_rows, colWidths=[1.35 * inch, 0.9 * inch, 1.9 * inch, 3.2 * inch, 1.15 * inch], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, 0), PDF_NAVY_ALT),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PDF_SURFACE]),
                    ('GRID', (0, 0), (-1, -1), 0.6, PDF_LINE),
                    ('BOX', (0, 0), (-1, -1), 0.8, PDF_LINE),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 7),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
                    ('LINEBELOW', (0, 0), (-1, 0), 1.2, PDF_CYAN),
                ]
            )
        )
        story.append(table)
    else:
        empty_style = ParagraphStyle(
            'EmployeeHistoryEmpty',
            parent=styles['BodyText'],
            fontName='Helvetica',
            fontSize=11,
            leading=15,
            textColor=PDF_MUTED,
        )
        story.append(Paragraph('No point history entries were found for this employee.', empty_style))

    page_decor = _build_page_decorator('Attendance Point History', employee_name)
    doc.build(story, onFirstPage=page_decor, onLaterPages=page_decor)
    filename = f"attendance-history-{int(employee['employee_id'])}-{safe_name}-{date.today().isoformat()}.pdf"
    return buffer.getvalue(), filename


def preview_filename(preview: dict, ext: str) -> str:
    return _make_filename(preview['report_type'], ext)
