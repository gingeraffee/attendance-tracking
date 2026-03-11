from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.deps import get_db
from backend.app.schemas.attendance import (
    CorrectiveActionEmployee,
    CorrectiveActionOverview,
    CorrectiveActionUpdateRequest,
    DashboardDetail,
    DashboardSummary,
    EmployeeCreateRequest,
    EmployeeDetail,
    EmployeeSummary,
    EmployeeUpdateRequest,
    MaintenanceJobResult,
    MaintenanceRunRequest,
    MutationResult,
    PointHistoryEntry,
    PointMutationRequest,
)
from backend.app.services import attendance

router = APIRouter(prefix='/attendance', tags=['attendance'])


@router.get('/dashboard', response_model=DashboardSummary)
def get_dashboard(conn=Depends(get_db)) -> DashboardSummary:
    return DashboardSummary(**attendance.dashboard_summary(conn))


@router.get('/dashboard/detail', response_model=DashboardDetail)
def get_dashboard_detail(conn=Depends(get_db)) -> DashboardDetail:
    return DashboardDetail(**attendance.dashboard_detail(conn))


@router.get('/corrective-actions', response_model=CorrectiveActionOverview)
def get_corrective_actions(conn=Depends(get_db)) -> CorrectiveActionOverview:
    return CorrectiveActionOverview(**attendance.list_corrective_actions(conn))


@router.patch('/corrective-actions/{employee_id}', response_model=CorrectiveActionEmployee)
def update_corrective_action(employee_id: int, payload: CorrectiveActionUpdateRequest, conn=Depends(get_db)) -> CorrectiveActionEmployee:
    try:
        result = attendance.update_corrective_action_date(conn, employee_id, payload.point_warning_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CorrectiveActionEmployee(**result)



@router.post('/employees', response_model=EmployeeDetail, status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeCreateRequest, conn=Depends(get_db)) -> EmployeeDetail:
    try:
        row = attendance.create_employee_record(conn, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EmployeeDetail(**row)


@router.patch('/employees/{employee_id}', response_model=EmployeeDetail)
def update_employee(employee_id: int, payload: EmployeeUpdateRequest, conn=Depends(get_db)) -> EmployeeDetail:
    try:
        row = attendance.update_employee_record(conn, employee_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EmployeeDetail(**row)


@router.delete('/employees/{employee_id}', status_code=status.HTTP_200_OK)
def delete_employee(employee_id: int, conn=Depends(get_db)) -> dict[str, bool]:
    try:
        attendance.delete_employee_record(conn, employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {'ok': True}


@router.get('/employees', response_model=list[EmployeeSummary])
def get_employees(
    q: str = Query('', description='Search by employee id or name'),
    building: str = Query('All'),
    conn=Depends(get_db),
) -> list[EmployeeSummary]:
    return [EmployeeSummary(**row) for row in attendance.list_employees(conn, q=q, building=building)]


@router.get('/employees/{employee_id}', response_model=EmployeeDetail)
def get_employee(employee_id: int, conn=Depends(get_db)) -> EmployeeDetail:
    row = attendance.get_employee_detail(conn, employee_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Employee not found')
    return EmployeeDetail(**row)


@router.get('/employees/{employee_id}/history', response_model=list[PointHistoryEntry])
def get_employee_history(employee_id: int, limit: int = 200, conn=Depends(get_db)) -> list[PointHistoryEntry]:
    return [PointHistoryEntry(**row) for row in attendance.get_employee_history(conn, employee_id, limit=limit)]


@router.post('/employees/{employee_id}/points', response_model=MutationResult)
def create_point(employee_id: int, payload: PointMutationRequest, conn=Depends(get_db)) -> MutationResult:
    try:
        result = attendance.create_point(conn, employee_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MutationResult(**result)


@router.patch('/employees/{employee_id}/points/{point_id}', response_model=MutationResult)
def update_point(employee_id: int, point_id: int, payload: PointMutationRequest, conn=Depends(get_db)) -> MutationResult:
    try:
        result = attendance.update_point(conn, employee_id, point_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MutationResult(**result)


@router.delete('/employees/{employee_id}/points/{point_id}', response_model=MutationResult)
def delete_point(employee_id: int, point_id: int, conn=Depends(get_db)) -> MutationResult:
    try:
        result = attendance.delete_point(conn, employee_id, point_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MutationResult(**result)


@router.post('/employees/{employee_id}/recalculate', response_model=MutationResult)
def recalculate_employee(employee_id: int, conn=Depends(get_db)) -> MutationResult:
    result = attendance.recalculate_employee(conn, employee_id)
    return MutationResult(**result)


@router.post('/recalculate', response_model=DashboardSummary)
def recalculate_all(conn=Depends(get_db)) -> DashboardSummary:
    return DashboardSummary(**attendance.recalculate_all(conn))


@router.post('/maintenance/rolloffs', response_model=MaintenanceJobResult)
def run_rolloffs(payload: MaintenanceRunRequest, conn=Depends(get_db)) -> MaintenanceJobResult:
    return MaintenanceJobResult(**attendance.run_two_month_rolloffs(conn, payload.run_date, payload.dry_run))


@router.post('/maintenance/perfect-attendance', response_model=MaintenanceJobResult)
def run_perfect_attendance(payload: MaintenanceRunRequest, conn=Depends(get_db)) -> MaintenanceJobResult:
    return MaintenanceJobResult(**attendance.run_perfect_attendance_advancement(conn, payload.run_date, payload.dry_run))


@router.post('/maintenance/ytd-rolloffs', response_model=MaintenanceJobResult)
def run_ytd_rolloffs(payload: MaintenanceRunRequest, conn=Depends(get_db)) -> MaintenanceJobResult:
    return MaintenanceJobResult(**attendance.run_ytd_rolloffs(conn, payload.run_date, payload.dry_run))
