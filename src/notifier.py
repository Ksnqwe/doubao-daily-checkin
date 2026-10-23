"""签到结果通知。

支持：Server酱 / 企业微信机器人 / Telegram / Bark / 自定义 Webhook。
任何一个通道挂了都不影响其他通道 —— 通知永远不能反过来搞坏签到。
"""

from __future__ import annotations

import json
import os
import urllib.parse

from . import http, logger
from .client import ALREADY, SUCCESS, CheckinResult

TIMEOUT = 10


def _get(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return ""


def build_message(result: CheckinResult) -> tuple[str, str]:
    """返回 (标题, 正文)。"""
    if result.status == SUCCESS:
        title = "✅ 豆包签到成功" + (f" +{result.amount} 额度" if result.amount else "")
    elif result.status == ALREADY:
        title = "🔁 豆包今日已签到"
    elif result.status == "AUTH_FAILED":
        title = "⚠️ 豆包 Cookie 可能已失效"
    elif result.status == "RISK":
        title = "🛡️ 豆包签到疑似触发风控"
    else:
        title = "❌ 豆包签到失败"

    lines = [
        f"**{title}**",
        "",
        f"- 状态：`{result.status}`",
        f"- 说明：{result.message}",
    ]
    if result.amount:
        lines.append(f"- 获得额度：{result.amount}")
    if result.http_status:
        lines.append(f"- HTTP：{result.http_status}")
    lines.append(f"- 耗时：{result.elapsed:.2f}s（尝试 {result.attempts} 次）")
    if not result.ok:
        lines.append(f"- 响应片段：`{result.body_snippet[:300]}`")
    return title, "\n".join(lines)


def _post_json(url: str, payload: dict, headers: dict | None = None) -> None:
    response = http.request(
        "POST",
        url,
        headers={"Content-Type": "application/json", **(headers or {})},
        body=json.dumps(payload, ensure_ascii=False),
        timeout=TIMEOUT,
    )
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status}: {response.text[:200]}")


def _serverchan(title: str, body: str) -> None:
    key = _get("SERVERCHAN_KEY", "SERVERCHAN_SENDKEY")
    if not key:
        raise RuntimeError("缺少 SERVERCHAN_KEY")
    if key.startswith("sctp"):
        url = f"https://{key.split('t')[0]}.push.ft07.com/send/{key}.send"
    else:
        url = f"https://sctapi.ftqq.com/{key}.send"
    form = urllib.parse.urlencode({"title": title, "desp": body})
    response = http.request(
        "POST",
        url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=form,
        timeout=TIMEOUT,
    )
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status}: {response.text[:200]}")


def _wecom(title: str, body: str) -> None:
    webhook = _get("WECOM_WEBHOOK", "WECOM_WEBHOOK_URL")
    if not webhook:
        raise RuntimeError("缺少 WECOM_WEBHOOK")
    _post_json(webhook, {"msgtype": "markdown", "markdown": {"content": f"### {title}\n{body}"}})


def _telegram(title: str, body: str) -> None:
    token = _get("TELEGRAM_BOT_TOKEN")
    chat_id = _get("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        raise RuntimeError("缺少 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    _post_json(url, {"chat_id": chat_id, "text": f"{title}\n\n{body}", "parse_mode": "Markdown"})


def _bark(title: str, body: str) -> None:
    base = _get("BARK_URL")
    if not base:
        raise RuntimeError("缺少 BARK_URL")
    url = f"{base.rstrip('/')}/{urllib.parse.quote(title)}/{urllib.parse.quote(body)}"
    response = http.request("GET", url, timeout=TIMEOUT)
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status}: {response.text[:200]}")


def _webhook(title: str, body: str) -> None:
    url = _get("CUSTOM_WEBHOOK", "WEBHOOK_URL")
    if not url:
        raise RuntimeError("缺少 CUSTOM_WEBHOOK")
    _post_json(url, {"title": title, "content": body})


CHANNELS = {
    "serverchan": _serverchan,
    "wecom": _wecom,
    "telegram": _telegram,
    "bark": _bark,
    "webhook": _webhook,
}


def notify(result: CheckinResult, channels: list[str], notify_on_already: bool = False) -> None:
    if not channels:
        logger.debug("未配置通知通道，跳过")
        return
    if result.status == ALREADY and not notify_on_already:
        logger.info("今日已签到，按配置不发送通知")
        return

    title, body = build_message(result)
    for name in channels:
        handler = CHANNELS.get(name.lower())
        if handler is None:
            logger.warn(f"未知通知通道：{name}", supported=",".join(CHANNELS))
            continue
        try:
            handler(title, body)
            logger.ok(f"通知已发送 → {name}")
        except Exception as exc:  # 通知失败不影响主流程
            logger.warn(f"通知失败 → {name}：{exc.__class__.__name__}: {exc}")
