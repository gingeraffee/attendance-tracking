# Deployed App Parity Review

Reviewed against: `https://pointtracker.streamlit.app/`.

## What I verified

I compared the deployed dashboard with the local app (`atp_streamlit/app.py`) and confirmed that:

- The navigation structure matches (`Dashboard`, `Employees`, `Points Ledger`, `Manage Employees`, `Exports & Forecasts`, `System Updates`).
- The dashboard sections match (overview cards, point overview table, roll-offs/perfect attendance tables, insights, trend chart, hotspots).
- The visual theme/layout in code aligns with what is deployed.

## Gaps found after revert

The biggest mismatch appears to be **data parity**, not UI structure:

- Deployed dashboard bucket counts observed:
  - All Employees: `145`
  - 0 Points: `76`
  - 1–4 Pts: `41`
  - 5–6 Pts: `14`
  - 7+ Pts: `1`
- Local bucket counts at review time:
  - All Employees: `145`
  - 0 Points: `70`
  - 1–4 Pts: `43`
  - 5–6 Pts: `15`
  - 7+ Pts: `6`

This indicates local data has drifted from deployed state (or vice versa).

## Recovery aid added

To speed up reconciliation after a revert, use:

```bash
python scripts/compare_dashboard_counts.py
```

This compares local DB bucket counts to expected deployed values and returns non-zero when they differ.

You can override expected values if production changes:

```bash
python scripts/compare_dashboard_counts.py --expected 145,76,41,14,1
```

Or point at a different SQLite DB:

```bash
python scripts/compare_dashboard_counts.py --db seed/employeeroster.db
```

## Recommended next steps

1. Export/copy the deployed production database snapshot.
2. Diff local vs deployed tables (`employees`, `points_history`) for missing post-revert updates.
3. Re-apply missing records (or replace local DB with a validated production snapshot).
4. Re-run the comparison script until bucket parity is restored.
