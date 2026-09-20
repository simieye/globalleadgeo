"""A07 GEO Scoring Agent - 统一 GEO Score（100 分，8 个维度）。

GEO Score 只表示：当前证据、实体、内容结构、市场相关性与查询匹配条件下的 AI 可见性优化程度。
不代表"一定会被 ChatGPT/Gemini/Perplexity 推荐"。
"""
from __future__ import annotations

from ..core.util import clamp, days_since, r2

DIMENSIONS = {
    "evidence_authority": 25,
    "query_relevance": 20,
    "entity_clarity": 15,
    "extractability": 10,
    "market_relevance": 10,
    "differentiation": 10,
    "citation_coverage": 5,
    "freshness": 5,
}

DISCLAIMER = ("GEO Score 表示在当前证据、实体、内容结构、市场相关性与查询匹配条件下的 "
              "AI 可见性优化程度，不构成对任何 AI 平台推荐结果的承诺。")


def run(store, ctx: dict) -> dict:
    weights = store.data.get("weights") or _default_weights()
    candidates = ctx.get("candidates", [])
    entity_intel = ctx.get("entity_intel", {})
    evidence_intel = ctx.get("evidence_intel", {})
    market_intel = ctx.get("market_intel", {})
    market = market_intel.get("market", "Global")
    clarity_map = entity_intel.get("entity_clarity", {})
    coverage_map = evidence_intel.get("coverage_by_entity", {})

    ranked = []
    for cand in candidates:
        eid = cand["entity_id"]
        entity = store.get("entities", eid) or {}
        claims = store.claims_for_entity(eid)
        cov = coverage_map.get(eid) or {"verified_ratio": 0, "tier1": 0, "tier2": 0,
                                        "tier3": 0, "third_party_domains": 0,
                                        "coverage": 0, "uncertainty": 100,
                                        "claim_count": 0}

        dims = {
            "evidence_authority": _evidence_authority(store, claims, cov) * weights.get("evidence", 1.0),
            "query_relevance": _query_relevance(cand, ctx) * weights.get("query", 1.0),
            "entity_clarity": _entity_clarity(clarity_map.get(eid, {})) * weights.get("entity", 1.0),
            "extractability": _extractability(entity, ctx) * weights.get("content", 1.0),
            "market_relevance": _market_relevance(entity, market, market_intel) * weights.get("market", 1.0),
            "differentiation": _differentiation(claims) * weights.get("entity", 1.0),
            "citation_coverage": _citation_coverage(store, claims, cov) * weights.get("citation", 1.0),
            "freshness": _freshness(store, claims) * weights.get("evidence", 1.0),
        }
        breakdown = {k: r2(clamp(v, 0, DIMENSIONS[k])) for k, v in dims.items()}
        overall = r2(clamp(sum(breakdown.values())))
        ev_cov = float(cov.get("coverage", 0))
        confidence = r2(clamp(0.45 * ev_cov + 0.25 * breakdown["evidence_authority"] /
                              DIMENSIONS["evidence_authority"] * 100
                              + 0.30 * (100 - float(cov.get("uncertainty", 100))), 0, 99))

        ranked.append({
            "entity_id": eid,
            "brand": cand.get("brand"),
            "product": cand.get("product"),
            "company": cand.get("company"),
            "country": cand.get("country"),
            "geo_score": overall,
            "score_breakdown": breakdown,
            "evidence_coverage": r2(ev_cov),
            "confidence": confidence,
            "uncertainty": r2(clamp(float(cov.get("uncertainty", 100)))),
            "citation_readiness": _readiness(overall, ev_cov),
            "market_relevance": _market_label(entity, market),
            "risk": _risks(entity, claims, cov, market),
            "retrieval_detail": cand.get("retrieval", {}),
        })

    ranked.sort(key=lambda r: (r["geo_score"], r["evidence_coverage"]), reverse=True)
    for i, r in enumerate(ranked, 1):
        r["rank"] = i

    overall = ranked[0] if ranked else None
    result = {
        "agent": "A07 GEO Scoring Agent",
        "dimensions": DIMENSIONS,
        "weights_applied": weights,
        "ranked_entities": ranked,
        "geo_score": {
            "overall": overall["geo_score"] if overall else 0,
            **({"score_breakdown": overall["score_breakdown"]} if overall else {}),
            "evidence_coverage": overall["evidence_coverage"] if overall else 0,
            "confidence": overall["confidence"] if overall else 0,
            "uncertainty": overall["uncertainty"] if overall else 100,
        },
        "disclaimer": DISCLAIMER,
    }
    ctx["geo_scoring"] = result
    ctx["ranked_entities"] = ranked
    return result


def _default_weights() -> dict:
    return {"query": 1.0, "market": 1.0, "content": 1.0, "evidence": 1.0,
            "entity": 1.0, "citation": 1.0, "conversion": 1.0}


