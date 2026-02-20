# ATP Web (Streamlit) — Starter

This starter converts ATP Beta7 into a Streamlit web UI while keeping business logic in reusable modules (so FastAPI + React later is a UI swap, not a rewrite).

## Local run

```bash
pip install -r requirements.txt
```

Set the DB path (recommended):

**Windows CMD**
```bat
set ATP_DB_PATH=/mnt/data/employeeroster.db
```

**PowerShell**
```powershell
$env:ATP_DB_PATH="/mnt/data/employeeroster.db"
```

Run:

```bash
streamlit run atp_streamlit/app.py
```

## Deployment notes

- Keep your database **out of git** (see `.gitignore`).
- If you deploy somewhere like Streamlit Cloud, you need a company-approved, secured database location and you’ll set `ATP_DB_PATH` via secrets/environment variables.
