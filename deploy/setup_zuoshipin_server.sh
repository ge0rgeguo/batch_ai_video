#!/usr/bin/env bash

set -euo pipefail

# ==============================================
# 生产一键部署脚本（Ubuntu 22.04）
# 域名：zuoshipin.net（Cloudflare 托管）
# 服务器：阿里云 ECS（你先创建）
# 说明：
# - 单实例部署（进程内队列，禁止多副本）
# - 优先使用 Cloudflare Origin 证书；若未安装证书则先以 HTTP 运行
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
ENV_DIR="${APP_HOME}/secrets"
ENV_FILE="${ENV_DIR}/app.env"
SERVICE_NAME="ai-batch"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
ORIGIN_CERT_DIR="/etc/ssl/origin"
ORIGIN_CERT_FILE="${ORIGIN_CERT_DIR}/cf-origin.crt"
ORIGIN_KEY_FILE="${ORIGIN_CERT_DIR}/cf-origin.key"
NGINX_SITE="/etc/nginx/sites-available/${SERVICE_NAME}"
USE_ALIYUN_MIRROR="${USE_ALIYUN_MIRROR:-0}"

log() { echo -e "\033[1;32m[$(date +%H:%M:%S)] $*\033[0m"; }
warn() { echo -e "\033[1;33m[$(date +%H:%M:%S)] $*\033[0m"; }
err() { echo -e "\033[1;31m[$(date +%H:%M:%S)] $*\033[0m"; }

log "1) 安装系统依赖 (git, nginx, python, ufw, fail2ban)"
# 可选：仅当 USE_ALIYUN_MIRROR=1 时，切换为阿里云 apt 镜像源；默认在香港/海外保持系统默认源
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
DEBIAN_FRONTEND=noninteractive apt-get install -y git nginx python3-venv python3-pip ufw fail2ban

log "2) 创建业务用户与目录: ${APP_USER}"
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "${APP_USER}"
fi
mkdir -p "${APP_HOME}/apps" "${ENV_DIR}"
chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}"

log "3) 防火墙：放行 22/80/443"
ufw allow OpenSSH || true
ufw allow http || true
ufw allow https || true
ufw --force enable || true

log "4) 拉取代码仓库"
sudo -iu "${APP_USER}" bash -lc "cd ${APP_HOME}/apps && \
  if [[ -d batch_ai_video ]]; then \
    cd batch_ai_video && git pull --rebase; \
  else \
    git clone '${REPO_URL}' batch_ai_video; \
  fi"

log "5) Python 虚拟环境与依赖安装"
sudo -iu "${APP_USER}" bash -lc "\
  cd '${APP_DIR}' && \
  python3 -m venv venv && \
  source venv/bin/activate && \
  pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com && \
  pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com"

log "6) 生成或设置生产环境变量文件"
read -r -s -p "请输入平台级 YUNWU_API_KEY（输入不可见）：" YW_KEY || true; echo
if [[ -z "${YW_KEY:-}" ]]; then
  warn "未输入 YUNWU_API_KEY，将占位写入，请稍后手动修改 ${ENV_FILE}"
  YW_KEY="PLEASE_SET_ME"
fi

# 生成随机加密主密钥（Fernet 32字节 urlsafe base64）
CRYPTO_SECRET=$(python3 - <<'PY'
import base64,os
print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PY
)

# 创建临时 env 文件，然后复制到目标位置
TMP_ENV=$(mktemp)
cat > "${TMP_ENV}" <<EOF
PUBLIC_BASE_URL=https://${DOMAIN}
YUNWU_API_KEY=${YW_KEY}
CRYPTO_SECRET=${CRYPTO_SECRET}
DISABLE_BACKGROUND=false
HOST=127.0.0.1
PORT=8888
EOF

sudo -iu "${APP_USER}" bash -c "\
  mkdir -p '${ENV_DIR}' && \
  cp '${TMP_ENV}' '${ENV_FILE}' && \
  chmod 600 '${ENV_FILE}'"
rm -f "${TMP_ENV}"

log "7) 初始化数据库（若首次）"
sudo -iu "${APP_USER}" bash -lc "\
  cd '${APP_DIR}' && \
  source venv/bin/activate && \
  python3 -c 'from server.db import init_db; init_db()'"

log "7.5) 创建必要的目录"
sudo -iu "${APP_USER}" bash -lc "\
  cd '${APP_DIR}' && \
  mkdir -p uploads public/temp-results && \
  chmod 755 uploads public/temp-results"

log "8) 写入 systemd 服务（单实例，禁止多副本）"
cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=AI Batch Video WebApp (single worker)
After=network.target

[Service]
User=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${APP_DIR}/venv/bin/uvicorn server.app:app --host 127.0.0.1 --port 8888 --log-level info
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}"

log "9) 配置 Nginx 反代"
mkdir -p "${ORIGIN_CERT_DIR}"

if [[ -f "${ORIGIN_CERT_FILE}" && -f "${ORIGIN_KEY_FILE}" ]]; then
  log "检测到 Cloudflare Origin 证书，启用 HTTPS 配置"
  cat > "${NGINX_SITE}" <<EOF
server {
    listen 80;
    server_name ${DOMAIN};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

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
  warn "未发现 ${ORIGIN_CERT_FILE} / ${ORIGIN_KEY_FILE}，先以 HTTP 运行；完成 Cloudflare Origin 证书安装后可重跑此脚本或手工改 HTTPS"
  cat > "${NGINX_SITE}" <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

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

log "10) 验收"
systemctl --no-pager status "${SERVICE_NAME}" || true
echo "\n========================================"
echo "域名: https://${DOMAIN}"
if [[ -f "${ORIGIN_CERT_FILE}" ]]; then
  echo "Nginx: 已开启 HTTPS (Cloudflare Origin 证书)"
else
  echo "Nginx: 当前为 HTTP（待安装 Cloudflare Origin 证书后切换 HTTPS）"
fi
echo "env 文件: ${ENV_FILE}"
echo "日志: journalctl -u ${SERVICE_NAME} -f"
echo "========================================\n"

log "完成。请在 Cloudflare DNS 将 ${DOMAIN} 指向此服务器公网 IP（橙云代理），并在 SSL/TLS 选择 Full (strict)。"



