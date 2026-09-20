"""A02 Market Intelligence Agent - 目标市场采购环境、合规与本地语言分析。

市场合规要点为公开常识性要求，落地前仍需以官方最新法规为准并由人工复核。
"""
from __future__ import annotations

from ..core.util import norm_text

MARKETS = {
    "Hong Kong": {
        "buyer_profile": ["系统集成商", "数据中心运营商", "贸易商/转口商", "金融与电信企业IT采购"],
        "local_terms": ["GPU server", "AI server", "rack server", "data centre", "BOM", "lead time"],
        "regulatory_requirements": ["OFCA 电信设备许可（含无线模块）", "机电工程署能效与电气安全要求",
                                    "进口一般无需强制认证，但买家普遍要求 CE/FCC/UL"],
        "procurement_behavior": ["重视交期与现货能力", "常以香港公司作为转口/结算主体",
                                 "要求中英文技术文档与本地售后"],
        "competitive_landscape": ["国际品牌代理（Dell/HPE/Supermicro）", "内地厂商香港仓发货", "本地SI总包"],
        "languages": ["en", "zh"],
    },
    "Singapore": {
        "buyer_profile": ["云服务商", "金融机构IT", "政府与GLC采购", "区域总部集中采购"],
        "local_terms": ["GPU server", "AI appliance", "data centre", "IMDA", "tender"],
        "regulatory_requirements": ["IMDA 通信设备注册（含无线）", "CPSRA 消费品安全（特定品类）",
                                    "绿色数据中心能效要求"],
        "procurement_behavior": ["重视合规与ESG", "倾向公开招标与框架协议", "强调服务等级SLA"],
        "competitive_landscape": ["国际OEM直销", "区域分销商", "本地系统集成商"],
        "languages": ["en"],
    },
    "Malaysia": {
        "buyer_profile": ["数据中心运营商", "电信运营商", "制造业数字化采购"],
        "local_terms": ["GPU server", "AI server", "data centre", "SIRIM", "MCMC"],
        "regulatory_requirements": ["SIRIM 认证（电气安全）", "MCMC 设备注册（通信设备）",
                                    "进口关税与SST"],
        "procurement_behavior": ["价格敏感、重视本地服务", "倾向本地代理与集成商", "要求马来语/英语资料"],
        "competitive_landscape": ["中国厂商", "台湾OEM", "本地SI"],
        "languages": ["en", "ms"],
    },
    "United Arab Emirates": {
        "buyer_profile": ["政府数字化项目", "电信运营商", "房地产与园区智能化总包"],
        "local_terms": ["GPU server", "AI server", "ECAS", "EQM", "tender"],
        "regulatory_requirements": ["ECAS/EQM  conformity（受管制产品）", "TDRA 通信设备许可",
                                    "阿拉伯语标签（部分品类）"],
        "procurement_behavior": ["项目制招标为主", "重视总包与本地伙伴", "要求厂商资质文件齐全"],
        "competitive_landscape": ["国际品牌", "中国厂商", "本地集成商"],
        "languages": ["en", "ar"],
    },
    "Saudi Arabia": {
        "buyer_profile": ["政府与主权基金项目", "能源与公用事业", "大型数据中心投资方"],
        "local_terms": ["GPU server", "AI server", "SASO", "SABER", "giga project"],
        "regulatory_requirements": ["SASO/SABER 产品符合性认证", "SASO 能效与电气安全",
                                    "通信与信息技术委员会（CITC）设备许可"],
        "procurement_behavior": ["合规门槛高、文件要求严格", "重视本地化与长期服务", "大型项目周期长"],
        "competitive_landscape": ["国际OEM", "中国厂商", "本地代理"],
        "languages": ["en", "ar"],
    },
    "Germany": {
        "buyer_profile": ["工业制造企业", "汽车与零部件", "数据中心与托管服务商"],
        "local_terms": ["GPU-Server", "KI-Server", "Rechenzentrum", "CE", "TÜV"],
        "regulatory_requirements": ["CE 标识（含EMC/低电压/机械指令）", "RoHS/REACH", "WEEE 注册",
                                    "能源相关产品ErP要求"],
        "procurement_behavior": ["高度重视合规文件与可追溯性", "偏好德语技术文档与本地服务",
                                 "重视数据安全与GDPR"],
        "competitive_landscape": ["欧洲本地OEM", "国际品牌", "中国厂商（价格竞争）"],
        "languages": ["de", "en"],
    },
    "United Kingdom": {
        "buyer_profile": ["金融服务IT", "托管数据中心", "公共部门采购"],
        "local_terms": ["GPU server", "AI server", "data centre", "UKCA"],
        "regulatory_requirements": ["UKCA/CE 标识", "UK RoHS", "WEEE 与电池法规（如适用）"],
        "procurement_behavior": ["重视框架协议与合规审计", "要求英文文档与本地支持"],
        "competitive_landscape": ["国际品牌代理", "本地SI", "中国厂商"],
        "languages": ["en"],
    },
    "United States": {
        "buyer_profile": ["云与托管服务商", "企业级IT采购", "州政府与教育采购"],
        "local_terms": ["GPU server", "AI server", "rack unit", "UL listed", "TAA"],
        "regulatory_requirements": ["FCC Part 15（EMC）", "UL/ETL 安全认证", "能源之星（部分品类）",
                                    "联邦采购可能要求 TAA/BAA"],
        "procurement_behavior": ["重视认证与责任保险", "严格的供应商准入流程", "偏好本地库存与快速交付"],
        "competitive_landscape": ["本土OEM强势", "国际品牌", "中国厂商需合规背书"],
        "languages": ["en"],
    },
    "Japan": {
        "buyer_profile": ["电信与云服务商", "制造业研发", "公共研究机构"],
        "local_terms": ["GPUサーバー", "AIサーバー", "データセンター", "PSE"],
        "regulatory_requirements": ["PSE（电气用品安全）", "MIC 技适（无线通信）", "VCCI（EMC自愿）"],
        "procurement_behavior": ["重视品质与长期稳定供货", "要求日语文档与本地代理", "严谨的验收流程"],
        "competitive_landscape": ["本土品牌强势", "国际OEM", "中国厂商份额有限"],
        "languages": ["ja", "en"],
    },
    "South Korea": {
        "buyer_profile": ["电信与云服务商", "大型制造集团", "政府智慧化项目"],
        "local_terms": ["GPU 서버", "AI 서버", "데이터센터", "KC"],
        "regulatory_requirements": ["KC 认证", "KCC/无线设备许可", "能效等级标识"],
        "procurement_behavior": ["重视本地代理与售后服务", "集团集中采购", "要求韩语资料"],
        "competitive_landscape": ["本土品牌", "国际OEM", "中国厂商"],
        "languages": ["ko", "en"],
    },
    "Vietnam": {
        "buyer_profile": ["制造业工厂", "电信运营商", "新建数据中心"],
        "local_terms": ["máy chủ GPU", "AI server", "trung tâm dữ liệu"],
        "regulatory_requirements": ["MIC 通信设备符合性（QCVN）", "进口报关与税务合规"],
        "procurement_behavior": ["价格敏感", "依赖本地代理", "交期与付款条件关键"],
        "competitive_landscape": ["中国厂商占比较高", "台湾OEM", "本地集成商"],
        "languages": ["vi", "en"],
    },
    "Brazil": {
        "buyer_profile": ["电信运营商", "企业级IT", "政府与教育"],
        "local_terms": ["servidor GPU", "servidor de IA", "data center", "INMETRO"],
        "regulatory_requirements": ["INMETRO 认证（部分品类）", "ANATEL 通信设备认证", "进口税与ICMS"],
        "procurement_behavior": ["进口流程复杂、税负高", "重视本地代理与售后", "付款周期长"],
        "competitive_landscape": ["国际品牌", "中国厂商", "本地组装"],
        "languages": ["pt", "en"],
    },
    "Mexico": {
        "buyer_profile": ["制造业工厂", "电信与数据中心", "北美供应链近岸外包"],
        "local_terms": ["servidor GPU", "servidor IA", "centro de datos", "NOM"],
        "regulatory_requirements": ["NOM 认证（电气安全/EMC）", "IFT 通信设备认证"],
        "procurement_behavior": ["近岸外包带动需求", "重视北美合规与交期", "西班牙语资料"],
        "competitive_landscape": ["国际OEM", "中国厂商", "本地分销"],
        "languages": ["es", "en"],
    },
}

