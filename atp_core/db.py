import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

def _get_database_url() -> str:
    # Streamlit secrets appear as env vars too
    return (os.getenv("DATABASE_URL") or "").strip()

def _sqlite_path() -> str:
    # Local fallback only
    repo_root = Path(__file__).resolve().parents[1]
    return str(repo_root / "employeeroster.db")

def connect():
    """
    Returns a DB connection.
    - If DATABASE_URL is set => Postgres (persistent).
    - Else => SQLite (local dev fallback).
    """
    db_url = _get_database_url()
    if db_url:
        import psycopg2
        conn = psycopg2.connect(db_url)
        return conn

    # SQLite fallback
    path = Path(_sqlite_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def tx(conn=None):
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
