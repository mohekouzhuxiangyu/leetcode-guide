"""历史记录存储：PostgreSQL 持久化（共享目录 + 按用户隔离）。

- user_id IS NULL 的记录 = 免费共享目录（hot100），所有注册用户只读可见
- user_id = 某用户 = 该用户独立维护的题目列表（增删改需 VIP）
- 表结构见 db/init.sql；连接串通过环境变量 DATABASE_URL 配置（backend/db.py）。
"""
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
        "shared": r["user_id"] is None,
        "created_at": _fmt_ts(r["created_at"]),
        "updated_at": _fmt_ts(r["updated_at"]),
    }


def list_records(user_id: int) -> list[dict]:
    """返回当前用户可见的题目列表（共享目录 + 自己的记录），按更新时间倒序。"""
    rows = query(
        """SELECT slug, title, difficulty, tags, category, group_name, url, user_id, created_at, updated_at
           FROM records
           WHERE user_id = %s OR user_id IS NULL
           ORDER BY updated_at DESC""",
        (user_id,),
        fetch="all",
    )
    return [_summary_from_row(r) for r in rows]


def get_record(user_id: int, slug: str) -> Optional[dict]:
    row = query(
        "SELECT * FROM records WHERE (user_id = %s OR user_id IS NULL) AND slug = %s",
        (user_id, slug),
        fetch="one",
    )
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
        "shared": row["user_id"] is None,
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


def upsert_record(user_id: Optional[int], slug: str, record: dict) -> None:
    """插入或更新记录（user_id 为空 = 共享目录；否则为用户私有）。"""
    params = (
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
    )
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if user_id is None:
                cur.execute(
                    """
                    INSERT INTO records (user_id, slug, title, difficulty, tags, category, group_name, url,
                                         problem, problem_zh, analysis, walkthrough, flowchart, code, errors,
                                         created_at, updated_at)
                    VALUES (NULL, %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now(), now())
                    ON CONFLICT (slug) WHERE user_id IS NULL DO UPDATE SET
                      title = EXCLUDED.title,
                      difficulty = EXCLUDED.difficulty,
                      tags = EXCLUDED.tags,
                      category = EXCLUDED.category,
                      group_name = EXCLUDED.group_name,
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
                    params,
                )
            else:
                cur.execute(
                    """
                    INSERT INTO records (user_id, slug, title, difficulty, tags, category, group_name, url,
                                         problem, problem_zh, analysis, walkthrough, flowchart, code, errors,
                                         created_at, updated_at)
                    VALUES (%s, %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now(), now())
                    ON CONFLICT (user_id, slug) WHERE user_id IS NOT NULL DO UPDATE SET
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
                    (user_id, *params),
                )
    finally:
        conn.close()


def delete_record(user_id: int, slug: str) -> bool:
    """删除用户自己的记录（共享目录不可删除）。"""
    n = query(
        "DELETE FROM records WHERE user_id = %s AND slug = %s",
        (user_id, slug),
    )
    return bool(n)


# ---------------- 分组 ----------------

def list_groups(user_id: int) -> list[dict]:
    """返回分组列表（共享分组 + 用户分组），带题数。"""
    explicit = [
        r["name"]
        for r in query(
            "SELECT name FROM groups WHERE user_id = %s OR user_id IS NULL ORDER BY name",
            (user_id,),
            fetch="all",
        )
    ]
    count_rows = query(
        """SELECT group_name, COUNT(*) AS c FROM records
           WHERE (user_id = %s OR user_id IS NULL) AND group_name <> '' GROUP BY group_name""",
        (user_id,),
        fetch="all",
    )
    counts = {r["group_name"]: r["c"] for r in count_rows}
    ungrouped_row = query(
        """SELECT COUNT(*) AS c FROM records
           WHERE (user_id = %s OR user_id IS NULL) AND (group_name = '' OR group_name IS NULL)""",
        (user_id,),
        fetch="one",
    )
    ungrouped = ungrouped_row["c"] if ungrouped_row else 0
    names = list(dict.fromkeys(explicit + list(counts.keys())))
    result = [{"name": n, "count": counts.get(n, 0), "explicit": n in explicit} for n in names]
    if ungrouped > 0:
        result.insert(0, {"name": "", "count": ungrouped, "explicit": False})
    return result


def create_group(user_id: int, name: str) -> bool:
    n = query(
        "INSERT INTO groups (name, user_id) VALUES (%s, %s) ON CONFLICT (name, user_id) WHERE user_id IS NOT NULL DO NOTHING",
        (name, user_id),
    )
    return bool(n)


def delete_group(user_id: int, name: str) -> None:
    query("DELETE FROM groups WHERE user_id = %s AND name = %s", (user_id, name))


def move_records(user_id: int, slugs: list, group: str) -> int:
    """把用户自己的记录移动到指定分组。"""
    if not slugs:
        return 0
    n = query(
        "UPDATE records SET group_name = %s WHERE user_id = %s AND slug = ANY(%s)",
        [group, user_id, list(slugs)],
    )
    return n or 0
