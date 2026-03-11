# Attendance Tracking Frontend

This Next.js app is the new UI shell for the attendance product. It talks to the FastAPI backend and lets us migrate pages one workflow at a time.

## Run locally

```powershell
npm.cmd install
npm.cmd run dev
```

Set the backend URL if needed:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"
```
