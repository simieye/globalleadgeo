"""A06 Evidence Verification Agent - Claim → Evidence → Source → Citation 核验与冲突处理。"""
from __future__ import annotations

from ..core import approval as approval_core
from ..core import evidence_graph
from ..core.util import clamp, r2

# 需要人工审核的 Claim 类别
SENSITIVE = {"certification_claim", "case_study", "sales_data", "market_share",
             "ranking_claim", "competitor_comparison", "price_commitment",
             "delivery_commitment", "company_qualification", "major_business_conclusion"}


def run(store, ctx: dict) -> dict:
    enable_web = bool(ctx.get("enable_web_verify"))
    verify_fn = None
    if enable_web:
        from ..core.web_research import verify_url
        verify_fn = verify_url

    entity_ids = [c["entity_id"] for c in ctx.get("candidates", [])]
    if not entity_ids:
        entity_ids = [e["id"] for e in store.all("entities")]

    verified_claims = []
    approvals = []
    for eid in entity_ids:
        for claim in store.claims_for_entity(eid):
            updated = evidence_graph.verify_claim(store, claim, enable_web=enable_web,
                                                  verify_fn=verify_fn)
            verified_claims.append(updated)
            if updated.get("category") in SENSITIVE or updated.get("requires_human_approval"):
                existing = [a for a in store.all("approvals")
                            if a.get("claim_id") == updated["id"] and a.get("status") == "pending"]
                if not existing:
                    approvals.append(approval_core.submit(
                        store,
                        category=updated.get("category", "major_business_conclusion"),
                        subject=f"{updated['claim'][:70]}",
                        entity_id=eid,
                        claim_id=updated["id"],
                        content=updated["claim"],
                        evidence_ids=updated.get("evidence_source_ids", []),
                        reason="敏感类声明需人工审核后方可用于对外内容与 Schema",
                        market=(updated.get("market") or [None])[0],
                        run_id=ctx.get("run_id"),
                    ))

    conflicts = evidence_graph.detect_conflicts(store, None)
    for conflict in conflicts:
        for cid in conflict["claim_ids"]:
            claim = store.get("claims", cid)
            if not claim:
                continue
            exists = [a for a in store.all("approvals")
                      if a.get("claim_id") == cid and a.get("status") == "pending"]
            if not exists:
                approvals.append(approval_core.submit(
                    store, category="major_business_conclusion",
                    subject=f"证据冲突：{claim['claim'][:60]}",
                    entity_id=claim.get("entity_id"), claim_id=cid, content=claim["claim"],
                    evidence_ids=claim.get("evidence_source_ids", []),
                    reason="conflicting_evidence：多来源核验结果冲突，需人工裁定",
                    run_id=ctx.get("run_id"),
                ))

    coverage = {eid: evidence_graph.coverage(store, eid) for eid in entity_ids}
    graph = evidence_graph.build_graph(store, entity_ids)

    result = {
        "agent": "A06 Evidence Verification Agent",
        "web_verification": "enabled" if enable_web else "disabled",
        "claims_verified_count": len(verified_claims),
        "verified": len([c for c in verified_claims if c.get("verification_status") == "verified"]),
        "unverified": len([c for c in verified_claims if c.get("verification_status") == "unverified"]),
        "conflicting": len([c for c in verified_claims if c.get("verification_status") == "conflicting"]),
        "conflicts": conflicts,
        "coverage_by_entity": coverage,
        "approval_items_created": len(approvals),
        "evidence_graph": graph,
        "rule": "任何无法验证的信息 status=unverified，不得作为核心推荐依据。",
    }
    ctx["evidence_intel"] = result
    return result
