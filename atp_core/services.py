from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
import sqlite3

from .db import tx
from . import repo
from .rules import calc_rolloff_and_perfect, step_next_perfect_attendance, step_next_rolloff


def _is_pg(conn) -> bool:
    return conn.__class__.__module__.startswith("psycopg2")


def _fetchall(conn, sql: str, params=()):
    if _is_pg(conn):
        cur = conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        rows = cur.fetchall()
        cur.close()
        return rows
    return conn.execute(sql, params).fetchall()


def _fetchone(conn, sql: str, params=()):
    if _is_pg(conn):
        cur = conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        row = cur.fetchone()
        cur.close()
        return row
    return conn.execute(sql, params).fetchone()


def _exec(conn, sql: str, params=()):
    if _is_pg(conn):
        cur = conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        cur.close()
        return
    conn.execute(sql, params)


def _coerce_iso_date(value):
    if value is None:
        return None
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _history_sort_key(row: dict) -> tuple:
    row_id = row.get("id")
    row_id_sort = int(row_id) if row_id not in (None, "") else 10**18
    return (str(row.get("point_date") or "")[:10], row_id_sort)


def _assert_transaction_does_not_overdraw(
    conn: sqlite3.Connection,
    employee_id: int,
    point_date: date,
    points: float,
    *,
    point_id: int | None = None,
) -> None:
    if float(points) >= 0.0:
        return

    history_rows = repo.get_points_history_ordered(conn, int(employee_id))

    if point_id is None:
        history_rows.append({
            "id": None,
            "point_date": point_date.isoformat(),
            "points": float(points),
        })
    else:
        replaced = False
        for row in history_rows:
            if int(row["id"]) == int(point_id):
                row["point_date"] = point_date.isoformat()
                row["points"] = float(points)
                replaced = True
                break
        if not replaced:
            raise ValueError("Point history row not found.")

    running_total = 0.0
    for row in sorted(history_rows, key=_history_sort_key):
        balance_before = running_total
        delta = round(float(row.get("points") or 0.0), 3)
        is_target_row = row.get("id") == point_id or (point_id is None and row.get("id") is None)
        if is_target_row and delta < 0.0 and (balance_before + delta) < -1e-9:
            raise ValueError("This transaction would take the employee below 0.0 points.")
        running_total = max(0.0, round(running_total + delta, 3))


def recalculate_all_employee_dates(conn: sqlite3.Connection) -> None:
    employee_rows = _fetchall(conn, "SELECT employee_id FROM employees ORDER BY employee_id")
    with tx(conn):
        for row in employee_rows:
            recalculate_employee_dates(conn, int(row["employee_id"]))

# ---------------------------------------------------------------------------
# Core recalculation — the single function called after EVERY history change
# ---------------------------------------------------------------------------

