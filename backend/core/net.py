"""轻量 HTTP 层：统一 SSL 校验、超时与错误处理（标准库 + 可选 certifi）。

外部大模型提供商可能部署在自建网关上，证书链不一定被系统根证书信任，
因此统一使用 certifi 根证书（若已安装），缺失时回退系统默认上下文。
"""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any

UA = "GlobalEagleGEO/1.2"
DEFAULT_TIMEOUT = 20
MAX_BYTES = 2_000_000


def ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001 - 无 certifi 时回退系统根证书
        return ssl.create_default_context()


_CTX = ssl_context()


def request(method: str, url: str, headers: dict | None = None, body: bytes | None = None,
            timeout: int = DEFAULT_TIMEOUT) -> tuple[int, dict, bytes]:
    """返回 (http_status, headers, body)。HTTPError 不抛出，按状态码返回。"""
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
            return resp.status, dict(resp.headers), resp.read(MAX_BYTES)
    except urllib.error.HTTPError as e:
        raw = b""
        try:
            raw = e.read(4096)
        except Exception:  # noqa: BLE001
            raw = b""
        return e.code, dict(e.headers or {}), raw


def json_request(method: str, url: str, headers: dict | None = None,
                 payload: dict | None = None,
                 timeout: int = DEFAULT_TIMEOUT) -> tuple[int, Any, str]:
    """返回 (http_status, parsed_json_or_None, raw_text)。"""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    status, _, raw = request(method, url, headers, body, timeout)
    text = raw.decode("utf-8", "ignore")
    try:
        return status, json.loads(text), text
    except json.JSONDecodeError:
        return status, None, text
