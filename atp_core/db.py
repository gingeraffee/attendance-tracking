import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

def get_db_path() -> str:
    p = (os.getenv("ATP_DB_PATH") or "").strip()
    if p:
        return p
    repo_root = Path(__file__).resolve().parents[1]
    return str(repo_root / "employeeroster.db")

def connect(db_path: str | None = None) -> sqlite3.Connection:
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

@contextmanager
def tx(conn=None, db_path: str | None = None):
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