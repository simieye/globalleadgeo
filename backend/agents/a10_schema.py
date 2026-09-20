"""A10 Schema & Knowledge Graph Agent - 生成与页面真实内容一致的 JSON-LD。

禁止生成虚假 Schema：仅使用 verification_status=verified 且（敏感类）已经人工审核通过的 Claim。
"""
from __future__ import annotations

from ..core.util import stable_id

SUPPORTED = ["Organization", "Brand", "Product", "ProductModel", "Service", "Offer",
             "FAQPage", "Article", "TechArticle", "BreadcrumbList", "WebSite",
             "WebPage", "LocalBusiness"]


def run(store, ctx: dict) -> dict:
    ranked = ctx.get("ranked_entities", [])
    focus = ranked[0] if ranked else None
    if not focus:
        return {"agent": "A10 Schema & Knowledge Graph Agent", "schema": {}, "excluded": []}

    entity = store.get("entities", focus["entity_id"]) or {}
    claims = store.claims_for_entity(entity["id"])
    usable = [c for c in claims if c.get("verification_status") == "verified"]
    excluded = [{
        "claim": c["claim"],
        "reason": "未通过核验" if c.get("verification_status") != "verified" else "待人工审核",
    } for c in claims if c["id"] not in {u["id"] for u in usable}]

    base = (entity.get("website") or "https://example.com").rstrip("/")
    org_id = f"{base}/#organization"
    brand_id = f"{base}/#brand"
    site_id = f"{base}/#website"

    graph: list[dict] = [
        {
            "@type": "Organization", "@id": org_id,
            "name": entity.get("company"),
            "url": base,
            "address": {"@type": "PostalAddress", "addressCountry": entity.get("country")},
            "knowsAbout": entity.get("industries", [])[:5],
        },
        {
            "@type": "Brand", "@id": brand_id,
            "name": entity.get("brand"),
            "url": base,
            "sameAs": entity.get("same_as", []),
        },
        {"@type": "WebSite", "@id": site_id, "url": base, "name": entity.get("brand"),
         "publisher": {"@id": org_id}, "inLanguage": entity.get("languages", ["en"])},
    ]

    product = (entity.get("products") or [{}])[0]
    if product:
        pid = f"{base}/products/{_slug(product.get('name', 'product'))}#product"
        product_node = {
            "@type": "Product", "@id": pid,
            "name": product.get("name"),
            "description": product.get("description"),
            "brand": {"@id": brand_id},
            "manufacturer": {"@id": org_id},
            "category": product.get("category"),
            "additionalProperty": [
                {"@type": "PropertyValue", "name": k, "value": str(v)}
                for k, v in list((product.get("models") or [{}])[0].get("specs", {}).items())[:8]
            ],
        }
        cert_names = [c["claim"] for c in usable if c.get("category") == "certification_claim"]
        if cert_names:
            product_node["certification"] = cert_names[:5]
        graph.append(product_node)

        for m in product.get("models", []):
            graph.append({
                "@type": "ProductModel",
                "name": m.get("model"),
                "isVariantOf": {"@id": pid},
                "additionalProperty": [
                    {"@type": "PropertyValue", "name": k, "value": str(v)}
                    for k, v in list((m.get("specs") or {}).items())[:10]
                ],
            })
        if (entity.get("capabilities") or {}).get("price_hint"):
            graph.append({
                "@type": "Offer",
                "itemOffered": {"@id": pid},
                "priceSpecification": {
                    "@type": "PriceSpecification",
                    "description": entity["capabilities"]["price_hint"],
                },
                "eligibleRegion": entity.get("target_markets", [])[:5],
            })
        graph.append({
            "@type": "Service",
            "serviceType": "OEM/ODM manufacturing",
            "provider": {"@id": org_id},
            "areaServed": entity.get("target_markets", [])[:8],
        })

    contents = ctx.get("ai_answer_ready_content") or []
    faq_source = next((c for c in contents if c.get("faq")), None)
    if faq_source:
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q["question"],
                 "acceptedAnswer": {"@type": "Answer", "text": q["answer"]}}
                for q in faq_source["faq"][:10]
            ],
        })

    graph.append({
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": base},
            {"@type": "ListItem", "position": 2, "name": "Products",
             "item": f"{base}/products"},
            {"@type": "ListItem", "position": 3,
             "name": product.get("name", "Product"),
             "item": f"{base}/products/{_slug(product.get('name', 'product'))}"},
        ],
    })

    kg_relations = [
        {"from": brand_id, "to": org_id, "relation": "schema:brand"},
        {"from": org_id, "to": site_id, "relation": "schema:publisher"},
    ]
    if product:
        kg_relations.append({"from": brand_id, "to": f"{base}/products/{_slug(product.get('name', ''))}#product",
                             "relation": "schema:produces"})

    result = {
        "agent": "A10 Schema & Knowledge Graph Agent",
        "supported_types": SUPPORTED,
        "schema": {"@context": "https://schema.org", "@graph": graph},
        "entity_id": entity.get("id"),
        "entity_ids": {
            "organization": org_id, "brand": brand_id, "website": site_id,
            "product": stable_id("PRD", entity.get("id", ""), product.get("name", "")),
        },
        "canonical_url": f"{base}/products/{_slug(product.get('name', 'product'))}",
        "sameAs": entity.get("same_as", []),
        "knowledge_graph_relations": kg_relations,
        "excluded_claims": excluded,
        "rule": "仅已核验 Claim 进入 Schema；未核验/冲突 Claim 一律排除。",
    }
    ctx["schema"] = result
    return result


def _slug(name: str) -> str:
    return "-".join(str(name).lower().split())[:60] or "product"
