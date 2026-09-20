"""A01 Intent Intelligence Agent - 识别买家真实采购意图与所处阶段。"""
from __future__ import annotations

import re

from ..core.util import clamp, norm_text, r2, tokenize

INTENT_PATTERNS = {
    "supplier_search": (r"\b(supplier|suppliers|manufacturer|vendor|factory|maker|oem|odm)\b|供应商|厂家|工厂"),
    "product_search": (r"\b(gpu|server|battery|module|inverter|cable|machine|equipment|sensor|display)\b|产品"),
    "price_inquiry": (r"\b(price|cost|quote|quotation|pricing|budget|cheap|rate|unit price)\b|价格|报价"),
    "certification": (r"\b(ce|fcc|ul|rohs|iso|ukca|kc|pse|bis|inmetro|nom|saber|sirim|certif\w*)\b|认证"),
    "oem_odm": (r"\b(oem|odm|private label|customiz\w*|custom\w*|white label)\b|定制|贴牌"),
    "technical_spec": (r"\b(spec\w*|watt|kw|tb|gb|latency|throughput|capacity|voltage|dimension|tflops)\b|参数|规格"),
    "comparison": (r"\b(vs|versus|compare|comparison|alternative|better than|or)\b|对比|比较"),
    "project_epc": (r"\b(epc|turnkey|project|tender|bid|integration|deploy\w*)\b|总包|项目|集成"),
    "compliance": (r"\b(compliance|regulat\w*|gdpr|hipaa|iso 27001|soc 2|standard)\b|合规|法规"),
    "delivery_logistics": (r"\b(deliver\w*|lead time|shipping|logistics|stock|warehouse|incoterm|fob|ddp)\b|交期|物流|发货"),
    "after_sales": (r"\b(warranty|support|maintenance|repair|rma|service)\b|售后|保修"),
    "sample_evaluation": (r"\b(sample|trial|pilot|poc|demo|test order)\b|样品|试样"),
    "partnership": (r"\b(distributor|agent|reseller|partner|channel)\b|代理|渠道"),
}

STAGE_PATTERNS = [
    ("Procurement", r"\b(rfq|purchase order|po\b|order|buy now|contract|invoice|payment term)\b|采购|下单"),
    ("Decision", r"\b(quote|quotation|price|moq|negotiat\w*|final|select|choose)\b|报价|定稿"),
    ("Evaluation", r"\b(vs|versus|compare|comparison|review|test|evaluat\w*|spec|certif\w*)\b|评估|对比"),
    ("Consideration", r"\b(supplier|manufacturer|vendor|best|top|recommend\w*|list of)\b|供应商|推荐"),
    ("Awareness", r"\b(what is|how to|guide|trend|why|introduction|overview)\b|什么是|如何|指南"),
    ("Repeat Purchase", r"\b(reorder|re-order|again|repeat|existing supplier|frequent)\b|复购|返单"),
]

INDUSTRY_PATTERNS = {
    "Data Center / AI Computing": r"\b(data ?cent(er|re)|ai|gpu|hpc|inference|training|llm)\b|数据中心|算力",
    "Telecom": r"\b(telecom|5g|base station|network|isp)\b|通信|基站",
    "Industrial Manufacturing": r"\b(industrial|factory automation|plc|cnc|manufacturing line)\b|工业|制造",
    "Renewable Energy": r"\b(solar|pv|wind|bess|energy storage|inverter|battery)\b|光伏|储能|新能源",
    "Medical Devices": r"\b(medical|hospital|clinic|patient|iso 13485)\b|医疗",
    "Automotive / EV": r"\b(automotive|ev\b|electric vehicle|bms|charging)\b|汽车|新能源车",
    "Consumer Electronics": r"\b(consumer|smartphone|wearable|audio|display)\b|消费电子",
    "Construction / Infrastructure": r"\b(construction|building|infrastructure|hvac|elevator)\b|建筑|基建",
    "Logistics / Warehousing": r"\b(logistics|warehouse|forklift|agv|fleet)\b|物流|仓储",
}

GEO_HINTS = {
    "Hong Kong": r"\b(hong ?kong|hk)\b|香港",
    "Singapore": r"\b(singapore|sg)\b|新加坡",
    "Malaysia": r"\b(malaysia|kuala lumpur|johor|penang)\b|马来西亚",
    "United Arab Emirates": r"\b(uae|dubai|abu dhabi)\b|阿联酋|迪拜",
    "Saudi Arabia": r"\b(saudi|riyadh|jeddah|dammam)\b|沙特",
    "Germany": r"\b(germany|berlin|munich|hamburg|deutschland)\b|德国",
    "United Kingdom": r"\b(uk|united kingdom|london|britain)\b|英国",
    "United States": r"\b(usa|u\.s\.|united states|america|california|texas)\b|美国",
    "Japan": r"\b(japan|tokyo|osaka)\b|日本",
    "South Korea": r"\b(korea|seoul)\b|韩国",
    "Vietnam": r"\b(vietnam|hanoi|ho chi minh)\b|越南",
    "Indonesia": r"\b(indonesia|jakarta|surabaya)\b|印尼",
    "India": r"\b(india|mumbai|delhi|bengaluru|bangalore)\b|印度",
    "Brazil": r"\b(brazil|brasil|sao paulo)\b|巴西",
    "Mexico": r"\b(mexico|monterrey|guadalajara)\b|墨西哥",
    "Australia": r"\b(australia|sydney|melbourne)\b|澳大利亚",
    "France": r"\b(france|paris)\b|法国",
    "Spain": r"\b(spain|madrid|barcelona)\b|西班牙",
    "Netherlands": r"\b(netherlands|amsterdam|rotterdam)\b|荷兰",
    "Turkey": r"\b(turkey|istanbul)\b|土耳其",
    "South Africa": r"\b(south africa|johannesburg|cape town)\b|南非",
    "Thailand": r"\b(thailand|bangkok)\b|泰国",
}

