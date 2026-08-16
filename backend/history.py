"""历史记录存储：JSON 文件持久化，按 slug 去重（同一题重复生成会更新记录）。

支持分组：记录可归属某个分组（如 hot100），分组清单单独存 groups.json。
"""
import json
import os
import threading
import time
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "history.json"
GROUPS_FILE = DATA_DIR / "groups.json"

_lock = threading.Lock()


def _load() -> dict:
    if not HISTORY_FILE.exists():
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save(records: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = HISTORY_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    os.replace(tmp, HISTORY_FILE)


def list_records() -> list[dict]:
    """按更新时间倒序返回摘要列表。"""
    with _lock:
        records = _load()
    items = []
    for slug, rec in records.items():
        items.append(
            {
                "slug": slug,
                "title": rec.get("title", slug),
                "difficulty": rec.get("difficulty", "Unknown"),
                "tags": rec.get("tags", []),
                "category": rec.get("category", "其他"),
                "group": rec.get("group", ""),
                "url": rec.get("url") or f"https://leetcode.com/problems/{slug}/",
                "created_at": rec.get("created_at"),
                "updated_at": rec.get("updated_at"),
            }
        )
    items.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
    return items


def upsert_record(slug: str, record: dict) -> None:
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with _lock:
        records = _load()
        existing = records.get(slug, {})
        record.setdefault("created_at", existing.get("created_at") or now)
        # 新记录未指定分组时，保留原有分组（避免重新生成时丢失 hot100 等分组）
        if not record.get("group"):
            record["group"] = existing.get("group", "")
        record["updated_at"] = now
        records[slug] = record
        _save(records)


def get_record(slug: str) -> Optional[dict]:
    with _lock:
        records = _load()
    return records.get(slug)


def delete_record(slug: str) -> bool:
    with _lock:
        records = _load()
        if slug in records:
            del records[slug]
            _save(records)
            return True
        return False


# ---------------- 分组 ----------------

def _load_groups() -> list:
    if not GROUPS_FILE.exists():
        return []
    try:
        with open(GROUPS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_groups(groups: list) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)


def list_groups() -> list[dict]:
    """返回分组列表（显式创建 + 记录中出现的分组），带题目数。"""
    with _lock:
        records = _load()
        explicit = _load_groups()
    counts: dict = {}
    for rec in records.values():
        g = rec.get("group") or ""
        counts[g] = counts.get(g, 0) + 1
    names = list(dict.fromkeys([g for g in explicit] + [g for g in counts if g]))
    result = [{"name": g, "count": counts.get(g, 0), "explicit": g in explicit} for g in names]
    if counts.get("", 0) > 0:
        result.insert(0, {"name": "", "count": counts[""], "explicit": False})
    return result


def create_group(name: str) -> bool:
    with _lock:
        groups = _load_groups()
        if name in groups:
            return False
        groups.append(name)
        _save_groups(groups)
        return True


def delete_group(name: str) -> None:
    with _lock:
        groups = _load_groups()
        if name in groups:
            groups.remove(name)
            _save_groups(groups)


def move_records(slugs: list, group: str) -> int:
    """把若干记录移动到指定分组，返回移动数量。"""
    with _lock:
        records = _load()
        n = 0
        for s in slugs:
            if s in records:
                records[s]["group"] = group
                n += 1
        if n:
            _save(records)
        return n
