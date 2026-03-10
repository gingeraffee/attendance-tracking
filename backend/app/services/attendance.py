from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from atp_core import repo, services  # noqa: E402


def _iso_date(value) -> str | None:
    if value in (None, ''):
        return None
    return str(value)[:10]


def _require_iso_date(value, field_name: str) -> str:
    raw = _iso_date(value)
    if not raw:
        raise ValueError(f'{field_name} is required.')
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError as exc:
        raise ValueError(f'{field_name} must be a valid ISO date.') from exc


def _employee_to_summary(row) -> dict:
    payload = dict(row)
    return {
        'employee_id': int(payload['employee_id']),
        'first_name': payload.get('first_name') or '',
        'last_name': payload.get('last_name') or '',
        'location': payload.get('location') or payload.get('Location') or '',
        'start_date': _iso_date(payload.get('start_date')),
        'point_total': float(payload.get('point_total') or 0.0),
        'rolloff_date': _iso_date(payload.get('rolloff_date')),
        'perfect_attendance': _iso_date(payload.get('perfect_attendance')),
        'last_point_date': _iso_date(payload.get('last_point_date')),
        'point_warning_date': _iso_date(payload.get('point_warning_date')),
        'is_active': bool(payload.get('is_active', 1)),
    }


def _employee_to_spotlight(row: dict) -> dict:
    return {
        'employee_id': int(row['employee_id']),
        'first_name': row.get('first_name') or '',
        'last_name': row.get('last_name') or '',
        'location': row.get('location') or '',
        'point_total': float(row.get('point_total') or 0.0),
        'rolloff_date': _iso_date(row.get('rolloff_date')),
        'perfect_attendance': _iso_date(row.get('perfect_attendance')),
        'last_point_date': _iso_date(row.get('last_point_date')),
    }


def _date_in_window(raw: str | None, start: date, end: date) -> bool:
    if not raw:
        return False
    try:
        value = date.fromisoformat(str(raw)[:10])
    except ValueError:
        return False
    return start <= value <= end


def _count_recent_positive_points(rows: list[dict], since: date) -> int:
    return sum(
        1
        for row in rows
        if float(row.get('points') or 0.0) > 0.0 and _date_in_window(_iso_date(row.get('point_date')), since, date.today())
    )


def list_employees(conn, q: str = '', building: str = 'All') -> list[dict]:
    rows = [dict(r) for r in repo.search_employees(conn, q=q, active_only=False, limit=3000)]
    if building != 'All':
        rows = [row for row in rows if (row.get('location') or '') == building]

    result = []
    for row in rows:
        employee = repo.get_employee(conn, int(row['employee_id']))
        if not employee:
            continue
        result.append(_employee_to_summary(employee))

    result.sort(key=lambda item: (item['last_name'].lower(), item['first_name'].lower()))
    return result


def get_employee_detail(conn, employee_id: int) -> dict | None:
    row = repo.get_employee(conn, int(employee_id))
    if not row:
        return None
    return _employee_to_summary(row)




def create_employee_record(conn, payload: dict) -> dict:
    services.create_employee(
        conn,
        employee_id=int(payload['employee_id']),
        last_name=payload['last_name'],
        first_name=payload['first_name'],
        start_date=date.fromisoformat(_require_iso_date(payload.get('start_date'), 'Start date')),
        location=payload.get('location'),
    )
    return get_employee_detail(conn, int(payload['employee_id']))


def update_employee_record(conn, employee_id: int, payload: dict) -> dict:
    existing = get_employee_detail(conn, int(employee_id))
    if not existing:
        raise ValueError('Employee not found')

    existing_start_date = _iso_date(existing.get('start_date'))
    next_start_date = _require_iso_date(payload.get('start_date'), 'Start date') if payload.get('start_date') not in (None, '') else None
    params = (
        str(payload['first_name']).strip(),
        str(payload['last_name']).strip(),
        next_start_date,
        (payload.get('location') or '').strip() or None,
        1 if payload.get('is_active', True) else 0,
        int(employee_id),
    )
    if conn.__class__.__module__.startswith('psycopg2'):
        cur = conn.cursor()
        cur.execute(
            'UPDATE employees SET first_name = %s, last_name = %s, start_date = %s, "Location" = %s, is_active = %s WHERE employee_id = %s',
            params,
        )
        cur.close()
        conn.commit()
        if existing_start_date != next_start_date:
            cur = conn.cursor()
            cur.execute('UPDATE employees SET perfect_attendance = NULL WHERE employee_id = %s', (int(employee_id),))
            cur.close()
            conn.commit()
    else:
        conn.execute(
            'UPDATE employees SET first_name = ?, last_name = ?, start_date = ?, "Location" = ?, is_active = ? WHERE employee_id = ?',
            params,
        )
        conn.commit()
        if existing_start_date != next_start_date:
            conn.execute('UPDATE employees SET perfect_attendance = NULL WHERE employee_id = ?', (int(employee_id),))
            conn.commit()

    services.recalculate_employee_dates(conn, int(employee_id))
    refreshed = get_employee_detail(conn, int(employee_id))
    if not refreshed:
        raise ValueError('Employee not found')
    return refreshed


