#!/usr/bin/env python3
"""
为 tasks 表添加 remote_started_at、remote_finished_at 字段
用法（服务器上）：
  cd /home/app/apps/batch_ai_video
  source venv/bin/activate
  python migrate_add_remote_times.py
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path
import shutil


def column_exists(cursor: sqlite3.Cursor, column: str) -> bool:
    cursor.execute("PRAGMA table_info(tasks)")
    return any(row[1] == column for row in cursor.fetchall())


def add_column(cursor: sqlite3.Cursor, column: str) -> None:
    if column_exists(cursor, column):
        print(f"[migrate] 列 {column} 已存在，跳过")
        return
    print(f"[migrate] 添加列 {column} ...")
    cursor.execute(f"ALTER TABLE tasks ADD COLUMN {column} DATETIME")


def migrate(db_path: Path) -> None:
    if not db_path.exists():
        print(f"❌ 数据库不存在: {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    print(f"[migrate] 备份数据库到: {backup_path}")
    shutil.copy2(db_path, backup_path)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        add_column(cursor, "remote_started_at")
        add_column(cursor, "remote_finished_at")
        conn.commit()
        print("[migrate] ✅ 迁移完成")
    except Exception as exc:
        conn.rollback()
        print(f"[migrate] ❌ 迁移失败: {exc}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "app.db"
    migrate(target)

