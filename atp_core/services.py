from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
import sqlite3

from .db import tx
from . import repo

# ---------------------------------------------------------------------------
# Date helpers (ported directly from ATP_Beta7)
# ---------------------------------------------------------------------------

def _add_months(orig: date, months: int) -> date:
    """Add calendar months to a date, clamping the day if needed."""
    y = orig.year + (orig.month - 1 + months) // 12
    m = (orig.month - 1 + months) % 12 + 1
    if m in (1, 3, 5, 7, 8, 10, 12):
        dim = 31
    elif m in (4, 6, 9, 11):
        dim = 30
    else:
        leap = (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
        dim = 29 if leap else 28
    d = min(orig.day, dim)
    return date(y, m, d)


def _first_of_next_month(d: date) -> date:
    """Return the first day of the month following d."""
    y = d.year + (1 if d.month == 12 else 0)
    m = 1 if d.month == 12 else d.month + 1
    return date(y, m, 1)


def _calc_rolloff_and_perfect(last_point: date) -> tuple[date, date]:
    """
    Core policy logic (mirrors Beta7 calc_rolloff_and_perfect):
      - Rolloff  = first day of the month after (last_point + 2 months)
      - Perfect  = first day of the month after (last_point + 3 months)

    Example:
      last_point = 2026-01-15
      rolloff    = 2026-04-01  (Jan+2=Mar, first of next = Apr 1)
      perfect    = 2026-05-01  (Jan+3=Apr, first of next = May 1)
    """
    roll_mark = _add_months(last_point, 2)
    perf_mark = _add_months(last_point, 3)
    return _first_of_next_month(roll_mark), _first_of_next_month(perf_mark)


# ---------------------------------------------------------------------------
# Core recalculation (mirrors Beta7 recompute_employee_after_change)
# ---------------------------------------------------------------------------

def recalculate_employee_dates(conn: sqlite3.Connection, employee_id: int) -> None:
    """
    Recompute point_total, last_point_date, rolloff_date, and perfect_attendance
    for one employee from their points_history.

    Mirrors the Beta7 recompute_employee_after_change() logic exactly:
      - Uses MAX(point_date) across ALL entries (positive and negative)
      - If history exists: recalculates both dates from last_point_date
      - If no history remains: clears all three date fields, sets total to 0.0
      - Point total is always floored at 0.0
    """
    row = conn.execute(
        """
        SELECT MAX(point_date) AS last_date,
               SUM(points)     AS total
        FROM points_history
        WHERE employee_id = ?
        """,
        (employee_id,),
    ).fetchone()

    new_total = float(row["total"]) if row["total"] is not None else 0.0
    new_total = max(0.0, round(new_total, 1))   # floor at 0.0
    last_date_iso = row["last_date"]

    if not last_date_iso:
        # No history at all — clear everything
        conn.execute(
            """
            UPDATE employees
               SET point_total        = ?,
                   last_point_date    = NULL,
                   rolloff_date       = NULL,
                   perfect_attendance = NULL
             WHERE employee_id = ?
            """,
            (new_total, employee_id),
        )
    else:
        last_point = datetime.strptime(last_date_iso, "%Y-%m-%d").date()
        rolloff, perfect = _calc_rolloff_and_perfect(last_point)
        conn.execute(
            """
            UPDATE employees
               SET point_total        = ?,
                   last_point_date    = ?,
                   rolloff_date       = ?,
                   perfect_attendance = ?
             WHERE employee_id = ?
            """,
            (
                new_total,
                last_date_iso,
                rolloff.isoformat(),
                perfect.isoformat(),
                employee_id,
            ),
        )


# ---------------------------------------------------------------------------
# Data transfer object
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AddPointPreview:
    employee_id: int
    point_date: date
    points: float
    reason: str
    note: str


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

def preview_add_point(
    employee_id: int,
    point_date: date,
    points: float,
    reason: str,
    note: str | None,
) -> AddPointPreview:
    if employee_id is None:
        raise ValueError("Employee is required.")
    if points is None:
        raise ValueError("Points are required.")
    if reason is None or not str(reason).strip():
        raise ValueError("Reason is required.")
    if point_date > date.today():
        raise ValueError("Point date cannot be in the future.")
    note_clean = (note or "").strip()
    return AddPointPreview(
        employee_id=int(employee_id),
        point_date=point_date,
        points=float(points),
        reason=str(reason).strip(),
        note=note_clean,
    )


def add_point(
    conn: sqlite3.Connection,
    preview: AddPointPreview,
    flag_code: str | None = None,
) -> None:
    """Insert a history row and recompute all employee date fields."""
    with tx(conn):
        repo.insert_points_history(
            conn,
            employee_id=preview.employee_id,
            point_date=preview.point_date,
            points=preview.points,
            reason=preview.reason,
            note=preview.note or None,
            flag_code=flag_code,
        )
        recalculate_employee_dates(conn, preview.employee_id)


def update_point_history_entry(
    conn: sqlite3.Connection,
    point_id: int,
    employee_id: int,
    point_date: date,
    points: float,
    reason: str,
    note: str | None,
    flag_code: str | None = None,
) -> None:
    if point_id is None:
        raise ValueError("Point history row is required.")
    if employee_id is None:
        raise ValueError("Employee is required.")
    if points is None:
        raise ValueError("Points are required.")
    if reason is None or not str(reason).strip():
        raise ValueError("Reason is required.")
    if point_date > date.today():
        raise ValueError("Point date cannot be in the future.")

    with tx(conn):
        repo.update_points_history_entry(
            conn,
            point_id=int(point_id),
            point_date=point_date,
            points=float(points),
            reason=str(reason).strip(),
            note=(note or "").strip() or None,
            flag_code=(flag_code or "").strip() or None,
        )
        # Recalculate total, last_point_date, rolloff_date, and perfect_attendance
        recalculate_employee_dates(conn, int(employee_id))


def delete_point_history_entry(
    conn: sqlite3.Connection,
    point_id: int,
    employee_id: int,
) -> None:
    if point_id is None:
        raise ValueError("Point history row is required.")
    if employee_id is None:
        raise ValueError("Employee is required.")

    with tx(conn):
        repo.delete_points_history_entry(conn, int(point_id))
        # Recalculate total, last_point_date, rolloff_date, and perfect_attendance
        recalculate_employee_dates(conn, int(employee_id))


def create_employee(
    conn: sqlite3.Connection,
    employee_id: int,
    last_name: str,
    first_name: str,
    location: str | None = None,
) -> None:
    if employee_id is None:
        raise ValueError("Employee ID is required.")
    if not str(last_name or "").strip():
        raise ValueError("Last name is required.")
    if not str(first_name or "").strip():
        raise ValueError("First name is required.")

    with tx(conn):
        repo.create_employee(
            conn,
            employee_id=int(employee_id),
            last_name=str(last_name).strip(),
            first_name=str(first_name).strip(),
            location=(location or "").strip(),
        )


def delete_employee(conn: sqlite3.Connection, employee_id: int) -> None:
    if employee_id is None:
        raise ValueError("Employee ID is required.")

    emp = repo.get_employee(conn, int(employee_id))
    if not emp:
        raise ValueError("Employee not found.")

    with tx(conn):
        repo.delete_employee(conn, int(employee_id))


# ---------------------------------------------------------------------------
# YTD Roll-Off Engine (preserved from original, duplicate helpers removed)
# ---------------------------------------------------------------------------

def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_month(d: date) -> date:
    y = d.year + (1 if d.month == 12 else 0)
    m = 1 if d.month == 12 else d.month + 1
    return date(y, m, 1)


def preview_ytd_rolloffs(conn, run_date: date | None = None):
    run_date = run_date or date.today()
    roll_date = _month_start(run_date)

    window_start = date(roll_date.year - 1, roll_date.month, 1)
    window_end = _add_month(window_start)
    label = window_start.strftime("%b %Y")

    rows = conn.execute(
        """
        SELECT employee_id,
               ROUND(COALESCE(SUM(points), 0.0), 3) AS net_points
          FROM points_history
         WHERE date(point_date) >= date(?)
           AND date(point_date) <  date(?)
         GROUP BY employee_id
        HAVING net_points > 0.0
         ORDER BY employee_id;
        """,
        (window_start.isoformat(), window_end.isoformat()),
    ).fetchall()

    return [
        (r["employee_id"], float(r["net_points"]), roll_date, label)
        for r in rows
    ]


def apply_ytd_rolloffs(
    conn,
    run_date: date | None = None,
    dry_run: bool = False,
):
    items = preview_ytd_rolloffs(conn, run_date=run_date)
    applied = []

    for employee_id, net_points, roll_date, label in items:
        already = conn.execute(
            """
            SELECT 1
              FROM points_history
             WHERE employee_id = ?
               AND date(point_date) = date(?)
               AND reason = 'YTD Roll-Off'
               AND note LIKE ?
             LIMIT 1;
            """,
            (employee_id, roll_date.isoformat(), f"%{label}%"),
        ).fetchone()

        if already:
            continue

        applied.append((employee_id, net_points, roll_date, label))

        if dry_run:
            continue

        with tx(conn):
            repo.insert_points_history(
                conn,
                employee_id=int(employee_id),
                point_date=roll_date,
                points=-float(net_points),
                reason="YTD Roll-Off",
                note=f"YTD roll-off for {label}",
                flag_code="AUTO",
            )
            # Recalculate all date fields after the YTD roll-off entry
            recalculate_employee_dates(conn, int(employee_id))

    return applied