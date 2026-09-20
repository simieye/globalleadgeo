"""A09 AI Answer Optimization Agent - 生成 AI Answer Ready Content。

结构：Direct Answer → Entity Definition → Key Specifications → Use Cases →
Target Market → Differentiation → Evidence → FAQ → Procurement CTA
原则：Answer First / Entity First / Evidence First / Structured First / Human Readable
未核验 Claim 只能标记为 unverified，不得写成事实结论。
"""
from __future__ import annotations

from ..core.util import norm_text


def run(store, ctx: dict) -> list[dict]:
    ranked = ctx.get("ranked_entities", [])
    market = ctx.get("market_intel", {}).get("market", "Global")
    languages = ctx.get("languages") or ["en"]
    contents: list[dict] = []

    for r in ranked[:3]:
        entity = store.get("entities", r["entity_id"])
        if not entity:
            continue
        claims = store.claims_for_entity(entity["id"])
        verified = [c for c in claims if c.get("verification_status") == "verified"]
        unverified = [c for c in claims if c.get("verification_status") != "verified"]
        product = (entity.get("products") or [{}])[0]
        models = product.get("models", [])

        for lang in languages:
            contents.append(_build(store, ctx, entity, r, product, models,
                                   verified, unverified, market, lang))
    ctx["ai_answer_ready_content"] = contents
    return contents


def _build(store, ctx, entity: dict, ranked: dict, product: dict, models: list[dict],
           verified: list[dict], unverified: list[dict], market: str, lang: str) -> dict:
    intent = ctx.get("intent", {})
    brand = entity.get("brand", "")
    company = entity.get("company", "")
    product_name = product.get("name", "")
    model_name = models[0].get("model", "") if models else ""
    specs = models[0].get("specs", {}) if models else {}

    direct = (f"{brand}（{company}）是面向 {', '.join(entity.get('industries', [])[:2]) or 'B2B 行业'} 的 "
              f"{product_name} 制造商与供应商，主力型号 {model_name or '见规格表'}，"
              f"服务市场包括 {', '.join(entity.get('target_markets', [])[:3]) or '多区域市场'}。")
    entity_def = (f"{brand} 是 {company} 旗下品牌，注册/生产地 {entity.get('country', 'n/a')}；"
                  f"核心产品为 {product_name}，应用涵盖 "
                  f"{', '.join(entity.get('applications', [])[:3]) or '通用工业与数据中心场景'}。")

    key_specs = [f"{k}: {v}" for k, v in list(specs.items())[:8]]
    use_cases = entity.get("applications", [])[:5] or intent.get("use_case", [])
    differentiation = [c["claim"] for c in verified
                       if c.get("category") in ("differentiation", "capability", "technology")]
    evidence_items = []
    for c in verified:
        for s in store.sources_by_ids(c.get("evidence_source_ids", [])):
            evidence_items.append({
                "claim": c["claim"],
                "source_url": s.get("url"),
                "source_type": s.get("source_type"),
                "tier": s.get("tier"),
                "publisher": s.get("publisher"),
                "verification_status": c.get("verification_status"),
                "confidence": c.get("confidence"),
            })

    faq = _faq(store, entity, product, model_name, market, verified)
    cta = (f"获取 {product_name} 的{model_name or ''}技术规格书、{'、'.join(entity.get('certifications', [])[:2]) or '认证'}清单"
           f"与 {market} 交付方案，请提交 RFQ（含数量、目标认证、交期与目的港）。")

    answer = "\n".join([
        f"## Direct Answer\n{direct}",
        "",
        f"## Entity Definition\n{entity_def}",
        "",
        "## Key Specifications",
        *([f"- {s}" for s in key_specs] or ["- 规格待补充（需官方 datasheet）"]),
        "",
        "## Use Cases",
        *([f"- {u}" for u in use_cases] or ["- 应用场景待补充"]),
        "",
        f"## Target Market\n{', '.join(entity.get('target_markets', [])[:6]) or '市场待声明'}"
        f"（当前查询市场：{market}）",
        "",
        "## Differentiation",
        *([f"- {d}" for d in differentiation] or ["- 暂无已核验证据支撑的差异化声明"]),
        "",
        "## Evidence",
        *([f"- {e['claim']}（Tier{e['tier']}｜{e['source_type']}｜{e['source_url']}）"
           for e in evidence_items[:6]] or ["- 暂无已核验证据"]),
        "",
        "## FAQ",
        *([f"- Q: {q['question']}\n  A: {q['answer']}" for q in faq]),
        "",
        f"## Procurement CTA\n{cta}",
    ])

    return {
        "entity_id": entity["id"],
        "language": lang,
        "market": market,
        "brand": brand,
        "product": product_name,
        "answer": answer,
        "key_facts": [c["claim"] for c in verified],
        "unverified_statements": [
            {"claim": c["claim"], "status": c.get("verification_status"),
             "note": "未通过核验，禁止作为事实结论对外发布"}
            for c in unverified
        ],
        "evidence": evidence_items,
        "faq": faq,
        "cta": cta,
        "structure": ["Direct Answer", "Entity Definition", "Key Specifications", "Use Cases",
                      "Target Market", "Differentiation", "Evidence", "FAQ", "Procurement CTA"],
        "geo_score": ranked.get("geo_score"),
        "citation_readiness": ranked.get("citation_readiness"),
        "disclaimer": ("内容为 AI 可见性优化结构，所有事实性表述均需与已核验证据一致；"
                       "不代表任何 AI 平台必然引用。"),
    }


