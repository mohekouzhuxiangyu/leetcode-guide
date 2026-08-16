"""一次性迁移：把所有历史记录移入「hot100」分组，并创建该分组。

用法：.venv/bin/python -m backend.migrate_hot100_group
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import history  # noqa: E402


def main() -> None:
    records = history._load()
    n = len(records)
    for rec in records.values():
        rec["group"] = "hot100"
    history._save(records)
    history.create_group("hot100")
    print(f"已将 {n} 条记录移入「hot100」分组")


if __name__ == "__main__":
    main()