REGION_MAP = {
    "Hong Kong": "APAC", "Singapore": "APAC", "Malaysia": "APAC", "Vietnam": "APAC",
    "Indonesia": "APAC", "India": "APAC", "Japan": "APAC", "South Korea": "APAC",
    "Australia": "APAC", "Thailand": "APAC",
    "United Arab Emirates": "MEA", "Saudi Arabia": "MEA", "Turkey": "MEA",
    "South Africa": "MEA",
    "Germany": "EU", "United Kingdom": "EU", "France": "EU", "Spain": "EU",
    "Netherlands": "EU",
    "United States": "NA", "Mexico": "NA", "Brazil": "LATAM",
}


def run(store, ctx: dict) -> dict:
    query = norm_text(ctx.get("query", ""))
    low = query.lower()

    intent_type = [name for name, pat in INTENT_PATTERNS.items() if re.search(pat, low)]
    if not intent_type:
        intent_type = ["product_search"]

    buyer_stage = "Consideration"
    for stage, pat in STAGE_PATTERNS:
        if re.search(pat, low):
            buyer_stage = stage
            break

    industry = ""
    for name, pat in INDUSTRY_PATTERNS.items():
        if re.search(pat, low):
            industry = name
            break

    country = ""
    for name, pat in GEO_HINTS.items():
        if re.search(pat, low):
            country = name
            break
    if not country and ctx.get("market"):
        country = ctx["market"]

    technical = [t for t in re.findall(
        r"\b(\d+\s?(?:kw|w|tb|gb|u|mm|v|a|tflops|ms))\b|\b(ddr5|pcie|nvlink|nvme|ip\d{2}|48v|400g)\b", low)]
    commercial = [t for t in re.findall(
        r"\b(moq|fob|ddp|cif|exw|lead time|bulk|wholesale|oem|odm|warranty)\b", low)]
    compliance = [t.upper() for t in re.findall(
        r"\b(ce|fcc|ul|rohs|reach|ukca|kc|pse|bis|inmetro|nom|saber|sirim|iso\s?\d{4,5})\b", low)]

    confidence = 0.35
    confidence += 0.15 if intent_type != ["product_search"] else 0
    confidence += 0.15 if country else 0
    confidence += 0.15 if industry else 0
    confidence += 0.10 if technical or commercial or compliance else 0
    confidence += 0.10 if len(tokenize(query)) >= 6 else 0

    result = {
        "agent": "A01 Intent Intelligence Agent",
        "query": query,
        "intent_type": intent_type,
        "buyer_stage": buyer_stage,
        "industry": industry,
        "product_category": _product_category(query),
        "target_country": country,
        "target_region": REGION_MAP.get(country, ""),
        "use_case": _use_cases(low),
        "technical_requirements": sorted(set(technical)),
        "commercial_requirements": sorted(set(commercial)),
        "compliance_requirements": sorted(set(compliance)),
        "implicit_requirements": _implicit(intent_type, buyer_stage, industry),
        "confidence": r2(clamp(confidence, 0, 0.99) / 1.0),
    }
    ctx["intent"] = result
    return result


def _product_category(query: str) -> str:
    for key in ("gpu server", "ai server", "server", "battery", "inverter", "display",
                "cable", "sensor", "module"):
        if key in query.lower():
            return key
    return ""


def _use_cases(low: str) -> list[str]:
    uc = []
    mapping = {
        "AI model training": r"\b(training|llm|fine[- ]?tun\w*)\b",
        "AI inference": r"\b(inference|serving|deploy\w*)\b",
        "Data center expansion": r"\b(data ?cent(er|re)|cluster|hpc)\b",
        "Edge computing": r"\b(edge|retail|branch|factory floor)\b",
        "Rendering / VFX": r"\b(render\w*|vfx|3d)\b",
        "Backup power / UPS": r"\b(ups|backup|power)\b",
    }
    for name, pat in mapping.items():
        if re.search(pat, low):
            uc.append(name)
    return uc


def _implicit(intent_type: list[str], stage: str, industry: str) -> list[str]:
    out = []
    if "supplier_search" in intent_type:
        out += ["供应商真实性核验", "出口经验与交付记录", "售后与备件能力"]
    if "price_inquiry" in intent_type:
        out += ["阶梯报价与MOQ", "含税/含运条款", "产能与交期稳定性"]
    if "certification" in intent_type:
        out += ["目标市场强制认证", "证书编号可核验", "认证覆盖范围（型号）"]
    if "oem_odm" in intent_type:
        out += ["研发与打样能力", "知识产权与保密", "最小定制批量"]
    if stage in ("Evaluation", "Decision", "Procurement"):
        out += ["可验证客户案例", "第三方信源背书", "付款与质保条款"]
    if industry:
        out.append(f"{industry} 行业合规与标准适配")
    return sorted(set(out))
