FROM python:3.11-slim

WORKDIR /app

# 安装 PostgreSQL 客户端（用于初始化数据库）
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY db ./db
COPY .env.example .env.example
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8001
CMD ["./docker-entrypoint.sh"]
