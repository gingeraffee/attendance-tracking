from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from io import StringIO
from math import ceil

from atp_core import repo


PTO_TYPE_COLORS = {
    'Vacation': '#45d7ff',
    'Floating Holiday': '#7de7ff',
    'Reward PTO': '#f24f64',
    'Personal': '#ff9f68',
    'Absence': '#7b61ff',
    'Absence (Sick)': '#ff6e72',
    'Absence (COVID)': '#ffb86c',
    'Long Term Sick Leave': '#f97316',
    'Jury Duty': '#2dd4bf',
    'Bereavement': '#93c5fd',
    'FMLA': '#38bdf8',
}

PLANNED_TYPES = {'vacation', 'floating holiday', 'reward pto'}
UNPLANNED_TYPES = {'personal', 'absence', 'absence (sick)', 'absence (covid)', 'long term sick leave'}
PROTECTED_TYPES = {'jury duty', 'bereavement', 'fmla'}

PTO_SAMPLE_CSV = (
    'employee_id,last_name,first_name,building,pto_type,start_date,end_date,hours\n'
    '1042,Doe,Jordan,Irving,Vacation,2026-02-10,2026-02-12,24\n'
    '1177,Nguyen,Avery,Dallas,Absence (Sick),2026-02-18,2026-02-18,8\n'
    '1383,Ramirez,Taylor,Irving,Floating Holiday,2026-03-03,2026-03-03,8\n'
)


def _clean_text(value) -> str:
    return str(value or '').strip()


