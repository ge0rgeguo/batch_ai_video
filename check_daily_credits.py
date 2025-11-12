#!/usr/bin/env python3
"""
查看今日积分使用情况
使用方法:
  python3 check_daily_credits.py           # 查看今天
  python3 check_daily_credits.py 2025-11-12  # 查看指定日期
"""

import sys
from datetime import datetime, timedelta
from collections import defaultdict
from server.db import SessionLocal
from server.models import User, CreditTransaction


def check_daily_credits(target_date: str = None):
    """查看指定日期的积分使用情况"""
    db = SessionLocal()
    try:
        # 确定查询日期
        if target_date:
            try:
                date = datetime.strptime(target_date, "%Y-%m-%d")
            except ValueError:
                print(f"❌ 日期格式错误，请使用 YYYY-MM-DD 格式，例如: 2025-11-12")
                return
        else:
            date = datetime.now()
        
        # 计算日期范围（当天0点到23:59:59）
        start_time = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1)
        
        # 查询当天的所有积分交易
        transactions = (
            db.query(CreditTransaction)
            .filter(
                CreditTransaction.created_at >= start_time,
                CreditTransaction.created_at < end_time
            )
            .all()
        )
        
        if not transactions:
            print(f"\n📅 {start_time.strftime('%Y-%m-%d')} 无积分消费记录\n")
            return
        
        # 按用户统计
        user_stats = defaultdict(lambda: {"consume": 0, "recharge": 0, "net": 0, "count": 0})
        
        for tx in transactions:
            user_id = tx.user_id
            if tx.delta < 0:
                user_stats[user_id]["consume"] += abs(tx.delta)
            else:
                user_stats[user_id]["recharge"] += tx.delta
            user_stats[user_id]["net"] += tx.delta
            user_stats[user_id]["count"] += 1
        
        # 获取用户信息
        user_ids = list(user_stats.keys())
        users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
        
        # 计算用户当前总积分
        def get_total_credits(user_id):
            all_tx = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).all()
            return sum(t.delta for t in all_tx)
        
        # 显示结果
        print(f"\n{'='*90}")
        print(f"📅 {start_time.strftime('%Y年%m月%d日')} 积分使用统计")
        print(f"{'='*90}")
        print(f"{'用户名':<20} {'消费':>10} {'充值':>10} {'净变化':>10} {'当前余额':>10} {'交易次数':>8}")
        print(f"{'-'*90}")
        
        total_consume = 0
        total_recharge = 0
        total_net = 0
        
        # 按消费量排序
        sorted_users = sorted(user_stats.items(), key=lambda x: x[1]["consume"], reverse=True)
        
        for user_id, stats in sorted_users:
            user = users.get(user_id)
            username = user.username if user else f"[已删除用户{user_id}]"
            current_credits = get_total_credits(user_id)
            
            consume = stats["consume"]
            recharge = stats["recharge"]
            net = stats["net"]
            count = stats["count"]
            
            total_consume += consume
            total_recharge += recharge
            total_net += net
            
            # 消费显示为负数
            consume_display = f"-{consume}" if consume > 0 else "0"
            recharge_display = f"+{recharge}" if recharge > 0 else "0"
            net_display = f"{net:+d}"
            
            print(f"{username:<20} {consume_display:>10} {recharge_display:>10} {net_display:>10} {current_credits:>10} {count:>8}")
        
        print(f"{'-'*90}")
        total_consume_display = f"-{total_consume}" if total_consume > 0 else "0"
        total_recharge_display = f"+{total_recharge}" if total_recharge > 0 else "0"
        total_net_display = f"{total_net:+d}"
        print(f"{'总计':<20} {total_consume_display:>10} {total_recharge_display:>10} {total_net_display:>10} {' ':>10} {len(transactions):>8}")
        print(f"{'='*90}\n")
        
        # 额外统计信息
        print(f"📊 统计汇总:")
        print(f"   活跃用户数: {len(user_stats)} 人")
        print(f"   总交易次数: {len(transactions)} 笔")
        print(f"   总消费积分: {total_consume} 分")
        print(f"   总充值积分: {total_recharge} 分")
        print(f"   净变化: {total_net:+d} 分")
        print()
        
    finally:
        db.close()


if __name__ == "__main__":
    target_date = sys.argv[1] if len(sys.argv) > 1 else None
    check_daily_credits(target_date)

