"""Global Eagle Orchestrator (OpenClaw) - 19 步 GEO 自动化闭环调度。"""
from __future__ import annotations

import time
from typing import Any

from .agents import (a01_intent, a02_market, a03_query_expansion, a04_retrieval,
                     a05_entity, a06_evidence, a07_geo_scoring, a08_competitor,
                     a09_answer_opt, a10_schema, a11_localization, a12_visibility,
                     a13_lead, a14_analytics, a15_feedback)
from .core import approval as approval_core
from .core import audit
from .core.llm import LLMAdapter
from .core.store import Store
from .core.util import now_iso, uid

PIPELINE = [
    "01_user_query", "02_intent_analysis", "03_market_analysis", "04_query_expansion",
    "05_candidate_retrieval", "06_entity_resolution", "07_evidence_verification",
    "08_geo_scoring", "09_competitor_gap", "10_content_optimization", "11_schema_generation",
    "12_visibility_monitoring", "13_ai_inquiry_tracking", "14_crm", "15_rfq",
    "16_order_attribution", "17_revenue_attribution", "18_feedback_learning",
    "19_geo_reoptimization",
]


class Orchestrator:
    def __init__(self, store: Store):
        self.store = store
        self.llm = LLMAdapter()

    def run(self, payload: dict) -> dict:
        started = time.time()
        run_id = uid("RUN")
        ctx: dict[str, Any] = {
            "run_id": run_id,
            "query": payload.get("query", ""),
            "market": payload.get("market"),
            "language": payload.get("language", "en"),
            "languages": payload.get("languages") or [payload.get("language", "en")],
            "engines": payload.get("engines"),
            "entity_ids": payload.get("entity_ids"),
            "enable_web_verify": bool(payload.get("enable_web_verify")),
        }
        audit.log(self.store, "pipeline.start", "OpenClaw Orchestrator",
                  {"query": ctx["query"], "market": ctx["market"]}, "low", run_id)

        trace: list[dict] = []

        def step(name: str, fn):
            t0 = time.time()
            result = fn()
            trace.append({"step": name, "agent": _agent_name(result),
                          "duration_ms": int((time.time() - t0) * 1000)})
            audit.log(self.store, f"agent.{name}", _agent_name(result),
                      {"duration_ms": trace[-1]["duration_ms"]}, "low", run_id)
            return result

        step("02_intent_analysis", lambda: a01_intent.run(self.store, ctx))
        if ctx.get("market"):
            from .agents.a02_market import normalize
            ctx["market"] = normalize(ctx["market"])
        else:
            ctx["market"] = ctx["intent"].get("target_country") or "Global"
        step("03_market_analysis", lambda: a02_market.run(self.store, ctx))
        ctx["languages"] = sorted(set(ctx["languages"] + ctx["market_intel"].get("languages", [])))
        step("04_query_expansion", lambda: a03_query_expansion.run(self.store, ctx))
        step("05_candidate_retrieval", lambda: a04_retrieval.run(self.store, ctx))
        step("06_entity_resolution", lambda: a05_entity.run(self.store, ctx))
        step("07_evidence_verification", lambda: a06_evidence.run(self.store, ctx))
        step("08_geo_scoring", lambda: a07_geo_scoring.run(self.store, ctx))
        step("09_competitor_gap", lambda: a08_competitor.run(self.store, ctx))
        step("11_localization", lambda: a11_localization.run(self.store, ctx))
        step("10_content_optimization", lambda: a09_answer_opt.run(self.store, ctx))
        if self.llm.available:
            ctx["ai_answer_ready_content"] = [
                a09_answer_opt.polish(self.llm, c, c["language"]) or c
                for c in ctx.get("ai_answer_ready_content", [])
            ]
        step("11_schema_generation", lambda: a10_schema.run(self.store, ctx))
        step("12_visibility_monitoring", lambda: a12_visibility.run(self.store, ctx))
        step("13_crm_tracking", lambda: a13_lead.run(self.store, ctx))
        analytics = step("14_analytics", lambda: a14_analytics.run(self.store, ctx))
        feedback = step("15_feedback_learning", lambda: a15_feedback.run(self.store, ctx))

        output = self._unified_output(ctx, analytics, feedback)
        output["pipeline_trace"] = trace

        approvals = approval_core.queue(self.store, "pending")
        output["human_approval_required"] = [
            {"id": a["id"], "category": a["category"], "subject": a["subject"],
             "status": a["status"], "entity_id": a.get("entity_id"),
             "created_at": a["created_at"]} for a in approvals[:20]
        ]

        output["audit_log"] = {
            "run_id": run_id,
            "events": [a["event"] for a in audit.for_run(self.store, run_id)],
            "risk_levels": audit.summary(self.store)["by_risk"],
        }

        record = {
            "id": run_id,
            "created_at": now_iso(),
            "query": ctx["query"],
            "market": ctx["market"],
            "language": ctx.get("language"),
            "duration_ms": int((time.time() - started) * 1000),
            "status": "completed",
            "pipeline": PIPELINE,
            "output": output,
        }
        self.store.add("runs", record)
        audit.log(self.store, "pipeline.complete", "OpenClaw Orchestrator",
                  {"duration_ms": record["duration_ms"],
                   "top_score": output["geo_score"]["overall"]},
                  "medium", run_id)
        return record

    def _unified_output(self, ctx: dict, analytics: dict, feedback: dict) -> dict:
        gaps = ctx.get("competitor_gap", {})
        ranked = ctx.get("ranked_entities", [])
        intent = ctx.get("intent", {})

        actions = _optimization_actions(gaps, ranked, ctx)

        return {
            "system": {
                "name": "全球鹰 GEO 全球AI推荐系统",
                "english_name": "Global Eagle GEO Recommendation & AI Visibility System",
                "positioning": "产业知识图谱驱动的 AI 推荐基础设施（非传统 SEO 工具）",
                "disclaimer": ("系统不承诺任何品牌一定被某个 AI 平台推荐；仅通过提升可发现性、"
                               "实体清晰度、证据可信度、查询相关性、内容结构化程度、"
                               "第三方信源覆盖与本地市场相关性来提高被理解、引用与推荐的概率。"),
            },
            "query": {
                "original": ctx.get("query"),
                "intent": intent,
                "market": ctx.get("market_intel", {}),
                "buyer_stage": intent.get("buyer_stage"),
            },
            "query_expansion": ctx.get("query_expansion", {}),
            "candidate_entities": ctx.get("candidates", []),
            "ranked_entities": ranked,
            "entity_graph": ctx.get("entity_intel", {}).get("entity_graph", {}),
            "industrial_intelligence_graph": ctx.get("entity_intel", {}).get(
                "industrial_intelligence_graph", {}),
            "evidence_graph": ctx.get("evidence_intel", {}).get("evidence_graph", {}),
            "evidence_verification": {
                k: v for k, v in ctx.get("evidence_intel", {}).items() if k != "evidence_graph"
            },
            "ai_answer_ready_content": ctx.get("ai_answer_ready_content", []),
            "localization": ctx.get("localization", {}),
            "schema": ctx.get("schema", {}),
            "geo_score": ctx.get("geo_scoring", {}).get("geo_score", {}),
            "geo_score_detail": ctx.get("geo_scoring", {}),
            "competitor_gap": gaps.get("entity_gap", []) + gaps.get("citation_gap", []),
            "content_gap": gaps.get("content_gap", []),
            "evidence_gap": gaps.get("evidence_gap", []),
            "query_gap": gaps.get("query_gap", []),
            "market_gap": gaps.get("market_gap", []),
            "competitor_matrix": ctx.get("competitor_intel", {}).get("competitor_matrix", []),
            "optimization_actions": actions,
            "visibility_monitoring_plan": ctx.get("visibility_monitoring_plan", {}),
            "crm_tracking": ctx.get("crm_tracking", {}),
            "analytics": analytics,
            "feedback_learning": feedback,
            "shared_context": _shared_context(self.store, ranked),
        }