def _parse_date(value) -> date | None:
    raw = _clean_text(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _parse_employee_id(value) -> int | None:
    raw = _clean_text(value)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _parse_hours(value) -> float | None:
    raw = _clean_text(value)
    if raw == '':
        return 0.0
    try:
        return round(float(raw), 3)
    except ValueError:
        return None


def _normalize_name(last_name: str, first_name: str) -> str:
    return f'{_clean_text(last_name).lower()}, {_clean_text(first_name).lower()}'


def _format_employee(last_name: str, first_name: str) -> str:
    return f'{_clean_text(last_name)}, {_clean_text(first_name)}'


def _classify_pto_type(value: str) -> str:
    normalized = _clean_text(value).lower()
    if normalized in PLANNED_TYPES:
        return 'Planned'
    if normalized in UNPLANNED_TYPES:
        return 'Unplanned'
    if normalized in PROTECTED_TYPES:
        return 'Protected / Neutral'
    return 'Other'


def _active_roster(conn) -> list[dict]:
    return [dict(row) for row in repo.search_employees(conn, q='', active_only=True, limit=5000)]


def _roster_maps(active_rows: list[dict]) -> tuple[dict[int, dict], dict[str, dict]]:
    by_id: dict[int, dict] = {}
    by_name: dict[str, dict] = {}
    for row in active_rows:
        employee_id = int(row['employee_id'])
        by_id[employee_id] = row
        by_name[_normalize_name(row.get('last_name', ''), row.get('first_name', ''))] = row
    return by_id, by_name


def _normalize_stored_rows(rows: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for raw in rows:
        row = dict(raw)
        start_date = _parse_date(row.get('start_date'))
        end_date = _parse_date(row.get('end_date'))
        if start_date is None or end_date is None:
            continue
        hours = _parse_hours(row.get('hours'))
        if hours is None:
            continue
        last_name = _clean_text(row.get('last_name'))
        first_name = _clean_text(row.get('first_name'))
        pto_type = _clean_text(row.get('pto_type'))
        building = _clean_text(row.get('building'))
        normalized.append(
            {
                'employee_id': _parse_employee_id(row.get('employee_id')),
                'last_name': last_name,
                'first_name': first_name,
                'employee': _format_employee(last_name, first_name),
                'building': building,
                'pto_type': pto_type,
                'category': _classify_pto_type(pto_type),
                'start_date': start_date,
                'end_date': end_date,
                'hours': hours,
                'days': round(hours / 8.0, 2),
            }
        )
    return normalized


def _empty_overview(active_rows: list[dict]) -> dict:
    buildings = sorted({_clean_text(row.get('location')) for row in active_rows if _clean_text(row.get('location'))})
    return {
        'has_data': False,
        'filters': {
            'available_buildings': buildings,
            'available_types': [],
            'selected_building': 'All',
            'selected_types': [],
            'selected_start_date': None,
            'selected_end_date': None,
            'date_min': None,
            'date_max': None,
            'total_records': 0,
        },
        'summary': {
            'total_records': 0,
            'total_hours': 0.0,
            'total_days': 0.0,
            'days_impacted': 0,
            'employees_used': 0,
            'utilization_pct': 0.0,
            'top_type': None,
            'avg_days_per_employee': 0.0,
            'utilization_30d_pct': 0.0,
        },
        'type_totals': [],
        'monthly_trend': [],
        'building_totals': [],
        'top_users': [],
        'low_usage_employees': [],
        'zero_pto_employees': [],
        'category_metrics': [],
        'pace': {
            'annualized_total_days': 0.0,
            'annualized_per_employee_days': 0.0,
            'trend_delta_pct': 0.0,
            'trend_direction': 'flat',
            'trend_label': 'Steady',
        },
        'rows': [],
    }


def import_pto_rows(conn, rows: list[dict]) -> dict:
    active_rows = _active_roster(conn)
    by_id, by_name = _roster_maps(active_rows)

    prepared: list[dict] = []
    excluded_names: set[str] = set()
    excluded = 0
    invalid = 0

    for raw in rows:
        item = {str(key).strip().lower().replace(' ', '_'): value for key, value in dict(raw).items()}

        last_name = _clean_text(item.get('last_name'))
        first_name = _clean_text(item.get('first_name'))
        building = _clean_text(item.get('building'))
        pto_type = _clean_text(item.get('pto_type'))
        start = _parse_date(item.get('start_date') or item.get('date'))
        end = _parse_date(item.get('end_date') or item.get('date'))
        hours = _parse_hours(item.get('hours'))
        requested_id = _parse_employee_id(item.get('employee_id'))

        if not last_name or not first_name or not building or not pto_type or start is None or end is None or hours is None:
            invalid += 1
            continue
        if end < start:
            invalid += 1
            continue

        roster_match = by_id.get(requested_id) if requested_id is not None else None
        if roster_match is None:
            roster_match = by_name.get(_normalize_name(last_name, first_name))
        if roster_match is None:
            excluded += 1
            excluded_names.add(_format_employee(last_name, first_name))
            continue

        prepared.append(
            {
                'employee_id': int(roster_match['employee_id']),
                'last_name': _clean_text(roster_match.get('last_name')) or last_name,
                'first_name': _clean_text(roster_match.get('first_name')) or first_name,
                'building': building,
                'pto_type': pto_type,
                'start_date': start.isoformat(),
                'end_date': end.isoformat(),
                'hours': hours,
            }
        )

    stats = repo.save_pto_data(conn, prepared)
    return {
        'inserted': int(stats['inserted']),
        'duplicate': int(stats['duplicate']),
        'total': int(stats['total']),
        'excluded': excluded,
        'invalid': invalid,
        'excluded_employees': sorted(excluded_names)[:25],
    }


def clear_pto_rows(conn) -> dict:
    repo.clear_pto_data(conn)
    return {'ok': True}


def _weekday_dates(start_value: date, end_value: date) -> list[str]:
    values: list[str] = []
    current = start_value
    while current <= end_value:
        if current.weekday() < 5:
            values.append(current.isoformat())
        current += timedelta(days=1)
    return values


def _scope_active_roster(active_rows: list[dict], building: str) -> list[dict]:
    if building == 'All':
        return active_rows
    return [row for row in active_rows if _clean_text(row.get('location')) == building]


def _trend_label(delta_pct: float) -> tuple[str, str]:
    if delta_pct > 5:
        return 'up', 'Running hotter'
    if delta_pct < -5:
        return 'down', 'Cooling off'
    return 'flat', 'Steady'


def _build_rows_payload(rows: list[dict], limit: int = 120) -> list[dict]:
    payload: list[dict] = []
    for row in sorted(rows, key=lambda item: (item['start_date'], item['employee']), reverse=True)[:limit]:
        payload.append(
            {
                'employee_id': row['employee_id'],
                'employee': row['employee'],
                'building': row['building'],
                'pto_type': row['pto_type'],
                'start_date': row['start_date'].isoformat(),
                'end_date': row['end_date'].isoformat(),
                'hours': round(float(row['hours']), 1),
                'days': round(float(row['days']), 1),
            }
        )
    return payload


def _filter_rows(
    rows: list[dict],
    start_date_iso: str | None,
    end_date_iso: str | None,
    building: str,
    selected_types: list[str],
) -> tuple[list[dict], date | None, date | None]:
    if not rows:
        return [], None, None

    date_min = min(row['start_date'] for row in rows)
    date_max = max(row['end_date'] for row in rows)
    start_date = _parse_date(start_date_iso) or date_min
    end_date = _parse_date(end_date_iso) or date_max

    if end_date < start_date:
        raise ValueError('End date must be on or after start date.')

    filtered = []
    for row in rows:
        if row['start_date'] > end_date or row['end_date'] < start_date:
            continue
        if building != 'All' and row['building'] != building:
            continue
        if selected_types and row['pto_type'] not in selected_types:
            continue
        filtered.append(row)
    return filtered, start_date, end_date


def _count_unique(values: list[str]) -> int:
    return len(set(values))


def get_pto_overview(
    conn,
    start_date_iso: str | None = None,
    end_date_iso: str | None = None,
    building: str = 'All',
    selected_types: list[str] | None = None,
) -> dict:
    active_rows = _active_roster(conn)
    selected_types = [value for value in (selected_types or []) if _clean_text(value)]
    source_rows = [dict(row) for row in repo.load_pto_data(conn)]
    rows = _normalize_stored_rows(source_rows)
    if not rows:
        return _empty_overview(active_rows)

    available_buildings = sorted({_clean_text(row['building']) for row in rows if _clean_text(row['building'])})
    available_types = sorted({_clean_text(row['pto_type']) for row in rows if _clean_text(row['pto_type'])})
    normalized_types = [value for value in selected_types if value in available_types]

    filtered, start_date, end_date = _filter_rows(rows, start_date_iso, end_date_iso, building, normalized_types)
    scoped_active = _scope_active_roster(active_rows, building)
    active_count = len(scoped_active)

    total_hours = round(sum(float(row['hours']) for row in filtered), 1)
    total_days = round(total_hours / 8.0, 1)
    unique_employees = _count_unique([row['employee'] for row in filtered])
    utilization_pct = round((unique_employees / active_count) * 100.0, 1) if active_count else 0.0

    top_type = None
    if filtered:
        type_totals_map: dict[str, float] = defaultdict(float)
        for row in filtered:
            type_totals_map[row['pto_type']] += float(row['hours'])
        top_type = max(type_totals_map.items(), key=lambda item: item[1])[0]

    impacted_dates: set[str] = set()
    for row in filtered:
        impacted_dates.update(_weekday_dates(row['start_date'], row['end_date']))

    recent_cutoff = date.today() - timedelta(days=30)
    recent_30 = []
    for row in rows:
        if row['start_date'] < recent_cutoff and row['end_date'] < recent_cutoff:
            continue
        if building != 'All' and row['building'] != building:
            continue
        if normalized_types and row['pto_type'] not in normalized_types:
            continue
        recent_30.append(row)
    utilization_30d_pct = round((_count_unique([row['employee'] for row in recent_30]) / active_count) * 100.0, 1) if active_count else 0.0

    type_totals: list[dict] = []
    if filtered:
        grouped_types: dict[str, float] = defaultdict(float)
        for row in filtered:
            grouped_types[row['pto_type']] += float(row['hours'])
        total_for_share = sum(grouped_types.values()) or 1.0
        fallback_colors = ['#45d7ff', '#f24f64', '#7de7ff', '#7b61ff', '#ff9f68']
        for index, (pto_type, hours) in enumerate(sorted(grouped_types.items(), key=lambda item: item[1], reverse=True)):
            color = PTO_TYPE_COLORS.get(pto_type, fallback_colors[index % len(fallback_colors)])
            type_totals.append(
                {
                    'pto_type': pto_type,
                    'hours': round(hours, 1),
                    'days': round(hours / 8.0, 1),
                    'percentage': round((hours / total_for_share) * 100.0, 1),
                    'color': color,
                    'category': _classify_pto_type(pto_type),
                }
            )

    monthly_groups: dict[tuple[int, int], dict[str, object]] = {}
    for row in filtered:
        key = (row['start_date'].year, row['start_date'].month)
        if key not in monthly_groups:
            monthly_groups[key] = {'hours': 0.0, 'types': defaultdict(float)}
        monthly_groups[key]['hours'] = float(monthly_groups[key]['hours']) + float(row['hours'])
        monthly_groups[key]['types'][row['pto_type']] += float(row['hours'])
    monthly_trend: list[dict] = []
    for year, month in sorted(monthly_groups.keys()):
        group = monthly_groups[(year, month)]
        type_hours = group['types']
        dominant_type = max(type_hours.items(), key=lambda item: item[1])[0] if type_hours else None
        month_date = date(year, month, 1)
        total_month_hours = float(group['hours'])
        monthly_trend.append(
            {
                'month': month_date.isoformat(),
                'label': month_date.strftime('%b %Y'),
                'total_hours': round(total_month_hours, 1),
                'total_days': round(total_month_hours / 8.0, 1),
                'dominant_type': dominant_type,
            }
        )

    building_groups: dict[str, dict[str, object]] = {}
    for row in filtered:
        key = row['building'] or 'Unassigned'
        if key not in building_groups:
            building_groups[key] = {'hours': 0.0, 'employees': set()}
        building_groups[key]['hours'] = float(building_groups[key]['hours']) + float(row['hours'])
        building_groups[key]['employees'].add(row['employee'])
    building_totals: list[dict] = []
    for key, value in sorted(building_groups.items(), key=lambda item: float(item[1]['hours']), reverse=True):
        hours = float(value['hours'])
        building_totals.append(
            {
                'building': key,
                'hours': round(hours, 1),
                'days': round(hours / 8.0, 1),
                'employees': len(value['employees']),
            }
        )

    user_groups: dict[tuple[int | None, str, str], dict[str, float]] = {}
    for row in filtered:
        key = (row['employee_id'], row['employee'], row['building'])
        if key not in user_groups:
            user_groups[key] = {'hours': 0.0, 'entries': 0.0}
        user_groups[key]['hours'] += float(row['hours'])
        user_groups[key]['entries'] += 1.0
    ordered_users = sorted(user_groups.items(), key=lambda item: item[1]['hours'], reverse=True)

    top_users: list[dict] = []
    for (employee_id, employee, employee_building), data in ordered_users[:12]:
        top_users.append(
            {
                'employee_id': employee_id,
                'employee': employee,
                'building': employee_building,
                'hours': round(float(data['hours']), 1),
                'days': round(float(data['hours']) / 8.0, 1),
                'entries': int(data['entries']),
            }
        )

    low_usage_employees: list[dict] = []
    if ordered_users:
        slice_size = max(1, ceil(len(ordered_users) * 0.10)) if len(ordered_users) >= 5 else len(ordered_users)
        low_slice = sorted(ordered_users[-slice_size:], key=lambda item: item[1]['hours'])
        for (employee_id, employee, employee_building), data in low_slice[:10]:
            low_usage_employees.append(
                {
                    'employee_id': employee_id,
                    'employee': employee,
                    'building': employee_building,
                    'hours': round(float(data['hours']), 1),
                    'days': round(float(data['hours']) / 8.0, 1),
                    'entries': int(data['entries']),
                }
            )

    names_with_pto = {row['employee'] for row in filtered}
    zero_pto_employees = sorted(
        {
            _format_employee(row.get('last_name', ''), row.get('first_name', ''))
            for row in scoped_active
        } - names_with_pto
    )

    category_totals: dict[str, float] = defaultdict(float)
    for row in filtered:
        category_totals[row['category']] += float(row['hours'])
    category_metrics: list[dict] = []
    category_order = [
        ('planned', 'Planned'),
        ('unplanned', 'Unplanned'),
        ('protected', 'Protected / Neutral'),
        ('other', 'Other'),
    ]
    total_category_hours = sum(category_totals.values()) or 1.0
    for key, label in category_order:
        raw_hours = float(category_totals.get(label, 0.0))
        category_metrics.append(
            {
                'key': key,
                'label': label,
                'hours': round(raw_hours, 1),
                'days': round(raw_hours / 8.0, 1),
                'percentage': round((raw_hours / total_category_hours) * 100.0, 1),
            }
        )

    annualized_total_days = 0.0
    annualized_per_employee_days = 0.0
    trend_delta_pct = 0.0
    trend_direction, trend_label = 'flat', 'Steady'
    if start_date is not None and end_date is not None and filtered:
        period_days = max(1, (end_date - start_date).days + 1)
        annualized_total_days = round((total_days / period_days) * 365.0, 1)
        annualized_per_employee_days = round(((total_days / max(unique_employees, 1)) / period_days) * 365.0, 1)
        midpoint = start_date + timedelta(days=period_days // 2)
        first_half_hours = sum(float(row['hours']) for row in filtered if row['start_date'] < midpoint)
        second_half_hours = sum(float(row['hours']) for row in filtered if row['start_date'] >= midpoint)
        first_half_days = max(1, period_days // 2)
        second_half_days = max(1, period_days - first_half_days)
        first_half_rate = first_half_hours / first_half_days
        second_half_rate = second_half_hours / second_half_days
        if first_half_rate:
            trend_delta_pct = round(((second_half_rate - first_half_rate) / first_half_rate) * 100.0, 1)
        trend_direction, trend_label = _trend_label(trend_delta_pct)

    return {
        'has_data': True,
        'filters': {
            'available_buildings': available_buildings,
            'available_types': available_types,
            'selected_building': building,
            'selected_types': normalized_types,
            'selected_start_date': start_date.isoformat() if start_date else None,
            'selected_end_date': end_date.isoformat() if end_date else None,
            'date_min': min(row['start_date'] for row in rows).isoformat(),
            'date_max': max(row['end_date'] for row in rows).isoformat(),
            'total_records': len(rows),
        },
        'summary': {
            'total_records': len(filtered),
            'total_hours': total_hours,
            'total_days': total_days,
            'days_impacted': len(impacted_dates),
            'employees_used': unique_employees,
            'utilization_pct': utilization_pct,
            'top_type': top_type,
            'avg_days_per_employee': round((total_days / unique_employees), 1) if unique_employees else 0.0,
            'utilization_30d_pct': utilization_30d_pct,
        },
        'type_totals': type_totals,
        'monthly_trend': monthly_trend,
        'building_totals': building_totals,
        'top_users': top_users,
        'low_usage_employees': low_usage_employees,
        'zero_pto_employees': zero_pto_employees[:50],
        'category_metrics': category_metrics,
        'pace': {
            'annualized_total_days': annualized_total_days,
            'annualized_per_employee_days': annualized_per_employee_days,
            'trend_delta_pct': trend_delta_pct,
            'trend_direction': trend_direction,
            'trend_label': trend_label,
        },
        'rows': _build_rows_payload(filtered, limit=max(len(filtered), 1)),
    }


def get_pto_export_rows(
    conn,
    start_date_iso: str | None = None,
    end_date_iso: str | None = None,
    building: str = 'All',
    selected_types: list[str] | None = None,
) -> list[dict]:
    selected_types = [value for value in (selected_types or []) if _clean_text(value)]
    source_rows = [dict(row) for row in repo.load_pto_data(conn)]
    rows = _normalize_stored_rows(source_rows)
    if not rows:
        return []

    filtered, _, _ = _filter_rows(rows, start_date_iso, end_date_iso, building, selected_types)
    return _build_rows_payload(filtered, limit=max(len(filtered), 1))


def export_rows_to_csv(rows: list[dict]) -> str:
    buffer = StringIO()
    buffer.write('employee_id,employee,building,pto_type,start_date,end_date,hours,days\n')
    for row in rows:
        values = [
            '' if row.get('employee_id') is None else str(row.get('employee_id')),
            str(row.get('employee', '')),
            str(row.get('building', '')),
            str(row.get('pto_type', '')),
            str(row.get('start_date', '')),
            str(row.get('end_date', '')),
            str(row.get('hours', '')),
            str(row.get('days', '')),
        ]
        escaped = []
        for value in values:
            safe = value.replace('"', '""')
            if ',' in safe or '"' in safe:
                safe = f'"{safe}"'
            escaped.append(safe)
        buffer.write(','.join(escaped) + '\n')
    return buffer.getvalue()

