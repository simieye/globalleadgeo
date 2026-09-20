"""Global Eagle GEO - Human-in-the-loop 人工审核队列.

以下类别必须进入人工审核：认证声明、重大企业资质、医疗/金融/法律声明、
客户案例、销售数据、市场份额、排名声明、竞品比较、价格承诺、交付承诺、重大商业结论。
"""
from __future__ import annotations

from .store import Store
from .util import now_iso, uid

REQUIRED_CATEGORIES = {
    "certification_claim",
    "company_qualification",
    "medical_claim",
    "financial_claim",
    "legal_claim",
    "case_study",
    "sales_data",
    "market_share",
    "ranking_claim",
    "competitor_comparison",
    "price_commitment",
    "delivery_commitment",
    "major_business_conclusion",
}

STATUS = ("pending", "approved", "rejected", "revision_required", "expired")


def submit(store: Store, *, category: str, subject: str, entity_id: str | None,
           claim_id: str | None, content: str, evidence_ids: list[str] | None = None,
           reason: str = "", market: str | None = None, run_id: str | None = None) -> dict:
    item = {
        "id": uid("APR"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "category": category,
        "subject": subject,
        "entity_id": entity_id,
        "claim_id": claim_id,
        "content": content,
        "evidence_ids": evidence_ids or [],
        "reason": reason,
        "market": market,
        "run_id": run_id,
        "status": "pending",
        "reviewer": None,
        "decision_note": None,
        "requires_approval": category in REQUIRED_CATEGORIES,
    }
    store.add("approvals", item)
    return item


def decide(store: Store, approval_id: str, decision: str, reviewer: str, note: str = "") -> dict | None:
    if decision not in STATUS:
        return None
    item = store.get("approvals", approval_id)
    if not item:
        return None
    store.update("approvals", approval_id, {
        "status": decision,
        "reviewer": reviewer,
        "decision_note": note,
        "updated_at": now_iso(),
    })
    if item.get("claim_id"):
        if decision == "approved":
            store.update("claims", item["claim_id"], {
                "human_approval": "approved",
                "verification_status": "verified",
                "last_verified": now_iso(),
            })
        elif decision == "rejected":
            store.update("claims", item["claim_id"], {"human_approval": "rejected"})
    return store.get("approvals", approval_id)


def queue(store: Store, status: str | None = None) -> list[dict]:
    items = store.all("approvals")
    if status:
        items = [i for i in items if i.get("status") == status]
    return sorted(items, key=lambda i: i.get("created_at", ""), reverse=True)