def _agent_name(result) -> str:
    if isinstance(result, dict):
        return result.get("agent", "agent")
    return "agent"


def _optimization_actions(gaps: dict, ranked: list[dict], ctx: dict) -> list[dict]:
    actions = []
    for category in ("evidence_gap", "entity_gap", "content_gap", "query_gap",
                     "market_gap", "citation_gap"):
        for g in gaps.get(category, []):
            actions.append({
                "priority": "P0" if g.get("severity") == "high" else
                            ("P1" if g.get("severity") == "medium" else "P2"),
                "category": category,
                "action": g.get("action") or g.get("item"),
                "item": g.get("item"),
            })
    for r in ranked[:3]:
        for risk in r.get("risk", []):
            actions.append({
                "priority": "P0",
                "category": "risk_mitigation",
                "action": f"[{r.get('brand')}] {risk}",
                "item": risk,
            })
    actions.sort(key=lambda a: {"P0": 0, "P1": 1, "P2": 2}[a["priority"]])
    return actions[:40]


def _shared_context(store, ranked: list[dict]) -> dict:
    entities = store.all("entities")
    primary_id = ranked[0]["entity_id"] if ranked else (entities[0]["id"] if entities else None)
    primary = store.get("entities", primary_id) if primary_id else {}
    return {
        "company": {"name": primary.get("company"), "country": primary.get("country"),
                    "website": primary.get("website"), "is_demo": primary.get("is_demo", False)},
        "brand": {"name": primary.get("brand"), "same_as": primary.get("same_as", [])},
        "products": [p.get("name") for e in entities for p in e.get("products", [])],
        "product_models": [m.get("model") for e in entities for p in e.get("products", [])
                           for m in p.get("models", [])],
        "industries": sorted({i for e in entities for i in e.get("industries", [])}),
        "target_markets": sorted({m for e in entities for m in e.get("target_markets", [])}),
        "certifications": sorted({c for e in entities for c in e.get("certifications", [])}),
        "buyer_segments": sorted({b for e in entities for b in e.get("buyer_segments", [])}),
        "case_studies": [c.get("title") for e in entities for c in e.get("case_studies", [])],
        "third_party_sources": sorted({s for e in entities for s in e.get("third_party_sources", [])}),
        "approved_claims": [c["claim"] for c in store.all("claims")
                            if c.get("human_approval") == "approved"],
        "restricted_claims": [c["claim"] for c in store.all("claims")
                              if c.get("verification_status") != "verified"],
        "counts": {
            "entities": len(entities),
            "claims": len(store.all("claims")),
            "sources": len(store.all("sources")),
            "approvals_pending": len([a for a in store.all("approvals")
                                      if a.get("status") == "pending"]),
        },
    }
