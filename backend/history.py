"""历史记录存储：JSON 文件持久化，按 slug 去重（同一题重复生成会更新记录）。"""
import json
import os
import threading
import time
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "history.json"

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
                "created_at": rec.get("created_at"),
                "updated_at": rec.get("updated_at"),
            }
        )
    items.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
    return items


def get_record(slug: str) -> Optional[dict]:
    with _lock:
        records = _load()
    return records.get(slug)


def upsert_record(slug: str, record: dict) -> None:
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with _lock:
        records = _load()
        existing = records.get(slug, {})
        record.setdefault("created_at", existing.get("created_at") or now)
        record["updated_at"] = now
        records[slug] = record
        _save(records)


def delete_record(slug: str) -> bool:
    with _lock:
        records = _load()
        if slug in records:
            del records[slug]
            _save(records)
            return True
        return False
