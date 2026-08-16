"""刷新共享 hot100 记录的题目信息（重新抓取内容与插图，不重新生成 LLM 内容）。

用法：.venv/bin/python -m backend.refresh_hot100_content
"""
import sys
import time
from pathlib import Path

import psycopg2.extras

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db import get_conn, query  # noqa: E402
from backend.leetcode import fetch_problem  # noqa: E402


def main() -> None:
    rows = query("SELECT slug FROM records WHERE user_id IS NULL ORDER BY slug", fetch="all")
    total = len(rows)
    ok = fail = 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for i, r in enumerate(rows, 1):
                slug = r["slug"]
                p = fetch_problem(slug)
                if not p:
                    print(f"[{i}/{total}] {slug}: 抓取失败，跳过")
                    fail += 1
                    continue
                cur.execute(
                    "UPDATE records SET problem = %s WHERE user_id IS NULL AND slug = %s",
                    (psycopg2.extras.Json(p), slug),
                )
                ok += 1
                imgs = len(p.get("images") or [])
                print(f"[{i}/{total}] {slug}: 更新成功（图片 {imgs} 张）")
                time.sleep(0.1)
    finally:
        conn.close()
    print(f"完成：成功 {ok}，失败 {fail}")


if __name__ == "__main__":
    main()
