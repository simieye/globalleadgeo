"""A14 GEO Analytics Agent - 四层指标体系与 GEO Revenue Attribution。"""
from __future__ import annotations

from ..core.util import r2


def run(store, ctx: dict) -> dict:
    return {"agent": "A14 GEO Analytics Agent", **metrics(store)}


def metrics(store) -> dict:
    monitoring = store.all("monitoring")
    leads = store.all("leads")
    rfqs = store.all("rfqs")
    feedback = store.all("feedback")

    live = [m for m in monitoring if m.get("mode") == "live"]
    lv = max(len(live), 1)

    level1 = {
        "brand_mention_rate": r2(100 * len([m for m in live if m.get("brand_mention")]) / lv),
        "entity_recognition_rate": r2(100 * len([m for m in live if m.get("brands_mentioned")]) / lv),
        "query_coverage": r2(100 * len({m.get("query") for m in monitoring}) /
                             max(len({m.get("query") for m in monitoring}) or 1, 1)),
        "ai_visibility_index": r2(
            100 * len([m for m in live if m.get("brand_mention") or m.get("citation_count")]) / lv),
        "probes_total": len(monitoring),
        "probes_live": len(live),
    }

    citations = [c for m in live for c in m.get("citations", [])]
    level2 = {
        "citation_rate": r2(100 * len([m for m in live if m.get("citation_count")]) / lv),
        "citation_count": len(citations),
        "unique_citation_domains": len({c.split("/")[2] for c in citations if "/" in c}),
        "third_party_citations": len(store.all("sources")),
        "source_authority_avg": r2(sum(s.get("authority", 0) for s in store.all("sources")) /
                                   max(len(store.all("sources")), 1)),
    }

    qualified = [l for l in leads if l.get("status") in ("qualified", "rfq_created")]
    level3 = {
        "ai_answer_to_website": len(monitoring),
        "website_to_ai_chat": len(leads),
        "ai_chat_to_inquiry": len(leads),
        "inquiry_to_rfq": len(rfqs),
        "inquiry_to_rfq_rate": r2(100 * len(rfqs) / max(len(leads), 1)),
        "qualified_rate": r2(100 * len(qualified) / max(len(leads), 1)),
    }

    orders = [f for f in feedback if f.get("signal") in ("Order", "Repeat Purchase")]
    level4 = {
        "rfq": len(rfqs),
        "sample": len([f for f in feedback if f.get("signal") == "Sample"]),
        "order": len(orders),
        "gmv": r2(sum(float(f.get("value", 0) or 0) for f in orders)),
        "repeat_purchase": len([f for f in feedback if f.get("signal") == "Repeat Purchase"]),
        "conversion_rate": r2(100 * len(orders) / max(len(leads), 1)),
        "customer_acquisition_cost": None,
    }

    return {
        "level1_visibility": level1,
        "level2_citation": level2,
        "level3_engagement": level3,
        "level4_revenue": level4,
        "attribution_chain": ["GEO曝光", "AI推荐/引用", "网站访问", "AI询盘", "RFQ", "成交"],
        "note": "Level 1/2 中 live 探针为真实观测；simulated 探针不计入真实指标。",
    }
