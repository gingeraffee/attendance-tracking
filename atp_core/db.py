import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager


@contextmanager
def tx(conn=None, db_path: str | None = None):
    """
    Transaction context manager.

    Usage:
        with tx(conn) as c:
            ... use c ...
        # commits on success, rolls back on error

    If conn is None, opens/closes its own connection.
    """
    own = False
    if conn is None:
        conn = connect(db_path=db_path)
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
            
            
def get_db_path() -> str:
    """
    Return the SQLite DB path.
    Uses ATP_DB_PATH if set (Render persistent disk).
    Falls back to repo-root employeeroster.db for local dev.
    Treats blank env var as unset.
    """
    p = (os.getenv("ATP_DB_PATH") or "").strip()
    if p:
        return p
    repo_root = Path(__file__).resolve().parents[1]
    return str(repo_root / "employeeroster.db")

def connect(db_path: str | None = None) -> sqlite3.Connection:
    """
    Connect to SQLite database, ensuring parent directory exists.
    """
    path_str = (db_path or get_db_path())
    path = Path(path_str)

    # Ensure parent directory exists (SQLite won't create directories)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(path),
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn