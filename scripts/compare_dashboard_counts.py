#!/usr/bin/env python3
"""Compare local dashboard point-bucket counts against deployed observations.

Usage:
  python scripts/compare_dashboard_counts.py
  python scripts/compare_dashboard_counts.py --db /path/to/employeeroster.db
  python scripts/compare_dashboard_counts.py --expected 145,76,41,14,1
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("employeeroster.db"),
        help="SQLite database path (default: ./employeeroster.db)",
    )
    parser.add_argument(
        "--expected",
        type=str,
        default="145,76,41,14,1",
        help="Expected counts in order: all,0,1-4,5-6,7+",
    )
    return parser.parse_args()


def get_counts(db_path: Path) -> tuple[int, int, int, int, int]:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                COUNT(*) AS all_employees,
                SUM(CASE WHEN COALESCE(point_total, 0) = 0 THEN 1 ELSE 0 END) AS zero_points,
                SUM(CASE WHEN COALESCE(point_total, 0) BETWEEN 1 AND 4 THEN 1 ELSE 0 END) AS one_to_four,
                SUM(CASE WHEN COALESCE(point_total, 0) BETWEEN 5 AND 6 THEN 1 ELSE 0 END) AS five_to_six,
                SUM(CASE WHEN COALESCE(point_total, 0) >= 7 THEN 1 ELSE 0 END) AS seven_plus
            FROM employees
            WHERE is_active = 1;
            """
        )
        row = cur.fetchone()
        assert row is not None
        return tuple(int(x or 0) for x in row)
    finally:
        conn.close()


def main() -> int:
    args = parse_args()
    expected = tuple(int(x.strip()) for x in args.expected.split(","))
    if len(expected) != 5:
        raise ValueError("--expected must provide exactly 5 comma-separated integers")

    current = get_counts(args.db)
    labels = ["All Employees", "0 Points", "1-4 Pts", "5-6 Pts", "7+ Pts"]

    print(f"Database: {args.db}")
    print("\nDashboard Bucket Counts")
    print("-" * 60)
    mismatches = 0
    for label, got, exp in zip(labels, current, expected):
        status = "OK" if got == exp else "DIFF"
        if status == "DIFF":
            mismatches += 1
        print(f"{label:18} current={got:>4}  expected={exp:>4}  [{status}]")

    print("-" * 60)
    if mismatches:
        print(f"Result: {mismatches} bucket(s) differ from expected deployed values.")
        return 1

    print("Result: Local data matches expected deployed bucket counts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
