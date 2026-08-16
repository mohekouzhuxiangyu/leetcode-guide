"""PostgreSQL 连接管理。

连接串通过环境变量 DATABASE_URL 配置（见 .env），默认本机 leetcode_guide 库。
"""
import os
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/leetcode_guide")


def get_conn():
    """返回自动提交的 PostgreSQL 连接。"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def query(sql: str, params=None, fetch: str = ""):
    """执行 SQL 并返回结果。

    fetch: "" -> rowcount | "one" -> 单行 dict | "all" -> 行列表 dict
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            if fetch == "one":
                return cur.fetchone()
            if fetch == "all":
                return cur.fetchall()
            return cur.rowcount
    finally:
        conn.close()