def _faq(store, entity: dict, product: dict, model: str, market: str,
         verified: list[dict]) -> list[dict]:
    faq = []
    for item in (entity.get("faq") or [])[:6]:
        faq.append({"question": item.get("question", ""), "answer": item.get("answer", "")})
    faq.append({
        "question": f"{product.get('name', '')} 的主要型号与规格是什么？",
        "answer": (f"主力型号 {model or '见规格表'}，关键规格见官方 datasheet；"
                   f"已核验参数：{'; '.join(c['claim'] for c in verified[:2]) or '待补充'}。"),
    })
    faq.append({
        "question": f"出口 {market} 需要哪些认证？",
        "answer": (f"已声明认证：{', '.join(entity.get('certifications', [])[:5]) or '未提供'}；"
                   f"{market} 具体强制要求须以当地官方最新法规与人工复核为准。"),
    })
    faq.append({
        "question": "最小起订量、交期与贸易条款？",
        "answer": (f"MOQ：{(entity.get('capabilities') or {}).get('moq', '按项目确认')}；"
                   f"交期：{(entity.get('capabilities') or {}).get('lead_time_days', '按项目确认')} 天；"
                   f"贸易条款：{', '.join((entity.get('capabilities') or {}).get('incoterms', []) or ['按项目确认'])}。"),
    })
    faq.append({
        "question": "是否支持 OEM/ODM 定制与样品？",
        "answer": (f"定制能力：{', '.join((entity.get('capabilities') or {}).get('customization', []) or ['按项目确认'])}；"
                   f"样品政策：{(entity.get('capabilities') or {}).get('sample_policy', '按项目确认')}。"),
    })
    return [f for f in faq if f["question"] and f["answer"]]


def polish(llm, content: dict, language: str) -> dict | None:
    """可选：接入 LLM 润色。不得新增无证据事实。"""
    if not llm or not llm.available:
        return None
    system = ("你是 GEO 内容优化助手。只能使用已提供的事实与证据，不得新增任何未经核验的"
              "认证、客户、价格、产能、市场份额或排名信息。保持结构化与自然可读。")
    user = f"目标语言：{language}\n目标市场：{content['market']}\n原文：\n{content['answer']}"
    text = llm.complete(system, user)
    if not text:
        return None
    polished = dict(content)
    polished["answer"] = text
    polished["llm_polished"] = True
    return polished


def short_answer(content: dict) -> str:
    return norm_text(content["answer"].split("## Entity Definition")[0].replace("## Direct Answer", ""))
