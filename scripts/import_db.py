from pathlib import Path
import os, shutil, time

TARGET = Path((os.getenv("ATP_DB_PATH") or "/var/data/employeeroster.db").strip())
SEED = Path(__file__).resolve().parents[1] / "seed" / "employeeroster.db"
FLAG = TARGET.parent / ".import_done"

def main():
    TARGET.parent.mkdir(parents=True, exist_ok=True)

    if not SEED.exists():
        print(f"[import_db] Seed DB not found: {SEED}")
        return

    # Prevent repeated overwrites unless you delete the flag
    if FLAG.exists():
        print("[import_db] Import already done (flag exists). Not overwriting.")
        return

    # If target exists, back it up first (timestamp)
    if TARGET.exists():
        ts = time.strftime("%Y%m%d-%H%M%S")
        backup = TARGET.parent / f"employeeroster.backup-{ts}.db"
        shutil.copy2(TARGET, backup)
        print(f"[import_db] Backed up existing DB to {backup}")

    shutil.copy2(SEED, TARGET)
    FLAG.write_text("ok\n")
    print(f"[import_db] Imported seed DB to {TARGET}")

if __name__ == "__main__":
    main()
