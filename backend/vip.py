"""VIP 会员：支付宝支付（开发模式自动模拟支付）。

- 未配置支付宝参数（ALIPAY_APP_ID 为空）时，pay_url 指向本站 mock-pay 接口，
  点击即模拟支付成功，方便本地联调。
- 配置后使用 python-alipay-sdk 生成支付宝 PC 收银台链接，异步通知验签后到账。
"""
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from .db import query

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

PLANS = {
    "monthly": {"name": "月度会员", "amount": "9.90", "days": 30, "desc": "30 天全功能 VIP"},
    "yearly": {"name": "年度会员", "amount": "99.00", "days": 365, "desc": "365 天全功能 VIP（约 8 折）"},
}

ALIPAY_APP_ID = os.getenv("ALIPAY_APP_ID", "")
ALIPAY_PRIVATE_KEY = os.getenv("ALIPAY_PRIVATE_KEY", "")
ALIPAY_PUBLIC_KEY = os.getenv("ALIPAY_PUBLIC_KEY", "")
ALIPAY_NOTIFY_URL = os.getenv("ALIPAY_NOTIFY_URL", "")
ALIPAY_RETURN_URL = os.getenv("ALIPAY_RETURN_URL", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8001")

# PayJS（个人支付宝当面付，payjs.cn）
PAYJS_MCHID = os.getenv("PAYJS_MCHID", "")
PAYJS_KEY = os.getenv("PAYJS_KEY", "")
PAYJS_NOTIFY_URL = os.getenv("PAYJS_NOTIFY_URL", "") or f"{APP_BASE_URL}/api/vip/payjs/notify"


def is_alipay_configured() -> bool:
    return bool(ALIPAY_APP_ID and ALIPAY_PRIVATE_KEY)


def is_payjs_configured() -> bool:
    return bool(PAYJS_MCHID and PAYJS_KEY)


def create_order(user_id: int, plan: str, method: str = "page"):
    """创建订单，返回 (order_dict|None, 错误信息)。

    支付通道优先级：PayJS（个人当面付扫码）> 支付宝官方（page/qr）> 开发模式模拟。
    """
    plan_info = PLANS.get(plan)
    if not plan_info:
        return None, "不支持的套餐"
    order_no = f"LC{int(time.time())}{secrets.randbelow(10000):04d}"
    query(
        "INSERT INTO vip_orders (user_id, order_no, plan, amount, status) VALUES (%s,%s,%s,%s,'pending')",
        (user_id, order_no, plan, plan_info["amount"]),
    )
    base = {
        "order_no": order_no,
        "pay_url": "",
        "qr_code": None,
        "dev": False,
        "provider": "",
        "amount": plan_info["amount"],
        "name": plan_info["name"],
        "desc": plan_info["desc"],
    }
    # 1) PayJS：个人支付宝扫码（当面付）
    if is_payjs_configured():
        qr = _payjs_native(order_no, plan_info["amount"])
        base.update({"qr_code": qr, "provider": "payjs"})
        return base, None
    # 2) 支付宝官方
    if is_alipay_configured():
        if method == "qr":
            base.update({"qr_code": _precreate(order_no, plan_info["amount"]), "provider": "alipay"})
            return base, None
        base.update({"pay_url": _build_alipay_url(order_no, plan_info["amount"]), "provider": "alipay"})
        return base, None
    # 3) 开发模式：模拟支付
    base.update(
        {"dev": True, "pay_url": f"{APP_BASE_URL}/api/vip/mock-pay?order_no={order_no}", "provider": "dev"}
    )
    return base, None


def _precreate(order_no: str, amount: str) -> str:
    """调用 alipay.trade.precreate 生成当面付二维码串（qr_code）。"""
    from alipay import AliPay

    alipay = AliPay(
        appid=ALIPAY_APP_ID,
        app_notify_url=ALIPAY_NOTIFY_URL,
        app_private_key_string=ALIPAY_PRIVATE_KEY,
        alipay_public_key_string=ALIPAY_PUBLIC_KEY,
        sign_type="RSA2",
        debug=False,
    )
    result = alipay.api_alipay_trade_precreate(
        out_trade_no=order_no,
        total_amount=amount,
        subject="力扣算法学习助手 VIP 会员",
        notify_url=ALIPAY_NOTIFY_URL,
    )
    if result.get("code") == "10000" and result.get("qr_code"):
        return result["qr_code"]
    raise RuntimeError(f"支付宝预下单失败: {result}")


def get_order_status(user_id: int, order_no: str):
    """查询订单状态（供前端扫码支付后轮询）。"""
    row = query(
        "SELECT order_no, status, plan, amount, created_at FROM vip_orders WHERE user_id = %s AND order_no = %s",
        (user_id, order_no),
        fetch="one",
    )
    if not row:
        return None
    return {"order_no": row["order_no"], "status": row["status"], "plan": row["plan"], "amount": row["amount"]}


def _build_alipay_url(order_no: str, amount: str) -> str:
    from alipay import AliPay

    alipay = AliPay(
        appid=ALIPAY_APP_ID,
        app_notify_url=ALIPAY_NOTIFY_URL,
        app_private_key_string=ALIPAY_PRIVATE_KEY,
        alipay_public_key_string=ALIPAY_PUBLIC_KEY,
        sign_type="RSA2",
        debug=False,
    )
    order_string = alipay.api_alipay_trade_page_pay(
        out_trade_no=order_no,
        total_amount=amount,
        subject="力扣算法学习助手 VIP 会员",
        return_url=ALIPAY_RETURN_URL,
        notify_url=ALIPAY_NOTIFY_URL,
    )
    return f"https://openapi.alipay.com/gateway.do?{order_string}"


# ---------------- PayJS（个人支付宝当面付扫码） ----------------

def _payjs_sign(params: dict) -> str:
    """PayJS 签名：参数按 key 升序拼接 key=value，末尾加 &key=KEY，MD5 大写。"""
    import hashlib

    items = sorted(params.items())
    raw = "&".join(f"{k}={v}" for k, v in items) + f"&key={PAYJS_KEY}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()


def _payjs_native(order_no: str, amount: str) -> str:
    """调用 PayJS /api/native 创建支付宝当面付订单，返回二维码串。"""
    import requests

    total_fee = str(int(round(float(amount) * 100)))  # 元 -> 分
    params = {
        "mchid": PAYJS_MCHID,
        "total_fee": total_fee,
        "out_trade_no": order_no,
        "body": "力扣算法学习助手 VIP 会员",
        "type": "1",  # 1=支付宝
        "notify_url": PAYJS_NOTIFY_URL,
    }
    params["sign"] = _payjs_sign(params)
    resp = requests.post("https://payjs.cn/api/native", data=params, timeout=20)
    data = resp.json()
    if data.get("return_code") == 1 and data.get("qrcode"):
        return data["qrcode"]
    raise RuntimeError(f"PayJS 下单失败: {data}")


def verify_payjs_notify(form: dict) -> bool:
    """校验 PayJS 异步通知签名。"""
    form = dict(form)
    sign = form.pop("sign", "")
    if not sign:
        return False
    return _payjs_sign(form) == sign


def mark_paid(order_no: str) -> bool:
    """订单支付成功：更新订单状态并给用户开通/续期 VIP。"""
    row = query(
        """UPDATE vip_orders SET status='paid', paid_at=now()
           WHERE order_no=%s AND status='pending' RETURNING user_id, plan""",
        (order_no,),
        fetch="one",
    )
    if not row:
        return False
    plan = PLANS.get(row["plan"], PLANS["monthly"])
    cur = query("SELECT vip_expires_at FROM users WHERE id=%s", (row["user_id"],), fetch="one")
    base = datetime.now(timezone.utc)
    if cur and cur["vip_expires_at"] and cur["vip_expires_at"] > base:
        base = cur["vip_expires_at"]
    new_exp = base + timedelta(days=plan["days"])
    query(
        "UPDATE users SET vip=TRUE, vip_expires_at=%s WHERE id=%s",
        (new_exp, row["user_id"]),
    )
    return True


def grant_vip(email: str, days: int) -> bool:
    """管理员手动为用户开通/续期 VIP（自愿捐款后人工开通）。"""
    email = (email or "").strip().lower()
    if not email or days <= 0:
        return False
    row = query("SELECT id, vip_expires_at FROM users WHERE email = %s", (email,), fetch="one")
    if not row:
        return False
    base = datetime.now(timezone.utc)
    if row["vip_expires_at"] and row["vip_expires_at"] > base:
        base = row["vip_expires_at"]
    new_exp = base + timedelta(days=days)
    query(
        "UPDATE users SET vip=TRUE, vip_expires_at=%s WHERE id=%s",
        (new_exp, row["id"]),
    )
    return True


def verify_alipay_notify(form: dict) -> bool:
    """校验支付宝异步通知签名（生产环境）。"""
    if not is_alipay_configured():
        return False
    from alipay import AliPay

    alipay = AliPay(
        appid=ALIPAY_APP_ID,
        app_notify_url=ALIPAY_NOTIFY_URL,
        app_private_key_string=ALIPAY_PRIVATE_KEY,
        alipay_public_key_string=ALIPAY_PUBLIC_KEY,
        sign_type="RSA2",
        debug=False,
    )
    signature = form.pop("sign", "")
    return alipay.verify(form, signature)
