from __future__ import annotations

from collections.abc import Generator

from atp_core import db as core_db
from atp_core.schema import ensure_schema


def get_db() -> Generator:
    conn = core_db.connect()
    ensure_schema(conn)
    try:
        yield conn
    finally:
        conn.close()
