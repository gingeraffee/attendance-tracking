from __future__ import annotations

import sqlite3
import unittest
from datetime import date

from atp_core import repo, services
from atp_core.schema import ensure_schema


class PerfectAttendanceStartDateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        ensure_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_new_employee_perfect_attendance_uses_start_date_rule(self) -> None:
        cases = {
            date(2026, 3, 10): '2026-07-01',
            date(2026, 3, 1): '2026-07-01',
            date(2026, 3, 31): '2026-07-01',
            date(2025, 12, 15): '2026-04-01',
            date(2026, 1, 20): '2026-05-01',
        }

        for index, (start_date, expected) in enumerate(cases.items(), start=1):
            services.create_employee(
                self.conn,
                employee_id=1000 + index,
                last_name=f'Last{index}',
                first_name=f'First{index}',
                start_date=start_date,
                location='HQ',
            )
            employee = dict(repo.get_employee(self.conn, 1000 + index))
            self.assertEqual(employee['start_date'], start_date.isoformat())
            self.assertEqual(employee['perfect_attendance'], expected)
            self.assertIsNone(employee['rolloff_date'])
            self.assertEqual(float(employee['point_total'] or 0.0), 0.0)

    def test_editing_start_date_reseeds_perfect_attendance_when_no_points_exist(self) -> None:
        services.create_employee(
            self.conn,
            employee_id=2001,
            last_name='Example',
            first_name='Employee',
            start_date=date(2026, 3, 10),
            location='HQ',
        )

        self.conn.execute(
            'UPDATE employees SET start_date = ?, perfect_attendance = NULL WHERE employee_id = ?',
            ('2026-01-20', 2001),
        )
        self.conn.commit()

        services.recalculate_employee_dates(self.conn, 2001)
        employee = dict(repo.get_employee(self.conn, 2001))
        self.assertEqual(employee['perfect_attendance'], '2026-05-01')
        self.assertIsNone(employee['rolloff_date'])


if __name__ == '__main__':
    unittest.main()
