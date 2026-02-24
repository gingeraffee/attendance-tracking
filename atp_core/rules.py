from __future__ import annotations
from dataclasses import dataclass
from datetime import date

# ---------------------------------------------------------------------------
# Reason options (positive incident reasons only — AUTO entries are system-generated)
# ---------------------------------------------------------------------------
REASON_OPTIONS = [
    "Tardy/Early Leave",
    "Absence",
    "No Call/No Show",
]

# ---------------------------------------------------------------------------
# Core date helpers — ported directly from ATP_Beta7, no external libs
# ---------------------------------------------------------------------------

def add_months(orig: date, months: int) -> date:
    """
    Add calendar months to a date, clamping the day to the last valid day of
    the target month (e.g., Jan 31 + 1 month = Feb 28/29).
    Matches Beta7 add_months() exactly.
    """
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


def first_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def first_of_next_month(d: date) -> date:
    """First day of the month following d. Matches Beta7 first_of_next_month()."""
    return add_months(first_of_month(d), 1)


def two_months_then_first(d: date) -> date:
    """First of the month after (d + 2 months). Used for roll-off cadence."""
    return first_of_next_month(add_months(d, 2))


def three_months_then_first(d: date) -> date:
    """
    First of the month after (d + 3 months). Used for perfect attendance.

    NOTE: In Beta7, three_months_then_first() incorrectly passes 2 (not 3)
    to add_months. That IS a bug in Beta7 that we are NOT carrying forward here.
    The correct policy is 3 full calendar months, confirmed by Nicole.
    """
    return first_of_next_month(add_months(d, 3))


# ---------------------------------------------------------------------------
# Policy calculation — single source of truth
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PolicyDates:
    """
    Holds the two computed date fields for an employee.

    rolloff_date:
        The date the next 2-month roll-off is due.
        Anchored to the most recent point entry of ANY type EXCEPT YTD Roll-Off
        (reason='YTD Roll-Off' AND flag_code='AUTO').
        Formula: first of the month after (anchor + 2 months).

    perfect_date:
        The date the next perfect attendance bonus is due.
        Anchored ONLY to positive point entries (points > 0).
        Formula: first of the month after (anchor + 3 months).
    """
    rolloff_date: date
    perfect_date: date


def calc_rolloff_and_perfect(last_any_point: date, last_positive_point: date) -> PolicyDates:
    """
    Compute rolloff_date and perfect_attendance from two separate anchors.

    Parameters
    ----------
    last_any_point:
        MAX(point_date) from all entries EXCEPT YTD Roll-Offs.
        Drives the roll-off clock.

    last_positive_point:
        MAX(point_date) WHERE points > 0.
        Drives the perfect attendance clock.

    Returns
    -------
    PolicyDates with both computed dates.
    """
    rolloff = two_months_then_first(last_any_point)
    perfect = three_months_then_first(last_positive_point)
    return PolicyDates(rolloff_date=rolloff, perfect_date=perfect)


def step_next_rolloff(current_due: date, perfect_date: date) -> date:
    """
    Advance the roll-off due date one step forward (Beta7 step_next_due logic).

    If the current due date is before the perfect attendance date, the next
    roll-off jumps to 2 months after the perfect date (skipping the
    perfect-attendance month). Otherwise it advances by the normal 2-month
    cadence from the current due date.
    """
    if current_due < perfect_date:
        return two_months_then_first(perfect_date)
    return two_months_then_first(current_due)


def step_next_perfect_attendance(current_due: date) -> date:
    """
    Advance perfect-attendance date by one monthly cycle.

    Perfect attendance bonuses follow a monthly cadence after becoming due,
    so we move to the first day of the next month.
    """
    return first_of_next_month(current_due)
