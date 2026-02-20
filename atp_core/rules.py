from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from dateutil.relativedelta import relativedelta

REASON_OPTIONS = [
    "Tardy/Early Leave",
    "Absence",
    "No Call/No Show",
    "YTD Roll-Off",
]

@dataclass(frozen=True)
class PolicyDates:
    rolloff_date: date
    perfect_date: date

def first_of_month(d: date) -> date:
    return date(d.year, d.month, 1)

def first_of_next_month(d: date) -> date:
    d2 = d + relativedelta(months=1)
    return date(d2.year, d2.month, 1)

def calc_rolloff_and_perfect(last_point: date) -> PolicyDates:
    # Matches ATP_Beta7
    roll_mark = last_point + relativedelta(months=2)
    perf_mark = last_point + relativedelta(months=3)
    return PolicyDates(
        rolloff_date=first_of_next_month(roll_mark),
        perfect_date=first_of_next_month(perf_mark),
    )
