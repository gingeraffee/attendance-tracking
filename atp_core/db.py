import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

def _database_url() -> str:
    return (os.getenv("DATABASE_URL") or "").strip()

def _sqlite_path() -> str:
    configured = (os.getenv("SQLITE_PATH") or "").strip()
    if configured:
        path = Path(configured)
        if path.suffix.lower() == ".db":
            return str(path)
        return str(path / "employeeroster.db")

    for env_name in ("RENDER_DISK_PATH", "DATA_DIR"):
        base = (os.getenv(env_name) or "").strip()
        if base:
            return str(Path(base) / "employeeroster.db")

    render_default = Path("/var/data")
    if render_default.exists():
        return str(render_default / "employeeroster.db")

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
    - If DATABASE_URL is set => Postgres (autocommit=True so a failed read
      query never poisons the shared cached connection for subsequent queries)
    - Else => SQLite (local dev fallback)
    """
    url = _database_url()
    if url:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
        conn.autocommit = True
        return conn

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

    For psycopg2 connections running in autocommit mode (the default set by
    connect() above), this temporarily disables autocommit so the block runs
    as a single atomic transaction, then restores autocommit on exit.
    """
    own = False
    if conn is None:
        conn = connect()
        own = True

    was_autocommit = getattr(conn, 'autocommit', False)
    if was_autocommit:
        conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if was_autocommit:
            conn.autocommit = True
        if own:
            conn.close()
