# FastAPI + Next.js Migration Notes

The Streamlit app remains the operational fallback and primary production app.

## Current decision (March 8, 2026)

We are **not** replacing Streamlit right now.

The current strategy is:

1. Keep the Streamlit app as the daily-use system because it is functional, familiar, and stable enough to operate.
2. Treat the `backend/` + `frontend/` FastAPI/Next.js work as a parallel side project.
3. Do not cut over to the new stack until it is clearly faster, easier to navigate, and feature-complete for real workflows.
4. Prioritize workflow parity and usability over visual ambition in the migrated app.
5. Use the migration project to gradually earn trust, page by page, instead of forcing a big-bang replacement.

## What already exists in the migration

- `backend/` exposes attendance data, corrective actions, PTO, exports, employee management, and maintenance endpoints through FastAPI.
- `frontend/` contains a Next.js app-router shell with dashboard, employees, operations, corrective actions, exports, manage employees, and PTO pages.
- `atp_core/` remains the source of truth for attendance rules and point recalculation.
- The Streamlit branch backup exists at `codex/streamlit-stable-backup`.

## Working approach going forward

When we work on migration tasks in the future:

1. Streamlit reliability comes first.
2. New-stack work should happen in small slices on the side.
3. We should favor compact, workflow-first internal tooling over oversized or showpiece UI decisions.
4. PTO and other high-value operational pages should preserve the depth of the Streamlit experience before adding extra polish.
5. No production deployment decision should happen until the new app feels genuinely useful day to day.

## Suggested next steps when we resume

1. Keep fixing business logic and operational issues in Streamlit as needed.
2. Tighten the Next.js information density and navigation patterns.
3. Restore missing workflow depth in migrated pages, especially PTO.
4. Reassess hosting only after the new app is truly worth operating.
