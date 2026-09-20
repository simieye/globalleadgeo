"""Global Eagle GEO - 通用工具层."""
from __future__ import annotations

import hashlib
import math
import re
import uuid
from datetime import datetime, timezone

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "for", "in", "on", "to", "with", "from", "by",
    "is", "are", "was", "be", "best", "top", "good", "need", "needs", "i", "we", "you",
    "our", "your", "at", "as", "it", "this", "that", "can", "do", "does", "how", "what",
    "which", "who", "where", "when", "why", "please", "looking", "find", "get", "buy",
    "supplier", "suppliers", "manufacturer", "manufacturers", "company", "companies",
    "price", "cost", "cheap", "high", "quality", "service", "product", "products",
    "的", "和", "与", "在", "是", "有", "为", "对", "我", "我们", "你", "您", "请",
}

TOKEN_RE = re.compile(r"[a-zA-Z0-9\u4e00-\u9fff+#\.]{2,}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p.lower() for p in parts if p)
    return f"{prefix}-{hashlib.md5(raw.encode()).hexdigest()[:10].upper()}"


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    out = []
    for tk in TOKEN_RE.findall(text.lower()):
        if tk in STOPWORDS:
            continue
        out.append(tk.strip("."))
    return out


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def r2(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    num = sum(a[k] * b[k] for k in common)
    da = math.sqrt(sum(v * v for v in a.values()))
    db = math.sqrt(sum(v * v for v in b.values()))
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


def days_since(iso_str: str | None) -> float | None:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    return max(delta.total_seconds() / 86400.0, 0.0)


def domain_of(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1).lower().replace("www.", "") if m else ""
