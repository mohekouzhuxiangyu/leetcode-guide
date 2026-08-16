"""历史记录存储：PostgreSQL 持久化。

表结构见 db/init.sql；连接串通过环境变量 DATABASE_URL 配置（backend/db.py）。
按 slug 去重（同一题重复生成会更新记录），记录可归属分组。
"""
import time
from typing import Optional

import psycopg2.extras

from .db import get_conn, query


def _fmt_ts(ts) -> str:
    if not ts:
        return ""
    if hasattr(ts, "strftime"):
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    return str(ts)


def _summary_from_row(r) -> dict:
    return {
        "slug": r["slug"],
        "title": r["title"],
        "difficulty": r["difficulty"],
        "tags": r["tags"] or [],
        "category": r["category"],
        "group": r["group_name"] or "",
        "url": r["url"] or f"https://leetcode.com/problems/{r['slug']}/",
        "created_at": _fmt_ts(r["created_at"]),
        "updated_at": _fmt_ts(r["updated_at"]),
    }


def list_records() -> list[dict]:
    """按更新时间倒序返回摘要列表。"""
    rows = query(
        """SELECT slug, title, difficulty, tags, category, group_name, url, created_at, updated_at
           FROM records ORDER BY updated_at DESC""",
        fetch="all",
    )
    return [_summary_from_row(r) for r in rows]


def get_record(slug: str) -> Optional[dict]:
    row = query("SELECT * FROM records WHERE slug = %s", (slug,), fetch="one")
    if row is None:
        return None
    return {
        "slug": row["slug"],
        "url": row["url"] or f"https://leetcode.com/problems/{row['slug']}/",
        "title": row["title"],
        "difficulty": row["difficulty"],
        "tags": row["tags"] or [],
        "category": row["category"],
        "group": row["group_name"] or "",
        "problem": row["problem"] or {},
        "problem_zh": row["problem_zh"] or "",
        "analysis": row["analysis"] or "",
        "walkthrough": row["walkthrough"] or "",
        "flowchart": row["flowchart"] or "",
        "code": row["code"] or {},
        "errors": row["errors"] or {},
        "created_at": _fmt_ts(row["created_at"]),
        "updated_at": _fmt_ts(row["updated_at"]),
    }


def upsert_record(slug: str, record: dict) -> None:
    """插入或更新记录；未指定分组时保留原有分组，created_at 首次写入后不变。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO records
                  (slug, title, difficulty, tags, category, group_name, url,
                   problem, problem_zh, analysis, walkthrough, flowchart, code, errors,
                   created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now(), now())
                ON CONFLICT (slug) DO UPDATE SET
                  title = EXCLUDED.title,
                  difficulty = EXCLUDED.difficulty,
                  tags = EXCLUDED.tags,
                  category = EXCLUDED.category,
                  group_name = CASE WHEN COALESCE(EXCLUDED.group_name, '') = ''
                                    THEN records.group_name ELSE EXCLUDED.group_name END,
                  url = EXCLUDED.url,
                  problem = EXCLUDED.problem,
                  problem_zh = EXCLUDED.problem_zh,
                  analysis = EXCLUDED.analysis,
                  walkthrough = EXCLUDED.walkthrough,
                  flowchart = EXCLUDED.flowchart,
                  code = EXCLUDED.code,
                  errors = EXCLUDED.errors,
                  updated_at = now()
                """,
                (
                    slug,
                    record.get("title", slug),
                    record.get("difficulty", "Unknown"),
                    psycopg2.extras.Json(record.get("tags") or []),
                    record.get("category", "其他"),
                    record.get("group") or "",
                    record.get("url", ""),
                    psycopg2.extras.Json(record.get("problem") or {}),
                    record.get("problem_zh", ""),
                    record.get("analysis", ""),
                    record.get("walkthrough", ""),
                    record.get("flowchart", ""),
                    psycopg2.extras.Json(record.get("code") or {}),
                    psycopg2.extras.Json(record.get("errors") or {}),
                ),
            )
    finally:
        conn.close()


def delete_record(slug: str) -> bool:
    n = query("DELETE FROM records WHERE slug = %s", (slug,))
    return bool(n)


# ---------------- 分组 ----------------

def list_groups() -> list[dict]:
    """返回分组列表（显式创建 + 记录中出现的分组），带题目数。"""
    explicit = [r["name"] for r in query("SELECT name FROM groups ORDER BY name", fetch="all")]
    count_rows = query(
        "SELECT group_name, COUNT(*) AS c FROM records WHERE group_name <> '' GROUP BY group_name",
        fetch="all",
    )
    counts = {r["group_name"]: r["c"] for r in count_rows}
    ungrouped_row = query(
        "SELECT COUNT(*) AS c FROM records WHERE group_name = '' OR group_name IS NULL", fetch="one"
    )
    ungrouped = ungrouped_row["c"] if ungrouped_row else 0
    names = list(dict.fromkeys(explicit + list(counts.keys())))
    result = [{"name": n, "count": counts.get(n, 0), "explicit": n in explicit} for n in names]
    if ungrouped > 0:
        result.insert(0, {"name": "", "count": ungrouped, "explicit": False})
    return result


def create_group(name: str) -> bool:
    n = query("INSERT INTO groups (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (name,))
    return bool(n)


def delete_group(name: str) -> None:
    query("DELETE FROM groups WHERE name = %s", (name,))


def move_records(slugs: list, group: str) -> int:
    if not slugs:
        return 0
    n = query("UPDATE records SET group_name = %s WHERE slug = ANY(%s)", [group, list(slugs)])
    return n or 0
