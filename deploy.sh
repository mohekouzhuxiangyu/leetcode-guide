#!/usr/bin/env bash
# ============================================================
# 力扣算法学习助手 · 一键部署脚本（Linux / macOS）
#
# 用法：
#   ./deploy.sh            # 安装依赖 + 初始化数据库 + 启动服务
#   ./deploy.sh --setup    # 只做环境准备（不启动服务）
#   ./deploy.sh --start    # 只启动服务（跳过环境检查）
#
# 环境要求：python3（>=3.9）、PostgreSQL（本地或远程，通过 DATABASE_URL 配置）
# ============================================================
set -e
cd "$(dirname "$0")"

PORT="${PORT:-8001}"
MODE="${1:-all}"

echo "=============================================="
echo " 力扣算法学习助手 · 一键部署"
echo "=============================================="

# ---------- 环境准备 ----------
if [ "$MODE" = "all" ] || [ "$MODE" = "--setup" ]; then
  echo "[1/4] 检查 Python 环境..."
  command -v python3 >/dev/null 2>&1 || { echo "错误：未找到 python3"; exit 1; }

  echo "[2/4] 创建虚拟环境并安装依赖..."
  if [ ! -d .venv ]; then
    python3 -m venv .venv
  fi
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q -r requirements.txt
  echo "      依赖安装完成"

  echo "[3/4] 准备 .env 配置文件..."
  if [ ! -f .env ]; then
    cp .env.example .env
    echo "      已生成 .env（请务必编辑填入 DEEPSEEK_API_KEY）"
  else
    echo "      .env 已存在，跳过"
  fi

  echo "[4/4] 初始化数据库..."
  DB_URL="${DATABASE_URL:-postgresql://localhost:5432/leetcode_guide}"
  DB_NAME="${DB_URL##*/}"
  if command -v psql >/dev/null 2>&1; then
    if psql -d "$DB_URL" -c "SELECT 1" >/dev/null 2>&1; then
      echo "      数据库 $DB_NAME 可连接，执行建表脚本（幂等）..."
      psql -d "$DB_URL" -f db/init.sql
    else
      echo "      数据库 $DB_NAME 不存在，尝试创建（需要本机 postgres 可免密连接）..."
      createdb "$DB_NAME" 2>/dev/null && psql -d "$DB_URL" -f db/init.sql \
        || echo "      ⚠️ 无法自动建库，请手动执行：createdb $DB_NAME && psql -d $DB_URL -f db/init.sql"
    fi
  else
    echo "      ⚠️ 未找到 psql，跳过数据库初始化（请确保 $DB_URL 已就绪并执行 db/init.sql）"
  fi
fi

if [ "$MODE" = "--setup" ]; then
  echo "✅ 环境准备完成，可运行 ./deploy.sh 启动服务"
  exit 0
fi

# ---------- 启动服务 ----------
echo "启动服务：http://127.0.0.1:${PORT}"
exec .venv/bin/python -m uvicorn backend.app:app --host 0.0.0.0 --port "$PORT"
