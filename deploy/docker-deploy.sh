#!/usr/bin/env bash

# ==============================================
# Docker 部署脚本
# 用途: 拉取代码、构建镜像、启动容器
# ==============================================

set -euo pipefail

APP_USER=${APP_USER:-"app"}
APP_HOME="/home/${APP_USER}"
APP_DIR="${APP_HOME}/apps/batch_ai_video"

log() { echo -e "\033[1;32m[$(date +%H:%M:%S)] $*\033[0m"; }
warn() { echo -e "\033[1;33m[$(date +%H:%M:%S)] $*\033[0m"; }
err() { echo -e "\033[1;31m[$(date +%H:%M:%S)] $*\033[0m"; }

# 检查是否在正确目录
if [[ ! -f "docker-compose.yml" ]]; then
    if [[ -d "${APP_DIR}" ]]; then
        cd "${APP_DIR}"
    else
        err "错误: 找不到 docker-compose.yml"
        err "请在项目根目录运行此脚本"
        exit 1
    fi
fi

log "当前目录: $(pwd)"

# 拉取最新代码
if [[ -d ".git" ]]; then
    log "拉取最新代码..."
    git pull origin main
else
    warn "非 Git 仓库，跳过代码拉取"
fi

# 确保 data 目录存在
if [[ ! -d "data" ]]; then
    log "创建 data 目录..."
    mkdir -p data
    # 如果旧的 app.db 存在于根目录，移动它
    if [[ -f "app.db" ]]; then
        log "迁移 app.db 到 data/ 目录..."
        mv app.db data/
    fi
fi

# 确保 uploads 目录存在
mkdir -p uploads public/temp-results

# 构建并启动容器
log "构建并启动容器..."
docker compose up -d --build

# 等待容器启动
log "等待服务启动..."
sleep 3

# 检查容器状态
log "容器状态:"
docker compose ps

# 健康检查
log "健康检查..."
if curl -sf http://localhost:8888/api/health > /dev/null 2>&1; then
    log "✅ 服务健康检查通过"
else
    warn "⚠️  健康检查未通过，查看日志: docker compose logs"
fi

log "✅ 部署完成"
echo ""
echo "========================================"
echo "常用命令:"
echo "  查看日志: docker compose logs -f"
echo "  重启服务: docker compose restart"
echo "  停止服务: docker compose down"
echo "========================================"
