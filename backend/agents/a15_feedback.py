"""A15 Feedback Learning Agent - 业务结果反馈 → 动态权重调优。

允许调整：Query / Market / Content / Evidence / Entity / Citation / Conversion 权重。
禁止：为提高评分而修改事实。
"""
from __future__ import annotations

from ..core.util import clamp, now_iso, r2, uid

SIGNAL_WEIGHT = {
    "AI Mention": {"query": 0.02, "entity": 0.02},
    "Citation": {"citation": 0.03, "evidence": 0.02},
    "Click": {"query": 0.01, "content": 0.01},
    "Inquiry": {"market": 0.02, "content": 0.02},
    "Qualified Lead": {"market": 0.02, "entity": 0.01},
    "RFQ": {"conversion": 0.03, "market": 0.01},
    "Sample": {"conversion": 0.02, "evidence": 0.01},
    "Order": {"conversion": 0.04, "evidence": 0.02},
    "Repeat Purchase": {"conversion": 0.03, "citation": 0.01},
}

BOUNDS = (0.7, 1.3)


def record(store, payload: dict) -> dict:
    event = {
        "id": uid("FBK"),
        "created_at": now_iso(),
        "signal": payload.get("signal"),
        "entity_id": payload.get("entity_id"),
        "query": payload.get("query"),
        "market": payload.get("market"),
        "value": payload.get("value"),
        "ai_platform": payload.get("ai_platform"),
        "note": payload.get("note"),
    }
    store.add("feedback", event)
    return event


def run(store, ctx: dict) -> dict:
    weights = dict(store.data.get("weights") or default_weights())
    updated = tune(store, weights)
    store.set_dict("weights", updated)
    store.add("weights_history", {"timestamp": now_iso(), "weights": updated,
                                  "run_id": ctx.get("run_id")})
    result = {
        "agent": "A15 Feedback Learning Agent",
        "signals_count": len(store.all("feedback")),
        "weights_before": weights,
        "weights_after": updated,
        "bounds": BOUNDS,
        "guardrail": "只允许调整权重；禁止为提高评分修改任何事实、证据或 Claim。",
    }
    ctx["feedback_learning"] = result
    return result


def tune(store, weights: dict | None = None) -> dict:
    weights = dict(weights or default_weights())
    counts: dict[str, int] = {}
    for f in store.all("feedback"):
        counts[f.get("signal", "")] = counts.get(f.get("signal", ""), 0) + 1
    for signal, n in counts.items():
        deltas = SIGNAL_WEIGHT.get(signal, {})
        for key, step in deltas.items():
            weights[key] = round(clamp(weights.get(key, 1.0) + step * min(n, 5), *BOUNDS), 3)
    return weights


def default_weights() -> dict:
    return {"query": 1.0, "market": 1.0, "content": 1.0, "evidence": 1.0,
            "entity": 1.0, "citation": 1.0, "conversion": 1.0}


def learning_loop(store) -> dict:
    return {
        "loop": ["Query", "Content", "AI Visibility", "Lead", "Revenue", "Feedback", "Optimization"],
        "signals": _signal_counts(store),
        "weights": store.data.get("weights") or default_weights(),
        "history": store.all("weights_history")[-10:],
    }


def _signal_counts(store) -> dict:
    out: dict[str, int] = {}
    for f in store.all("feedback"):
        out[f.get("signal", "")] = out.get(f.get("signal", ""), 0) + 1
    return out
