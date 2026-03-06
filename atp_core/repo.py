from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .rules import calc_rolloff_and_perfect


def _is_pg(conn) -> bool:
    return conn.__class__.__module__.startswith("psycopg2")


def _adapt_sql(sql: str, pg: bool) -> str:
    if not pg:
        return sql
    return sql.replace("?", "%s")


def _fetchall(conn, sql: str, params=()):
    sql = _adapt_sql(sql, _is_pg(conn))
    if _is_pg(conn):
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows
    return conn.execute(sql, params).fetchall()


def _fetchone(conn, sql: str, params=()):
    sql = _adapt_sql(sql, _is_pg(conn))
    if _is_pg(conn):
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return row
    return conn.execute(sql, params).fetchone()


def _exec(conn, sql: str, params=()):
    sql = _adapt_sql(sql, _is_pg(conn))
    if _is_pg(conn):
        cur = conn.cursor()
        cur.execute(sql, params)
        cur.close()
        return
    conn.execute(sql, params)


def _row_get(row, key: str, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    return row[key] if key in row.keys() else default


def search_employees(conn, q: str, active_only: bool = True, limit: int = 50):
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
        SELECT employee_id, last_name, first_name, COALESCE("Location", '') AS location, is_active
        FROM employees
        {where_sql}
        ORDER BY lower(last_name), lower(first_name)
        LIMIT ?;
    """
    params.append(int(limit))
    return _fetchall(conn, sql, tuple(params))


def get_employee(conn, employee_id: int):
    return _fetchone(
        conn,
        """
        SELECT employee_id, last_name, first_name, COALESCE("Location", '') AS location,
               point_total, last_point_date, rolloff_date, perfect_attendance, point_warning_date, is_active
        FROM employees
        WHERE employee_id = ?;
        """,
        (int(employee_id),),
    )


def get_points_history(conn, employee_id: int, limit: int = 200):
    if _is_pg(conn):
        sql = """
            WITH ordered AS (
                SELECT
                    id,
                    point_date,
                    points,
                    reason,
                    note,
                    flag_code,
                    ROUND(
                        (
                            SUM(COALESCE(points, 0.0)) OVER (
                                PARTITION BY employee_id
                                ORDER BY (point_date::date), id
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                            )
                        )::numeric,
                        1
                    )::float8 AS point_total
                FROM points_history
                WHERE employee_id = %s
            )
            SELECT id, point_date, points, reason, note, flag_code, point_total
            FROM ordered
            ORDER BY (point_date::date) DESC, id DESC
            LIMIT %s;
        """
        return _fetchall(conn, sql, (int(employee_id), int(limit)))

    sql = """
        WITH ordered AS (
            SELECT
                id,
                point_date,
                points,
                reason,
                note,
                flag_code,
                ROUND(
                    SUM(COALESCE(points, 0.0)) OVER (
                        PARTITION BY employee_id
                        ORDER BY date(point_date), id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ),
                    1
                ) AS point_total
            FROM points_history
            WHERE employee_id = ?
        )
        SELECT id, point_date, points, reason, note, flag_code, point_total
        FROM ordered
        ORDER BY date(point_date) DESC, id DESC
        LIMIT ?;
    """
    return _fetchall(conn, sql, (int(employee_id), int(limit)))


def insert_points_history(conn, employee_id: int, point_date: date, points: float,
                          reason: str, note: str | None, flag_code: str | None):
    _exec(
        conn,
        """
        INSERT INTO points_history (employee_id, point_date, points, reason, note, flag_code)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (int(employee_id), point_date.isoformat(), float(points), reason, note, flag_code),
    )


def create_employee(conn, employee_id: int, last_name: str, first_name: str, location: str | None = None):
    _exec(
        conn,
        """
        INSERT INTO employees (employee_id, last_name, first_name, "Location", is_active)
        VALUES (?, ?, ?, ?, 1);
        """,
        (int(employee_id), str(last_name).strip(), str(first_name).strip(), (location or "").strip() or None),
    )


