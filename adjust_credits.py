#!/usr/bin/env python3
"""
调整用户积分脚本
使用方法:
  python3 adjust_credits.py <用户名> <增减数量> [原因]
  
示例:
  python3 adjust_credits.py doll +100 充值
  python3 adjust_credits.py doll -50 扣款
  python3 adjust_credits.py yimanxing 200 赠送积分
  
说明:
  - 增减数量可以是正数（增加）或负数（减少）
  - 也可以使用 +/- 前缀明确表示增减
  - 原因为可选项，默认为"管理员调整"
"""

import sys
from server.db import SessionLocal
from server.models import User, CreditTransaction

def _get_user_credits(db, user_id: int) -> int:
    """计算用户当前积分（通过汇总所有交易记录）"""
    total = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).all()
    return sum(t.delta for t in total)

def adjust_credits(username: str, delta: int, reason: str = "管理员调整") -> None:
    db = SessionLocal()
    try:
        # 查找用户
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"❌ 用户 '{username}' 不存在!")
            return
        
        # 记录调整前的积分
        old_credits = _get_user_credits(db, user.id)
        
        # 创建积分交易记录
        tx = CreditTransaction(
            user_id=user.id,
            delta=delta,
            reason=reason
        )
        db.add(tx)
        db.commit()
        
        # 获取调整后的积分
        new_credits = _get_user_credits(db, user.id)
        
        # 显示结果
        action = "增加" if delta > 0 else "减少"
        abs_delta = abs(delta)
        print(f"✅ 积分调整成功:")
        print(f"   用户名: {username}")
        print(f"   操作: {action} {abs_delta} 积分")
        print(f"   原因: {reason}")
        print(f"   调整前: {old_credits} 积分")
        print(f"   调整后: {new_credits} 积分")
        
    except Exception as e:
        print(f"❌ 调整积分失败: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("使用方法: python3 adjust_credits.py <用户名> <增减数量> [原因]")
        print("示例: python3 adjust_credits.py doll +100 充值")
        sys.exit(1)
    
    username = sys.argv[1]
    delta_str = sys.argv[2]
    reason = sys.argv[3] if len(sys.argv) >= 4 else "管理员调整"
    
    # 解析增减数量
    try:
        # 去除可能的 + 前缀
        if delta_str.startswith('+'):
            delta_str = delta_str[1:]
        delta = int(delta_str)
    except ValueError:
        print(f"❌ 无效的数量: {delta_str}")
        print("数量必须是整数，例如: 100, -50, +200")
        sys.exit(1)
    
    if delta == 0:
        print("❌ 增减数量不能为 0")
        sys.exit(1)
    
    adjust_credits(username, delta, reason)

