from __future__ import annotations
import sqlite3

def _is_pg(conn) -> bool:
    return conn.__class__.__module__.startswith("psycopg2")

def ensure_schema(conn):
    """
    Create tables/indexes if needed.
    - SQLite: original schema + PRAGMA migration
    - Postgres: Postgres-safe schema
    """
    if _is_pg(conn):
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            employee_id BIGINT PRIMARY KEY,
            last_name TEXT NOT NULL,
            first_name TEXT NOT NULL,
            start_date TEXT,
            point_total DOUBLE PRECISION DEFAULT 0.0,
            last_point_date TEXT,
            rolloff_date TEXT,
            perfect_attendance TEXT,
            point_warning_date TEXT,
            is_active INTEGER DEFAULT 1,
            "Location" TEXT,
            manager TEXT
        );
        """)

        cur.execute('ALTER TABLE employees ADD COLUMN IF NOT EXISTS start_date TEXT;')
        cur.execute('ALTER TABLE employees ADD COLUMN IF NOT EXISTS manager TEXT;')

        cur.execute("""
        CREATE TABLE IF NOT EXISTS points_history (
            id BIGSERIAL PRIMARY KEY,
            employee_id BIGINT NOT NULL REFERENCES employees(employee_id),
            point_date TEXT NOT NULL,
            points DOUBLE PRECISION NOT NULL,
            reason TEXT,
            note TEXT,
            flag_code TEXT
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS pto_uploads (
            id BIGSERIAL PRIMARY KEY,
            employee_id BIGINT,
            last_name TEXT NOT NULL,
            first_name TEXT NOT NULL,
            building TEXT,
            pto_type TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            hours DOUBLE PRECISION DEFAULT 0.0
        );
        """)

        # Indexes (idempotent)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_emp_name ON employees(last_name, first_name);")
        cur.execute('CREATE INDEX IF NOT EXISTS idx_emp_loc_name ON employees("Location", last_name, first_name);')
        cur.execute("CREATE INDEX IF NOT EXISTS idx_points_emp ON points_history(employee_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_points_date ON points_history(point_date);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pto_emp ON pto_uploads(employee_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pto_dates ON pto_uploads(start_date, end_date);")

        conn.commit()
        return

    # ---------------- SQLite branch (your original behavior) ----------------
    assert isinstance(conn, sqlite3.Connection)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            employee_id INTEGER PRIMARY KEY,
            last_name TEXT NOT NULL,
            first_name TEXT NOT NULL,
            start_date TEXT,
            point_total REAL DEFAULT 0,
            last_point_date TEXT,
            rolloff_date TEXT,
            perfect_attendance TEXT,
            point_warning_date TEXT,
            is_active INTEGER DEFAULT 1
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS points_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            point_date TEXT NOT NULL,
            points REAL NOT NULL,
            reason TEXT,
            note TEXT,
            flag_code TEXT,
            FOREIGN KEY(employee_id) REFERENCES employees(employee_id)
        );
    """)

    # Migration: add Location column if missing
    cur.execute("PRAGMA table_info(employees);")
    cols = [r[1] for r in cur.fetchall()]
    if "Location" not in cols:
        cur.execute('ALTER TABLE employees ADD COLUMN "Location" TEXT;')
    if "start_date" not in cols:
        cur.execute('ALTER TABLE employees ADD COLUMN start_date TEXT;')
    if "manager" not in cols:
        cur.execute('ALTER TABLE employees ADD COLUMN manager TEXT;')

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pto_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            last_name TEXT NOT NULL,
            first_name TEXT NOT NULL,
            building TEXT,
            pto_type TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            hours REAL DEFAULT 0.0
        );
    """)

    # Indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_emp_name ON employees(last_name, first_name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_points_emp ON points_history(employee_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_points_date ON points_history(point_date);")
    cur.execute('CREATE INDEX IF NOT EXISTS idx_emp_loc_name ON employees("Location", last_name, first_name);')
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pto_emp ON pto_uploads(employee_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pto_dates ON pto_uploads(start_date, end_date);")

    conn.commit()
