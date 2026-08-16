"""FastAPI 主应用：用户系统、生成接口、批量生成、历史记录、分组、模板、前端托管。"""
import asyncio
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, history, vip
from .db import query
from .graph import run_pipeline
from .leetcode import extract_slug
from .templates import CATEGORY_TEMPLATES

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="力扣算法学习助手", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- 认证 ----------------

def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    token = ""
    if authorization:
        token = authorization.removeprefix("Bearer ").strip()
    user = auth.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return user


def get_current_user_optional(authorization: Optional[str] = Header(default=None)) -> Optional[dict]:
    """可选的当前用户：未登录返回 None（游客，可浏览共享 hot100）。"""
    if not authorization:
        return None
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return None
    return auth.get_user_by_token(token)


def require_vip(user: dict = Depends(get_current_user)) -> dict:
    """增删改等写操作需要 VIP 权限。"""
    row = auth.get_user_row(user["id"])
    if not auth.is_vip(row):
        raise HTTPException(status_code=403, detail="该操作需要开通 VIP，请先购买会员")
    return user


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/auth/register")
async def register(req: RegisterRequest) -> dict:
    user, token = auth.create_user(req.username, req.email, req.password)
    if user is None:
        raise HTTPException(status_code=400, detail=token)
    verify_url = auth.send_verification_email(user["email"], user["verify_token"])
    return {
        "ok": True,
        "message": "注册成功，请查收验证邮件完成邮箱验证",
        "dev_verify_url": verify_url,  # 未配置 SMTP 时返回验证链接（开发模式）
    }


@app.get("/api/auth/verify", response_class=HTMLResponse)
async def verify_email(token: str, email: str) -> str:
    ok = auth.verify_email(token, email)
    if ok:
        html = """
        <html><head><meta charset="utf-8"><title>验证成功</title></head>
        <body style="font-family:sans-serif;text-align:center;padding-top:80px;">
          <h2 style="color:#16a34a;">✅ 邮箱验证成功</h2>
          <p>现在可以返回应用并登录了。</p>
          <p><a href="/">返回力扣算法学习助手 →</a></p>
        </body></html>
        """
    else:
        html = """
        <html><head><meta charset="utf-8"><title>验证失败</title></head>
        <body style="font-family:sans-serif;text-align:center;padding-top:80px;">
          <h2 style="color:#dc2626;">❌ 验证链接无效或已过期</h2>
          <p><a href="/">返回应用重新注册或登录</a></p>
        </body></html>
        """
    return html


@app.post("/api/auth/login")
async def login(req: LoginRequest) -> dict:
    user, token = auth.login(req.email, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail=token)
    return {"token": token, "user": user}


@app.post("/api/auth/logout")
async def logout(authorization: Optional[str] = Header(default=None)) -> dict:
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    auth.logout(token)
    return {"ok": True}


@app.get("/api/auth/me")
async def me(user: dict = Depends(get_current_user)) -> dict:
    return {"user": user}


# ---------------- VIP 会员 / 支付宝 ----------------

@app.get("/api/vip/plans")
async def vip_plans() -> dict:
    return {"plans": {k: {"name": v["name"], "amount": v["amount"], "desc": v["desc"]} for k, v in vip.PLANS.items()}}


class VipOrderRequest(BaseModel):
    plan: str
    method: str = "page"  # page=电脑跳转, qr=扫码支付


@app.post("/api/vip/order")
async def vip_order(req: VipOrderRequest, user: dict = Depends(get_current_user)) -> dict:
    order, err = vip.create_order(user["id"], req.plan, req.method)
    if order is None:
        raise HTTPException(status_code=400, detail=err)
    return order


@app.get("/api/vip/order/{order_no}")
async def vip_order_status(order_no: str, user: dict = Depends(get_current_user)) -> dict:
    """扫码支付后轮询订单状态。"""
    st = vip.get_order_status(user["id"], order_no)
    if st is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    return st


@app.get("/api/vip/mock-pay")
async def vip_mock_pay(order_no: str) -> RedirectResponse:
    """开发模式：未配置支付宝时点击该链接模拟支付成功。"""
    ok = vip.mark_paid(order_no)
    if ok:
        return RedirectResponse(url="/?vip=ok")
    return RedirectResponse(url="/?vip=fail")


@app.post("/api/vip/alipay/notify")
async def vip_alipay_notify(request: Request) -> str:
    """支付宝异步通知（生产环境验签，开发环境直接按订单号入账）。"""
    form = dict(await request.form())
    if vip.is_alipay_configured() and not vip.verify_alipay_notify(dict(form)):
        return "failure"
    if form.get("trade_status") == "TRADE_SUCCESS" and form.get("out_trade_no"):
        vip.mark_paid(form["out_trade_no"])
    return "success"


