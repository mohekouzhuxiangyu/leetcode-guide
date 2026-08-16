"""把历史记录中的题目标题批量回填为中文（通过 leetcode.cn translatedTitle）。

用法：.venv/bin/python -m backend.backfill_titles
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import history  # noqa: E402
from backend.leetcode import fetch_cn_title  # noqa: E402


def main() -> None:
    records = history._load()
    total = len(records)
    updated = 0
    for i, (slug, rec) in enumerate(records.items(), 1):
        if rec.get("problem", {}).get("title_cn"):
            continue  # 已有中文标题
        title_cn = fetch_cn_title(slug)
        if title_cn:
            rec["title"] = title_cn
            rec.setdefault("problem", {})["title_cn"] = title_cn
            updated += 1
            print(f"[{i}/{total}] {slug}: {title_cn}")
        else:
            print(f"[{i}/{total}] {slug}: 获取失败，保留原标题")
        time.sleep(0.15)
    history._save(records)
    print(f"完成：共 {total} 条，更新 {updated} 条中文标题")


if __name__ == "__main__":
    main()
