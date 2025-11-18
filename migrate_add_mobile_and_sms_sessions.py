#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime


DB_PATH = Path(__file__).parent / "app.db"


def column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def add_mobile_column(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    if column_exists(cursor, "users", "mobile"):
        print("[migrate] users.mobile already exists, skipping column addition")
        return

    print("[migrate] adding users.mobile column...")
    cursor.execute("ALTER TABLE users ADD COLUMN mobile TEXT")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_mobile_unique ON users(mobile) WHERE mobile IS NOT NULL")
    conn.commit()


def create_sms_sessions_table(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    if table_exists(cursor, "sms_verify_sessions"):
        print("[migrate] sms_verify_sessions already exists, skipping creation")
        return

    print("[migrate] creating sms_verify_sessions table...")
    cursor.execute(
        """
        CREATE TABLE sms_verify_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mobile TEXT NOT NULL,
            scene TEXT NOT NULL DEFAULT 'login',
            sms_session_id TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            verified_at TEXT,
            attempts INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sms_sessions_mobile ON sms_verify_sessions(mobile)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sms_sessions_created_at ON sms_verify_sessions(created_at)")
    conn.commit()


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"[migrate] database not found at {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        add_mobile_column(conn)
        create_sms_sessions_table(conn)
    finally:
        conn.close()
    print("[migrate] migration completed at", datetime.utcnow().isoformat())


if __name__ == "__main__":
    main()


