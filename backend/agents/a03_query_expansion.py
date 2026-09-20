"""A03 Query Expansion Agent - 将自然语言 Query 扩展为 GEO Query Matrix（10 类）。

禁止机械关键词堆砌；所有 Query 必须是真实买家会提出的自然语言问题。
"""
from __future__ import annotations

from ..core.util import norm_text

TEMPLATES = {
    "product_query": [
        "{product} for {industry}",
        "{product} with {spec}",
        "{product} {model} specification and datasheet",
        "what is {product} and how to choose it",
    ],
    "supplier_query": [
        "{product} supplier in {market}",
        "{product} manufacturer with export experience",
        "reliable {product} supplier for {industry}",
        "{product} OEM supplier {market}",
    ],
    "comparison_query": [
        "{product} vs {alt} which is better",
        "best {product} brands comparison {year}",
        "{product} supplier comparison - certification, lead time, warranty",
    ],
    "technical_query": [
        "{product} technical specification {spec}",
        "how to size {product} for {usecase}",
        "{product} power consumption and cooling requirements",
        "{product} integration with existing infrastructure",
    ],
    "price_query": [
        "{product} price {year}",
        "{product} cost breakdown and MOQ",
        "how much does {product} cost for {market} delivery",
        "{product} quotation lead time and payment terms",
    ],
    "certification_query": [
        "{product} certification required in {market}",
        "{product} {cert} compliance checklist",
        "{product} import requirements and standards {market}",
    ],
    "application_query": [
        "{product} for {usecase}",
        "{product} use case in {industry}",
        "deployment architecture for {product} in {usecase}",
    ],
    "local_market_query": [
        "{product} supplier {market} local support",
        "{market} {industry} {product} procurement guide",
        "{product} distributor and service partner in {market}",
    ],
    "long_tail_query": [
        "{product} supplier with {cert} certification and {lead} lead time",
        "{product} for {usecase} in {market} - total cost of ownership",
        "customized {product} OEM ODM for {industry} buyer {market}",
        "{product} supplier that provides samples and factory audit",
    ],
    "conversational_query": [
        "I need a {product} supplier for {market}, who can deliver quickly?",
        "which {product} manufacturer can meet {cert} for {market}?",
        "can you recommend a {product} supplier for {usecase}?",
        "what should I check before importing {product} to {market}?",
    ],
}


def run(store, ctx: dict) -> dict:
    intent = ctx.get("intent", {})
    market_intel = ctx.get("market_intel", {})
    query = norm_text(ctx.get("query", ""))

    product = intent.get("product_category") or _guess_product(query) or "industrial equipment"
    industry = intent.get("industry") or "industrial"
    market = market_intel.get("market") or intent.get("target_country") or "global market"
    cert = (intent.get("compliance_requirements") or market_intel.get(
        "regulatory_requirements") or ["CE/FCC"])[0]
    usecases = intent.get("use_case") or ["production deployment"]
    lead = "4-week"
    year = "2026"

    entity_hints = ctx.get("entity_hints", {})
    model = entity_hints.get("model", "")
    spec = entity_hints.get("spec", "key parameters")
    alt = entity_hints.get("competitor", "alternatives")

    def fill(tpl: str) -> str:
        return (tpl.replace("{product}", product)
                   .replace("{industry}", industry)
                   .replace("{market}", market)
                   .replace("{cert}", cert)
                   .replace("{usecase}", usecases[0])
                   .replace("{model}", model or product)
                   .replace("{spec}", spec)
                   .replace("{alt}", alt)
                   .replace("{lead}", lead)
                   .replace("{year}", year)).strip()

    matrix: dict[str, list[str]] = {}
    for category, tpls in TEMPLATES.items():
        items = []
        for tpl in tpls:
            q = fill(tpl)
            if q and q not in items:
                items.append(q)
        if category == "local_market_query":
            for term in market_intel.get("local_terms", [])[:2]:
                items.append(f"{term} supplier {market}")
        matrix[category] = _dedup(items)

    flat = [q for items in matrix.values() for q in items]
    result = {
        "agent": "A03 Query Expansion Agent",
        "original_query": query,
        "matrix": matrix,
        "total_queries": len(flat),
        "queries": flat,
        "coverage_note": "覆盖产品/供应商/对比/技术/价格/认证/应用/本地市场/长尾/对话 10 类查询意图。",
    }
    ctx["query_expansion"] = result
    return result


def _guess_product(query: str) -> str:
    low = query.lower()
    for key in ("gpu server", "ai server", "server", "battery pack", "energy storage",
                "inverter", "led display", "sensor", "cable", "module"):
        if key in low:
            return key
    return ""


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for i in items:
        if i.lower() not in seen:
            seen.add(i.lower())
            out.append(i)
    return out
