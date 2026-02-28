import os
import sqlite3
from contextlib import contextmanager

DEFAULT_DB_FILENAME = "employeeroster.db"

def get_db_path() -> str:
    env = os.getenv("ATP_DB_PATH")
    if env:
        return env
    return "/var/data/employeeroster.db"  # Render persistent disk)

def connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def tx(conn: sqlite3.Connection):
    try:
        conn.execute("BEGIN;")
        yield
        conn.commit()
    except Exception:
        conn.rollback()
        raise
