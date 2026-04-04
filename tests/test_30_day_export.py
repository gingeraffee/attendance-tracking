import sqlite3
import unittest
from datetime import date

from atp_core import services
from atp_core.schema import ensure_schema
from atp_streamlit.app import run_export_query


class ThirtyDayExportTests(unittest.TestCase):
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
                point_date=date(2026, 2, 20),
                points=1.0,
                reason="Absence",
                note="Pre-window point",
            ),
            flag_code="MANUAL",
        )
        services.add_point(
            self.conn,
            services.preview_add_point(
                employee_id=101,
                point_date=date(2026, 3, 10),
                points=1.0,
                reason="Absence",
                note="Initial point in window",
            ),
            flag_code="MANUAL",
        )
        services.add_point(
            self.conn,
            services.preview_add_point(
                employee_id=101,
                point_date=date(2026, 3, 12),
                points=0.5,
                reason="Tardy",
                note="Second point in window",
            ),
            flag_code="AUTO",
        )

    def tearDown(self) -> None:
        self.conn.close()

    def test_30_day_export_includes_flag_code_and_per_entry_running_total(self) -> None:
        df = run_export_query(
            self.conn,
            "30-day point history",
            "All",
            date(2026, 3, 1),
            date(2026, 3, 31),
        )

        self.assertIn("Flag Code", df.columns)
        self.assertEqual(df["Flag Code"].tolist(), ["MANUAL", "AUTO"])
        self.assertEqual(df["Point Total"].tolist(), ["2.0", "2.5"])


if __name__ == "__main__":
    unittest.main()
