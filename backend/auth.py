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
    # 首个用户认领历史遗留数据（旧版全局数据）
    query("UPDATE records SET user_id = %s WHERE user_id IS NULL", (row["id"],))
    query("UPDATE groups SET user_id = %s WHERE user_id IS NULL", (row["id"],))
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
    user = {"id": row["id"], "username": row["username"], "email": row["email"], "email_verified": True}
    return user, token


def get_user_by_token(token: str):
    if not token:
        return None
    row = query(
        """SELECT u.id, u.username, u.email, u.email_verified
           FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token = %s""",
        (token,),
        fetch="one",
    )
    return dict(row) if row else None


def logout(token: str) -> None:
    if token:
        query("DELETE FROM sessions WHERE token = %s", (token,))
