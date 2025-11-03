#!/usr/bin/env python3
"""
添加新用户脚本
使用方法:
  python3 add_user.py <用户名> <密码> [初始积分] [--admin]
  
示例:
  python3 add_user.py user1 password123
  python3 add_user.py user2 password456 100
  python3 add_user.py superuser secret456 1000 --admin
"""

import sys
import bcrypt
from datetime import datetime
from server.db import SessionLocal
from server.models import User, CreditTransaction

def add_user(username: str, password: str, is_admin: bool = False, initial_credits: int = 0) -> None:
    db = SessionLocal()
    try:
        # 检查用户是否已存在
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"❌ 用户 '{username}' 已存在!")
            return
        
        # 创建新用户 (使用原生 bcrypt)
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        new_user = User(
            username=username,
            password_hash=password_hash,
            is_admin=is_admin,
            enabled=True
        )
        db.add(new_user)
        db.flush()  # 获取 user_id
        
        # 如果指定了初始积分，创建积分交易记录
        if initial_credits > 0:
            credit_tx = CreditTransaction(
                user_id=new_user.id,
                delta=initial_credits,
                reason="初始积分",
                created_at=datetime.utcnow()
            )
            db.add(credit_tx)
        
        db.commit()
        
        role = "管理员" if is_admin else "普通用户"
        print(f"✅ 成功创建用户:")
        print(f"   用户ID: {new_user.id}")
        print(f"   用户名: {username}")
        print(f"   权限: {role}")
        print(f"   初始积分: {initial_credits}")
        print(f"   状态: 启用")
        
    except Exception as e:
        print(f"❌ 创建用户失败: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("使用方法: python3 add_user.py <用户名> <密码> [初始积分] [--admin]")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    is_admin = "--admin" in sys.argv
    
    # 解析初始积分（如果提供）
    initial_credits = 0
    if len(sys.argv) >= 4:
        try:
            # 尝试将第三个参数解析为积分
            initial_credits = int(sys.argv[3])
        except ValueError:
            # 如果不是数字，可能是 --admin 标志
            pass
    
    add_user(username, password, is_admin, initial_credits)