def delete_employee_record(conn, employee_id: int) -> None:
    services.delete_employee(conn, int(employee_id))

def get_employee_history(conn, employee_id: int, limit: int = 200) -> list[dict]:
    rows = [dict(r) for r in repo.get_points_history(conn, int(employee_id), limit=limit)]
    return [
        {
            'id': int(row['id']),
            'point_date': str(row.get('point_date') or '')[:10],
            'points': float(row.get('points') or 0.0),
            'reason': row.get('reason'),
            'note': row.get('note'),
            'flag_code': row.get('flag_code'),
            'point_total': float(row.get('point_total') or 0.0),
        }
        for row in rows
    ]


def create_point(conn, employee_id: int, payload: dict) -> dict:
    preview = services.preview_add_point(
        int(employee_id),
        date.fromisoformat(payload['point_date']),
        float(payload['points']),
        payload['reason'],
        payload.get('note'),
    )
    services.add_point(conn, preview, flag_code=payload.get('flag_code'))
    return {
        'employee': get_employee_detail(conn, int(employee_id)),
        'history': get_employee_history(conn, int(employee_id), limit=200),
    }


def update_point(conn, employee_id: int, point_id: int, payload: dict) -> dict:
    services.update_point_history_entry(
        conn,
        point_id=int(point_id),
        employee_id=int(employee_id),
        point_date=date.fromisoformat(payload['point_date']),
        points=float(payload['points']),
        reason=payload['reason'],
        note=payload.get('note'),
        flag_code=payload.get('flag_code'),
    )
    return {
        'employee': get_employee_detail(conn, int(employee_id)),
        'history': get_employee_history(conn, int(employee_id), limit=200),
    }


def delete_point(conn, employee_id: int, point_id: int) -> dict:
    services.delete_point_history_entry(conn, point_id=int(point_id), employee_id=int(employee_id))
    return {
        'employee': get_employee_detail(conn, int(employee_id)),
        'history': get_employee_history(conn, int(employee_id), limit=200),
    }


def recalculate_employee(conn, employee_id: int) -> dict:
    services.recalculate_employee_dates(conn, int(employee_id))
    return {
        'employee': get_employee_detail(conn, int(employee_id)),
        'history': get_employee_history(conn, int(employee_id), limit=200),
    }


def recalculate_all(conn) -> dict:
    services.recalculate_all_employee_dates(conn)
    return dashboard_summary(conn)


def dashboard_summary(conn) -> dict:
    employees = list_employees(conn, building='All')
    today = date.today()
    in_30_days = today + timedelta(days=30)

    active_employees = [row for row in employees if row['is_active']]
    return {
        'total_employees': len(employees),
        'active_employees': len(active_employees),
        'employees_at_or_above_five': sum(1 for row in active_employees if float(row['point_total']) >= 5.0),
        'upcoming_rolloffs': sum(1 for row in active_employees if _date_in_window(row.get('rolloff_date'), today, in_30_days)),
        'upcoming_perfect_attendance': sum(1 for row in active_employees if _date_in_window(row.get('perfect_attendance'), today, in_30_days)),
    }


