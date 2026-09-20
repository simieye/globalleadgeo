"""Global Eagle GEO - 统一证据图谱 (Claim → Evidence → Source → Citation).

任何 AI 生成内容必须能反向追溯：AI Answer → Claim → Evidence → Source。
未经核验的信息 status = unverified，不得作为核心推荐依据。
"""
from __future__ import annotations

from typing import Any

from .store import Store
from .util import clamp, days_since, domain_of, now_iso, r2, uid

# 证据分层权重（对应系统文档 Principle 01：Evidence First）
TIER_WEIGHT = {1: 10.0, 2: 8.0, 3: 5.0, 4: 3.0, 5: 1.5}
TIER_LABEL = {
    1: "Tier1 官方来源（产品页/技术文档/认证文件/白皮书/企业信息）",
    2: "Tier2 政府监管/认证机构/行业协会/大学/标准组织",
    3: "Tier3 主流行业媒体/专业媒体/可信商业数据库",
    4: "Tier4 LinkedIn/YouTube/Reddit/Quora/行业社区",
    5: "Tier5 普通博客/论坛/用户生成内容",
}


def add_source(store: Store, url: str, source_type: str, tier: int, publisher: str = "",
               authority: float | None = None, published_date: str | None = None,
               language: str = "en", market: str | None = None) -> dict:
    src = {
        "id": uid("SRC"),
        "url": url,
        "domain": domain_of(url),
        "source_type": source_type,
        "tier": tier,
        "tier_label": TIER_LABEL.get(tier, ""),
        "publisher": publisher,
        "authority": authority if authority is not None else TIER_WEIGHT.get(tier, 1.0),
        "published_date": published_date,
        "language": language,
        "market": market,
        "reachable": None,
        "last_checked": None,
        "http_status": None,
        "fetched_title": None,
    }
    store.add("sources", src)
    return src


def add_claim(store: Store, *, entity_id: str, claim: str, category: str = "general",
              evidence_source_ids: list[str] | None = None, market: list[str] | None = None,
              language: list[str] | None = None, verification_status: str = "unverified",
              confidence: float = 0.3, requires_human: bool = False) -> dict:
    claim_obj = {
        "id": uid("CLM"),
        "entity_id": entity_id,
        "claim": claim,
        "category": category,
        "evidence_source_ids": evidence_source_ids or [],
        "market": market or [],
        "language": language or ["en"],
        "verification_status": verification_status,
        "confidence": confidence,
        "requires_human_approval": requires_human,
        "human_approval": None,
        "created_at": now_iso(),
        "last_verified": None if verification_status != "verified" else now_iso(),
        "conflict": None,
    }
    store.add("claims", claim_obj)
    return claim_obj


def verify_claim(store: Store, claim: dict, enable_web: bool = False, verify_fn=None) -> dict:
    """核验单条 Claim：证据存在性 → 信源层级 → 可达性 → 冲突检测。"""
    sources = store.sources_by_ids(claim.get("evidence_source_ids", []))
    if not sources:
        claim["verification_status"] = "unverified"
        claim["confidence"] = 0.15
        store.update("claims", claim["id"], claim)
        return claim

    if enable_web and verify_fn:
        for s in sources:
            res = verify_fn(s["url"])
            store.update("sources", s["id"], {
                "reachable": res.get("reachable"),
                "http_status": res.get("status_code"),
                "fetched_title": res.get("title"),
                "last_checked": res.get("checked_at"),
            })
            s.update(res)

    # 只有通过真实可达性核验（HTTP 请求）的信源才可作为核验依据；
    # 未核验（reachable=None）或不可达（False）一律计为 unverified。
    reachable = [s for s in sources if s.get("reachable") is True]
    if claim.get("human_approval") == "approved":
        claim["verification_status"] = "verified"
        claim["confidence"] = max(claim.get("confidence", 0.3), 0.6)
        claim["verification_note"] = "经人工审核批准"
        claim["last_verified"] = now_iso()
        store.update("claims", claim["id"], claim)
        return claim
    if not reachable:
        claim["verification_status"] = "unverified"
        claim["confidence"] = 0.2
        claim["verification_note"] = "信源未通过可达性核验，需启用联网核验或人工审核"
    else:
        claim.pop("verification_note", None)
        best_tier = min(s.get("tier", 5) for s in reachable)
        authority = max(s.get("authority", 0) for s in reachable)
        freshness = _freshness_score([s.get("published_date") for s in reachable])
        score = (authority / 10.0) * 0.6 + freshness * 0.2 + min(len(reachable) / 3.0, 1.0) * 0.2
        claim["confidence"] = r2(clamp(min(score, 1.0) * 100, 5, 99) / 100)
        claim["best_tier"] = best_tier
        if best_tier <= 2 and claim["confidence"] >= 0.55:
            claim["verification_status"] = "verified"
        elif best_tier <= 3 and claim["confidence"] >= 0.4:
            claim["verification_status"] = "verified"
        else:
            claim["verification_status"] = "unverified"
    claim["last_verified"] = now_iso()
    store.update("claims", claim["id"], claim)
    return claim


