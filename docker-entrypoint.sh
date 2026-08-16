#!/bin/sh
# Docker 容器入口：等待数据库就绪 → 初始化表结构 → 启动服务
set -e

echo "[init] 等待数据库就绪..."
if [ -n "$DATABASE_URL" ]; then
  HOST=$(echo "$DATABASE_URL" | sed -E 's#postgresql://[^@]*@([^:/]+).*#\1#')
  PORT_DB=$(echo "$DATABASE_URL" | sed -E 's#postgresql://[^@]*@[^:]+:([0-9]+).*#\1#')
  echo "[init] 等待 $HOST:$PORT_DB ..."
  i=0
  while ! pg_isready -h "$HOST" -p "${PORT_DB:-5432}" >/dev/null 2>&1; do
    i=$((i+1))
    if [ "$i" -gt 60 ]; then echo "[init] 数据库等待超时"; exit 1; fi
    sleep 2
  done
  echo "[init] 初始化表结构（db/init.sql）..."
  psql "$DATABASE_URL" -f /app/db/init.sql
fi

echo "[init] 启动服务..."
exec python -m uvicorn backend.app:app --host 0.0.0.0 --port "${PORT:-8001}"
