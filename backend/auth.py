"""用户系统：注册、登录、邮箱验证、会话管理。

- 密码使用 PBKDF2-SHA256 加盐哈希
- 会话：sessions 表存随机 token，前端通过 Authorization: Bearer <token> 携带
- 邮箱验证：注册生成一次性 token，通过 SMTP 发送验证链接；
  未配置 SMTP 时为开发模式，直接把验证链接打印到日志并返回给前端
"""
import hashlib
import os
import secrets
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from .db import query

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "leetcode-guide@example.com")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8001")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

_PBKDF2_ITERATIONS = 120_000


# ---------------- 密码 ----------------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS).hex()
    return secrets.compare_digest(calc, digest)


def change_password(user_id: int, old_password: str, new_password: str, keep_token: str = "") -> Optional[str]:
    """修改密码：返回 None=成功，否则返回错误信息。

    成功后使该用户的其他会话失效（保留当前会话 keep_token）。
    """
    if len(new_password or "") < 6:
        return "新密码至少 6 位"
    row = query("SELECT password_hash FROM users WHERE id = %s", (user_id,), fetch="one")
    if not row:
        return "用户不存在"
    if not verify_password(old_password or "", row["password_hash"]):
        return "原密码不正确"
    query("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(new_password), user_id))
    if keep_token:
        query("DELETE FROM sessions WHERE user_id = %s AND token <> %s", (user_id, keep_token))
    else:
        query("DELETE FROM sessions WHERE user_id = %s", (user_id,))
    return None


# ---------------- 注册 / 验证 / 登录 ----------------

def create_user(username: str, email: str, password: str):
    """创建用户并返回 (user_dict|None, 错误码|verify_token)。"""
    email = (email or "").strip().lower()
    username = (username or "").strip()
    if not email or "@" not in email:
        return None, "邮箱格式不正确"
    if len(password) < 6:
        return None, "密码至少 6 位"
    if not username:
        return None, "用户名不能为空"
    if query("SELECT id FROM users WHERE email = %s", (email,), fetch="one"):
        return None, "该邮箱已注册"
    if query("SELECT id FROM users WHERE username = %s", (username,), fetch="one"):
        return None, "该用户名已被占用"
    token = secrets.token_urlsafe(32)
    row = query(
        """INSERT INTO users (username, email, password_hash, verify_token)
           VALUES (%s,%s,%s,%s) RETURNING id, username, email, email_verified, verify_token""",
        (username, email, hash_password(password), token),
        fetch="one",
    )
    return dict(row), token


def verify_email(token: str, email: str) -> bool:
    row = query(
        """UPDATE users SET email_verified = TRUE, verify_token = NULL
           WHERE verify_token = %s AND email = %s RETURNING id""",
        (token, (email or "").strip().lower()),
        fetch="one",
    )
    return row is not None


def send_verification_email(email: str, token: str) -> str:
    """发送验证邮件；未配置 SMTP 时返回验证链接（开发模式，同时打印到日志）。"""
    url = f"{APP_BASE_URL}/api/auth/verify?token={token}&email={email}"
    if not SMTP_HOST:
        print(f"[auth][开发模式] 邮箱验证链接: {url}")
        return url
    msg = EmailMessage()
    msg["Subject"] = "力扣算法学习助手 · 邮箱验证"
    msg["From"] = SMTP_FROM
    msg["To"] = email
    msg.set_content(f"欢迎使用力扣算法学习助手！\n\n请点击以下链接完成邮箱验证：\n{url}\n\n如非本人操作，请忽略本邮件。")
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=20) as server:
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
    return ""


def login(email: str, password: str):
    """返回 (user_dict|None, token|错误信息)。"""
    email = (email or "").strip().lower()
    row = query("SELECT * FROM users WHERE email = %s", (email,), fetch="one")
    if not row or not verify_password(password, row["password_hash"]):
        return None, "邮箱或密码错误"
    if not row["email_verified"]:
        return None, "邮箱未验证，请先查收验证邮件完成验证"
    token = secrets.token_urlsafe(48)
    query("INSERT INTO sessions (token, user_id) VALUES (%s, %s)", (token, row["id"]))
    user = _user_public(row)
    return user, token


def _user_public(row) -> dict:
    today = 0
    row2 = query(
        "SELECT count FROM daily_usage WHERE user_id = %s AND day = CURRENT_DATE",
        (row["id"],),
        fetch="one",
    )
    if row2:
        today = int(row2["count"] or 0)
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "email_verified": row["email_verified"],
        "vip": bool(row["vip"]),
        "vip_expires_at": None,  # VIP 为永久，无期限
        "today_usage": today,
        "is_admin": bool(ADMIN_EMAIL) and row["email"].strip().lower() == ADMIN_EMAIL.strip().lower(),
    }


def get_user_by_token(token: str):
    if not token:
        return None
    row = query(
        """SELECT u.id, u.username, u.email, u.email_verified, u.vip, u.vip_expires_at, u.credits
           FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token = %s""",
        (token,),
        fetch="one",
    )
    return _user_public(row) if row else None


def get_user_row(user_id: int):
    return query("SELECT * FROM users WHERE id = %s", (user_id,), fetch="one")


def is_vip(row) -> bool:
    """VIP 是否有效（永久有效，无期限限制）。"""
    return bool(row and row["vip"])


def logout(token: str) -> None:
    if token:
        query("DELETE FROM sessions WHERE token = %s", (token,))
