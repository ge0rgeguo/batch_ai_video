#!/usr/bin/env bash

set -euo pipefail

# ==============================================
# Docker 版生产一键部署脚本（Ubuntu 22.04）
# 域名：zuoshipin.net（Cloudflare 托管）
# 服务器：阿里云 ECS（你先创建）
# 说明：
# - 使用 Docker Compose 部署
# - Nginx 保持宿主机安装
# - 优先使用 Cloudflare Origin 证书
# ==============================================

if [[ $EUID -ne 0 ]]; then
  echo "请使用 sudo 运行：sudo $0" >&2
  exit 1
fi

DOMAIN=${DOMAIN:-"zuoshipin.net"}
APP_USER=${APP_USER:-"app"}
APP_HOME="/home/${APP_USER}"
REPO_URL=${REPO_URL:-"https://github.com/ge0rgeguo/batch_ai_video.git"}
APP_DIR="${APP_HOME}/apps/batch_ai_video"
SERVICE_NAME="ai-batch"
ORIGIN_CERT_DIR="/etc/ssl/origin"
ORIGIN_CERT_FILE="${ORIGIN_CERT_DIR}/cf-origin.crt"
ORIGIN_KEY_FILE="${ORIGIN_CERT_DIR}/cf-origin.key"
NGINX_SITE="/etc/nginx/sites-available/${SERVICE_NAME}"
USE_ALIYUN_MIRROR="${USE_ALIYUN_MIRROR:-0}"

log() { echo -e "\033[1;32m[$(date +%H:%M:%S)] $*\033[0m"; }
warn() { echo -e "\033[1;33m[$(date +%H:%M:%S)] $*\033[0m"; }
err() { echo -e "\033[1;31m[$(date +%H:%M:%S)] $*\033[0m"; }

log "1) 安装系统依赖 (git, nginx, docker, ufw, fail2ban)"
if [[ "${USE_ALIYUN_MIRROR}" == "1" ]]; then
  if ! grep -q "mirrors.aliyun.com" /etc/apt/sources.list 2>/dev/null; then
    log "使用阿里云 apt 镜像源..."
    if [[ -f /etc/apt/sources.list ]]; then
      cp /etc/apt/sources.list /etc/apt/sources.list.backup.$(date +%Y%m%d_%H%M%S)
      sed -i 's|http://.*archive.ubuntu.com|http://mirrors.aliyun.com|g; s|http://.*security.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list
      sed -i 's|http://.*mirrors.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list
      log "已配置阿里云 apt 镜像源"
    fi
  fi
else
  log "跳过镜像源替换，使用系统默认源"
fi
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y git nginx curl ufw fail2ban

log "2) 安装 Docker"
if ! command -v docker &> /dev/null; then
  log "Docker 未安装，正在安装..."
  curl -fsSL https://get.docker.com | bash
else
  log "Docker 已安装: $(docker --version)"
fi

log "3) 创建业务用户与目录: ${APP_USER}"
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "${APP_USER}"
fi
usermod -aG docker "${APP_USER}"
mkdir -p "${APP_HOME}/apps"
chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}"

log "4) 防火墙：放行 22/80/443"
ufw allow OpenSSH || true
ufw allow http || true
ufw allow https || true
ufw --force enable || true

log "5) 拉取代码仓库"
sudo -iu "${APP_USER}" bash -lc "cd ${APP_HOME}/apps && \
  if [[ -d batch_ai_video ]]; then \
    cd batch_ai_video && git pull --rebase; \
  else \
    git clone '${REPO_URL}' batch_ai_video; \
  fi"

