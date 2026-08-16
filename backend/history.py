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
        "url": r["url"] or f"https://leetcode.cn/problems/{r['slug']}/",
        "shared": r["user_id"] is None,
        "created_at": _fmt_ts(r["created_at"]),
        "updated_at": _fmt_ts(r["updated_at"]),
    }


def _groups_map(user_id: int) -> dict:
    """用户记录的分组归属 {slug: [group_name,...]}。"""
    rows = query(
        "SELECT slug, group_name FROM record_groups WHERE user_id = %s",
        (user_id,),
        fetch="all",
    )
    m: dict = {}
    for r in rows:
        m.setdefault(r["slug"], []).append(r["group_name"])
    return m


def list_records(user_id: Optional[int]) -> list[dict]:
    """返回当前用户可见的题目列表。

    user_id 为 None（游客）时只返回共享目录（user_id IS NULL）。
    记录可属于多个分组（groups 数组）。
    """
    if user_id is None:
        rows = query(
            """SELECT slug, title, difficulty, tags, category, group_name, url, user_id, created_at, updated_at
               FROM records WHERE user_id IS NULL ORDER BY updated_at DESC""",
            fetch="all",
        )
        items = []
        for r in rows:
            item = _summary_from_row(r)
            item["groups"] = [r["group_name"]] if r["group_name"] else []
            items.append(item)
        return items
    rows = query(
        """SELECT slug, title, difficulty, tags, category, group_name, url, user_id, created_at, updated_at
           FROM records
           WHERE user_id = %s OR user_id IS NULL
           ORDER BY updated_at DESC""",
        (user_id,),
        fetch="all",
    )
    m = _groups_map(user_id)
    items = []
    for r in rows:
        item = _summary_from_row(r)
        item["groups"] = m.get(r["slug"], []) if r["user_id"] is not None else ([r["group_name"]] if r["group_name"] else [])
        items.append(item)
    return items


def user_has_record(user_id: int, slug: str) -> bool:
    """判断用户是否已生成过该题目（只看用户自己的记录，共享目录不算重复）。"""
    row = query(
        "SELECT 1 FROM records WHERE user_id = %s AND slug = %s",
        (user_id, slug),
        fetch="one",
    )
    return row is not None


