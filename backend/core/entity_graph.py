"""Global Eagle GEO - 实体图谱与全球鹰五维产业 Graph.

Brand → Company → Product → Model → Specification → Certification → Industry
→ Application → Target Market → Buyer，并与产业链/采购决策链/买家链/流量链/信任链/履约链相连。
"""
from __future__ import annotations

from typing import Any

from .store import Store
from .util import stable_id


def build(store: Store, entity_ids: list[str] | None = None) -> dict[str, Any]:
    entities = store.all("entities")
    if entity_ids:
        entities = [e for e in entities if e["id"] in set(entity_ids)]
    nodes: list[dict] = []
    edges: list[dict] = []
    seen: set[str] = set()

    def node(nid: str, ntype: str, label: str, **extra):
        if nid in seen:
            return
        seen.add(nid)
        nodes.append({"id": nid, "type": ntype, "label": label, **extra})

    for e in entities:
        brand_id = stable_id("BRD", e.get("brand", ""))
        comp_id = stable_id("CMP", e.get("company", ""))
        node(brand_id, "Brand", e.get("brand", ""), entity_id=e["id"])
        node(comp_id, "Company", e.get("company", ""), country=e.get("country", ""))
        edges.append({"source": brand_id, "target": comp_id, "relation": "OWNS"})
        edges.append({"source": comp_id, "target": brand_id, "relation": "OPERATES_BRAND"})

        for p in e.get("products", []):
            pid = stable_id("PRD", e["id"], p.get("name", ""))
            node(pid, "Product", p.get("name", ""), category=p.get("category", ""))
            edges.append({"source": comp_id, "target": pid, "relation": "PRODUCES"})
            edges.append({"source": brand_id, "target": pid, "relation": "BRAND_PRODUCT"})
            for m in p.get("models", []):
                mid = stable_id("MDL", p.get("name", ""), m.get("model", ""))
                node(mid, "ProductModel", m.get("model", ""))
                edges.append({"source": pid, "target": mid, "relation": "HAS_MODEL"})
                for spec in (m.get("specs") or {}).keys():
                    sid = stable_id("SPC", m.get("model", ""), spec)
                    node(sid, "Specification", spec)
                    edges.append({"source": mid, "target": sid, "relation": "HAS_SPEC"})
            for cert in p.get("certifications", []) or e.get("certifications", []):
                cid = stable_id("CER", cert)
                node(cid, "Certification", cert)
                edges.append({"source": pid, "target": cid, "relation": "CERTIFIED_BY"})
            for ind in p.get("industries", []) or e.get("industries", []):
                iid = stable_id("IND", ind)
                node(iid, "Industry", ind)
                edges.append({"source": pid, "target": iid, "relation": "SERVES_INDUSTRY"})
            for app in p.get("applications", []) or e.get("applications", []):
                aid = stable_id("APP", app)
                node(aid, "Application", app)
                edges.append({"source": pid, "target": aid, "relation": "USED_FOR"})
            for mk in e.get("target_markets", []):
                mid2 = stable_id("MKT", mk)
                node(mid2, "Market", mk)
                edges.append({"source": pid, "target": mid2, "relation": "AVAILABLE_IN"})
            for buyer in e.get("buyer_segments", []):
                bid = stable_id("BYR", buyer)
                node(bid, "Buyer", buyer)
                edges.append({"source": pid, "target": bid, "relation": "TARGETS_BUYER"})
        for comp in e.get("competitors", []):
            cid = stable_id("CMPT", comp)
            node(cid, "Competitor", comp)
            edges.append({"source": brand_id, "target": cid, "relation": "COMPETES_WITH"})
        for src in e.get("third_party_sources", []):
            sid = stable_id("TPS", src)
            node(sid, "ThirdPartySource", src)
            edges.append({"source": brand_id, "target": sid, "relation": "MENTIONED_BY"})
        for cs in e.get("case_studies", []):
            cid = stable_id("CAS", cs.get("title", ""))
            node(cid, "CaseStudy", cs.get("title", ""))
            edges.append({"source": comp_id, "target": cid, "relation": "HAS_CASE_STUDY"})

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "by_type": _by_type(nodes),
        },
    }


def _by_type(nodes: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for n in nodes:
        out[n["type"]] = out.get(n["type"], 0) + 1
    return out


def industrial_chain(store: Store, entity: dict) -> dict[str, Any]:
    """全球鹰五维产业 Graph：产业链 + 采购决策链 + 买家链 + 流量链 + 信任链 + 履约链。"""
    products = [p.get("name", "") for p in entity.get("products", [])]
    return {
        "industry_chain": {
            "raw_material": entity.get("supply_chain", {}).get("raw_material", []),
            "manufacturer": entity.get("company", ""),
            "product": products,
            "application": entity.get("applications", []),
            "distributor": entity.get("supply_chain", {}).get("distributor", []),
            "importer": entity.get("supply_chain", {}).get("importer", []),
        },
        "procurement_decision_chain": {
            "buyer": entity.get("buyer_segments", []),
            "decision_maker": entity.get("decision_makers", []),
            "country": entity.get("target_markets", []),
            "regulation": entity.get("compliance", []),
            "certification": entity.get("certifications", []),
        },
        "buyer_chain": entity.get("buyer_segments", []),
        "traffic_chain": {
            "owned": [entity.get("website", "")] if entity.get("website") else [],
            "earned": entity.get("third_party_sources", []),
            "ai_engines": ["ChatGPT", "Gemini", "Perplexity", "Google AI Overviews",
                           "Microsoft Copilot", "Claude"],
        },
        "trust_chain": {
            "certifications": entity.get("certifications", []),
            "case_studies": [c.get("title") for c in entity.get("case_studies", [])],
            "third_party_sources": entity.get("third_party_sources", []),
        },
        "fulfillment_chain": {
            "lead_time_days": entity.get("capabilities", {}).get("lead_time_days"),
            "moq": entity.get("capabilities", {}).get("moq"),
            "production_capacity": entity.get("capabilities", {}).get("capacity"),
            "incoterms": entity.get("capabilities", {}).get("incoterms", []),
            "after_sales": entity.get("capabilities", {}).get("after_sales", []),
        },
    }
