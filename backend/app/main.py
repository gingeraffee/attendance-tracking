from __future__ import annotations

from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from backend.app.api.routes import attendance, exports, health, pto  # noqa: E402

app = FastAPI(
    title='Attendance Tracking API',
    version='0.1.0',
    description='FastAPI backend for the attendance tracking migration.',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(health.router, prefix='/api/v1')
app.include_router(attendance.router, prefix='/api/v1')
app.include_router(exports.router, prefix='/api/v1')
app.include_router(pto.router, prefix='/api/v1')


@app.get('/')
def root() -> dict[str, str]:
    return {'name': 'attendance-tracking-api', 'docs': '/docs'}
