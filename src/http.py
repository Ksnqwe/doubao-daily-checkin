"""极简 HTTP 客户端（仅用标准库）。

为什么不用 requests：
1. 零第三方依赖 —— GitHub Actions 里省掉 pip install，启动快、没有供应链风险；
2. 签到脚本只需要「发一个请求、读一段文本」，urllib 完全够用。
"""

from __future__ import annotations

import gzip
import ssl
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass, field


@dataclass
class Response:
    status: int
    text: str
    headers: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


def _decode(raw: bytes, encoding: str) -> bytes:
    encoding = (encoding or "").lower()
    try:
        if encoding == "gzip":
            return gzip.decompress(raw)
        if encoding == "deflate":
            return zlib.decompress(raw)
    except Exception:
        pass
    return raw


def request(
    method: str,
    url: str,
    headers: dict | None = None,
    body: str | bytes | None = None,
    timeout: float = 20.0,
) -> Response:
    """发一个请求，任何 HTTP 状态码都正常返回（不抛异常，交给上层判定）。"""
    payload = body.encode("utf-8") if isinstance(body, str) else body

    merged = {"Accept-Encoding": "identity"}
    merged.update(headers or {})

    req = urllib.request.Request(url=url, data=payload, headers=merged, method=method.upper())

    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            raw = resp.read()
            raw = _decode(raw, resp.headers.get("Content-Encoding", ""))
            return Response(
                status=resp.status,
                text=raw.decode("utf-8", "replace"),
                headers=dict(resp.headers),
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read() if hasattr(exc, "read") else b""
        raw = _decode(raw, exc.headers.get("Content-Encoding", "") if exc.headers else "")
        return Response(
            status=exc.code,
            text=raw.decode("utf-8", "replace"),
            headers=dict(exc.headers) if exc.headers else {},
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise ConnectionError(f"{exc.__class__.__name__}: {reason}") from exc
