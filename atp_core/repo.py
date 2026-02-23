from __future__ import annotations
import sqlite3
from datetime import date, timedelta
from typing import Any

from .rules import calc_rolloff_and_perfect

def search_employees(conn: sqlite3.Connection, q: str, active_only: bool = True, limit: int = 50):
    q = (q or "").strip()
    where = []
    params: list[Any] = []
    if active_only:
        where.append("is_active = 1")
    if q:
        where.append("(CAST(employee_id AS TEXT) LIKE ? OR last_name LIKE ? OR first_name LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS location, is_active
        FROM employees
        {where_sql}
        ORDER BY last_name COLLATE NOCASE, first_name COLLATE NOCASE
        LIMIT ?;
    """
    params.append(limit)
    return conn.execute(sql, params).fetchall()

def get_employee(conn: sqlite3.Connection, employee_id: int):
    return conn.execute("""
        SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS location,
               point_total, last_point_date, rolloff_date, perfect_attendance, point_warning_date, is_active
        FROM employees
        WHERE employee_id = ?;
    """, (employee_id,)).fetchone()

def get_points_history(conn: sqlite3.Connection, employee_id: int, limit: int = 200):
    return conn.execute("""
        WITH ordered AS (
            SELECT
                id,
                point_date,
                points,
                reason,
                note,
                flag_code,
                ROUND(SUM(COALESCE(points, 0.0)) OVER (
                    PARTITION BY employee_id
                    ORDER BY date(point_date), id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ), 1) AS point_total
            FROM points_history
            WHERE employee_id = ?
        )
        SELECT id, point_date, points, reason, note, flag_code, point_total
        FROM ordered
        ORDER BY date(point_date) DESC, id DESC
        LIMIT ?;
    """, (employee_id, limit)).fetchall()

def insert_points_history(conn: sqlite3.Connection, employee_id: int, point_date: date, points: float,
                         reason: str, note: str | None, flag_code: str | None):
    conn.execute("""
        INSERT INTO points_history (employee_id, point_date, points, reason, note, flag_code)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (employee_id, point_date.isoformat(), float(points), reason, note, flag_code))

def create_employee(
    conn: sqlite3.Connection,
    employee_id: int,
    last_name: str,
    first_name: str,
    location: str | None = None,
):
    conn.execute(
        """
        INSERT INTO employees (employee_id, last_name, first_name, "Location", is_active)
        VALUES (?, ?, ?, ?, 1);
        """,
        (int(employee_id), str(last_name).strip(), str(first_name).strip(), (location or "").strip() or None),
    )

def delete_employee(conn: sqlite3.Connection, employee_id: int):
    conn.execute("DELETE FROM points_history WHERE employee_id = ?;", (int(employee_id),))
    conn.execute("DELETE FROM employees WHERE employee_id = ?;", (int(employee_id),))

def update_employee_point_total(conn: sqlite3.Connection, employee_id: int):
    row = conn.execute("""
        SELECT ROUND(COALESCE(SUM(points),0.0), 3) AS total
        FROM points_history
        WHERE employee_id = ?;
    """, (employee_id,)).fetchone()
    total = float(row["total"] or 0.0)

    last_positive = conn.execute(
        """
        SELECT MAX(date(point_date)) AS last_point_date
        FROM points_history
        WHERE employee_id = ?
          AND COALESCE(points, 0.0) > 0.0;
        """,
        (employee_id,),
    ).fetchone()
    last_point_date = last_positive["last_point_date"]

    if last_point_date:
        policy_dates = calc_rolloff_and_perfect(date.fromisoformat(last_point_date))
        rolloff_date = policy_dates.rolloff_date.isoformat()
        perfect_attendance = policy_dates.perfect_date.isoformat()
    else:
        rolloff_date = None
        perfect_attendance = None

    conn.execute("""
        UPDATE employees
           SET point_total = ?,
               last_point_date = ?,
               rolloff_date = ?,
               perfect_attendance = ?
         WHERE employee_id = ?;
    """, (total, last_point_date, rolloff_date, perfect_attendance, employee_id))


def update_points_history_entry(
    conn: sqlite3.Connection,
    point_id: int,
    point_date: date,
    points: float,
    reason: str,
    note: str | None,
    flag_code: str | None,
):
    conn.execute(
        """
        UPDATE points_history
           SET point_date = ?,
               points = ?,
               reason = ?,
               note = ?,
               flag_code = ?
         WHERE id = ?;
        """,
        (
            point_date.isoformat(),
            float(points),
            str(reason).strip(),
            (note or "").strip() or None,
            (flag_code or "").strip() or None,
            int(point_id),
        ),
    )


def delete_points_history_entry(conn: sqlite3.Connection, point_id: int):
    conn.execute("DELETE FROM points_history WHERE id = ?;", (int(point_id),))

def report_rolloff_next_2_months(conn: sqlite3.Connection, start: date | None = None):
    start = start or date.today()
    end = start + timedelta(days=62)

    return conn.execute("""
        SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS location,
               COALESCE(point_total, 0) AS point_total,
               rolloff_date
        FROM employees
        WHERE is_active = 1
          AND rolloff_date IS NOT NULL
          AND date(rolloff_date) >= date(?)
          AND date(rolloff_date) <= date(?)
          AND COALESCE(point_total, 0) > 0
        ORDER BY date(rolloff_date), last_name COLLATE NOCASE, first_name COLLATE NOCASE;
    """, (start.isoformat(), end.isoformat())).fetchall()

def report_perfect_attendance_upcoming(conn: sqlite3.Connection, start: date | None = None):
    start = start or date.today()
    end = start + timedelta(days=62)

    return conn.execute("""
        SELECT employee_id, last_name, first_name, COALESCE("Location",'') AS location,
               COALESCE(point_total, 0) AS point_total,
               perfect_attendance
        FROM employees
        WHERE is_active = 1
          AND perfect_attendance IS NOT NULL
          AND date(perfect_attendance) >= date(?)
          AND date(perfect_attendance) <= date(?)
        ORDER BY date(perfect_attendance), last_name COLLATE NOCASE, first_name COLLATE NOCASE;
    """, (start.isoformat(), end.isoformat())).fetchall()

def report_points_last_30_days(conn: sqlite3.Connection, as_of: date | None = None):
    as_of = as_of or date.today()
    start = as_of - timedelta(days=30)

    return conn.execute("""
        SELECT ph.employee_id,
               e.last_name, e.first_name, COALESCE(e."Location",'') AS location,
               ph.point_date, ph.points, ph.reason, ph.note, ph.flag_code
        FROM points_history ph
        JOIN employees e ON e.employee_id = ph.employee_id
        WHERE date(ph.point_date) >= date(?)
        ORDER BY date(ph.point_date) DESC, ph.employee_id, ph.id DESC;
    """, (start.isoformat(),)).fetchall()

def report_full_year_perfect_attendance(conn: sqlite3.Connection, year: int):
    start = date(year, 1, 1).isoformat()
    end = date(year + 1, 1, 1).isoformat()
    return conn.execute("""
        SELECT
            e.employee_id,
            e.last_name,
            e.first_name,
            COALESCE(e."Location", '') AS location
        FROM employees e
        WHERE e.is_active = 1
          AND NOT EXISTS (
              SELECT 1
              FROM points_history ph
              WHERE ph.employee_id = e.employee_id
                AND COALESCE(ph.points, 0.0) > 0
                AND date(ph.point_date) >= date(?)
                AND date(ph.point_date) <  date(?)
          )
        ORDER BY e.last_name COLLATE NOCASE, e.first_name COLLATE NOCASE;
    """, (start, end)).fetchall()