def dashboard_detail(conn) -> dict:
    today = date.today()
    in_7_days = today + timedelta(days=7)
    in_30_days = today + timedelta(days=30)
    last_24h = today - timedelta(days=1)
    last_7d = today - timedelta(days=7)

    employees = list_employees(conn, building='All')
    active_employees = [row for row in employees if row['is_active']]
    recent_rows = [dict(row) for row in repo.report_points_last_30_days(conn, as_of=today)]

    summary = dashboard_summary(conn)
    pulse = {
        'points_added_24h': _count_recent_positive_points(recent_rows, last_24h),
        'points_added_7d': _count_recent_positive_points(recent_rows, last_7d),
        'rolloffs_due_7d': sum(1 for row in active_employees if float(row['point_total']) > 0 and _date_in_window(row.get('rolloff_date'), today, in_7_days)),
        'perfect_due_7d': sum(1 for row in active_employees if _date_in_window(row.get('perfect_attendance'), today, in_7_days)),
    }
    bucket_counts = {
        'above_one': sum(1 for row in active_employees if float(row['point_total']) > 1.0),
        'one_to_four': sum(1 for row in active_employees if 1.0 <= float(row['point_total']) <= 4.5),
        'five_to_six': sum(1 for row in active_employees if 5.0 <= float(row['point_total']) <= 6.5),
        'seven_plus': sum(1 for row in active_employees if float(row['point_total']) >= 7.0),
    }

    ranked_active = sorted(
        active_employees,
        key=lambda row: (-float(row['point_total']), row['last_name'].lower(), row['first_name'].lower()),
    )
    at_risk_employees = [_employee_to_spotlight(row) for row in ranked_active if float(row['point_total']) >= 5.0][:8]

    upcoming_rolloffs = [
        _employee_to_spotlight(row)
        for row in sorted(
            [row for row in active_employees if float(row['point_total']) > 0 and _date_in_window(row.get('rolloff_date'), today, in_30_days)],
            key=lambda row: (row.get('rolloff_date') or '9999-12-31', row['last_name'].lower(), row['first_name'].lower()),
        )[:8]
    ]

    upcoming_perfect_attendance = [
        _employee_to_spotlight(row)
        for row in sorted(
            [row for row in active_employees if _date_in_window(row.get('perfect_attendance'), today, in_30_days)],
            key=lambda row: (row.get('perfect_attendance') or '9999-12-31', row['last_name'].lower(), row['first_name'].lower()),
        )[:8]
    ]

    recent_activity = []
    for row in recent_rows:
        recent_activity.append(
            {
                'employee_id': int(row['employee_id']),
                'first_name': row.get('first_name') or '',
                'last_name': row.get('last_name') or '',
                'location': row.get('location') or '',
                'point_date': _iso_date(row.get('point_date')) or '',
                'points': float(row.get('points') or 0.0),
                'reason': row.get('reason'),
                'note': row.get('note'),
            }
        )
        if len(recent_activity) >= 10:
            break

    return {
        'summary': summary,
        'pulse': pulse,
        'bucket_counts': bucket_counts,
        'at_risk_employees': at_risk_employees,
        'upcoming_rolloffs': upcoming_rolloffs,
        'upcoming_perfect_attendance': upcoming_perfect_attendance,
        'recent_activity': recent_activity,
    }



def _normalize_maintenance_rows(rows: list) -> list[dict]:
    normalized: list[dict] = []
    for row in rows:
        if isinstance(row, dict):
            item = {}
            for key, value in row.items():
                if hasattr(value, 'isoformat'):
                    item[key] = value.isoformat()
                else:
                    item[key] = value
            normalized.append(item)
            continue

        if isinstance(row, tuple) and len(row) >= 4:
            employee_id, net_points, roll_date, label = row[:4]
            normalized.append(
                {
                    'employee_id': int(employee_id),
                    'net_points': float(net_points),
                    'roll_date': roll_date.isoformat() if hasattr(roll_date, 'isoformat') else str(roll_date),
                    'label': label,
                }
            )

    return normalized


def run_two_month_rolloffs(conn, run_date_iso: str, dry_run: bool) -> dict:
    rows = services.apply_2mo_rolloffs(conn, run_date=date.fromisoformat(run_date_iso), dry_run=dry_run)
    return {
        'job': '2-Month Roll-offs',
        'dry_run': bool(dry_run),
        'affected': len(rows),
        'rows': _normalize_maintenance_rows(rows),
        'summary': dashboard_summary(conn),
    }


def run_perfect_attendance_advancement(conn, run_date_iso: str, dry_run: bool) -> dict:
    rows = services.advance_due_perfect_attendance_dates(conn, run_date=date.fromisoformat(run_date_iso), dry_run=dry_run)
    return {
        'job': 'Perfect Attendance',
        'dry_run': bool(dry_run),
        'affected': len(rows),
        'rows': _normalize_maintenance_rows(rows),
        'summary': dashboard_summary(conn),
    }


