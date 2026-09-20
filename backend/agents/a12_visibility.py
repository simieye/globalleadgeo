"""A12 AI Visibility Monitoring Agent - GEO Visibility Dashboard 与监测计划。"""
from __future__ import annotations

from ..core.util import clamp, now_iso, r2, uid
from ..core.web_research import probe_ai_engine

ENGINES = ["ChatGPT", "Gemini", "Perplexity", "Google AI Overviews", "Microsoft Copilot", "Claude"]


def run(store, ctx: dict) -> dict:
    queries = ctx.get("query_expansion", {}).get("queries", [])[:12] or [ctx.get("query", "")]
    market = ctx.get("market_intel", {}).get("market", "Global")
    languages = ctx.get("languages") or ["en"]
    engines = ctx.get("engines") or ENGINES

    plan = {
        "agent": "A12 AI Visibility Monitoring Agent",
        "cadence": "daily（核心查询）/ weekly（长尾查询）/ monthly（竞品对照）",
        "matrix": [
            {"query": q, "engines": engines, "market": market, "languages": languages}
            for q in queries
        ],
        "fields": ["query", "ai_engine", "brand_mention", "product_mention", "citation",
                   "citation_source", "competitor_mention", "position_presence",
                   "answer_context", "market", "language", "timestamp"],
        "probe_counts": {"queries": len(queries), "engines": len(engines),
                         "total_probes": len(queries) * len(engines)},
        "note": "未配置 AI 引擎 API Key 时返回模拟基线（mode=simulated），不得作为事实结论。",
    }
    ctx["visibility_monitoring_plan"] = plan
    return plan


def probe(store, payload: dict) -> dict:
    queries = payload.get("queries") or []
    engines = payload.get("engines") or ENGINES
    market = payload.get("market")
    language = payload.get("language", "en")
    entity_ids = payload.get("entity_ids") or [e["id"] for e in store.all("entities")]
    brands = [e.get("brand", "") for e in store.all("entities") if e["id"] in set(entity_ids)]

    snapshots = []
    for q in queries:
        for engine in engines:
            res = probe_ai_engine(engine, q, market, language)
            answer = res.get("answer") or ""
            mentions = [b for b in brands if b and b.lower() in answer.lower()]
            competitor_mentions = [c for e in store.all("entities")
                                   for c in e.get("competitors", [])
                                   if c.lower() in answer.lower()]
            snap = {
                "id": uid("VIS"),
                "timestamp": now_iso(),
                "query": q,
                "ai_engine": engine,
                "market": market,
                "language": language,
                "mode": res.get("mode"),
                "brand_mention": bool(mentions),
                "brands_mentioned": mentions,
                "competitor_mention": bool(competitor_mentions),
                "competitors_mentioned": sorted(set(competitor_mentions)),
                "citations": res.get("citations", []),
                "citation_count": len(res.get("citations", [])),
                "answer_excerpt": answer[:400] if answer else None,
            }
            if res.get("mode") == "simulated":
                # 模拟基线：以 GEO Score 作为曝光概率估计，明确标注非真实观测
                score = _geo_score_for(store, entity_ids[0] if entity_ids else None)
                snap["simulated_mention_probability"] = r2(clamp(score * 0.8))
                snap["brand_mention"] = None
                snap["estimated"] = True
            snapshots.append(snap)
    store.add_many("monitoring", snapshots)
    return {"snapshots": snapshots, "dashboard": dashboard(store)}


def _geo_score_for(store, entity_id: str | None) -> float:
    runs = store.all("runs")
    if not runs:
        return 40.0
    last = sorted(runs, key=lambda r: r.get("created_at", ""), reverse=True)[0]
    out = last.get("output", {}).get("ranked_entities", [])
    if entity_id:
        hit = next((r for r in out if r["entity_id"] == entity_id), None)
        return hit["geo_score"] if hit else 40.0
    return out[0]["geo_score"] if out else 40.0


def dashboard(store) -> dict:
    snaps = store.all("monitoring")
    live = [s for s in snaps if s.get("mode") == "live"]
    simulated = [s for s in snaps if s.get("mode") == "simulated"]
    total = len(snaps) or 1
    return {
        "total_probes": len(snaps),
        "live_probes": len(live),
        "simulated_probes": len(simulated),
        "ai_mention_rate": r2(100 * len([s for s in live if s.get("brand_mention")]) / max(len(live), 1)),
        "citation_rate": r2(100 * len([s for s in live if s.get("citation_count")]) / max(len(live), 1)),
        "entity_recognition_rate": r2(100 * len([s for s in live if s.get("brands_mentioned")]) / max(len(live), 1)),
        "competitor_share_of_voice": r2(
            100 * len([s for s in live if s.get("competitor_mention")]) / max(len(live), 1)),
        "query_coverage": r2(100 * len({s.get("query") for s in snaps}) / max(total, 1)),
        "by_engine": _by_engine(snaps),
        "latest": sorted(snaps, key=lambda s: s.get("timestamp", ""), reverse=True)[:10],
    }


def _by_engine(snaps: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for s in snaps:
        e = s.get("ai_engine", "unknown")
        d = out.setdefault(e, {"probes": 0, "mentions": 0, "citations": 0, "live": 0})
        d["probes"] += 1
        d["mentions"] += 1 if s.get("brand_mention") else 0
        d["citations"] += s.get("citation_count", 0)
        d["live"] += 1 if s.get("mode") == "live" else 0
    return out