def delete_employee(conn, employee_id: int):
    _exec(conn, "DELETE FROM points_history WHERE employee_id = ?;", (int(employee_id),))
    _exec(conn, "DELETE FROM employees WHERE employee_id = ?;", (int(employee_id),))


def update_employee_point_total(conn, employee_id: int):
    if _is_pg(conn):
        total_row = _fetchone(
            conn,
            """
            SELECT ROUND((COALESCE(SUM(points), 0.0))::numeric, 3)::float8 AS total
            FROM points_history
            WHERE employee_id = %s;
            """,
            (int(employee_id),),
        )
        last_row = _fetchone(
            conn,
            """
            SELECT MAX(point_date::date)::text AS last_point_date
            FROM points_history
            WHERE employee_id = %s
              AND COALESCE(points, 0.0) > 0.0;
            """,
            (int(employee_id),),
        )
    else:
        total_row = _fetchone(
            conn,
            """
            SELECT ROUND(COALESCE(SUM(points), 0.0), 3) AS total
            FROM points_history
            WHERE employee_id = ?;
            """,
            (int(employee_id),),
        )
        last_row = _fetchone(
            conn,
            """
            SELECT MAX(date(point_date)) AS last_point_date
            FROM points_history
            WHERE employee_id = ?
              AND COALESCE(points, 0.0) > 0.0;
            """,
            (int(employee_id),),
        )

    total = float(_row_get(total_row, "total", 0.0) or 0.0)
    last_point_date = _row_get(last_row, "last_point_date")

    rolloff_date = None
    perfect_attendance = None
    if last_point_date:
        policy_dates = calc_rolloff_and_perfect(date.fromisoformat(str(last_point_date)))
        rolloff_date = policy_dates.rolloff_date.isoformat()
        perfect_attendance = policy_dates.perfect_date.isoformat()

    _exec(
        conn,
        """
        UPDATE employees
           SET point_total = ?,
               last_point_date = ?,
               rolloff_date = ?,
               perfect_attendance = ?
         WHERE employee_id = ?;
        """,
        (total, last_point_date, rolloff_date, perfect_attendance, int(employee_id)),
    )


