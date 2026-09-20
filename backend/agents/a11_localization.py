"""A11 Multi-language Localization Agent - 按市场与买家角色重构语言（非机翻直译）。

无 LLM 时输出本地化结构骨架（本地术语、合规说明、采购话术），并标记需人工审校。
"""
from __future__ import annotations

from ..core.util import now_iso

LANGUAGES = {
    "en": "English", "es": "Spanish", "de": "German", "fr": "French", "ja": "Japanese",
    "ko": "Korean", "ar": "Arabic", "pt": "Portuguese", "zh": "Chinese",
    "ms": "Malay", "vi": "Vietnamese",
}

PROCUREMENT_VOCAB = {
    "en": {"rfq": "Request for Quotation", "moq": "Minimum Order Quantity",
           "lead_time": "Lead time", "warranty": "Warranty", "certification": "Certification"},
    "es": {"rfq": "Solicitud de cotización", "moq": "Cantidad mínima de pedido",
           "lead_time": "Plazo de entrega", "warranty": "Garantía", "certification": "Certificación"},
    "de": {"rfq": "Angebotsanfrage", "moq": "Mindestbestellmenge",
           "lead_time": "Lieferzeit", "warranty": "Garantie", "certification": "Zertifizierung"},
    "fr": {"rfq": "Demande de devis", "moq": "Quantité minimale de commande",
           "lead_time": "Délai de livraison", "warranty": "Garantie", "certification": "Certification"},
    "ja": {"rfq": "見積依頼", "moq": "最小発注数量", "lead_time": "納期",
           "warranty": "保証", "certification": "認証"},
    "ko": {"rfq": "견적 요청", "moq": "최소 주문 수량", "lead_time": "납기",
           "warranty": "보증", "certification": "인증"},
    "ar": {"rfq": "طلب عرض سعر", "moq": "الحد الأدنى لكمية الطلب",
           "lead_time": "مدة التسليم", "warranty": "الضمان", "certification": "الشهادة"},
    "pt": {"rfq": "Solicitação de cotação", "moq": "Quantidade mínima de pedido",
           "lead_time": "Prazo de entrega", "warranty": "Garantia", "certification": "Certificação"},
    "zh": {"rfq": "询价单", "moq": "最小起订量", "lead_time": "交期",
           "warranty": "质保", "certification": "认证"},
    "ms": {"rfq": "Permintaan sebut harga", "moq": "Kuantiti pesanan minimum",
           "lead_time": "Masa penghantaran", "warranty": "Waranti", "certification": "Pensijilan"},
    "vi": {"rfq": "Yêu cầu báo giá", "moq": "Số lượng đặt hàng tối thiểu",
           "lead_time": "Thời gian giao hàng", "warranty": "Bảo hành", "certification": "Chứng nhận"},
}

LOCAL_NOTES = {
    "de": "德国买家重视 CE/RoHS/REACH/WEEE 文件与德语技术文档，需提供可追溯合规证据。",
    "ja": "日本买家重视 PSE/MIC 与长期稳定供货，建议经本地代理并提供日语资料。",
    "ko": "韩国买家重视 KC 认证与本地服务网络，建议提供韩语规格书。",
    "ar": "海湾市场重视 ECAS/EQM（阿联酋）或 SASO/SABER（沙特），部分品类需阿拉伯语标签。",
    "es": "拉美市场重视本地代理、税务与进口流程说明，西语资料可显著提升询盘转化。",
    "pt": "巴西需关注 INMETRO/ANATEL 与税负，付款周期较长，需明确贸易条款。",
    "zh": "中文市场强调交期、产能与案例数据，需避免夸张表述。",
    "ms": "马来西亚需 SIRIM/MCMC 相关合规，本地代理渠道重要。",
    "vi": "越南价格敏感，重视交期与付款条件，建议本地代理承接售后。",
    "fr": "法国及法语区重视合规文件与本地服务，需法语技术资料。",
    "en": "英语市场重视认证、案例与总拥有成本分析，需清晰的结构化规格。",
}


def run(store, ctx: dict) -> dict:
    market_intel = ctx.get("market_intel", {})
    market = market_intel.get("market", "Global")
    requested = ctx.get("languages") or (market_intel.get("languages") or ["en"])
    languages = sorted(set([l for l in requested if l in LANGUAGES]) or ["en"])

    packages = []
    for lang in languages:
        packages.append({
            "language": lang,
            "language_name": LANGUAGES.get(lang, lang),
            "market": market,
            "local_terms": market_intel.get("local_terms", []),
            "procurement_vocabulary": PROCUREMENT_VOCAB.get(lang, PROCUREMENT_VOCAB["en"]),
            "compliance_note": LOCAL_NOTES.get(lang, "需以目标市场官方最新法规为准。"),
            "rewrite_rules": [
                "按本地采购术语重写，而非逐句机翻",
                "优先回答买家最关心的认证、交期、MOQ、总拥有成本",
                "保留结构化规格表与 FAQ，提升 AI 抽取能力",
                "合规表述须与官方最新法规一致，并标注复核日期",
            ],
            "human_review_required": lang != "en",
            "status": "scaffold" if lang != "en" else "ready",
            "generated_at": now_iso(),
        })

    result = {
        "agent": "A11 Multi-language Localization Agent",
        "supported_languages": LANGUAGES,
        "target_market": market,
        "packages": packages,
        "note": "非英语内容为本地化结构骨架（含本地术语、采购话术与合规说明），"
                "正式发布前须由母语审校，不得直接机翻发布。",
    }
    ctx["localization"] = result
    return result


def vocabulary(lang: str) -> dict:
    return PROCUREMENT_VOCAB.get(lang, PROCUREMENT_VOCAB["en"])
