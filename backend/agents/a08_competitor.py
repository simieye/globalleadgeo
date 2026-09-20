"""A08 Competitor Intelligence Agent - 竞争实体矩阵与五类 Gap 识别。

禁止贬低竞争对手、禁止无证据的"第一/最佳/最低价/最大供应商"表述。
"""
from __future__ import annotations

from ..core.util import clamp, r2

MATRIX_FIELDS = ["brand", "product", "price_hint", "specification", "certification",
                 "market", "distribution", "content_authority", "third_party_mentions",
                 "ai_visibility"]


def run(store, ctx: dict) -> dict:
    ranked = ctx.get("ranked_entities", [])
    focus = ranked[0] if ranked else None
    entity = store.get("entities", focus["entity_id"]) if focus else None

    matrix = []
    for e in store.all("entities"):
        claims = store.claims_for_entity(e["id"])
        matrix.append({
            "entity_id": e["id"],
            "brand": e.get("brand"),
            "product": (e.get("products") or [{}])[0].get("name"),
            "price_hint": (e.get("capabilities") or {}).get("price_hint", "n/a"),
            "specification": _spec_summary(e),
            "certification": e.get("certifications", []),
            "market": e.get("target_markets", []),
            "distribution": (e.get("supply_chain") or {}).get("distributor", []),
            "content_authority": r2(clamp(len(e.get("content_assets", [])) * 12)),
            "third_party_mentions": len(e.get("third_party_sources", [])),
            "ai_visibility": _visibility(ctx, e["id"]),
            "third_party_domains": e.get("third_party_sources", []),
        })

    gaps = {
        "entity_gap": [], "content_gap": [], "evidence_gap": [],
        "query_gap": [], "market_gap": [], "citation_gap": [],
    }
    if entity and focus:
        gaps = _analyze(store, ctx, entity, focus, matrix)

    result = {
        "agent": "A08 Competitor Intelligence Agent",
        "focus_entity": focus["brand"] if focus else None,
        "competitor_matrix": matrix,
        "gaps": gaps,
        "guideline": [
            "禁止贬低竞争对手",
            "禁止制造虚假对比",
            "禁止无证据的'第一/最佳/最低价格/最大供应商'表述",
            "所有对比必须以可核验证据为基础",
        ],
    }
    ctx["competitor_intel"] = result
    ctx["competitor_gap"] = gaps
    return result


def _spec_summary(entity: dict) -> str:
    specs = []
    for p in entity.get("products", []):
        for m in p.get("models", []):
            items = list((m.get("specs") or {}).items())[:3]
            specs.append(f"{m.get('model')}: " + ", ".join(f"{k}={v}" for k, v in items))
    return " | ".join(specs[:2]) or "n/a"


def _visibility(ctx: dict, entity_id: str) -> float:
    for r in ctx.get("ranked_entities", []):
        if r["entity_id"] == entity_id:
            return r["geo_score"]
    return 0.0


def _analyze(store, ctx, entity: dict, focus: dict, matrix: list[dict]) -> dict:
    market = ctx.get("market_intel", {}).get("market", "Global")
    claims = store.claims_for_entity(entity["id"])
    gaps = {"entity_gap": [], "content_gap": [], "evidence_gap": [],
            "query_gap": [], "market_gap": [], "citation_gap": []}

    # Entity gap
    if not entity.get("same_as"):
        gaps["entity_gap"].append({
            "item": "缺少 sameAs 权威实体关联（LinkedIn/官方社媒/行业数据库）",
            "severity": "medium",
            "action": "补充官方社媒与行业数据库 sameAs 链接，提升 Entity Recognition",
        })
    if not any(m.get("specs") for p in entity.get("products", []) for m in p.get("models", [])):
        gaps["entity_gap"].append({
            "item": "产品型号缺少结构化规格参数",
            "severity": "high",
            "action": "补齐型号级 Spec 表（GPU/内存/功耗/接口/尺寸）",
        })

    # Evidence gap
    cov = ctx.get("evidence_intel", {}).get("coverage_by_entity", {}).get(entity["id"], {})
    if cov.get("tier1", 0) < 2:
        gaps["evidence_gap"].append({
            "item": f"Tier1 官方来源仅 {cov.get('tier1', 0)} 条",
            "severity": "high",
            "action": "发布官方技术白皮书、认证扫描件、产品 datasheet 并绑定 Claim",
        })
    if cov.get("verified_ratio", 0) < 0.6:
        gaps["evidence_gap"].append({
            "item": f"Claim 核验率 {r2(cov.get('verified_ratio', 0) * 100)}%",
            "severity": "medium",
            "action": "对未核验 Claim 补充信源或移出核心推荐依据",
        })
    if not any(c.get("category") == "case_study" for c in claims):
        gaps["evidence_gap"].append({
            "item": "缺少可验证客户案例",
            "severity": "high",
            "action": "产出含客户授权与可核验结果的案例页",
        })

    # Content gap
    assets = set(a.get("type", "") for a in entity.get("content_assets", []))
    for need in ("comparison", "buyer_guide", "country_page", "faq", "certification_guide"):
        if need not in assets:
            gaps["content_gap"].append({
                "item": f"缺少 {need} 类型内容资产",
                "severity": "medium",
                "action": f"在 GEO Topic Cluster 中新增 {need} 页面并接入 Pillar",
            })
    if not entity.get("faq"):
        gaps["content_gap"].append({
            "item": "缺少 FAQ 结构，AI 难以直接抽取答案",
            "severity": "high",
            "action": "补齐 6-10 条买家真实问题 FAQ 并标记 FAQPage Schema",
        })

    # Query gap
    matrix_q = ctx.get("query_expansion", {}).get("matrix", {})
    for category, queries in matrix_q.items():
        gaps["query_gap"].append({
            "item": f"{category} 共 {len(queries)} 条待覆盖查询",
            "severity": "low" if len(queries) < 4 else "medium",
            "action": f"针对 {queries[0] if queries else category} 建设对应内容资产",
        })

    # Market gap
    if market not in entity.get("target_markets", []):
        gaps["market_gap"].append({
            "item": f"{market} 未列入目标市场",
            "severity": "high",
            "action": f"建设 {market} 国家页：本地认证、本地术语、本地案例与交付方案",
        })
    langs = set(entity.get("languages", []) or ["en"])
    need_langs = set(ctx.get("market_intel", {}).get("languages", ["en"]))
    missing = need_langs - langs
    if missing:
        gaps["market_gap"].append({
            "item": f"缺少本地语言内容：{', '.join(sorted(missing))}",
            "severity": "medium",
            "action": "按本地采购术语重写（非机翻），并补充本地合规说明",
        })

    # Citation gap
    best = max((m["third_party_mentions"] for m in matrix if m["entity_id"] != entity["id"]),
               default=0)
    own = len(entity.get("third_party_sources", []))
    if own < best:
        gaps["citation_gap"].append({
            "item": f"第三方信源数量 {own} < 竞品最高 {best}",
            "severity": "medium",
            "action": "通过行业协会、媒体投稿、行业目录与标准组织名录增加可核验第三方提及",
        })
    return gaps
