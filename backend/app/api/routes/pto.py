from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from backend.app.api.deps import get_db
from backend.app.schemas.pto import PTOClearResult, PTOImportRequest, PTOImportResult, PTOOverview
from backend.app.services import pto

router = APIRouter(prefix='/pto', tags=['pto'])


def _parse_types(raw: str) -> list[str]:
    return [value.strip() for value in raw.split(',') if value.strip()]


@router.get('', response_model=PTOOverview)
def get_pto_overview(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    building: str = Query('All'),
    types: str = Query(''),
    conn=Depends(get_db),
) -> PTOOverview:
    try:
        payload = pto.get_pto_overview(
            conn,
            start_date_iso=start_date,
            end_date_iso=end_date,
            building=building,
            selected_types=_parse_types(types),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PTOOverview(**payload)


@router.post('/import', response_model=PTOImportResult, status_code=status.HTTP_201_CREATED)
def import_pto(payload: PTOImportRequest, conn=Depends(get_db)) -> PTOImportResult:
    result = pto.import_pto_rows(conn, [row.model_dump() for row in payload.rows])
    return PTOImportResult(**result)


@router.delete('/clear', response_model=PTOClearResult)
def clear_pto(conn=Depends(get_db)) -> PTOClearResult:
    return PTOClearResult(**pto.clear_pto_rows(conn))


@router.get('/export.csv')
def export_pto_csv(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    building: str = Query('All'),
    types: str = Query(''),
    conn=Depends(get_db),
) -> Response:
    try:
        rows = pto.get_pto_export_rows(
            conn,
            start_date_iso=start_date,
            end_date_iso=end_date,
            building=building,
            selected_types=_parse_types(types),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    csv_data = pto.export_rows_to_csv(rows)
    return Response(
        content=csv_data,
        media_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="pto-export.csv"'},
    )
