import sqlite3

def ensure_schema(conn: sqlite3.Connection) -> None:
    """Idempotent schema creation/migration, matching ATP_Beta7."""
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            employee_id INTEGER PRIMARY KEY,
            last_name TEXT NOT NULL,
            first_name TEXT NOT NULL,
            point_total REAL DEFAULT 0.0,
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

    cur.execute("CREATE INDEX IF NOT EXISTS idx_emp_name ON employees(last_name, first_name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_points_emp ON points_history(employee_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_points_date ON points_history(point_date);")

    cols = [r[1] for r in cur.execute("PRAGMA table_info(employees)").fetchall()]
    if "Location" not in cols:
        cur.execute('ALTER TABLE employees ADD COLUMN "Location" TEXT;')

    try:
        cur.execute('CREATE INDEX IF NOT EXISTS idx_emp_loc_name ON employees("Location", last_name, first_name);')
    except Exception:
        pass

    conn.commit()
