"""A05 Entity Intelligence Agent - 实体解析、实体清晰度与产业图谱连接。"""
from __future__ import annotations

from ..core import entity_graph
from ..core.util import clamp, r2

CLARITY_FIELDS = [
    ("brand", 12, "品牌名唯一且稳定"),
    ("company", 12, "公司法律主体清晰"),
    ("website", 8, "官方站点 canonical"),
    ("country", 8, "注册/生产国清晰"),
    ("products", 16, "产品实体完整（名称+型号+规格）"),
    ("industries", 10, "服务行业明确"),
    ("applications", 10, "应用场景明确"),
    ("target_markets", 12, "目标市场明确"),
    ("certifications", 12, "认证实体绑定"),
]


def run(store, ctx: dict) -> dict:
    ids = [c["entity_id"] for c in ctx.get("candidates", [])] or None
    graph = entity_graph.build(store, ids)
    entities = [e for e in store.all("entities") if (not ids or e["id"] in set(ids))]

    clarity = {}
    for e in entities:
        detail = []
        for field, weight, label in CLARITY_FIELDS:
            value = e.get(field)
            present = bool(value) and (len(value) > 0 if isinstance(value, (list, str, dict)) else True)
            detail.append({"field": field, "label": label, "weight": weight,
                           "present": present, "value_sample": _sample(value)})
        models = sum(len(p.get("models", [])) for p in e.get("products", []))
        specs = sum(len(m.get("specs") or {}) for p in e.get("products", [])
                    for m in p.get("models", []))
        bonus = 0
        bonus += 5 if models >= 2 else 0
        bonus += 5 if specs >= 6 else 0
        bonus += 3 if e.get("same_as") else 0
        raw = sum(d["weight"] for d in detail if d["present"]) + bonus
        clarity[e["id"]] = {
            "entity_id": e["id"],
            "brand": e.get("brand"),
            "entity_clarity_score": r2(clamp(raw)),
            "model_count": models,
            "spec_count": specs,
            "missing_fields": [d["label"] for d in detail if not d["present"]],
            "detail": detail,
        }

    industrial = {e["id"]: entity_graph.industrial_chain(store, e) for e in entities}

    result = {
        "agent": "A05 Entity Intelligence Agent",
        "entity_graph": graph,
        "entity_clarity": clarity,
        "industrial_intelligence_graph": industrial,
        "relations_supported": [
            "Brand-Company", "Company-Product", "Product-ProductModel", "Model-Specification",
            "Product-Certification", "Product-Industry", "Product-Application",
            "Product-Market", "Product-Buyer", "Brand-Competitor",
            "Brand-ThirdPartySource", "Company-CaseStudy",
        ],
    }
    ctx["entity_intel"] = result
    return result


def _sample(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value[:3])
    if isinstance(value, dict):
        return ", ".join(str(v) for v in list(value.values())[:3])
    return str(value)[:60]
