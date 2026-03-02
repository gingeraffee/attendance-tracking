# atp_core/db.py
import os
import sqlite3
from pathlib import Path

def get_db_path() -> str:
    return os.getenv("ATP_DB_PATH", "employeeroster.db")

def connect(db_path: str | None = None) -> sqlite3.Connection:
    raw = db_path or get_db_path()
    path = Path(raw)

    # Debug-friendly checks
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise RuntimeError(
            f"mkdir failed for parent={parent} (raw path={raw}). "
            f"Parent exists={parent.exists()} is_dir={parent.is_dir()} "
            f"/var/data exists={Path('/var/data').exists()} "
            f"ATP_DB_PATH={os.getenv('ATP_DB_PATH')!r}. "
            f"Error={repr(e)}"
        ) from e

    conn = sqlite3.connect(
        str(path),
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
