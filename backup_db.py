#!/usr/bin/env python3
"""
Daily SQLite backup script for Casetta.
Keeps 30 rolling daily backups in ~/backups/casetta/

To schedule on PythonAnywhere:
  Go to Dashboard → Tasks → Add a new scheduled task
  Command: python3 /home/marcuslc/backup_db.py
  Frequency: Daily
"""

import os
import shutil
import sqlite3
from datetime import datetime, timedelta

DB_PATH     = os.path.join(os.path.dirname(__file__), "casetta.db")
BACKUP_DIR  = os.path.expanduser("~/backups/casetta")
KEEP_DAYS   = 30

def backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)

    stamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest    = os.path.join(BACKUP_DIR, f"casetta_{stamp}.db")

    # Use SQLite online backup API — safe even while app is running
    src_conn = sqlite3.connect(DB_PATH)
    dst_conn = sqlite3.connect(dest)
    src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()

    size_kb = os.path.getsize(dest) / 1024
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Backup OK → {dest} ({size_kb:.1f} KB)")

    # Prune backups older than KEEP_DAYS
    cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
    pruned = 0
    for fname in os.listdir(BACKUP_DIR):
        if not fname.startswith("casetta_") or not fname.endswith(".db"):
            continue
        fpath = os.path.join(BACKUP_DIR, fname)
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
        if mtime < cutoff:
            os.remove(fpath)
            pruned += 1

    if pruned:
        print(f"  Pruned {pruned} backup(s) older than {KEEP_DAYS} days.")

if __name__ == "__main__":
    backup()