def run_ytd_rolloffs(conn, run_date_iso: str, dry_run: bool) -> dict:
    rows = services.apply_ytd_rolloffs(conn, run_date=date.fromisoformat(run_date_iso), dry_run=dry_run)
    return {
        'job': 'YTD Roll-offs',
        'dry_run': bool(dry_run),
        'affected': len(rows),
        'rows': _normalize_maintenance_rows(rows),
        'summary': dashboard_summary(conn),
    }



CORRECTIVE_ACTION_TIERS = [
    ('termination', 'Termination', '7.6+', lambda points: points > 7.5),
    ('written_warning', 'Written Warning', '7.0-7.5', lambda points: 7.0 <= points <= 7.5),
    ('verbal_warning', 'Verbal Warning', '6.0-6.5', lambda points: 6.0 <= points <= 6.5),
    ('verbal_coaching', 'Verbal Coaching', '5.0-5.5', lambda points: 5.0 <= points <= 5.5),
]


def _last_positive_point_date(conn, employee_id: int) -> str | None:
    if conn.__class__.__module__.startswith('psycopg2'):
        cur = conn.cursor()
        cur.execute(
            """
            SELECT MAX(point_date::date)::text AS last_date
              FROM points_history
             WHERE employee_id = %s
               AND COALESCE(points, 0.0) > 0.0
            """,
            (int(employee_id),),
        )
        row = cur.fetchone()
        cur.close()
        return _iso_date(row['last_date']) if row else None

    row = conn.execute(
        """
        SELECT MAX(date(point_date)) AS last_date
          FROM points_history
         WHERE employee_id = ?
           AND COALESCE(points, 0.0) > 0.0
        """,
        (int(employee_id),),
    ).fetchone()
    return _iso_date(row['last_date']) if row else None


def _corrective_tier(points: float) -> dict:
    for key, label, value_range, predicate in CORRECTIVE_ACTION_TIERS:
        if predicate(points):
            return {'tier_key': key, 'tier_label': label, 'tier_range': value_range}
    return {'tier_key': 'none', 'tier_label': 'None', 'tier_range': '-'}


def list_corrective_actions(conn) -> dict:
    rows = []
    for employee in list_employees(conn, building='All'):
        if not employee['is_active'] or float(employee['point_total']) < 5.0:
            continue

        detail = get_employee_detail(conn, int(employee['employee_id']))
        if not detail:
            continue

        tier = _corrective_tier(float(detail['point_total']))
        rows.append(
            {
                'employee_id': int(detail['employee_id']),
                'first_name': detail['first_name'],
                'last_name': detail['last_name'],
                'location': detail.get('location') or '',
                'point_total': float(detail['point_total']),
                'last_positive_point_date': _last_positive_point_date(conn, int(detail['employee_id'])),
                'point_warning_date': _iso_date(detail.get('point_warning_date')),
                **tier,
            }
        )

    rows.sort(key=lambda item: (-item['point_total'], item['last_name'].lower(), item['first_name'].lower()))
    return {
        'total_flagged': len(rows),
        'tiers': [
            {
                'key': key,
                'label': label,
                'count': sum(1 for row in rows if row['tier_key'] == key),
            }
            for key, label, _, _ in CORRECTIVE_ACTION_TIERS
        ],
        'employees': rows,
    }


def update_corrective_action_date(conn, employee_id: int, point_warning_date_iso: str) -> dict:
    employee = get_employee_detail(conn, int(employee_id))
    if not employee:
        raise ValueError('Employee not found')

    if conn.__class__.__module__.startswith('psycopg2'):
        cur = conn.cursor()
        cur.execute(
            'UPDATE employees SET point_warning_date = %s WHERE employee_id = %s',
            (point_warning_date_iso, int(employee_id)),
        )
        cur.close()
        conn.commit()
    else:
        conn.execute(
            'UPDATE employees SET point_warning_date = ? WHERE employee_id = ?',
            (point_warning_date_iso, int(employee_id)),
        )
        conn.commit()

    refreshed = get_employee_detail(conn, int(employee_id))
    if not refreshed:
        raise ValueError('Employee not found')

    tier = _corrective_tier(float(refreshed['point_total']))
    return {
        'employee_id': int(refreshed['employee_id']),
        'first_name': refreshed['first_name'],
        'last_name': refreshed['last_name'],
        'location': refreshed.get('location') or '',
        'point_total': float(refreshed['point_total']),
        'last_positive_point_date': _last_positive_point_date(conn, int(employee_id)),
        'point_warning_date': _iso_date(refreshed.get('point_warning_date')),
        **tier,
    }
