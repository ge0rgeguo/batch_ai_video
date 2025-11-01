#!/usr/bin/env python3
"""
命令行积分管理工具

用法示例：
  # 列出所有用户及当前积分
  python manage_credits.py list

  # 查看某个用户积分
  python manage_credits.py show <用户名>

  # 增加/减少积分（负数为减少）
  python manage_credits.py add <用户名> <数量> [原因]

  # 设定为精确积分（会自动计算差额并写一笔交易）
  python manage_credits.py set <用户名> <目标积分> [原因]

  # 查看积分变动历史
  python manage_credits.py history <用户名> [--limit 20]

说明：
  - 系统采用交易表累计积分（见 server.models.CreditTransaction）。
  - 本工具不会直接修改用户表，仅新增积分交易记录。
  - 数据库连接由 server/db.py 决定（默认 sqlite:///app.db，或使用环境变量 DATABASE_URL）。
"""

import argparse
import sys
from typing import List

from server.db import SessionLocal
from server.models import User, CreditTransaction


def get_user_by_username(db, username: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise SystemExit(f"❌ 用户 '{username}' 不存在")
    return user


def compute_user_credits(db, user_id: int) -> int:
    transactions: List[CreditTransaction] = (
        db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).all()
    )
    return sum(t.delta for t in transactions)


def cmd_list(_: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        users: List[User] = db.query(User).order_by(User.created_at.desc()).all()
        print(f"{'ID':<6}{'用户名':<24}{'权限':<10}{'状态':<8}{'积分':>10}  创建时间")
        print("-" * 70)
        for u in users:
            credits = compute_user_credits(db, u.id)
            role = "管理员" if u.is_admin else "普通"
            status = "启用" if u.enabled else "禁用"
            created = u.created_at.strftime("%Y-%m-%d %H:%M:%S")
            print(f"{u.id:<6}{u.username:<24}{role:<10}{status:<8}{credits:>10}  {created}")
    finally:
        db.close()


def cmd_show(args: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        user = get_user_by_username(db, args.username)
        credits = compute_user_credits(db, user.id)
        print(f"✅ 用户: {user.username}\n当前积分: {credits}")
    finally:
        db.close()


def cmd_add(args: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        user = get_user_by_username(db, args.username)
        if args.amount == 0:
            raise SystemExit("❌ 数量不能为 0")
        reason = args.reason or ("增加积分" if args.amount > 0 else "减少积分")
        tx = CreditTransaction(user_id=user.id, delta=args.amount, reason=reason)
        db.add(tx)
        db.commit()
        new_total = compute_user_credits(db, user.id)
        action = "增加" if args.amount > 0 else "减少"
        print(f"✅ {action} {abs(args.amount)} 分成功，当前积分: {new_total}")
    finally:
        db.close()


def cmd_set(args: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        user = get_user_by_username(db, args.username)
        current = compute_user_credits(db, user.id)
        delta = args.target - current
        if delta == 0:
            print(f"ℹ️  用户 {user.username} 当前已是 {current} 分，无需变更")
            return
        reason = args.reason or f"set_to_{args.target}"
        tx = CreditTransaction(user_id=user.id, delta=delta, reason=reason)
        db.add(tx)
        db.commit()
        print(f"✅ 已将 {user.username} 调整为 {args.target} 分（写入差额 {delta:+d}）")
    finally:
        db.close()


def cmd_history(args: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        user = get_user_by_username(db, args.username)
        q = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.user_id == user.id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(args.limit)
        )
        items = list(q)
        print(f"最近 {len(items)} 条交易记录（用户: {user.username}）")
        print(f"{'时间':<20}  {'变动':>6}  {'原因'}")
        print("-" * 50)
        for t in items:
            ts = t.created_at.strftime("%Y-%m-%d %H:%M:%S")
            print(f"{ts:<20}  {t.delta:>+6}  {t.reason}")
        total = compute_user_credits(db, user.id)
        print("-" * 50)
        print(f"当前积分: {total}")
    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="账户积分管理工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="列出所有用户及积分")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="查看用户积分")
    p_show.add_argument("username", help="用户名")
    p_show.set_defaults(func=cmd_show)

    p_add = sub.add_parser("add", help="增加/减少积分（负数为减少）")
    p_add.add_argument("username", help="用户名")
    p_add.add_argument("amount", type=int, help="变动数量，可为负数")
    p_add.add_argument("reason", nargs="?", default=None, help="原因，可选")
    p_add.set_defaults(func=cmd_add)

    p_set = sub.add_parser("set", help="将积分设为指定数值")
    p_set.add_argument("username", help="用户名")
    p_set.add_argument("target", type=int, help="目标积分")
    p_set.add_argument("reason", nargs="?", default=None, help="原因，可选")
    p_set.set_defaults(func=cmd_set)

    p_hist = sub.add_parser("history", help="查看积分变动历史")
    p_hist.add_argument("username", help="用户名")
    p_hist.add_argument("--limit", type=int, default=20, help="条数，默认20")
    p_hist.set_defaults(func=cmd_history)

    return parser


def main(argv: List[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


