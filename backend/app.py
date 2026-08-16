"""FastAPI 主应用：生成接口（后台任务 + 轮询进度）、Hot100 批量生成、历史记录、模板、前端托管。"""
import asyncio
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import history
from .graph import run_pipeline
from .leetcode import extract_slug
from .templates import CATEGORY_TEMPLATES

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="力扣算法学习助手", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- 生成任务（后台执行，前端轮询进度） ----------------

jobs: dict[str, dict] = {}
_job_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=4)


class GenerateRequest(BaseModel):
    url: str


def _record_from_result(result: dict) -> dict:
    problem = result.get("problem") or {}
    return {
        "slug": result["slug"],
        "url": result["url"],
        "title": result["title"],
        "difficulty": problem.get("difficulty", "Unknown"),
        "tags": problem.get("tags", []),
        "category": result.get("category", "其他"),
        "problem": problem,
        "problem_zh": result.get("problem_zh", ""),
        "analysis": result.get("analysis", ""),
        "walkthrough": result.get("walkthrough", ""),
        "flowchart": result.get("flowchart", ""),
        "code": result.get("code", {}),
        "errors": result.get("errors", {}),
    }


def _worker(job_id: str, url: str) -> None:
    def set_stage(stage: str, message: str = "") -> None:
        with _job_lock:
            if job_id in jobs:
                jobs[job_id]["stage"] = stage
                jobs[job_id]["message"] = message

    try:
        result = run_pipeline(url, set_stage)
        history.upsert_record(result["slug"], _record_from_result(result))
        with _job_lock:
            if job_id in jobs:
                jobs[job_id]["status"] = "done"
                jobs[job_id]["result"] = result
    except Exception as exc:  # noqa: BLE001
        print(f"[job {job_id}] 失败: {exc}")
        with _job_lock:
            if job_id in jobs:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"] = str(exc)


@app.post("/api/generate")
async def generate(req: GenerateRequest) -> dict:
    url = (req.url or "").strip()
    slug = extract_slug(url)
    if not slug:
        raise HTTPException(status_code=400, detail="无法解析题目链接，请检查格式（需包含 /problems/ 路径）")

    job_id = uuid.uuid4().hex
    with _job_lock:
        jobs[job_id] = {"status": "running", "stage": "queued", "message": "任务已创建，等待执行…", "result": None, "error": None}
    loop = asyncio.get_running_loop()
    loop.run_in_executor(_executor, _worker, job_id, url)
    return {"job_id": job_id, "slug": slug}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    with _job_lock:
        job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "status": job["status"],
        "stage": job.get("stage"),
        "message": job.get("message"),
        "error": job.get("error"),
        "result": job.get("result"),
    }


# ---------------- 批量生成（通用：输入链接列表 + 可选分组） ----------------

_batch: dict = {
    "status": "idle",  # idle | running | done | stopped | error
    "queue": [],
    "total": 0,
    "done": 0,
    "failed": 0,
    "current": None,
    "message": "",
}
_batch_lock = threading.Lock()
_batch_thread = None


def _batch_worker() -> None:
    """后台线程：顺序生成批量队列中的题目。"""
    while True:
        with _batch_lock:
            if _batch["status"] != "running" or not _batch["queue"]:
                if not _batch["queue"] and _batch["status"] == "running":
                    _batch["status"] = "done"
                    _batch["message"] = "批量生成完成"
                break
            item = _batch["queue"][0]
            _batch["current"] = item
        try:
            result = run_pipeline(item["url"])
            record = _record_from_result(result)
            if item.get("group"):
                record["group"] = item["group"]
            history.upsert_record(result["slug"], record)
            with _batch_lock:
                _batch["done"] += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[batch] {item.get('slug')} 失败: {exc}")
            with _batch_lock:
                _batch["failed"] += 1
        with _batch_lock:
            if _batch["queue"]:
                _batch["queue"].pop(0)
            _batch["current"] = None


class BatchStartRequest(BaseModel):
    urls: list = []
    group: str = ""


@app.post("/api/batch/start")
async def batch_start(req: BatchStartRequest) -> dict:
    global _batch_thread
    with _batch_lock:
        if _batch["status"] == "running":
            raise HTTPException(status_code=409, detail="已有批量任务在运行中，请先停止")
        queue = []
        invalid: list[str] = []
        seen = set()
        for raw in req.urls:
            url = (raw or "").strip()
            if not url:
                continue
            slug = extract_slug(url)
            if not slug:
                invalid.append(url)
                continue
            if slug in seen:
                continue
            seen.add(slug)
            queue.append({"url": url, "slug": slug, "group": (req.group or "").strip()})
        if not queue:
            raise HTTPException(status_code=400, detail="没有有效的题目链接（需包含 /problems/ 路径）")
        _batch.update(
            status="running", queue=queue, total=len(queue), done=0, failed=0,
            current=None, message="批量生成进行中…",
        )
    _batch_thread = threading.Thread(target=_batch_worker, daemon=True)
    _batch_thread.start()
    return {"status": "running", "total": len(queue), "invalid_count": len(invalid)}


@app.post("/api/batch/stop")
async def batch_stop() -> dict:
    with _batch_lock:
        if _batch["status"] == "running":
            _batch["status"] = "stopped"
            _batch["message"] = "已手动停止"
    return {"status": _batch["status"]}


@app.get("/api/batch")
async def batch_status() -> dict:
    with _batch_lock:
        snapshot = {
            "status": _batch["status"],
            "total": _batch["total"],
            "done": _batch["done"],
            "failed": _batch["failed"],
            "current": _batch["current"],
            "message": _batch["message"],
        }
    return snapshot


# ---------------- 分组 ----------------

class GroupRequest(BaseModel):
    name: str


class MoveRequest(BaseModel):
    slugs: list = []
    group: str = ""


@app.get("/api/groups")
async def list_groups_api() -> dict:
    return {"groups": history.list_groups()}


@app.post("/api/groups")
async def create_group_api(req: GroupRequest) -> dict:
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="分组名称不能为空")
    ok = history.create_group(name)
    return {"ok": ok, "name": name}


@app.delete("/api/groups/{name}")
async def delete_group_api(name: str) -> dict:
    history.delete_group(name)
    return {"deleted": name}


@app.post("/api/records/move")
async def move_records_api(req: MoveRequest) -> dict:
    n = history.move_records(req.slugs, (req.group or "").strip())
    return {"moved": n}


# ---------------- 模板 ----------------

@app.get("/api/templates")
async def get_templates() -> dict:
    return {"templates": CATEGORY_TEMPLATES}


# ---------------- 历史记录 ----------------

@app.get("/api/history")
async def list_history() -> dict:
    return {"items": history.list_records()}


@app.get("/api/history/{slug}")
async def get_history(slug: str) -> dict:
    rec = history.get_record(slug)
    if rec is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return rec


@app.delete("/api/history/{slug}")
async def delete_history(slug: str) -> dict:
    ok = history.delete_record(slug)
    if not ok:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"deleted": slug}


@app.get("/api/health")
async def health() -> dict:
    from .config import DEEPSEEK_MODEL

    return {"status": "ok", "model": DEEPSEEK_MODEL}


# ---------------- 前端静态托管 ----------------

@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")
