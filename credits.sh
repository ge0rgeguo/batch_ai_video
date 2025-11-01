#!/usr/bin/env bash
# 积分管理工具包装脚本
# 用法: ./credits.sh [命令] [参数...]
# 示例: ./credits.sh list
#       ./credits.sh add test0 +5000 充值

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检测运行环境
if [[ "$USER" == "app" ]]; then
    # 以 app 用户运行时，直接使用 venv
    if [[ -f "venv/bin/python" ]]; then
        exec venv/bin/python manage_credits.py "$@"
    else
        echo "❌ 错误: 未找到 venv，请先运行部署脚本" >&2
        exit 1
    fi
else
    # 以其他用户（如 root/admin）运行时，切换到 app 用户
    if [[ -f "/home/app/apps/batch_ai_video/venv/bin/python" ]]; then
        exec sudo -iu app bash -lc "cd /home/app/apps/batch_ai_video && venv/bin/python manage_credits.py \"\$@\"" -- "$@"
    else
        # 尝试当前目录
        if [[ -f "venv/bin/python" ]]; then
            exec venv/bin/python manage_credits.py "$@"
        else
            echo "❌ 错误: 未找到 Python 环境" >&2
            exit 1
        fi
    fi
fi
