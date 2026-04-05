# Page modules for the Attendance Point Tracker.
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so that `atp_core` and `atp_streamlit`
# are importable regardless of how Streamlit launches the app.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
