"""Global Eagle GEO - 审计日志.

每一次 Agent 调用、证据变更、人工审核、对外写入都必须留痕。
"""
from __future__ import annotations

from typing import Any

from .store import Store
from .util import now_iso, uid


def log(store: Store, event: str, actor: str, payload: dict | None = None,
        risk: str = "low", run_id: str | None = None) -> dict:
    entry = {
        "id": uid("AUD"),
        "timestamp": now_iso(),
        "event": event,
        "actor": actor,
        "run_id": run_id,
        "risk_level": risk,
        "payload": payload or {},
    }
    store.add("audit", entry)
    return entry


def for_run(store: Store, run_id: str) -> list[dict]:
    return [a for a in store.all("audit") if a.get("run_id") == run_id]


def tail(store: Store, limit: int = 200) -> list[dict]:
    items = sorted(store.all("audit"), key=lambda a: a.get("timestamp", ""), reverse=True)
    return items[:limit]


def summary(store: Store) -> dict[str, Any]:
    items = store.all("audit")
    by_risk: dict[str, int] = {}
    by_event: dict[str, int] = {}
    for a in items:
        by_risk[a.get("risk_level", "low")] = by_risk.get(a.get("risk_level", "low"), 0) + 1
        by_event[a.get("event", "")] = by_event.get(a.get("event", ""), 0) + 1
    return {"total": len(items), "by_risk": by_risk, "by_event": by_event}
