"""把旧 JSON 数据迁移到 PostgreSQL。

用法：.venv/bin/python -m backend.migrate_json_to_pg
（迁移后 data/history.json、data/groups.json 保留作为备份，不再使用）
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db import query  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    history_file = DATA_DIR / "history.json"
    groups_file = DATA_DIR / "groups.json"

    records = {}
    if history_file.exists():
        records = json.loads(history_file.read_text(encoding="utf-8"))
    groups = []
    if groups_file.exists():
        groups = json.loads(groups_file.read_text(encoding="utf-8"))

    # 清空旧数据，避免重复迁移
    query("TRUNCATE records, groups RESTART IDENTITY")

    from backend import history

    for slug, rec in records.items():
        history.upsert_record(slug, rec)
    for name in groups:
        query("INSERT INTO groups (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (name,))

    n_records = query("SELECT COUNT(*) AS c FROM records", fetch="one")["c"]
    n_groups = query("SELECT COUNT(*) AS c FROM groups", fetch="one")["c"]
    print(f"迁移完成：records={n_records}，groups={n_groups}")


if __name__ == "__main__":
    main()
