#!/usr/bin/env python3
"""豆包签到状态查询（只读，不领取）。

用途：WorkBuddy 每日汇报时调用，查今日是否已签、连续天数、累计额度。
与 main.py 配套：main.py 负责领取，本脚本只负责"读状态"。

用法：
    python status.py            # 人类可读输出
    python status.py --json     # JSON 输出（供自动化解析）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import logger
from src.config import ConfigError, load_config
from src.http import request

DETAIL_URL = "https://www.doubao.com/alice/ug/campaign/v3/detail/"

# 豆包活动接口要求桌面版客户端指纹，普通 UA 会被服务端拒绝（710010702 系统错误）
COMMON_PARAMS = {
    "version_code": "20800",
    "language": "zh",
    "device_platform": "web",
    "doubao_device_platform": "web",
    "aid": "497858",
    "real_aid": "497858",
    "pkg_type": "release_version",
    "pc_version": "2.32.6",
    "doubao_pc_version": "5.72.66",
    "samantha_web": "1",
    "web_platform": "desktop",
    "use-olympus-account": "1",
    "web_tab_id": "0",
    "web_id": "761234567890123456",
    "tea_uuid": "1234567890123456",
    "device_id": "",
    "region": "",
    "sys_region": "",
}

CAMPAIGN_GROUP = "pc_incentive_task_mvp_v3"
LOGIN_INVALID = 710012001


def build_url() -> str:
    from urllib.parse import urlencode

    return DETAIL_URL + "?" + urlencode(COMMON_PARAMS)


def fetch_status(cookie: str, user_agent: str) -> dict:
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Cookie": cookie,
        "Referer": "https://www.doubao.com/pc/agent-explore",
        "Origin": "https://www.doubao.com",
    }
    resp = request(
        method="POST",
        url=build_url(),
        headers=headers,
        body=json.dumps({"campaign_group_code": CAMPAIGN_GROUP}),
        timeout=20.0,
    )
    try:
        body = json.loads(resp.text)
    except json.JSONDecodeError:
        return {"ok": False, "error": f"响应非 JSON（HTTP {resp.status}）"}

    code = body.get("code")
    if code == LOGIN_INVALID:
        return {"ok": False, "error": "会话已失效，请重新抓取 Cookie", "code": code}
    if code != 0:
        return {
            "ok": False,
            "error": body.get("msg") or body.get("message") or "查询失败",
            "code": code,
        }

    data = body.get("data") or {}
    tasks = data.get("tasks") or []
    task = next((t for t in tasks if t.get("task_kind") == "daily_signin"), None)
    if not task:
        return {
            "ok": False,
            "error": "当前账号没有签到任务（活动未开放，或企业账号不支持参与）",
            "code": code,
        }

    c = task.get("daily_checkin") or {}
    reward = c.get("reward") or {}
    progress = data.get("progress") or {}
    return {
        "ok": True,
        "checked_in_today": c.get("checked_in_today") is True,
        "continuous_days": c.get("continuous_days") or 0,
        "last_checkin_date": c.get("last_checkin_date"),
        "reward_amount": reward.get("reward_amount") or 0,
        "total_amount": progress.get("total_amount") or 0,
        "task_status": task.get("task_status"),
        "reward_status": c.get("reward_status"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="豆包签到状态查询")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = parser.parse_args(argv)

    try:
        config = load_config()
    except ConfigError as exc:
        result = {"ok": False, "error": str(exc)}
        print(json.dumps(result, ensure_ascii=False) if args.json else f"[ERROR] {exc}")
        return 2

    try:
        result = fetch_status(config.cookie, config.headers.get("User-Agent", ""))
    except ConnectionError as exc:
        result = {"ok": False, "error": f"网络异常：{exc}"}

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    if not result.get("ok"):
        print(f"[WARN] {result.get('error')}")
        return 1

    state = "今日已签到" if result["checked_in_today"] else "今日尚未签到"
    print(
        f"[INFO ] {state}｜连续 {result['continuous_days']} 天"
        f"｜累计额度 {result['total_amount']}"
        f"｜上次签到 {result['last_checkin_date']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