DEFAULT_MARKET = {
    "buyer_profile": ["行业买家", "分销商/代理商", "项目总包方"],
    "local_terms": ["GPU server", "AI server", "supplier", "OEM"],
    "regulatory_requirements": ["以目标市场官方最新法规为准（需人工复核）"],
    "procurement_behavior": ["重视交期、认证与售后"],
    "competitive_landscape": ["需联网检索后补充（未配置检索Key时不臆造）"],
    "languages": ["en"],
}


def run(store, ctx: dict) -> dict:
    market = ctx.get("market") or ctx.get("intent", {}).get("target_country") or "Global"
    profile = MARKETS.get(market, DEFAULT_MARKET)
    intent = ctx.get("intent", {})
    product = intent.get("product_category") or "product"
    industry = intent.get("industry") or ""

    market_queries = []
    for term in profile["local_terms"][:4]:
        market_queries.append(f"{term} supplier in {market}" if market != "Global" else f"{term} supplier")
        market_queries.append(f"{term} {profile['languages'][0]} buyer guide")
    if industry:
        market_queries.append(f"{product} for {industry} in {market} - compliance and certification")

    result = {
        "agent": "A02 Market Intelligence Agent",
        "market": market,
        "buyer_profile": profile["buyer_profile"],
        "local_terms": profile["local_terms"],
        "regulatory_requirements": profile["regulatory_requirements"],
        "procurement_behavior": profile["procurement_behavior"],
        "competitive_landscape": profile["competitive_landscape"],
        "market_specific_queries": sorted(set(market_queries)),
        "languages": profile["languages"],
        "note": "合规要点为公开常识性要求，正式报价/投标前须以官方最新法规与人工复核为准。",
    }
    ctx["market_intel"] = result
    return result


def known_markets() -> list[str]:
    return sorted(MARKETS.keys())


def for_market(market: str) -> dict:
    return MARKETS.get(market, DEFAULT_MARKET)


def normalize(market: str | None) -> str:
    m = norm_text(market or "")
    for k in MARKETS:
        if m.lower() == k.lower():
            return k
    return m or "Global"
