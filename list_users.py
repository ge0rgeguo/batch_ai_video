#!/usr/bin/env python3
"""
列出所有用户脚本
使用方法:
  python3 list_users.py
"""

from server.db import SessionLocal
from server.models import User

def list_users() -> None:
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        
        print("\n" + "="*80)
        print("系统用户列表".center(80))
        print("="*80)
        print(f"{'ID':<5} {'用户名':<20} {'权限':<10} {'状态':<10} {'创建时间':<25}")
        print("-"*80)
        
        for u in users:
            role = "管理员" if u.is_admin else "普通用户"
            status = "启用" if u.enabled else "禁用"
            created = u.created_at.strftime("%Y-%m-%d %H:%M:%S")
            print(f"{u.id:<5} {u.username:<20} {role:<10} {status:<10} {created:<25}")
        
        print("="*80)
        print(f"共 {len(users)} 个用户\n")
        
    finally:
        db.close()

if __name__ == "__main__":
    list_users()