log "6) 生成环境变量文件"
ENV_FILE="${APP_DIR}/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  read -r -s -p "请输入平台级 YUNWU_API_KEY（输入不可见）：" YW_KEY || true; echo
  if [[ -z "${YW_KEY:-}" ]]; then
    warn "未输入 YUNWU_API_KEY，将占位写入，请稍后手动修改 ${ENV_FILE}"
    YW_KEY="PLEASE_SET_ME"
  fi

  # 生成随机加密主密钥
  CRYPTO_SECRET=$(python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")

  sudo -iu "${APP_USER}" bash -c "cat > '${ENV_FILE}' <<EOF
PUBLIC_BASE_URL=https://${DOMAIN}
YUNWU_API_KEY=${YW_KEY}
CRYPTO_SECRET=${CRYPTO_SECRET}
DISABLE_BACKGROUND=false
DATABASE_URL=sqlite:///data/app.db
EOF
chmod 600 '${ENV_FILE}'"
else
  log "环境变量文件已存在，跳过生成"
fi

log "7) 创建数据目录并迁移数据库"
sudo -iu "${APP_USER}" bash -lc "cd '${APP_DIR}' && \
  mkdir -p data uploads public/temp-results && \
  if [[ -f app.db && ! -f data/app.db ]]; then \
    mv app.db data/; \
    echo '已迁移 app.db 到 data/ 目录'; \
  fi"

log "8) 构建并启动 Docker 容器"
sudo -iu "${APP_USER}" bash -lc "cd '${APP_DIR}' && docker compose up -d --build"

log "9) 配置 Nginx 反代"
mkdir -p "${ORIGIN_CERT_DIR}"

if [[ -f "${ORIGIN_CERT_FILE}" && -f "${ORIGIN_KEY_FILE}" ]]; then
  log "检测到 Cloudflare Origin 证书，启用 HTTPS 配置"
  cat > "${NGINX_SITE}" <<EOF
server {
    listen 80;
    server_name ${DOMAIN};
    client_max_body_size 20M;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN};
    client_max_body_size 20M;

    ssl_certificate     ${ORIGIN_CERT_FILE};
    ssl_certificate_key ${ORIGIN_KEY_FILE};

    location / {
        proxy_pass         http://127.0.0.1:8888;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }

    location /api/ {
        proxy_pass         http://127.0.0.1:8888;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        add_header         Cache-Control "no-store";
    }
}
EOF
else
  warn "未发现 ${ORIGIN_CERT_FILE} / ${ORIGIN_KEY_FILE}，先以 HTTP 运行"
  cat > "${NGINX_SITE}" <<EOF
server {
    listen 80;
    server_name ${DOMAIN};
    client_max_body_size 20M;

    location / {
        proxy_pass         http://127.0.0.1:8888;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }
}
EOF
fi

ln -sf "${NGINX_SITE}" "/etc/nginx/sites-enabled/${SERVICE_NAME}"
nginx -t
systemctl reload nginx

log "10) 禁用旧的 systemd 服务（如果存在）"
if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
  systemctl stop "${SERVICE_NAME}"
  systemctl disable "${SERVICE_NAME}"
  log "已停止并禁用旧的 systemd 服务"
fi

log "11) 验收"
sleep 3
sudo -iu "${APP_USER}" bash -lc "cd '${APP_DIR}' && docker compose ps"

echo ""
echo "========================================"
echo "域名: https://${DOMAIN}"
if [[ -f "${ORIGIN_CERT_FILE}" ]]; then
  echo "Nginx: 已开启 HTTPS (Cloudflare Origin 证书)"
else
  echo "Nginx: 当前为 HTTP（待安装 Cloudflare Origin 证书后切换 HTTPS）"
fi
echo "env 文件: ${ENV_FILE}"
echo ""
echo "常用命令:"
echo "  查看日志: cd ${APP_DIR} && docker compose logs -f"
echo "  重启服务: cd ${APP_DIR} && docker compose restart"
echo "  更新部署: cd ${APP_DIR} && bash deploy/docker-deploy.sh"
echo "========================================"

log "完成。请在 Cloudflare DNS 将 ${DOMAIN} 指向此服务器公网 IP（橙云代理），并在 SSL/TLS 选择 Full (strict)。"