def get_record(user_id: Optional[int], slug: str) -> Optional[dict]:
    if user_id is None:
        row = query(
            "SELECT * FROM records WHERE user_id IS NULL AND slug = %s",
            (slug,),
            fetch="one",
        )
    else:
        row = query(
            "SELECT * FROM records WHERE (user_id = %s OR user_id IS NULL) AND slug = %s",
            (user_id, slug),
            fetch="one",
        )
    if row is None:
        return None
    groups = []
    if user_id is not None and row["user_id"] is not None:
        groups = [
            r["group_name"]
            for r in query(
                "SELECT group_name FROM record_groups WHERE user_id = %s AND slug = %s",
                (user_id, slug),
                fetch="all",
            )
        ]
    elif row["user_id"] is None and row["group_name"]:
        groups = [row["group_name"]]
    return {
        "slug": row["slug"],
        "url": row["url"] or f"https://leetcode.cn/problems/{row['slug']}/",
        "title": row["title"],
        "difficulty": row["difficulty"],
        "tags": row["tags"] or [],
        "category": row["category"],
        "group": groups[0] if groups else "",
        "groups": groups,
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
    """删除用户自己的记录及分组归属（共享目录不可删除）。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM record_groups WHERE user_id = %s AND slug = %s", (user_id, slug))
            cur.execute("DELETE FROM records WHERE user_id = %s AND slug = %s", (user_id, slug))
        return True
    finally:
        conn.close()


# ---------------- 分组（多对多：一题可属多组，内容共享） ----------------

def add_to_group(user_id: int, slug: str, group: str) -> bool:
    """把记录加入分组（组内重复自动忽略，返回是否新增）。"""
    if not group:
        return False
    n = query(
        "INSERT INTO record_groups (user_id, slug, group_name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
        (user_id, slug, group),
    )
    return bool(n)


def remove_from_group(user_id: int, slug: str, group: str) -> None:
    query(
        "DELETE FROM record_groups WHERE user_id = %s AND slug = %s AND group_name = %s",
        (user_id, slug, group),
    )


def slugs_in_group(user_id: int, group: str, slugs: list) -> set:
    if not slugs:
        return set()
    rows = query(
        "SELECT slug FROM record_groups WHERE user_id = %s AND group_name = %s AND slug = ANY(%s)",
        [user_id, group, list(slugs)],
        fetch="all",
    )
    return {r["slug"] for r in rows}


def list_groups(user_id: Optional[int]) -> list[dict]:
    """返回分组列表（共享分组 + 用户分组），带题数。游客只看到共享分组。"""
    shared_names = {
        r["name"]
        for r in query("SELECT name FROM groups WHERE user_id IS NULL", fetch="all")
    }
    if user_id is None:
        explicit = [
            r["name"]
            for r in query("SELECT name FROM groups WHERE user_id IS NULL ORDER BY name", fetch="all")
        ]
        count_rows = query(
            """SELECT group_name, COUNT(*) AS c FROM records
               WHERE user_id IS NULL AND group_name <> '' GROUP BY group_name""",
            fetch="all",
        )
        ungrouped_row = query(
            """SELECT COUNT(*) AS c FROM records
               WHERE user_id IS NULL AND (group_name = '' OR group_name IS NULL)""",
            fetch="one",
        )
    else:
        explicit = [
            r["name"]
            for r in query(
                "SELECT name FROM groups WHERE user_id = %s OR user_id IS NULL ORDER BY name",
                (user_id,),
                fetch="all",
            )
        ]
        # 用户分组题数 = 各组去重 slug 数（多对多）
        count_rows = query(
            "SELECT group_name, COUNT(DISTINCT slug) AS c FROM record_groups WHERE user_id = %s GROUP BY group_name",
            (user_id,),
            fetch="all",
        )
        # 共享 hot100 分组
        count_rows += query(
            """SELECT group_name, COUNT(*) AS c FROM records
               WHERE user_id IS NULL AND group_name <> '' GROUP BY group_name""",
            fetch="all",
        )
        ungrouped_row = query(
            "SELECT COUNT(*) AS c FROM records WHERE user_id = %s AND slug NOT IN (SELECT slug FROM record_groups WHERE user_id = %s)",
            (user_id, user_id),
            fetch="one",
        )
    counts = {}
    for r in count_rows:
        counts[r["group_name"]] = counts.get(r["group_name"], 0) + r["c"]
    ungrouped = ungrouped_row["c"] if ungrouped_row else 0
    names = list(dict.fromkeys(explicit + list(counts.keys())))
    result = [
        {"name": n, "count": counts.get(n, 0), "explicit": n in explicit, "shared": n in shared_names}
        for n in names
    ]
    if ungrouped > 0:
        result.insert(0, {"name": "", "count": ungrouped, "explicit": False, "shared": False})
    return result


def user_group_count(user_id: int) -> int:
    """用户拥有的分组数（显式创建 + 隐式由批量/移动产生的分组，去重）。"""
    row = query(
        """SELECT COUNT(*) AS c FROM (
             SELECT DISTINCT group_name AS n FROM record_groups WHERE user_id = %s
             UNION
             SELECT name AS n FROM groups WHERE user_id = %s
           ) t""",
        (user_id, user_id),
        fetch="one",
    )
    return row["c"] if row else 0


def user_has_group(user_id: int, name: str) -> bool:
    """该分组名是否已是用户的分组（显式或隐式）。"""
    row = query(
        """SELECT 1 FROM (
             SELECT DISTINCT group_name AS n FROM record_groups WHERE user_id = %s
             UNION
             SELECT name AS n FROM groups WHERE user_id = %s
           ) t WHERE n = %s""",
        (user_id, user_id, name),
        fetch="one",
    )
    return row is not None


def create_group(user_id: int, name: str) -> bool:
    n = query(
        "INSERT INTO groups (name, user_id) VALUES (%s, %s) ON CONFLICT (name, user_id) WHERE user_id IS NOT NULL DO NOTHING",
        (name, user_id),
    )
    return bool(n)


def delete_group(user_id: int, name: str) -> None:
    query("DELETE FROM groups WHERE user_id = %s AND name = %s", (user_id, name))
    query("DELETE FROM record_groups WHERE user_id = %s AND group_name = %s", (user_id, name))


def move_records(user_id: int, slugs: list, group: str) -> int:
    """把记录加入指定分组（多对多；已在组内自动忽略）。"""
    if not slugs:
        return 0
    n = 0
    for s in slugs:
        if add_to_group(user_id, s, group):
            n += 1
    return n
