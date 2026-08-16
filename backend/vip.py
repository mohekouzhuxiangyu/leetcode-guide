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


def is_alipay_configured() -> bool:
    return bool(ALIPAY_APP_ID and ALIPAY_PRIVATE_KEY)


def create_order(user_id: int, plan: str, method: str = "page"):
    """创建订单，返回 (order_dict|None, 错误信息)。

    method: "page" 电脑网站支付跳转 / "qr" 扫码支付（alipay.trade.precreate）
    未配置支付宝时为开发模式：返回模拟支付地址/标记。
    """
    plan_info = PLANS.get(plan)
    if not plan_info:
        return None, "不支持的套餐"
    order_no = f"LC{int(time.time())}{secrets.randbelow(10000):04d}"
    query(
        "INSERT INTO vip_orders (user_id, order_no, plan, amount, status) VALUES (%s,%s,%s,%s,'pending')",
        (user_id, order_no, plan, plan_info["amount"]),
    )
    if not is_alipay_configured():
        # 开发模式：模拟支付
        pay_url = f"{APP_BASE_URL}/api/vip/mock-pay?order_no={order_no}"
        return {
            "order_no": order_no,
            "pay_url": pay_url,
            "qr_code": None,
            "dev": True,
            "amount": plan_info["amount"],
            "name": plan_info["name"],
            "desc": plan_info["desc"],
        }, None
    if method == "qr":
        qr_code = _precreate(order_no, plan_info["amount"])
        return {
            "order_no": order_no,
            "pay_url": "",
            "qr_code": qr_code,
            "dev": False,
            "amount": plan_info["amount"],
            "name": plan_info["name"],
            "desc": plan_info["desc"],
        }, None
    pay_url = _build_alipay_url(order_no, plan_info["amount"])
    return {"order_no": order_no, "pay_url": pay_url, "qr_code": None, "dev": False, "amount": plan_info["amount"], "name": plan_info["name"], "desc": plan_info["desc"]}, None


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
