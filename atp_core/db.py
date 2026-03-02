import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

def _database_url() -> str:
    return (os.getenv("DATABASE_URL") or "").strip()

def _sqlite_path() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return str(repo_root / "employeeroster.db")

def get_db_path() -> str:
    """
    Backwards-compatible helper used by the Streamlit app for diagnostics.
    If using Postgres, return a sanitized descriptor (no credentials).
    If using SQLite, return the file path.
    """
    if _database_url():
        return "postgresql://<DATABASE_URL set>"
    return _sqlite_path()

def connect():
    """
    Returns a DB connection.
    - If DATABASE_URL is set => Postgres (persistent)
    - Else => SQLite (local dev fallback)
    """
    url = _database_url()
    if url:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2.connect(url, cursor_factory=RealDictCursor)

    path = Path(_sqlite_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(path),
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def tx(conn=None):
    """
    Transaction context manager that works for sqlite3 + psycopg2.
    """
    own = False
    if conn is None:
        conn = connect()
        own = True
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if own:
            conn.close()