def update_points_history_entry(conn, point_id: int, point_date: date, points: float,
                                reason: str, note: str | None, flag_code: str | None):
    _exec(
        conn,
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


def delete_points_history_entry(conn, point_id: int):
    _exec(conn, "DELETE FROM points_history WHERE id = ?;", (int(point_id),))


def report_rolloff_next_2_months(conn, start: date | None = None):
    start = start or date.today()
    end = start + timedelta(days=62)

    if _is_pg(conn):
        sql = """
            SELECT employee_id, last_name, first_name, COALESCE("Location", '') AS location,
                   COALESCE(point_total, 0) AS point_total,
                   rolloff_date
            FROM employees
            WHERE is_active = 1
              AND rolloff_date IS NOT NULL
              AND (rolloff_date::date) >= (%s::date)
              AND (rolloff_date::date) <= (%s::date)
              AND COALESCE(point_total, 0) > 0
            ORDER BY (rolloff_date::date), lower(last_name), lower(first_name);
        """
        return _fetchall(conn, sql, (start.isoformat(), end.isoformat()))

    sql = """
        SELECT employee_id, last_name, first_name, COALESCE("Location", '') AS location,
               COALESCE(point_total, 0) AS point_total,
               rolloff_date
        FROM employees
        WHERE is_active = 1
          AND rolloff_date IS NOT NULL
          AND date(rolloff_date) >= date(?)
          AND date(rolloff_date) <= date(?)
          AND COALESCE(point_total, 0) > 0
        ORDER BY date(rolloff_date), lower(last_name), lower(first_name);
    """
    return _fetchall(conn, sql, (start.isoformat(), end.isoformat()))


def report_perfect_attendance_upcoming(conn, start: date | None = None):
    start = start or date.today()
    end = start + timedelta(days=62)

    if _is_pg(conn):
        sql = """
            SELECT employee_id, last_name, first_name, COALESCE("Location", '') AS location,
                   COALESCE(point_total, 0) AS point_total,
                   perfect_attendance
            FROM employees
            WHERE is_active = 1
              AND perfect_attendance IS NOT NULL
              AND (perfect_attendance::date) >= (%s::date)
              AND (perfect_attendance::date) <= (%s::date)
            ORDER BY (perfect_attendance::date), lower(last_name), lower(first_name);
        """
        return _fetchall(conn, sql, (start.isoformat(), end.isoformat()))

    sql = """
        SELECT employee_id, last_name, first_name, COALESCE("Location", '') AS location,
               COALESCE(point_total, 0) AS point_total,
               perfect_attendance
        FROM employees
        WHERE is_active = 1
          AND perfect_attendance IS NOT NULL
          AND date(perfect_attendance) >= date(?)
          AND date(perfect_attendance) <= date(?)
        ORDER BY date(perfect_attendance), lower(last_name), lower(first_name);
    """
    return _fetchall(conn, sql, (start.isoformat(), end.isoformat()))


def report_points_last_30_days(conn, as_of: date | None = None):
    as_of = as_of or date.today()
    start = as_of - timedelta(days=30)

    if _is_pg(conn):
        sql = """
            SELECT ph.employee_id,
                   e.last_name, e.first_name, COALESCE(e."Location", '') AS location,
                   ph.point_date, ph.points, ph.reason, ph.note, ph.flag_code
            FROM points_history ph
            JOIN employees e ON e.employee_id = ph.employee_id
            WHERE (ph.point_date::date) >= (%s::date)
            ORDER BY (ph.point_date::date) DESC, ph.employee_id, ph.id DESC;
        """
        return _fetchall(conn, sql, (start.isoformat(),))

    sql = """
        SELECT ph.employee_id,
               e.last_name, e.first_name, COALESCE(e."Location", '') AS location,
               ph.point_date, ph.points, ph.reason, ph.note, ph.flag_code
        FROM points_history ph
        JOIN employees e ON e.employee_id = ph.employee_id
        WHERE date(ph.point_date) >= date(?)
        ORDER BY date(ph.point_date) DESC, ph.employee_id, ph.id DESC;
    """
    return _fetchall(conn, sql, (start.isoformat(),))


def save_pto_data(conn, rows: list) -> None:
    """Replace all stored PTO data with the provided rows (list of dicts)."""
    pg = _is_pg(conn)
    if pg:
        _exec(conn, "TRUNCATE pto_uploads;")
    else:
        _exec(conn, "DELETE FROM pto_uploads;")
    for row in rows:
        _exec(
            conn,
            """
            INSERT INTO pto_uploads (employee_id, last_name, first_name, building, pto_type, start_date, end_date, hours)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                row.get("employee_id"),
                str(row.get("last_name", "")).strip(),
                str(row.get("first_name", "")).strip(),
                str(row.get("building", "")).strip(),
                str(row.get("pto_type", "")).strip(),
                str(row.get("start_date", ""))[:10],
                str(row.get("end_date", ""))[:10],
                float(row.get("hours", 0) or 0),
            ),
        )


def load_pto_data(conn) -> list:
    """Return all stored PTO rows as a list of dicts. Empty list if none saved."""
    return _fetchall(
        conn,
        """
        SELECT employee_id, last_name, first_name, building, pto_type, start_date, end_date, hours
        FROM pto_uploads
        ORDER BY start_date, last_name, first_name;
        """,
    )


def clear_pto_data(conn) -> None:
    """Delete all stored PTO data."""
    _exec(conn, "DELETE FROM pto_uploads;")


def report_full_year_perfect_attendance(conn, year: int):
    start = date(year, 1, 1).isoformat()
    end = date(year + 1, 1, 1).isoformat()

    if _is_pg(conn):
        sql = """
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
                    AND (ph.point_date::date) >= (%s::date)
                    AND (ph.point_date::date) < (%s::date)
              )
            ORDER BY lower(e.last_name), lower(e.first_name);
        """
        return _fetchall(conn, sql, (start, end))

    sql = """
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
                AND date(ph.point_date) < date(?)
          )
        ORDER BY lower(e.last_name), lower(e.first_name);
    """
    return _fetchall(conn, sql, (start, end))
