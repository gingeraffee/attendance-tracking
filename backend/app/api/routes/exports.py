from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from backend.app.api.deps import get_db
from backend.app.schemas.exports import ExportPreview, ExportReportType
from backend.app.services import exports

router = APIRouter(prefix='/exports', tags=['exports'])


def _coerce_dates(start_date: str | None, end_date: str | None) -> tuple[date, date]:
    today = date.today()
    start = date.fromisoformat(start_date) if start_date else today - timedelta(days=30)
    end = date.fromisoformat(end_date) if end_date else today + timedelta(days=60)
    if end < start:
        raise HTTPException(status_code=400, detail='End date cannot be before start date.')
    return start, end


@router.get('/preview', response_model=ExportPreview)
def get_export_preview(
    report_type: ExportReportType = Query(...),
    building: str = Query('All'),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    conn=Depends(get_db),
) -> ExportPreview:
    try:
        start, end = _coerce_dates(start_date, end_date)
        payload = exports.build_export_preview(conn, report_type, building, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExportPreview(**payload)


@router.get('/download.csv')
def download_export_csv(
    report_type: ExportReportType = Query(...),
    building: str = Query('All'),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    conn=Depends(get_db),
) -> Response:
    try:
        start, end = _coerce_dates(start_date, end_date)
        preview = exports.build_export_preview(conn, report_type, building, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filename = exports.preview_filename(preview, 'csv')
    return Response(
        content=exports.build_csv_bytes(preview),
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@router.get('/employee-history/{employee_id}.pdf')
def download_employee_history_pdf(employee_id: int, conn=Depends(get_db)) -> Response:
    try:
        pdf_bytes, filename = exports.build_employee_history_pdf(conn, employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@router.get('/download.pdf')
def download_export_pdf(
    report_type: ExportReportType = Query(...),
    building: str = Query('All'),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    conn=Depends(get_db),
) -> Response:
    try:
        start, end = _coerce_dates(start_date, end_date)
        preview = exports.build_export_preview(conn, report_type, building, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filename = exports.preview_filename(preview, 'pdf')
    return Response(
        content=exports.build_pdf_bytes(preview),
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
