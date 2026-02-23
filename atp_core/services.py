from __future__ import annotations
from dataclasses import dataclass
from datetime import date
import sqlite3

from .db import tx
from . import repo

@dataclass(frozen=True)
class AddPointPreview:
    employee_id: int
    point_date: date
    points: float
    reason: str
    note: str

def preview_add_point(employee_id: int, point_date: date, points: float, reason: str, note: str | None) -> AddPointPreview:
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

def add_point(conn: sqlite3.Connection, preview: AddPointPreview, flag_code: str | None = None) -> None:
    """Single, validated write path: inserts history row + recomputes employee total."""
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
        repo.update_employee_point_total(conn, preview.employee_id)




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
        repo.update_employee_point_total(conn, int(employee_id))


def delete_point_history_entry(conn: sqlite3.Connection, point_id: int, employee_id: int) -> None:
    if point_id is None:
        raise ValueError("Point history row is required.")
    if employee_id is None:
        raise ValueError("Employee is required.")

    with tx(conn):
        repo.delete_points_history_entry(conn, int(point_id))
        repo.update_employee_point_total(conn, int(employee_id))
def create_employee(conn: sqlite3.Connection, employee_id: int, last_name: str, first_name: str, location: str | None = None) -> None:
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

from datetime import date
from .db import tx
from . import repo

def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)

def _add_month(d: date) -> date:
    # add 1 month, keep day=1
    y = d.year + (1 if d.month == 12 else 0)
    m = 1 if d.month == 12 else d.month + 1
    return date(y, m, 1)

def preview_ytd_rolloffs(conn, run_date: date | None = None):
    run_date = run_date or date.today()
    roll_date = _month_start(run_date)

    # roll off the month from 1 year ago
    window_start = date(roll_date.year - 1, roll_date.month, 1)
    window_end = _add_month(window_start)

    rows = conn.execute("""
        SELECT employee_id, ROUND(COALESCE(SUM(points), 0.0), 3) AS net_points
        FROM points_history
        WHERE date(point_date) >= date(?)
          AND date(point_date) <  date(?)
        GROUP BY employee_id
        HAVING net_points > 0.0
        ORDER BY employee_id;
    """, (window_start.isoformat(), window_end.isoformat())).fetchall()

    # return list of (employee_id, net_points, roll_date, window_label)
    label = window_start.strftime("%b %Y")
    return [(r["employee_id"], float(r["net_points"]), roll_date, label) for r in rows]


def apply_ytd_rolloffs(conn, run_date: date | None = None, dry_run: bool = False):
    """
    Inserts negative YTD Roll-Off rows into points_history for the month 1 year ago.
    Prevents duplicates if already applied for the month.
    Returns list of applied (employee_id, points_rolled, roll_date, label).
    """
    items = preview_ytd_rolloffs(conn, run_date=run_date)
    applied = []

    for employee_id, net_points, roll_date, label in items:
        # prevent double-apply
        already = conn.execute("""
            SELECT 1
            FROM points_history
            WHERE employee_id = ?
              AND date(point_date) = date(?)
              AND reason = 'YTD Roll-Off'
              AND note LIKE ?
            LIMIT 1;
        """, (employee_id, roll_date.isoformat(), f"%{label}%")).fetchone()

        if already:
            continue

        applied.append((employee_id, net_points, roll_date, label))

        if dry_run:
            continue

        with tx(conn):
            # Insert rolloff entry (negative)
            conn.execute("""
                INSERT INTO points_history (employee_id, point_date, points, reason, note, flag_code)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (employee_id, roll_date.isoformat(), -net_points, "YTD Roll-Off",
                  f"YTD roll-off for {label}", "AUTO"))

            # Recompute employee totals/fields using your existing repo function (if present)
            if hasattr(repo, "update_employee_point_total"):
                repo.update_employee_point_total(conn, employee_id)

    return applied

from datetime import date

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

    rows = conn.execute("""
        SELECT employee_id, ROUND(COALESCE(SUM(points), 0.0), 3) AS net_points
        FROM points_history
        WHERE date(point_date) >= date(?)
          AND date(point_date) <  date(?)
        GROUP BY employee_id
        HAVING net_points > 0.0
        ORDER BY employee_id;
    """, (window_start.isoformat(), window_end.isoformat())).fetchall()

    return [(r["employee_id"], float(r["net_points"]), roll_date, label) for r in rows]

def apply_ytd_rolloffs(conn, run_date: date | None = None, dry_run: bool = False):
    items = preview_ytd_rolloffs(conn, run_date=run_date)
    applied = []

    for employee_id, net_points, roll_date, label in items:
        already = conn.execute("""
            SELECT 1
            FROM points_history
            WHERE employee_id = ?
              AND date(point_date) = date(?)
              AND reason = 'YTD Roll-Off'
              AND note LIKE ?
            LIMIT 1;
        """, (employee_id, roll_date.isoformat(), f"%{label}%")).fetchone()

        if already:
            continue

        applied.append((employee_id, net_points, roll_date, label))

        if dry_run:
            continue

        # Write entry and refresh totals atomically
        from .db import tx
        from . import repo

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
            repo.update_employee_point_total(conn, int(employee_id))

    return applied
