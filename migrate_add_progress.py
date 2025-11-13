#!/usr/bin/env python3
"""
数据库迁移脚本：为 tasks 表添加 progress 列
用法（服务器上）：
  cd /home/app/apps/batch_ai_video
  source venv/bin/activate
  python migrate_add_progress.py
"""

import sys
import sqlite3
from pathlib import Path

def migrate(db_path: str):
    print(f"[migrate] 连接数据库: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("[migrate] 检查当前表结构...")
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'")
        old_schema = cursor.fetchone()
        if old_schema:
            print(f"[migrate] 旧表结构（前500字符）: {old_schema[0][:500]}...")
            if 'progress' in old_schema[0]:
                print("[migrate] ⚠️  progress 列已存在，无需迁移")
                return
        
        print("[migrate] 开始迁移：添加 progress 列...")
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN TRANSACTION")
        
        # 创建新表，添加 progress 列
        cursor.execute("""
            CREATE TABLE tasks_new (
                id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                prompt TEXT NOT NULL,
                model TEXT NOT NULL,
                orientation TEXT NOT NULL,
                size TEXT NOT NULL,
                duration INTEGER NOT NULL CHECK(duration IN (5, 10, 15, 25)),
                image_path TEXT,
                status TEXT NOT NULL,
                error_summary TEXT,
                progress TEXT,
                retries INTEGER NOT NULL DEFAULT 0,
                rerun_of_task_id TEXT,
                result_path TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                deleted_at DATETIME,
                FOREIGN KEY (batch_id) REFERENCES batches(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # 复制数据
        print("[migrate] 复制现有数据...")
        cursor.execute("""
            INSERT INTO tasks_new
            SELECT id, batch_id, user_id, prompt, model, orientation, size, duration,
                   image_path, status, error_summary, NULL as progress, retries, rerun_of_task_id,
                   result_path, created_at, updated_at, deleted_at
            FROM tasks
        """)
        
        # 删除旧表并重命名
        cursor.execute("DROP TABLE tasks")
        cursor.execute("ALTER TABLE tasks_new RENAME TO tasks")
        
        # 重建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_tasks_batch_id ON tasks(batch_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_tasks_user_id ON tasks(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_tasks_rerun_of_task_id ON tasks(rerun_of_task_id)")
        
        conn.commit()
        conn.execute("PRAGMA foreign_keys=ON")
        
        print("[migrate] ✅ 迁移成功！tasks 表已添加 progress 列")
        
        # 验证
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'")
        new_schema = cursor.fetchone()
        if new_schema and "progress" in new_schema[0]:
            print("[migrate] ✅ 验证通过：progress 列已添加")
        else:
            print("[migrate] ⚠️  验证失败：请检查表结构")
            
    except Exception as e:
        conn.rollback()
        print(f"[migrate] ❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    # 默认数据库路径
    db_path = Path(__file__).parent / "app.db"
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])
    
    if not db_path.exists():
        print(f"❌ 数据库文件不存在: {db_path}")
        sys.exit(1)
    
    # 自动备份
    import shutil
    from datetime import datetime
    backup_path = db_path.with_suffix(f".db.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    print(f"[migrate] 备份数据库到: {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    migrate(str(db_path))

