#!/usr/bin/env bash
# 启动力扣算法学习助手
set -e
cd "$(dirname "$0")"
PORT="${PORT:-8001}"
if [ ! -d .venv ]; then
  echo "首次运行：创建虚拟环境并安装依赖…"
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
echo "启动服务：http://127.0.0.1:${PORT}"
exec .venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port "$PORT"
