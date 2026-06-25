FROM python:3.11-slim

# PIL 系统依赖（处理 JPEG/PNG/WebP）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev zlib1g-dev libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# 非 root 用户（安全 + 文件权限简单）
RUN useradd -m -u 1000 appuser

WORKDIR /app

# 单独 COPY requirements 以利用 Docker 缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据目录（main.py 启动时也会创建，这里先建好避免权限问题）
RUN mkdir -p assets/input assets/output assets/library assets/uploads \
    output data/canvases data/conversations && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 3000

# 使用 uvicorn 直接启动以启用 --reload
# 保留 main.py:15073 的 ws_ping_interval=None 配置
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000", \
     "--ws-ping-interval", "0", "--reload", "--reload-dir", "/app"]
