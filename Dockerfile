FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（Pillow、cryptography 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY server/ ./server/
COPY public/ ./public/

# 创建必要目录
RUN mkdir -p uploads public/temp-results data

# 非 root 用户运行（安全最佳实践）
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8888

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8888"]
