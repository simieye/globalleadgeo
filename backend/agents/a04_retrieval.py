"""A04 Candidate Retrieval Agent - 向量 + 图谱 + 实体 + 证据 + Web 混合召回（Top 20）。"""
from __future__ import annotations

from ..core.util import clamp, r2, tokenize
from ..core.vector_index import TfidfIndex


def _entity_document(entity: dict) -> str:
    parts = [
        entity.get("brand", ""), entity.get("company", ""), entity.get("country", ""),
        " ".join(entity.get("target_markets", [])),
        " ".join(entity.get("industries", [])),
        " ".join(entity.get("applications", [])),
        " ".join(entity.get("certifications", [])),
        " ".join(entity.get("buyer_segments", [])),
        entity.get("positioning", ""),
    ]
    for p in entity.get("products", []):
        parts.append(p.get("name", ""))
        parts.append(p.get("description", ""))
        for m in p.get("models", []):
            parts.append(m.get("model", ""))
            parts.append(" ".join(f"{k} {v}" for k, v in (m.get("specs") or {}).items()))
    return " ".join(x for x in parts if x)


def run(store, ctx: dict, top_k: int = 20) -> dict:
    entities = store.all("entities")
    if ctx.get("entity_ids"):
        wanted = set(ctx["entity_ids"])
        pool = [e for e in entities if e["id"] in wanted]
    else:
        pool = entities

    queries: list[str] = ctx.get("query_expansion", {}).get("queries") or []
    primary = ctx.get("query", "")
    search_space = [primary] + queries[:12]

    index = TfidfIndex().fit({e["id"]: _entity_document(e) for e in pool})

    intent = ctx.get("intent", {})
    market = ctx.get("market_intel", {}).get("market") or intent.get("target_country") or ""
    intent_tokens = set(tokenize(primary))
    cert_tokens = set(c.lower() for c in intent.get("compliance_requirements", []))

    candidates = []
    for e in pool:
        vector_score = 0.0
        for q in search_space:
            hits = dict(index.search(q, top_k=len(pool) or 1))
            vector_score = max(vector_score, hits.get(e["id"], 0.0))
        vector_score = min(vector_score * 1.6, 1.0)

        doc_tokens = set(tokenize(_entity_document(e)))
        graph_score = _graph_overlap(e, intent_tokens, market, cert_tokens)
        entity_score = len(intent_tokens & doc_tokens) / max(len(intent_tokens), 1)

        claims = store.claims_for_entity(e["id"])
        evidence_score = min(len([c for c in claims
                                  if c.get("verification_status") == "verified"]) / 8.0, 1.0)
        web_bonus = 0.05 * min(len(e.get("third_party_sources", [])), 4) / 4

        hybrid = (0.40 * vector_score + 0.22 * graph_score + 0.16 * entity_score
                  + 0.14 * evidence_score + 0.08 * (web_bonus * 4))

        candidates.append({
            "entity_id": e["id"],
            "brand": e.get("brand", ""),
            "company": e.get("company", ""),
            "product": (e.get("products") or [{}])[0].get("name", ""),
            "model": (e.get("products") or [{}])[0].get("models", [{}])[0].get("model", ""),
            "country": e.get("country", ""),
            "market": e.get("target_markets", []),
            "attributes": {
                "industries": e.get("industries", []),
                "applications": e.get("applications", []),
                "certifications": e.get("certifications", []),
                "capabilities": e.get("capabilities", {}),
            },
            "evidence_ids": [c["id"] for c in claims],
            "source_urls": [s["url"] for c in claims
                            for s in store.sources_by_ids(c.get("evidence_source_ids", []))],
            "source_types": sorted({s.get("source_type") for c in claims
                                    for s in store.sources_by_ids(c.get("evidence_source_ids", []))}),
            "verification_status": _status_mix(claims),
            "retrieval": {
                "vector": r2(clamp(vector_score * 100)),
                "graph": r2(clamp(graph_score * 100)),
                "entity": r2(clamp(entity_score * 100)),
                "evidence": r2(clamp(evidence_score * 100)),
                "hybrid": r2(clamp(hybrid * 100)),
            },
            "hybrid_score": r2(clamp(hybrid * 100)),
        })

    candidates.sort(key=lambda c: c["hybrid_score"], reverse=True)
    candidates = candidates[:top_k]

    result = {
        "agent": "A04 Candidate Retrieval Agent",
        "pool_size": len(pool),
        "query_count": len(search_space),
        "top_k": top_k,
        "channels": ["vector_tfidf", "knowledge_graph", "entity_match", "evidence_boost", "web_signal"],
        "candidates": candidates,
    }
    ctx["candidates"] = candidates
    return result


def _graph_overlap(entity: dict, intent_tokens: set[str], market: str,
                   cert_tokens: set[str]) -> float:
    score = 0.0
    if market and market in entity.get("target_markets", []):
        score += 0.5
    if market and market == entity.get("country"):
        score += 0.2
    ents = set(" ".join(entity.get("industries", []) + entity.get("applications", [])).lower().split())
    score += min(len(intent_tokens & ents) / max(len(intent_tokens), 1), 1.0) * 0.3
    certs = set(c.lower() for c in entity.get("certifications", []))
    if cert_tokens and cert_tokens & certs:
        score += 0.2
    return min(score, 1.0)


def _status_mix(claims: list[dict]) -> str:
    if not claims:
        return "no_evidence"
    statuses = {c.get("verification_status") for c in claims}
    if statuses == {"verified"}:
        return "verified"
    if "conflicting" in statuses:
        return "conflicting"
    if "verified" in statuses:
        return "partially_verified"
    return "unverified"