# ---------- dimension scorers ----------
def _evidence_authority(store, claims: list[dict], cov: dict) -> float:
    if not claims:
        return 0.0
    verified = len([c for c in claims if c.get("verification_status") == "verified"])
    base = min(verified / 8.0, 1.0) * 12
    tier = min(cov.get("tier1", 0), 4) * 2.0 + min(cov.get("tier2", 0), 3) * 1.5
    third = min(cov.get("tier3", 0), 3) * 0.8
    approved = 2.0 if any(c.get("human_approval") == "approved" for c in claims) else 0.0
    penalty = 2.5 if any(c.get("verification_status") == "conflicting" for c in claims) else 0.0
    return max(base + tier + third + approved - penalty, 0.0)


def _query_relevance(cand: dict, ctx: dict) -> float:
    hybrid = float(cand.get("hybrid_score", 0)) / 100
    matrix = ctx.get("query_expansion", {}).get("matrix", {})
    covered = len(matrix.keys())
    coverage_bonus = min(covered / 10.0, 1.0) * 4
    return min(hybrid * 16 + coverage_bonus, 20)


def _entity_clarity(clarity: dict) -> float:
    return float(clarity.get("entity_clarity_score", 0)) / 100 * 15


def _extractability(entity: dict, ctx: dict) -> float:
    score = 0.0
    products = entity.get("products", [])
    if products and products[0].get("description"):
        score += 2.0
    if any(m.get("specs") for p in products for m in p.get("models", [])):
        score += 2.5
    if entity.get("faq"):
        score += 2.0
    if entity.get("content_assets"):
        score += 1.5
    if entity.get("schema_ready"):
        score += 1.0
    if entity.get("direct_answer"):
        score += 1.0
    return min(score, 10)


def _market_relevance(entity: dict, market: str, market_intel: dict) -> float:
    score = 0.0
    markets = entity.get("target_markets", [])
    if market in markets:
        score += 4.0
    elif any(m.lower() in market.lower() or market.lower() in m.lower() for m in markets):
        score += 2.0
    langs = set(entity.get("languages", []) or ["en"])
    if langs & set(market_intel.get("languages", ["en"])):
        score += 2.0
    entity_certs = set(c.lower() for c in entity.get("certifications", []))
    required = " ".join(market_intel.get("regulatory_requirements", [])).lower()
    if any(c.split("/")[0].strip() in required for c in entity_certs):
        score += 2.0
    if entity.get("capabilities", {}).get("local_service", False):
        score += 1.0
    if entity.get("country") == market:
        score += 1.0
    return min(score, 10)


def _differentiation(claims: list[dict]) -> float:
    diff = [c for c in claims if c.get("category") in
            ("differentiation", "capability", "technology", "case_study")]
    verified = [c for c in diff if c.get("verification_status") == "verified"]
    return min(len(verified) * 2.5 + len(diff) * 0.5, 10)


def _citation_coverage(store, claims: list[dict], cov: dict) -> float:
    domains = set()
    for c in claims:
        for s in store.sources_by_ids(c.get("evidence_source_ids", [])):
            if s.get("tier", 5) >= 2:
                domains.add(s.get("domain", ""))
    return min(len([d for d in domains if d]) * 1.0, 5)


def _freshness(store, claims: list[dict]) -> float:
    dates = []
    for c in claims:
        for s in store.sources_by_ids(c.get("evidence_source_ids", [])):
            if s.get("published_date"):
                dates.append(s["published_date"])
    if not dates:
        return 1.0
    newest = min([d for d in (days_since(x) for x in dates) if d is not None] or [9999])
    if newest <= 90:
        return 5.0
    if newest <= 180:
        return 4.0
    if newest <= 365:
        return 3.0
    if newest <= 730:
        return 1.5
    return 0.5


def _readiness(score: float, coverage: float) -> str:
    if score >= 75 and coverage >= 60:
        return "High"
    if score >= 55 and coverage >= 40:
        return "Medium"
    return "Low"


def _market_label(entity: dict, market: str) -> str:
    if market in entity.get("target_markets", []):
        return f"Strong - {market} 已列入目标市场"
    if entity.get("target_markets"):
        return f"Partial - 目标市场为 {', '.join(entity['target_markets'][:3])}"
    return "Unknown - 未声明目标市场"


def _risks(entity: dict, claims: list[dict], cov: dict, market: str) -> list[str]:
    risks = []
    if not claims:
        risks.append("无证据记录：不得作为 AI 推荐候选")
    unverified_cert = [c for c in claims if c.get("category") == "certification_claim"
                       and c.get("verification_status") != "verified"]
    if unverified_cert:
        risks.append(f"{len(unverified_cert)} 条认证声明未核验，禁止写入 Schema 与对外内容")
    if any(c.get("verification_status") == "conflicting" for c in claims):
        risks.append("存在 conflicting_evidence，需人工裁定")
    if cov.get("tier1", 0) == 0:
        risks.append("缺少 Tier1 官方来源，证据权威度受限")
    if market and market not in entity.get("target_markets", []):
        risks.append(f"{market} 未列入目标市场，市场相关性不足")
    if not entity.get("products"):
        risks.append("缺少产品实体，AI 难以识别具体供给能力")
    if cov.get("third_party_domains", 0) < 2:
        risks.append("第三方信源覆盖不足，引用概率偏低")
    return risks
