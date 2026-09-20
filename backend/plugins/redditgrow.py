"""RedditGrow 插件 · 通过 MCP（Streamable HTTP）接入 RedditGrow 的 Reddit 获客能力。

接入信息（来自 https://redditgrow.ai/integrations/mcp）：
- MCP 端点：https://redditgrow.ai/mcp
- 鉴权：Authorization: Bearer rg_live_*
- 可用能力组：机会与回复 / 冷启动 DM / 品牌与竞品提及 / SEO·SERP·AI 可见性 / 账号养号 / 项目与 subreddit 管理等
- Webhook：订阅后按 HMAC-SHA256 签名投递，签名头 X-RedditGrow-Signature
- 频率限制：Growth 100 次/小时，Agency 500 次/小时

设计原则与本系统一致：
- 未配置 REDDITGROW_API_KEY 时返回 mode='disabled'，不返回任何编造数据；
- 所有导入的 Reddit 机会标记为 lead_source='RedditGrow' 且 verification_status='unverified'；
- 生成回复（generate_response）只写入草稿，需人工审核后才可发布。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import ssl
import urllib.error
import urllib.request
import uuid
from typing import Any

from ..core.util import now_iso

DEFAULT_MCP_URL = "https://redditgrow.ai/mcp"
PROTOCOL_VERSION = "2025-06-18"
UA = "GlobalEagleGEO/1.1 (+redditgrow-plugin)"
TIMEOUT = 20
def _ssl_context() -> ssl.SSLContext:
    """优先使用 certifi 根证书，避免部分 Python 发行版缺少 CA 导致 SSL 校验失败。"""
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


_CTX = _ssl_context()

# MCP 会话（streamable-http，服务端可能返回 Mcp-Session-Id）
_session: dict[str, Any] = {"id": None, "initialized": False}

# 插件暴露的工具名（与 RedditGrow MCP 保持一致，便于前端展示与白名单校验）
TOOLS = [
    "find_opportunities", "get_opportunity_details", "generate_response",
    "list_brand_mentions", "get_competitive_mentions", "check_ai_visibility",
    "check_reddit_serp_ranking", "get_money_keywords", "list_projects",
    "discover_subreddits", "search_reddit_live", "get_next_best_action",
]


# ---------------- 配置 ----------------
def config(settings: dict | None = None) -> dict:
    """读取插件配置：store.settings['redditgrow'] 优先，其次环境变量。"""
    s = settings or {}
    return {
        "api_key": s.get("api_key") or os.getenv("REDDITGROW_API_KEY", ""),
        "mcp_url": s.get("mcp_url") or os.getenv("REDDITGROW_MCP_URL", DEFAULT_MCP_URL),
        "webhook_secret": s.get("webhook_secret") or os.getenv("REDDITGROW_WEBHOOK_SECRET", ""),
    }


def mask(key: str | None) -> str:
    if not key:
        return ""
    return f"{key[:8]}…{key[-4:]}" if len(key) > 14 else "••••"


def status(settings: dict | None = None) -> dict:
    cfg = config(settings)
    enabled = bool(cfg["api_key"])
    return {
        "id": "redditgrow",
        "name": "RedditGrow",
        "vendor": "https://redditgrow.ai",
        "transport": "MCP over HTTP (streamable-http)",
        "mcp_url": cfg["mcp_url"],
        "mode": "live" if enabled else "disabled",
        "enabled": enabled,
        "api_key_masked": mask(cfg["api_key"]),
        "webhook_enabled": bool(cfg["webhook_secret"]),
        "tools": TOOLS,
        "plan_note": "MCP / REST API 需 Growth 或 Agency 套餐；频率 100–500 次/小时。",
        "note": None if enabled else "未配置 REDDITGROW_API_KEY，插件停用且不返回任何编造数据。",
    }


# ---------------- MCP 传输 ----------------
def _post(url: str, headers: dict, body: bytes) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"User-Agent": UA, **headers})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_CTX) as resp:
        return resp.status, dict(resp.headers), resp.read(4_000_000)


def _parse_payload(raw: bytes) -> dict | None:
    """支持 JSON 与 text/event-stream 两种响应体。"""
    text = raw.decode("utf-8", "ignore").strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    for line in text.splitlines():
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
    return None


def _rpc(method: str, params: dict | None = None, *, api_key: str,
         mcp_url: str, call_id: str | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if _session["id"]:
        headers["Mcp-Session-Id"] = _session["id"]
    payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if call_id is not None:
        payload["id"] = call_id
    status, resp_headers, raw = _post(mcp_url, headers, json.dumps(payload).encode())
    if resp_headers.get("Mcp-Session-Id"):
        _session["id"] = resp_headers["Mcp-Session-Id"]
    data = _parse_payload(raw)
    return {"http_status": status, "data": data, "error": None if data else f"HTTP {status}"}


def _ensure_initialized(cfg: dict) -> None:
    if _session["initialized"]:
        return
    _rpc("initialize", {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "GlobalEagleGEO", "version": "1.1.0"},
    }, api_key=cfg["api_key"], mcp_url=cfg["mcp_url"], call_id=str(uuid.uuid4()))
    _session["initialized"] = True
    try:
        _rpc("notifications/initialized", {}, api_key=cfg["api_key"], mcp_url=cfg["mcp_url"])
    except Exception:  # noqa: BLE001 - 通知失败不影响后续调用
        pass


def _unwrap(result: dict) -> Any:
    """从 MCP tools/call 结果中取出结构化数据。"""
    if "error" in result:
        return {"_error": result["error"]}
    structured = result.get("structuredContent")
    if structured:
        return structured
    for item in result.get("content", []) or []:
        text = item.get("text") if isinstance(item, dict) else None
        if not text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}
    return result


def call_tool(tool: str, arguments: dict | None = None, settings: dict | None = None) -> dict:
    """调用 RedditGrow MCP 工具。无 Key / 出错时明确标注 mode，绝不编造结果。"""
    cfg = config(settings)
    if not cfg["api_key"]:
        return {"mode": "disabled", "tool": tool, "data": None,
                "note": "未配置 REDDITGROW_API_KEY，插件停用（不会返回编造数据）。"}
    if tool not in TOOLS:
        return {"mode": "error", "tool": tool, "data": None, "error": f"工具不在白名单：{tool}"}
    try:
        _ensure_initialized(cfg)
        resp = _rpc("tools/call", {"name": tool, "arguments": arguments or {}},
                    api_key=cfg["api_key"], mcp_url=cfg["mcp_url"], call_id=str(uuid.uuid4()))
        data = resp.get("data") or {}
        if "error" in data:
            return {"mode": "error", "tool": tool, "data": None, "error": str(data["error"])[:300]}
        return {"mode": "live", "tool": tool, "data": _unwrap(data.get("result", {}))}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:200]
        return {"mode": "error", "tool": tool, "data": None, "error": f"HTTP {e.code}: {detail}"}
    except Exception as e:  # noqa: BLE001
        _session["initialized"] = False
        return {"mode": "error", "tool": tool, "data": None, "error": f"{type(e).__name__}: {e}"[:300]}


def reset_session() -> None:
    _session["id"] = None
    _session["initialized"] = False


# ---------------- 高层能力 ----------------
def find_opportunities(min_score: float = 7.0, limit: int = 10, project_id: str | None = None,
                       settings: dict | None = None) -> dict:
    args: dict[str, Any] = {"min_score": min_score, "limit": limit}
    if project_id:
        args["project_id"] = project_id
    return call_tool("find_opportunities", args, settings)


def list_brand_mentions(mention_type: str | None = None, unseen_only: bool = True,
                        limit: int = 20, settings: dict | None = None) -> dict:
    args: dict[str, Any] = {"limit": limit, "unseen_only": unseen_only}
    if mention_type:
        args["mention_type"] = mention_type
    return call_tool("list_brand_mentions", args, settings)


def check_ai_visibility(project_id: str | None = None, settings: dict | None = None) -> dict:
    args = {"project_id": project_id} if project_id else {}
    return call_tool("check_ai_visibility", args, settings)


def check_serp(keyword: str, settings: dict | None = None) -> dict:
    return call_tool("check_reddit_serp_ranking", {"keyword": keyword}, settings)


def generate_reply_draft(opportunity_id: str, tone: str = "professional",
                         length: str = "medium", settings: dict | None = None) -> dict:
    """生成回复草稿（只落草稿，不自动发布；发布需人工审核）。"""
    result = call_tool("generate_response",
                       {"opportunity_id": opportunity_id, "tone": tone, "length": length},
                       settings)
    if result.get("mode") == "live":
        result["requires_human_review"] = True
    return result


# ---------------- 归一化 → 询盘 ----------------
def _first(d: dict, keys: list[str], default: Any = None) -> Any:
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return default


def _stage_by_score(score: float) -> str:
    if score >= 9:
        return "Decision"
    if score >= 8:
        return "Evaluation"
    if score >= 7:
        return "Consideration"
    return "Awareness"


def normalize_opportunity(op: dict) -> dict:
    """把 RedditGrow 机会对象归一化为系统询盘字段（字段缺失时留空，不做推断填充）。"""
    score = float(_first(op, ["score", "opportunity_score", "relevance", "intent_score"], 0) or 0)
    title = _first(op, ["title", "post_title", "text"], "")
    subreddit = _first(op, ["subreddit", "sub", "subreddit_name"], "")
    if subreddit and not subreddit.startswith("r/"):
        subreddit = f"r/{subreddit}"
    url = _first(op, ["url", "permalink", "post_url", "link"], "")
    if url and url.startswith("/"):
        url = f"https://www.reddit.com{url}"
    return {
        "lead_source": "RedditGrow",
        "query": title,
        "market": _first(op, ["market", "target_market"], None),
        "product": _first(op, ["product", "matched_keyword", "keyword"], None),
        "intent": _first(op, ["intent", "intent_type", "buying_intent"], ["supplier_search"]),
        "buyer_stage": _stage_by_score(score),
        "ai_platform": None,
        "landing_page": url,
        "campaign": f"RedditGrow:{subreddit}" if subreddit else "RedditGrow",
        "source_ref": _first(op, ["id", "opportunity_id", "post_id"], None),
        "verification_status": "unverified",
        "metadata": {
            "plugin": "redditgrow",
            "subreddit": subreddit,
            "url": url,
            "opportunity_score": score,
            "author": _first(op, ["author", "username"], None),
            "created_at": _first(op, ["created_at", "posted_at", "timestamp"], None),
            "fetched_at": now_iso(),
        },
    }


def extract_opportunities(result: dict) -> list[dict]:
    data = result.get("data")
    if isinstance(data, list):
        return [o for o in data if isinstance(o, dict)]
    if isinstance(data, dict):
        for key in ("opportunities", "results", "items", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [o for o in value if isinstance(o, dict)]
    return []


# ---------------- Webhook ----------------
def verify_webhook(body: bytes, signature: str | None, secret: str) -> bool:
    """校验 RedditGrow Webhook 签名（HMAC-SHA256，头 X-RedditGrow-Signature）。"""
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    provided = signature.strip()
    if provided.lower().startswith("sha256="):
        provided = provided[7:]
    return hmac.compare_digest(expected, provided)


def ingest_webhook_event(event: dict) -> dict | None:
    """把 opportunity.created 事件归一化为询盘载荷。"""
    payload = event.get("data") if isinstance(event, dict) and "data" in event else event
    if not isinstance(payload, dict):
        return None
    return normalize_opportunity(payload)
