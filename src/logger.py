"""统一的日志输出。

- 本地运行时带时间戳、级别、颜色
- 在 GitHub Actions 中自动转成 ::group:: / ::error:: 注解，方便在页面上折叠查看
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

_IN_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"

_LEVEL_TAG = {
    "debug": "DEBUG",
    "info": "INFO ",
    "warn": "WARN ",
    "error": "ERROR",
    "ok": "OK   ",
}

_COLOR = {
    "debug": "\033[90m",
    "info": "\033[36m",
    "warn": "\033[33m",
    "error": "\033[31m",
    "ok": "\033[32m",
}
_RESET = "\033[0m"


def _enable_utf8() -> None:
    """Windows 控制台默认 GBK，中文会乱码，这里强制 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - 老版本 Python 或非标准流
            pass


_enable_utf8()

_use_color = sys.stdout.isatty() and not _IN_ACTIONS and os.getenv("NO_COLOR") is None


def _emit(level: str, message: str, **fields) -> None:
    parts = [f"[{_LEVEL_TAG.get(level, 'INFO ')}] {message}"]
    if fields:
        parts.append(" ".join(f"{k}={v}" for k, v in fields.items()))
    line = "  ".join(parts)

    if _use_color:
        line = f"{_COLOR.get(level, '')}{line}{_RESET}"

    print(line, flush=True)


def debug(message: str, **fields) -> None:
    if os.getenv("DOUBAO_DEBUG") == "1":
        _emit("debug", message, **fields)


def info(message: str, **fields) -> None:
    _emit("info", message, **fields)


def warn(message: str, **fields) -> None:
    _emit("warn", message, **fields)


def error(message: str, **fields) -> None:
    _emit("error", message, **fields)
    if _IN_ACTIONS:
        print(f"::error::{message}")


def ok(message: str, **fields) -> None:
    _emit("ok", message, **fields)


class section:
    """上下文管理器：把一个阶段包成可折叠分组。"""

    def __init__(self, title: str) -> None:
        self.title = title

    def __enter__(self) -> "section":
        if _IN_ACTIONS:
            print(f"::group::{self.title}", flush=True)
        else:
            print(f"\n=== {self.title} ===", flush=True)
        return self

    def __exit__(self, *exc) -> None:
        if _IN_ACTIONS:
            print("::endgroup::", flush=True)


def mask(secret: str, keep: int = 4) -> str:
    """脱敏，日志里永远不要出现完整 cookie。"""
    if not secret:
        return "<empty>"
    if len(secret) <= keep * 2:
        return "*" * len(secret)
    return f"{secret[:keep]}***{secret[-keep:]} (len={len(secret)})"


def timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
