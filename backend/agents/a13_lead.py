"""A13 Lead Conversion Agent - GEO → 网站 → AI 接待 → 资质判定 → CRM → RFQ。"""
from __future__ import annotations

from ..core.util import clamp, now_iso, r2, uid

STAGES = ["AI Answer", "Website", "AI Agent Reception", "Qualification", "CRM",
          "RFQ", "Quotation", "Sample", "Negotiation", "Order", "Repeat Purchase"]


def run(store, ctx: dict) -> dict:
    intent = ctx.get("intent", {})
    result = {
        "agent": "A13 Lead Conversion Agent",
        "conversion_chain": STAGES,
        "lead_source": "GEO",
        "tracking_fields": ["lead_source", "query", "market", "product", "intent",
                            "buyer_stage", "ai_platform", "landing_page", "campaign",
                            "conversation", "rfq", "entity_id", "language"],
        "qualification_model": {
            "signals": {
                "buyer_stage_weight": {"Awareness": 10, "Consideration": 25, "Evaluation": 40,
                                       "Decision": 60, "Procurement": 80, "Repeat Purchase": 70},
                "intent_weight": {"price_inquiry": 20, "supplier_search": 15, "oem_odm": 20,
                                  "project_epc": 25, "certification": 10, "technical_spec": 15},
                "completeness_weight": {"company_name": 15, "email_domain": 10,
                                        "quantity": 15, "target_market": 10, "timeline": 10},
            },
            "qualified_threshold": 60,
        },
        "routing_rules": [
            "Qualified(≥60) → 30 分钟内人工/AI 跟进并生成 RFQ 草稿",
            "40-59 → AI 接待补充资质信息（数量、认证、交期、目的港）",
            "<40 → 进入内容培育（案例、认证指南、选型手册）",
        ],
        "current_query_context": {
            "query": ctx.get("query"),
            "market": ctx.get("market_intel", {}).get("market"),
            "intent": intent.get("intent_type"),
            "buyer_stage": intent.get("buyer_stage"),
        },
    }
    ctx["crm_tracking"] = result
    return result


def create_lead(store, payload: dict) -> dict:
    intent = payload.get("intent") or {}
    stage = payload.get("buyer_stage", "Consideration")
    score = 0.0
    score += {"Awareness": 10, "Consideration": 25, "Evaluation": 40, "Decision": 60,
              "Procurement": 80, "Repeat Purchase": 70}.get(stage, 20)
    for it in intent if isinstance(intent, list) else [intent]:
        score += {"price_inquiry": 20, "supplier_search": 15, "oem_odm": 20,
                  "project_epc": 25, "certification": 10, "technical_spec": 15}.get(it, 5)
    for field, w in (("company_name", 15), ("email", 10), ("quantity", 15),
                     ("target_market", 10), ("timeline", 10)):
        if payload.get(field):
            score += w
    score = r2(clamp(score))

    lead = {
        "id": uid("LED"),
        "created_at": now_iso(),
        "lead_source": payload.get("lead_source", "GEO"),
        "entity_id": payload.get("entity_id"),
        "query": payload.get("query"),
        "market": payload.get("target_market") or payload.get("market"),
        "product": payload.get("product"),
        "intent": intent,
        "buyer_stage": stage,
        "ai_platform": payload.get("ai_platform"),
        "landing_page": payload.get("landing_page"),
        "campaign": payload.get("campaign"),
        "conversation": payload.get("conversation", []),
        "contact": {
            "company_name": payload.get("company_name"),
            "contact_name": payload.get("contact_name"),
            "email": payload.get("email"),
            "phone": payload.get("phone"),
            "country": payload.get("country"),
        },
        "requirements": {
            "quantity": payload.get("quantity"),
            "certification": payload.get("certification", []),
            "timeline": payload.get("timeline"),
            "incoterm": payload.get("incoterm"),
        },
        "language": payload.get("language", "en"),
        "source_ref": payload.get("source_ref"),
        "verification_status": payload.get("verification_status", "unverified"),
        "metadata": payload.get("metadata", {}),
        "qualification_score": score,
        "status": "qualified" if score >= 60 else ("nurturing" if score >= 40 else "raw"),
        "rfq_id": None,
    }
    store.add("leads", lead)
    return lead


def to_rfq(store, lead_id: str, items: list[dict] | None = None) -> dict | None:
    lead = store.get("leads", lead_id)
    if not lead:
        return None
    rfq = {
        "id": uid("RFQ"),
        "created_at": now_iso(),
        "lead_id": lead_id,
        "entity_id": lead.get("entity_id"),
        "market": lead.get("market"),
        "items": items or [{
            "product": lead.get("product"),
            "quantity": lead.get("requirements", {}).get("quantity"),
            "certification_required": lead.get("requirements", {}).get("certification", []),
        }],
        "status": "draft",
        "source": "GEO",
    }
    store.add("rfqs", rfq)
    store.update("leads", lead_id, {"rfq_id": rfq["id"], "status": "rfq_created"})
    return rfq


def pipeline(store, status: str | None = None) -> list[dict]:
    leads = store.all("leads")
    if status:
        leads = [l for l in leads if l.get("status") == status]
    return sorted(leads, key=lambda l: l.get("created_at", ""), reverse=True)
