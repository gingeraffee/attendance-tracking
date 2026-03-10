# Attendance Tracking Backend

This backend is the first migration step away from Streamlit. It reuses the existing `atp_core` attendance rules and exposes them through FastAPI.

## Run locally

```powershell
python -m uvicorn backend.app.main:app --reload --port 8000
```

## Initial endpoints

- `GET /api/v1/health`
- `GET /api/v1/attendance/dashboard`
- `GET /api/v1/attendance/employees`
- `GET /api/v1/attendance/employees/{employee_id}`
- `GET /api/v1/attendance/employees/{employee_id}/history`
- `POST /api/v1/attendance/employees/{employee_id}/points`
- `PATCH /api/v1/attendance/employees/{employee_id}/points/{point_id}`
- `DELETE /api/v1/attendance/employees/{employee_id}/points/{point_id}`
- `POST /api/v1/attendance/employees/{employee_id}/recalculate`
- `POST /api/v1/attendance/recalculate`
