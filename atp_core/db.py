# atp_core/db.py
import os
import sqlite3
from pathlib import Path

def get_db_path() -> str:
    # env override (Render)
    return os.getenv("ATP_DB_PATH", "employeeroster.db")

def connect(db_path: str | None = None) -> sqlite3.Connection:
    path = Path(db_path or get_db_path())

    # Ensure parent directory exists
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise RuntimeError(
            f"Cannot create DB directory: {path.parent}\n"
            f"ATP_DB_PATH={os.getenv('ATP_DB_PATH')}\n"
            f"Working dir={os.getcwd()}\n"
            f"Original error: {e}"
        ) from e

    # Connect
    try:
        conn = sqlite3.connect(
            str(path),
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False
        )
    except Exception as e:
        raise RuntimeError(
            f"Cannot open DB file: {path}\n"
            f"Parent exists={path.parent.exists()} writable={os.access(str(path.parent), os.W_OK)}\n"
            f"ATP_DB_PATH={os.getenv('ATP_DB_PATH')}\n"
            f"Working dir={os.getcwd()}\n"
            f"Original error: {e}"
        ) from e

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
