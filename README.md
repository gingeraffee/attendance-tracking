# ATP Web Migration Workspace

This repo now supports the current Streamlit app and the first migration pass toward `FastAPI + Next.js`.

## Current apps

- `atp_streamlit/`: current production fallback UI
- `backend/`: FastAPI API layer reusing `atp_core`
- `frontend/`: Next.js app-router shell for the new UI
- `atp_core/`: shared attendance rules, data access, and recalculation logic

## Streamlit fallback

```powershell
python -m streamlit run atp_streamlit/app.py
```

## FastAPI backend

```powershell
python -m uvicorn backend.app.main:app --reload --port 8000
```

## Next.js frontend

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

## Deployment approach

Keep Streamlit operational while the new stack grows in parallel. The migration should be additive until the new frontend reaches feature parity.
