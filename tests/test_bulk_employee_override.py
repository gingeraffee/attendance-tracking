import sqlite3
import unittest
from datetime import date

from atp_core import repo, services
from atp_core.schema import ensure_schema


class BulkEmployeeOverrideTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        ensure_schema(self.conn)

        services.create_employee(
            self.conn,
            employee_id=101,
            last_name="Tester",
            first_name="Taylor",
            start_date=date(2026, 1, 5),
            location="APIM",
        )
        services.add_point(
            self.conn,
            services.preview_add_point(
                employee_id=101,
                point_date=date(2026, 1, 10),
                points=1.0,
                reason="Absence",
                note="Initial point",
            ),
        )
        services.add_point(
            self.conn,
            services.preview_add_point(
                employee_id=101,
                point_date=date(2026, 1, 20),
                points=1.0,
                reason="Absence",
                note="Second point",
            ),
        )

    def tearDown(self) -> None:
        self.conn.close()

    def test_bulk_override_uses_history_backed_adjustment(self) -> None:
        self.conn.execute(
            "UPDATE employees SET point_total = ? WHERE employee_id = ?",
            (9.0, 101),
        )
        self.conn.commit()

        services.apply_bulk_employee_override(
            self.conn,
            employee_id=101,
            point_total=0.5,
            update_point_total=True,
            note="Bulk correction",
        )

        employee = dict(repo.get_employee(self.conn, 101))
        history = repo.get_points_history_ordered(self.conn, 101)

        self.assertEqual(employee["point_total"], 0.5)
        self.assertEqual(history[-1]["points"], -1.5)
        self.assertEqual(history[-1]["reason"], "Manual Adjustment")
        self.assertEqual(history[-1]["flag_code"], "MANUAL")

    def test_bulk_override_preserves_manual_dates_after_recalc(self) -> None:
        services.apply_bulk_employee_override(
            self.conn,
            employee_id=101,
            point_total=1.0,
            update_point_total=True,
            rolloff_date=date(2026, 6, 1),
            update_rolloff_date=True,
            perfect_attendance=date(2026, 7, 1),
            update_perfect_attendance=True,
            note="Bulk correction",
        )

        employee = dict(repo.get_employee(self.conn, 101))

        self.assertEqual(employee["point_total"], 1.0)
        self.assertEqual(employee["rolloff_date"], "2026-06-01")
        self.assertEqual(employee["perfect_attendance"], "2026-07-01")

    def test_bulk_override_recalculates_even_when_no_adjustment_is_needed(self) -> None:
        self.conn.execute(
            "UPDATE employees SET point_total = ? WHERE employee_id = ?",
            (7.0, 101),
        )
        self.conn.commit()

        services.apply_bulk_employee_override(
            self.conn,
            employee_id=101,
            point_total=services.get_history_point_total(self.conn, 101),
            update_point_total=True,
            note="Bulk correction",
        )

        employee = dict(repo.get_employee(self.conn, 101))
        history = repo.get_points_history_ordered(self.conn, 101)

        self.assertEqual(employee["point_total"], 2.0)
        self.assertEqual(len(history), 2)


if __name__ == "__main__":
    unittest.main()
