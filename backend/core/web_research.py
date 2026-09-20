"""Global Eagle GEO - Web Research / 信源可达性核验 / AI 引擎探针.

设计原则：
1. 未配置任何外部 Key 时，系统只做「真实可达性核验」（HTTP 状态 + 标题 + Last-Modified），
   不臆造检索结果、不臆造 AI 平台回答。
2. 配置了 TAVILY_API_KEY / SERPER_API_KEY 时执行真实联网检索。
3. 配置了 OPENAI_API_KEY / PERPLEXITY_API_KEY / ANTHROPIC_API_KEY 时执行真实 AI 引擎探针，
   否则返回 mode="simulated"，并在结果中明确标注。
"""
from __future__ import annotations

import json
import os
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime

from .util import domain_of, now_iso

UA = "GlobalEagleGEO/1.0 (+research-bot)"
TIMEOUT = 10
_CTX = ssl.create_default_context()


def _http(method: str, url: str, headers: dict | None = None, body: bytes | None = None):
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_CTX) as resp:
        raw = resp.read(2_000_000)
        return resp.status, dict(resp.headers), raw


def verify_url(url: str) -> dict:
    """真实核验：可达性 + HTTP 状态 + 页面标题 + Last-Modified。不做内容断言。"""
    result = {
        "url": url,
        "domain": domain_of(url),
        "checked_at": now_iso(),
        "reachable": False,
        "status_code": None,
        "title": None,
        "last_modified": None,
        "error": None,
    }
    try:
        status, headers, raw = _http("GET", url)
        result["status_code"] = status
        result["reachable"] = 200 <= status < 400
        result["last_modified"] = headers.get("Last-Modified") or headers.get("last-modified")
        try:
            html = raw.decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            html = ""
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        if m:
            result["title"] = re.sub(r"\s+", " ", m.group(1)).strip()[:180]
    except urllib.error.HTTPError as e:
        result["status_code"] = e.code
        result["error"] = f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        result["error"] = f"{type(e).__name__}: {e}"[:200]
    return result


def web_search(query: str, max_results: int = 5) -> dict:
    """联网检索。无 Key 时返回 mode='disabled'，绝不使用编造结果填充。"""
    tavily = os.getenv("TAVILY_API_KEY")
    serper = os.getenv("SERPER_API_KEY")
    if tavily:
        try:
            body = json.dumps({
                "api_key": tavily, "query": query, "max_results": max_results,
                "search_depth": "basic", "include_answer": False,
            }).encode()
            status, _, raw = _http("POST", "https://api.tavily.com/search",
                                   {"Content-Type": "application/json"}, body)
            data = json.loads(raw.decode("utf-8", "ignore"))
            return {"mode": "live", "provider": "tavily", "results": [
                {"title": r.get("title"), "url": r.get("url"), "snippet": r.get("content"),
                 "score": r.get("score")} for r in data.get("results", [])
            ]}
        except Exception as e:  # noqa: BLE001
            return {"mode": "error", "provider": "tavily", "error": str(e)[:200], "results": []}
    if serper:
        try:
            body = json.dumps({"q": query, "num": max_results}).encode()
            status, _, raw = _http("POST", "https://google.serper.dev/search",
                                   {"X-API-KEY": serper, "Content-Type": "application/json"}, body)
            data = json.loads(raw.decode("utf-8", "ignore"))
            return {"mode": "live", "provider": "serper", "results": [
                {"title": r.get("title"), "url": r.get("link"), "snippet": r.get("snippet")}
                for r in data.get("organic", [])
            ]}
        except Exception as e:  # noqa: BLE001
            return {"mode": "error", "provider": "serper", "error": str(e)[:200], "results": []}
    return {
        "mode": "disabled",
        "provider": None,
        "results": [],
        "note": "未配置 TAVILY_API_KEY / SERPER_API_KEY，系统不会返回编造的检索结果。",
    }


def probe_ai_engine(engine: str, query: str, market: str | None = None,
                    language: str = "en") -> dict:
    """向真实 AI 引擎提问并解析是否出现品牌/引用。

    未配置对应 Key 时返回 mode='simulated'，结果仅供基线参考，不得作为事实结论。
    """
    engine = engine.lower()
    prompt = query if not market else f"{query} (market: {market}; language: {language})"
    key = None
    endpoint = None
    headers = {"Content-Type": "application/json"}
    if engine in ("chatgpt", "openai", "gpt"):
        key = os.getenv("OPENAI_API_KEY")
        endpoint = "https://api.openai.com/v1/chat/completions"
        payload = {"model": os.getenv("GEO_OPENAI_MODEL", "gpt-4o-mini"),
                   "messages": [{"role": "user", "content": prompt}]}
        headers["Authorization"] = f"Bearer {key}" if key else ""
    elif engine in ("perplexity",):
        key = os.getenv("PERPLEXITY_API_KEY")
        endpoint = "https://api.perplexity.ai/chat/completions"
        payload = {"model": os.getenv("GEO_PPLX_MODEL", "sonar"),
                   "messages": [{"role": "user", "content": prompt}]}
        headers["Authorization"] = f"Bearer {key}" if key else ""
    elif engine in ("claude", "anthropic"):
        key = os.getenv("ANTHROPIC_API_KEY")
        endpoint = "https://api.anthropic.com/v1/messages"
        payload = {"model": os.getenv("GEO_ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                   "max_tokens": 800,
                   "messages": [{"role": "user", "content": prompt}]}
        headers["x-api-key"] = key or ""
        headers["anthropic-version"] = "2023-06-01"

    if not key:
        return {
            "engine": engine, "query": query, "market": market, "language": language,
            "mode": "simulated", "answer": None, "brand_mentioned": None,
            "citations": [], "note": "未配置该引擎 API Key，结果为模拟基线，不代表真实 AI 回答。",
        }

    try:
        status, _, raw = _http("POST", endpoint, headers, json.dumps(payload).encode())
        data = json.loads(raw.decode("utf-8", "ignore"))
        if engine in ("claude", "anthropic"):
            text = "".join(b.get("text", "") for b in data.get("content", []))
        else:
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {
            "engine": engine, "query": query, "market": market, "language": language,
            "mode": "live", "answer": text, "citations": _extract_citations(text),
            "checked_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
    except Exception as e:  # noqa: BLE001
        return {"engine": engine, "query": query, "mode": "error", "error": str(e)[:200]}


def _extract_citations(text: str) -> list[str]:
    return sorted(set(re.findall(r"https?://[^\s)\]]+", text or "")))[:20]