def recalculate_employee_dates(conn: sqlite3.Connection, employee_id: int) -> None:
    """
    Recompute point_total, last_point_date, rolloff_date, and perfect_attendance
    for one employee from their points_history. Called after every add, edit,
    delete, roll-off, or YTD roll-off.

    Policy rules encoded here
    -------------------------
    POINT TOTAL
        SUM(points) across ALL history rows, floored at 0.0.

    ROLL-OFF ANCHOR  (last_point_date stored on the employee)
        MAX(point_date) from all entries EXCEPT YTD Roll-Offs
        (reason = 'YTD Roll-Off' AND flag_code = 'AUTO').
        2-month roll-off entries (flag_code='AUTO', reason='2 Month Roll Off')
        DO count — they reset the roll-off clock.

    PERFECT ATTENDANCE ANCHOR
        MAX(point_date) WHERE points > 0 only (positive incidents).
        Roll-off entries (negative) and YTD entries do NOT move this anchor.

    DATE FORMULAS
        rolloff_date       = first of month after (roll-off anchor + 2 months)
        perfect_attendance = first of month after (perfect anchor  + 3 months)

    WHEN POINT TOTAL HITS 0
        rolloff_date is cleared (NULL) — nothing left to roll off.
        perfect_attendance is cleared (NULL) — no positive history means
        the clock hasn't started (or has already been fully cleared).

    WHEN NO HISTORY EXISTS AT ALL
        All three date fields are cleared and total is set to 0.0.
    """
    # --- Step 1: total across all history, flooring at zero after each event ---
    history_rows = repo.with_running_point_totals(repo.get_points_history_ordered(conn, int(employee_id)))
    new_total = float(history_rows[-1]["point_total"]) if history_rows else 0.0

    # --- Step 2: roll-off anchor (any entry except YTD Roll-Off) ---
    rolloff_anchor_row = _fetchone(conn,
        """
        SELECT MAX(point_date) AS last_date
          FROM points_history
         WHERE employee_id = ?
           AND NOT (reason = 'YTD Roll-Off' AND flag_code = 'AUTO')
        """,
        (employee_id,),
    )
    rolloff_anchor_iso = rolloff_anchor_row["last_date"] if rolloff_anchor_row else None

    # --- Step 3: perfect attendance anchor (positive entries only) ---
    perfect_anchor_row = _fetchone(conn,
        """
        SELECT MAX(point_date) AS last_date
          FROM points_history
         WHERE employee_id = ?
           AND points > 0
        """,
        (employee_id,),
    )
    perfect_anchor_iso = perfect_anchor_row["last_date"] if perfect_anchor_row else None

    # --- Step 4: decide what to write ---
    if not rolloff_anchor_iso and not perfect_anchor_iso:
        # No history at all — clear everything
        _exec(conn,
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
        return

    # Compute dates
    rolloff_date_iso = None
    perfect_date_iso = None

    if rolloff_anchor_iso and new_total > 0:
        # Only schedule a rolloff if there are points left to roll off
        rolloff_anchor = datetime.strptime(rolloff_anchor_iso, "%Y-%m-%d").date()

        if perfect_anchor_iso:
            perfect_anchor = datetime.strptime(perfect_anchor_iso, "%Y-%m-%d").date()
        else:
            # No positive points; use the rolloff anchor for perfect calc too
            perfect_anchor = rolloff_anchor

        policy = calc_rolloff_and_perfect(rolloff_anchor, perfect_anchor)
        rolloff_date_iso = policy.rolloff_date.isoformat()
        perfect_date_iso = policy.perfect_date.isoformat()

    elif perfect_anchor_iso:
        # Has positive history but total is currently 0 (all rolled off).
        # Clear rolloff_date; still keep perfect_attendance cleared too
        # (per policy: no points = no rolloff scheduled, no perfect date shown).
        rolloff_date_iso = None
        perfect_date_iso = None

    _exec(conn,
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
            rolloff_anchor_iso,   # last_point_date = rolloff anchor
            rolloff_date_iso,
            perfect_date_iso,
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
# Service functions — all write through recalculate_employee_dates
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
        _assert_transaction_does_not_overdraw(
            conn,
            preview.employee_id,
            preview.point_date,
            preview.points,
        )
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
        _assert_transaction_does_not_overdraw(
            conn,
            int(employee_id),
            point_date,
            float(points),
            point_id=int(point_id),
        )
        repo.update_points_history_entry(
            conn,
            point_id=int(point_id),
            point_date=point_date,
            points=float(points),
            reason=str(reason).strip(),
            note=(note or "").strip() or None,
            flag_code=(flag_code or "").strip() or None,
        )
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
# 2-Month Roll-Off Engine
# ---------------------------------------------------------------------------

def apply_2mo_rolloffs(
    conn: sqlite3.Connection,
    run_date: date | None = None,
    dry_run: bool = False,
) -> list[dict]:
    """
    Apply 2-month roll-offs for all employees whose rolloff_date is on or
    before run_date (default: today).

    Policy
    ------
    - ALL remaining points roll off at once in a single history entry.
    - The roll-off entry DOES reset the roll-off clock (step_next_rolloff).
    - The roll-off entry does NOT move the perfect attendance anchor
      (because it is not a positive point entry).
    - If the employee's total hits 0, rolloff_date is cleared (NULL).
    - YTD Roll-Off entries are excluded from the roll-off anchor.

    Returns
    -------
    List of dicts describing what was (or would be) applied, one per employee.
    """
    run_date = run_date or date.today()

    if _is_pg(conn):
        expired = _fetchall(
            conn,
            """
            SELECT employee_id, first_name, last_name,
                   rolloff_date,
                   COALESCE(point_total, 0.0) AS pt,
                   NULLIF(last_point_date, '') AS last_point_iso
              FROM employees
             WHERE rolloff_date IS NOT NULL
               AND (rolloff_date::date) <= (%s::date)
            """,
            (run_date.isoformat(),),
        )
    else:
        expired = _fetchall(
            conn,
            """
            SELECT employee_id, first_name, last_name,
                   rolloff_date,
                   COALESCE(point_total, 0.0) AS pt,
                   NULLIF(last_point_date, '') AS last_point_iso
              FROM employees
             WHERE rolloff_date IS NOT NULL
               AND date(rolloff_date) <= date(?)
            """,
            (run_date.isoformat(),),
        )

    applied = []

    for rec in expired:
        emp_id = int(rec["employee_id"])
        current_total = float(rec["pt"] or 0.0)
        next_roll = _coerce_iso_date(rec["rolloff_date"])
        last_point_iso = rec["last_point_iso"]

        # perfect_date anchor: still based on last POSITIVE point entry
        # (the stored last_point_date is the rolloff anchor, which may differ)
        perfect_anchor_row = _fetchone(conn,
            """
            SELECT MAX(point_date) AS last_date
              FROM points_history
             WHERE employee_id = ? AND points > 0
            """,
            (emp_id,),
        )
        perfect_iso = perfect_anchor_row["last_date"] if perfect_anchor_row else None

        if perfect_iso:
            perfect_date = _coerce_iso_date(perfect_iso)
            from .rules import three_months_then_first
            perfect_milestone = three_months_then_first(perfect_date)
        else:
            from datetime import date as _date
            perfect_milestone = _date.min

        # Count how many periods are overdue and advance next_roll
        removed = 0
        while next_roll <= run_date and current_total > 0:
            current_total = max(0.0, round(current_total - 1.0, 2))
            removed += 1
            next_roll = step_next_rolloff(next_roll, perfect_milestone)

        # Even if no points removed, advance an overdue date
        while next_roll <= run_date:
            next_roll = step_next_rolloff(next_roll, perfect_milestone)

        if removed == 0 and rec["rolloff_date"] == next_roll.isoformat():
            continue  # nothing to do

        applied.append({
            "employee_id": emp_id,
            "first_name": rec["first_name"],
            "last_name": rec["last_name"],
            "roll_date": run_date,
            "points_removed": -float(removed),
            "new_total": round(current_total, 1),
        })

        if dry_run:
            continue

        with tx(conn):
            if removed > 0:
                # Single aggregated history entry for the roll-off
                repo.insert_points_history(
                    conn,
                    employee_id=emp_id,
                    point_date=run_date,
                    points=-float(removed),
                    reason="2 Month Roll Off",
                    note="",
                    flag_code="AUTO",
                )
            # Recalculate all date fields — this handles the cleared rolloff
            # if total hits 0, and resets next rolloff date from the new entry
            recalculate_employee_dates(conn, emp_id)

    return applied


def advance_due_perfect_attendance_dates(
    conn,
    run_date: date | None = None,
    dry_run: bool = False,
):
    """
    Advance due perfect-attendance dates to the next future month boundary.

    For each employee with perfect_attendance <= run_date, repeatedly advance
    by one month until the date is strictly greater than run_date.
    """
    run_date = run_date or date.today()

    if _is_pg(conn):
        due_rows = _fetchall(
            conn,
            """
            SELECT employee_id, first_name, last_name, perfect_attendance
              FROM employees
             WHERE perfect_attendance IS NOT NULL
               AND (perfect_attendance::date) <= (%s::date)
             ORDER BY (perfect_attendance::date) ASC, last_name, first_name
            """,
            (run_date.isoformat(),),
        )
    else:
        due_rows = _fetchall(
            conn,
            """
            SELECT employee_id, first_name, last_name, perfect_attendance
              FROM employees
             WHERE perfect_attendance IS NOT NULL
               AND date(perfect_attendance) <= date(?)
             ORDER BY date(perfect_attendance) ASC, last_name, first_name
            """,
            (run_date.isoformat(),),
        )

    advanced = []

    for rec in due_rows:
        old_due = _coerce_iso_date(rec["perfect_attendance"])
        new_due = old_due
        steps = 0

        while new_due <= run_date:
            new_due = step_next_perfect_attendance(new_due)
            steps += 1

        if steps == 0:
            continue

        advanced.append({
            "employee_id": int(rec["employee_id"]),
            "first_name": rec["first_name"],
            "last_name": rec["last_name"],
            "old_perfect_attendance": old_due.isoformat(),
            "new_perfect_attendance": new_due.isoformat(),
            "months_advanced": steps,
        })

        if dry_run:
            continue

        with tx(conn):
            repo.insert_points_history(
                conn,
                employee_id=int(rec["employee_id"]),
                point_date=run_date,
                points=0.0,
                reason="Perfect Attendance",
                note=(
                    f"Perfect attendance milestone advanced "
                    f"from {old_due.isoformat()} to {new_due.isoformat()}"
                ),
                flag_code="AUTO",
            )
            _exec(
                conn,
                "UPDATE employees SET perfect_attendance = ? WHERE employee_id = ?",
                (new_due.isoformat(), int(rec["employee_id"])),
            )

    return advanced


# ---------------------------------------------------------------------------
# YTD Roll-Off Engine (matches Beta7 apply_ytd_rolloffs exactly)
# ---------------------------------------------------------------------------

def _first_of_month(d: date) -> date:
    return d.replace(day=1)


def _add_month(d: date) -> date:
    y = d.year + (1 if d.month == 12 else 0)
    m = 1 if d.month == 12 else d.month + 1
    return date(y, m, 1)


def preview_ytd_rolloffs(
    conn,
    run_date: date | None = None,
    *,
    exclude_applied: bool = False,
):
    run_date = run_date or date.today()
    roll_date = _first_of_month(run_date)

    window_start = date(roll_date.year - 1, roll_date.month, 1)
    window_end = _add_month(window_start)
    label = window_start.strftime("%b %Y")

    if _is_pg(conn):
        rows = _fetchall(
            conn,
            """
            SELECT employee_id,
                   ROUND((COALESCE(SUM(points), 0.0))::numeric, 3)::float8 AS net_points
              FROM points_history
             WHERE (point_date::date) >= (%s::date)
               AND (point_date::date) < (%s::date)
             GROUP BY employee_id
            HAVING ROUND((COALESCE(SUM(points), 0.0))::numeric, 3)::float8 > 0.0
             ORDER BY employee_id;
            """,
            (window_start.isoformat(), window_end.isoformat()),
        )
    else:
        rows = _fetchall(
            conn,
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
        )

    items = [
        (r["employee_id"], float(r["net_points"]), roll_date, label)
        for r in rows
    ]

    if not exclude_applied:
        return items

    pending = []
    for employee_id, net_points, item_roll_date, item_label in items:
        if _is_pg(conn):
            already = _fetchone(
                conn,
                """
                SELECT 1
                  FROM points_history
                 WHERE employee_id = %s
                   AND (point_date::date) = (%s::date)
                   AND reason = 'YTD Roll-Off'
                   AND note LIKE %s
                 LIMIT 1;
                """,
                (employee_id, item_roll_date.isoformat(), f"%{item_label}%"),
            )
        else:
            already = _fetchone(
                conn,
                """
                SELECT 1
                  FROM points_history
                 WHERE employee_id = ?
                   AND date(point_date) = date(?)
                   AND reason = 'YTD Roll-Off'
                   AND note LIKE ?
                 LIMIT 1;
                """,
                (employee_id, item_roll_date.isoformat(), f"%{item_label}%"),
            )

        if not already:
            pending.append((employee_id, net_points, item_roll_date, item_label))

    return pending


def apply_ytd_rolloffs(
    conn,
    run_date: date | None = None,
    dry_run: bool = False,
):
    """
    YTD roll-offs do NOT reset the roll-off or perfect attendance clock
    (flag_code='AUTO', reason='YTD Roll-Off' — excluded from both anchors).
    """
    items = preview_ytd_rolloffs(conn, run_date=run_date)
    applied = []

    for employee_id, net_points, roll_date, label in items:
        if _is_pg(conn):
            already = _fetchone(
                conn,
                """
                SELECT 1
                  FROM points_history
                 WHERE employee_id = %s
                   AND (point_date::date) = (%s::date)
                   AND reason = 'YTD Roll-Off'
                   AND note LIKE %s
                 LIMIT 1;
                """,
                (employee_id, roll_date.isoformat(), f"%{label}%"),
            )
        else:
            already = _fetchone(
                conn,
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
            )

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
            # Recalculate — YTD entry will be excluded from both anchors
            # so dates will NOT shift; only point_total changes
            recalculate_employee_dates(conn, int(employee_id))

    return applied
