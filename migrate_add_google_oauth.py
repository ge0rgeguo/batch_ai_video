#!/usr/bin/env python3
"""
数据库迁移脚本：为 User 表添加 email 和 google_id 字段（支持 Google OAuth）

运行方式:
    python migrate_add_google_oauth.py

或者手动执行 SQLite 命令:
    sqlite3 app.db
    ALTER TABLE users ADD COLUMN email VARCHAR(128);
    ALTER TABLE users ADD COLUMN google_id VARCHAR(64);
    CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);
    CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_id ON users (google_id);
"""

import sqlite3
import os

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        print("   如果是首次运行，请先启动服务器让它自动创建数据库")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]

        # 添加 email 字段
        if "email" not in columns:
            print("📝 添加 email 字段...")
            cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(128)")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)")
            print("   ✅ email 字段添加成功")
        else:
            print("   ⏭️  email 字段已存在，跳过")

        # 添加 google_id 字段
        if "google_id" not in columns:
            print("📝 添加 google_id 字段...")
            cursor.execute("ALTER TABLE users ADD COLUMN google_id VARCHAR(64)")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_id ON users (google_id)")
            print("   ✅ google_id 字段添加成功")
        else:
            print("   ⏭️  google_id 字段已存在，跳过")

        conn.commit()
        print("\n✅ 数据库迁移完成！")
        return True

    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
