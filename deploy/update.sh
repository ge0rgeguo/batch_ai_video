#!/usr/bin/env bash

# ==============================================
# 服务器代码更新脚本
# 用途: 从 GitHub 拉取最新代码并重启服务
# ==============================================

set -euo pipefail

APP_USER=${APP_USER:-"app"}
APP_HOME="/home/${APP_USER}"
APP_DIR="${APP_HOME}/apps/batch_ai_video"
SERVICE_NAME="ai-batch"

log() { echo -e "\033[1;32m[$(date +%H:%M:%S)] $*\033[0m"; }
warn() { echo -e "\033[1;33m[$(date +%H:%M:%S)] $*\033[0m"; }
err() { echo -e "\033[1;31m[$(date +%H:%M:%S)] $*\033[0m"; }

if [[ $EUID -eq 0 ]]; then
  log "检测到 root 权限，切换到 ${APP_USER} 用户执行更新"
  exec sudo -iu "${APP_USER}" bash -lc "$0"
fi

log "开始更新代码..."

# 检查代码目录是否存在
if [[ ! -d "${APP_DIR}" ]]; then
  err "错误: 代码目录不存在: ${APP_DIR}"
  err "请先运行部署脚本: sudo bash deploy/setup_zuoshipin_server.sh"
  exit 1
fi

cd "${APP_DIR}"

# 检查是否有未提交的更改
if [[ -n $(git status --porcelain) ]]; then
  warn "检测到未提交的更改:"
  git status --short
  read -p "是否继续更新？(y/N): " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log "已取消更新"
    exit 0
  fi
  # 可以选择暂存或丢弃更改
  log "暂存当前更改..."
  git stash || true
fi

# 拉取最新代码
log "从 GitHub 拉取最新代码..."
git fetch origin
git pull origin main

# 检查是否需要更新依赖
log "检查是否需要更新依赖..."
if [[ -f requirements.txt ]] && [[ requirements.txt -nt venv/.installed ]]; then
  log "检测到 requirements.txt 更新，重新安装依赖..."
  source venv/bin/activate
  pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --upgrade
  touch venv/.installed
fi

# 重启服务（需要 root 权限）
log "更新完成！"
if sudo systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
  log "重启服务 ${SERVICE_NAME}..."
  sudo systemctl restart "${SERVICE_NAME}"
  sleep 2
  if sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
    log "✅ 服务已重启成功"
  else
    err "⚠️  服务重启失败，请检查日志: sudo journalctl -u ${SERVICE_NAME} -n 50"
  fi
else
  warn "服务 ${SERVICE_NAME} 未运行，跳过重启"
fi

log "✅ 代码更新完成！"
log "查看服务状态: sudo systemctl status ${SERVICE_NAME}"
log "查看服务日志: sudo journalctl -u ${SERVICE_NAME} -f"