@app.post("/api/vip/payjs/notify")
async def vip_payjs_notify(request: Request) -> str:
    """PayJS 异步通知（个人支付宝当面付）：验签后入账。"""
    form = dict(await request.form())
    if not vip.verify_payjs_notify(form):
        return "fail"
    if form.get("return_code") == "1" and form.get("out_trade_no"):
        vip.mark_paid(form["out_trade_no"])
    return "success"


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


def _worker(user_id: int, job_id: str, url: str) -> None:
    def set_stage(stage: str, message: str = "") -> None:
        with _job_lock:
            if job_id in jobs:
                jobs[job_id]["stage"] = stage
                jobs[job_id]["message"] = message

    try:
        result = run_pipeline(url, set_stage)
        history.upsert_record(user_id, result["slug"], _record_from_result(result))
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
async def generate(req: GenerateRequest, user: dict = Depends(require_vip)) -> dict:
    url = (req.url or "").strip()
    slug = extract_slug(url)
    if not slug:
        raise HTTPException(status_code=400, detail="无法解析题目链接，请检查格式（需包含 /problems/ 路径）")

    job_id = uuid.uuid4().hex
    with _job_lock:
        jobs[job_id] = {"status": "running", "stage": "queued", "message": "任务已创建，等待执行…", "result": None, "error": None}
    loop = asyncio.get_running_loop()
    loop.run_in_executor(_executor, _worker, user["id"], job_id, url)
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
            history.upsert_record(item["user_id"], result["slug"], record)
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
async def batch_start(req: BatchStartRequest, user: dict = Depends(require_vip)) -> dict:
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
            queue.append({"url": url, "slug": slug, "group": (req.group or "").strip(), "user_id": user["id"]})
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
async def list_groups_api(user: Optional[dict] = Depends(get_current_user_optional)) -> dict:
    return {"groups": history.list_groups(user["id"] if user else None)}


@app.post("/api/groups")
async def create_group_api(req: GroupRequest, user: dict = Depends(require_vip)) -> dict:
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="分组名称不能为空")
    ok = history.create_group(user["id"], name)
    return {"ok": ok, "name": name}


@app.delete("/api/groups/{name}")
async def delete_group_api(name: str, user: dict = Depends(require_vip)) -> dict:
    history.delete_group(user["id"], name)
    return {"deleted": name}


@app.post("/api/records/move")
async def move_records_api(req: MoveRequest, user: dict = Depends(require_vip)) -> dict:
    n = history.move_records(user["id"], req.slugs, (req.group or "").strip())
    return {"moved": n}


# ---------------- 模板 ----------------

@app.get("/api/templates")
async def get_templates() -> dict:
    return {"templates": CATEGORY_TEMPLATES}


# ---------------- 题目心得（Markdown 文档，按用户独立） ----------------

class NoteRequest(BaseModel):
    content: str = ""


@app.get("/api/notes/{slug}")
async def get_note(slug: str, user: Optional[dict] = Depends(get_current_user_optional)) -> dict:
    """读取自己的题目心得（免费）；游客返回空。"""
    if user is None:
        return {"slug": slug, "content": "", "updated_at": None}
    row = query(
        "SELECT content, updated_at FROM user_notes WHERE user_id = %s AND slug = %s",
        (user["id"], slug),
        fetch="one",
    )
    if not row:
        return {"slug": slug, "content": "", "updated_at": None}
    ts = row["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if row["updated_at"] else None
    return {"slug": slug, "content": row["content"] or "", "updated_at": ts}


@app.put("/api/notes/{slug}")
async def save_note(slug: str, req: NoteRequest, user: dict = Depends(require_vip)) -> dict:
    """保存自己的题目心得（Markdown，VIP 权限）。"""
    query(
        """INSERT INTO user_notes (user_id, slug, content, updated_at)
           VALUES (%s, %s, %s, now())
           ON CONFLICT (user_id, slug) DO UPDATE SET content = EXCLUDED.content, updated_at = now()""",
        (user["id"], slug, req.content or ""),
    )
    return {"ok": True, "slug": slug}


# ---------------- 历史记录（按用户隔离） ----------------

@app.get("/api/history")
async def list_history(user: Optional[dict] = Depends(get_current_user_optional)) -> dict:
    return {"items": history.list_records(user["id"] if user else None)}


@app.get("/api/history/{slug}")
async def get_history(slug: str, user: Optional[dict] = Depends(get_current_user_optional)) -> dict:
    rec = history.get_record(user["id"] if user else None, slug)
    if rec is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return rec


@app.delete("/api/history/{slug}")
async def delete_history(slug: str, user: dict = Depends(require_vip)) -> dict:
    ok = history.delete_record(user["id"], slug)
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