def _freshness_score(dates: list[str | None]) -> float:
    vals = [d for d in (days_since(x) for x in dates) if d is not None]
    if not vals:
        return 0.3
    newest = min(vals)
    if newest <= 90:
        return 1.0
    if newest <= 365:
        return 0.7
    if newest <= 730:
        return 0.45
    return 0.2


def detect_conflicts(store: Store, entity_id: str | None = None) -> list[dict]:
    """同一 Claim 出现相互冲突的核验状态时标记 conflicting 并提交人工队列。"""
    claims = store.claims_for_entity(entity_id) if entity_id else store.all("claims")
    buckets: dict[str, list[dict]] = {}
    for c in claims:
        key = c["claim"].strip().lower()
        buckets.setdefault(key, []).append(c)
    conflicts = []
    for key, group in buckets.items():
        statuses = {c.get("verification_status") for c in group}
        if len(group) > 1 and ("verified" in statuses and "unverified" in statuses):
            for c in group:
                store.update("claims", c["id"], {"verification_status": "conflicting",
                                                 "conflict": "conflicting_evidence"})
                c["verification_status"] = "conflicting"
            conflicts.append({
                "claim": group[0]["claim"],
                "entity_id": entity_id,
                "claim_ids": [c["id"] for c in group],
                "resolution": "submitted_to_human_approval_queue",
            })
    return conflicts


def coverage(store: Store, entity_id: str) -> dict[str, Any]:
    claims = store.claims_for_entity(entity_id)
    if not claims:
        return {"claim_count": 0, "verified_ratio": 0.0, "tier1": 0, "tier2": 0,
                "tier3": 0, "third_party_domains": 0, "coverage": 0.0, "uncertainty": 1.0}
    verified = [c for c in claims if c.get("verification_status") == "verified"]
    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    domains: set[str] = set()
    for c in claims:
        for s in store.sources_by_ids(c.get("evidence_source_ids", [])):
            tier_counts[s.get("tier", 5)] = tier_counts.get(s.get("tier", 5), 0) + 1
            if s.get("tier", 5) >= 2:
                domains.add(s.get("domain", ""))
    ratio = len(verified) / len(claims)
    cov = (0.60 * ratio
           + 0.15 * min(tier_counts[1], 3) / 3
           + 0.15 * min(tier_counts[2], 3) / 3
           + 0.10 * min(len([d for d in domains if d]), 6) / 6)
    return {
        "claim_count": len(claims),
        "verified_count": len(verified),
        "verified_ratio": r2(ratio),
        "tier1": tier_counts[1], "tier2": tier_counts[2], "tier3": tier_counts[3],
        "tier4": tier_counts[4], "tier5": tier_counts[5],
        "third_party_domains": len([d for d in domains if d]),
        "coverage": r2(clamp(cov * 100, 0, 100)),
        "uncertainty": r2(clamp((1 - cov) * 100, 0, 100)),
    }


def build_graph(store: Store, entity_ids: list[str] | None = None) -> dict[str, Any]:
    ids = set(entity_ids) if entity_ids else None
    nodes: list[dict] = []
    edges: list[dict] = []
    for c in store.all("claims"):
        if ids and c.get("entity_id") not in ids:
            continue
        nodes.append({"id": c["id"], "type": "claim", "label": c["claim"][:80],
                      "status": c.get("verification_status"),
                      "confidence": c.get("confidence")})
        edges.append({"source": c["entity_id"], "target": c["id"], "relation": "HAS_CLAIM"})
        for sid in c.get("evidence_source_ids", []):
            s = store.get("sources", sid)
            if not s:
                continue
            nodes.append({"id": s["id"], "type": "source", "label": s["domain"],
                          "tier": s.get("tier"),
                          "status": "reachable" if s.get("reachable") else "unknown"})
            edges.append({"source": c["id"], "target": s["id"], "relation": "SUPPORTED_BY"})
    return {"nodes": nodes, "edges": edges}
