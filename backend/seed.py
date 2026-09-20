"""演示产业数据（AI GPU 服务器 / 算力硬件产业带）。

重要声明：
- 以下企业、品牌、案例与 .example.com 信源均为演示样例（is_demo=True），
  未经真实核验，verification_status=unverified，不得作为事实结论。
- 仅 iso.org / ec.europa.eu / fcc.gov / nvidia.com 等公开权威页面为真实可核验信源，
  启用"联网核验"后由系统真实发起 HTTP 请求判定可达性。
"""
from __future__ import annotations

from .core import evidence_graph
from .core.store import Store
from .core.util import now_iso

DEMO_NOTICE = ("演示数据：企业、品牌、案例与 .example.com 信源为示例数据（is_demo=True），"
               "未经真实核验；请接入真实企业数据后重新运行。")


def seed(store: Store, force: bool = False) -> dict:
    if store.all("entities") and not force:
        return {"status": "skipped", "entities": len(store.all("entities")), "notice": DEMO_NOTICE}

    store.reset()
    sources = _sources(store)
    counts = {"sources": len(sources), "entities": 0, "claims": 0}

    for spec in _entities():
        entity = dict(spec)
        entity["is_demo"] = True
        entity["created_at"] = now_iso()
        store.add("entities", entity)
        counts["entities"] += 1
        for claim in spec.get("_claims", []):
            evidence_graph.add_claim(
                store,
                entity_id=entity["id"],
                claim=claim["claim"],
                category=claim.get("category", "general"),
                evidence_source_ids=[sources[k] for k in claim.get("sources", []) if k in sources],
                market=claim.get("market"),
                language=["en"],
                verification_status="unverified",
                confidence=0.3,
                requires_human=claim.get("category", "general") in
                ("certification_claim", "case_study", "sales_data", "market_share",
                 "ranking_claim", "competitor_comparison", "price_commitment",
                 "delivery_commitment", "company_qualification"),
            )
            counts["claims"] += 1

    store.set_dict("weights", {"query": 1.0, "market": 1.0, "content": 1.0, "evidence": 1.0,
                               "entity": 1.0, "citation": 1.0, "conversion": 1.0})
    store.set_dict("settings", {"demo_notice": DEMO_NOTICE, "seeded_at": now_iso()})
    return {"status": "seeded", **counts, "notice": DEMO_NOTICE}


def _sources(store: Store) -> dict[str, str]:
    """返回 {key: source_id}。真实权威页面 + 演示占位页面（.example.com）。"""
    real = {
        "nvidia_hgx": ("https://www.nvidia.com/en-us/data-center/hgx/", "official", 1,
                       "NVIDIA", "2025-06-01"),
        "iso9001": ("https://www.iso.org/standard/62085.html", "standards_org", 2,
                    "ISO", "2015-09-15"),
        "iso14001": ("https://www.iso.org/standard/60857.html", "standards_org", 2,
                     "ISO", "2015-09-15"),
        "ce_marking": ("https://ec.europa.eu/growth/single-market/ce-marking_en",
                       "government", 2, "European Commission", "2024-01-10"),
        "fcc_auth": ("https://www.fcc.gov/general/equipment-authorization",
                     "government", 2, "U.S. FCC", "2024-05-01"),
    }
    demo = {
        "vxf_datasheet": ("https://www.vertexforge.example.com/datasheet/vx-840g",
                          "official_product_page", 1, "VertexForge (demo)", "2026-01-15"),
        "vxf_cert": ("https://www.vertexforge.example.com/certifications",
                     "official_certificate", 1, "VertexForge (demo)", "2025-11-20"),
        "vxf_case": ("https://www.vertexforge.example.com/cases/sea-datacenter",
                     "official_case_study", 1, "VertexForge (demo)", "2025-09-05"),
        "vxf_media": ("https://www.datacenternews.example.com/vertexforge-hk-warehouse",
                      "industry_media", 3, "DataCenterNews (demo)", "2026-02-10"),
        "vxf_linkedin": ("https://www.linkedin.com/company/vertexforge-demo",
                         "social_profile", 4, "LinkedIn (demo)", "2026-03-01"),
        "sky_datasheet": ("https://www.skylattice.example.com/products/sl-8200",
                          "official_product_page", 1, "SkyLattice (demo)", "2026-02-01"),
        "sky_cert": ("https://www.skylattice.example.com/compliance",
                     "official_certificate", 1, "SkyLattice (demo)", "2025-12-01"),
        "sky_media": ("https://www.hktechpost.example.com/skylattice-oem",
                      "industry_media", 3, "HK Tech Post (demo)", "2026-01-20"),
        "axis_datasheet": ("https://www.deepaxis.example.com/edge/ax-200",
                           "official_product_page", 1, "DeepAxis (demo)", "2025-10-10"),
        "axis_blog": ("https://www.edgeaiblog.example.com/deepaxis-review",
                      "industry_blog", 5, "Edge AI Blog (demo)", "2025-08-08"),
    }
    out: dict[str, str] = {}
    for key, (url, stype, tier, publisher, date) in {**real, **demo}.items():
        src = evidence_graph.add_source(store, url=url, source_type=stype, tier=tier,
                                        publisher=publisher, published_date=date,
                                        language="en")
        src["is_demo"] = url.endswith(".example.com") or "example.com" in url
        store.update("sources", src["id"], {"is_demo": src["is_demo"]})
        out[key] = src["id"]
    return out


def _entities() -> list[dict]:
    return [_vertexforge(), _skylattice(), _deepaxis()]


def _vertexforge() -> dict:
    return {
        "id": "ENT-VXF-001",
        "brand": "VertexForge",
        "company": "Shenzhen VertexForge Intelligent Computing Co., Ltd.",
        "country": "China",
        "city": "Shenzhen",
        "website": "https://www.vertexforge.example.com",
        "same_as": ["https://www.linkedin.com/company/vertexforge-demo"],
        "positioning": "AI GPU 服务器与液冷算力集群制造商，香港仓现货交付",
        "industries": ["Data Center / AI Computing", "Telecom", "Cloud Service"],
        "applications": ["AI model training", "AI inference", "HPC cluster",
                         "Rendering / VFX", "Edge computing"],
        "target_markets": ["Hong Kong", "Singapore", "Malaysia", "United Arab Emirates",
                           "Germany", "Japan"],
        "certifications": ["CE", "FCC", "RoHS", "ISO9001", "ISO14001"],
        "buyer_segments": ["Data center operator", "System integrator",
                           "Cloud service provider", "Enterprise IT"],
        "decision_makers": ["CTO", "IT Procurement Manager", "Data Center Director"],
        "compliance": ["CE", "FCC", "RoHS", "WEEE"],
        "capabilities": {
            "moq": "1 unit", "lead_time_days": 21, "capacity": "3000 units/year",
            "incoterms": ["FOB Shenzhen", "DDP"], "price_hint": "on request",
            "customization": ["OEM", "ODM", "BMC/BIOS customization", "Liquid cooling option"],
            "sample_policy": "Paid sample, refundable on bulk order",
            "after_sales": ["3-year warranty", "24/7 remote support", "HK spare parts stock"],
            "local_service": True,
        },
        "supply_chain": {
            "raw_material": ["NVIDIA GPU module", "Server mainboard", "Redundant PSU"],
            "distributor": ["Hong Kong warehouse", "Singapore partner"],
            "importer": ["Buyer-side importer"],
        },
        "products": [{
            "name": "VertexForge AI GPU Server",
            "category": "AI computing hardware",
            "description": "4U/8U 高密度 GPU 服务器，支持风冷与冷板式液冷，面向大模型训练与推理集群。",
            "models": [
                {"model": "VX-840G", "specs": {
                    "GPU": "8x NVIDIA HGX H100 80GB", "Form factor": "4U rack",
                    "CPU": "2x Intel Xeon Scalable", "Memory": "32x DDR5-4800 64GB",
                    "Storage": "8x NVMe U.2 3.84TB", "Network": "2x 400GbE + 8x 200GbE",
                    "Power": "6x 3000W redundant PSU", "Cooling": "Air / cold-plate liquid"}},
                {"model": "VX-420E", "specs": {
                    "GPU": "4x NVIDIA L40S", "Form factor": "2U rack",
                    "CPU": "2x Intel Xeon Silver", "Memory": "16x DDR5-4800 32GB",
                    "Storage": "4x NVMe U.2 1.92TB", "Network": "2x 100GbE",
                    "Power": "4x 2000W redundant PSU", "Cooling": "Air"}},
            ],
        }],
        "case_studies": [{
            "title": "东南亚数据中心 120 台 GPU 服务器集群交付",
            "client": "SEA Data Center Operator (demo)",
            "result": "分两批 21 天内交付，PUE 优化至 1.25（数据为演示样例，需人工核验）",
        }],
        "third_party_sources": [
            "https://www.datacenternews.example.com/vertexforge-hk-warehouse",
            "https://www.linkedin.com/company/vertexforge-demo",
        ],
        "competitors": ["NorthPeak Systems", "SkyLattice", "DeepAxis"],
        "languages": ["en", "zh"],
        "schema_ready": True,
        "direct_answer": "VertexForge 是深圳 AI GPU 服务器制造商，主力型号 VX-840G。",
        "faq": [
            {"question": "VX-840G 支持哪些 GPU 配置？",
             "answer": "标配 8x NVIDIA HGX H100 80GB，可按项目评估其他 GPU 配置。"},
            {"question": "是否支持液冷？",
             "answer": "提供风冷与冷板式液冷两种方案，需按机房条件评估。"},
        ],
        "content_assets": [
            {"type": "product_page", "title": "VX-840G AI GPU Server"},
            {"type": "buyer_guide", "title": "AI Server Buyer Guide 2026"},
            {"type": "certification_guide", "title": "CE/FCC/RoHS Compliance Guide"},
            {"type": "case_study", "title": "SEA Data Center Cluster Delivery"},
        ],
        "_claims": [
            {"claim": "VX-840G 采用 8x NVIDIA HGX H100 80GB GPU 架构",
             "category": "technology", "sources": ["nvidia_hgx", "vxf_datasheet"]},
            {"claim": "产品具备 CE 合规声明（EMC/LVD）",
             "category": "certification_claim", "sources": ["vxf_cert", "ce_marking"]},
            {"claim": "产品具备 FCC 合规声明（Part 15）",
             "category": "certification_claim", "sources": ["vxf_cert", "fcc_auth"]},
            {"claim": "通过 ISO 9001:2015 质量管理体系认证",
             "category": "company_qualification", "sources": ["iso9001", "vxf_cert"]},
            {"claim": "通过 ISO 14001:2015 环境管理体系认证",
             "category": "company_qualification", "sources": ["iso14001"]},
            {"claim": "标准交期 21 天，香港仓备有现货",
             "category": "delivery_commitment", "sources": ["vxf_datasheet", "vxf_media"]},
            {"claim": "年产能 3000 台 GPU 服务器",
             "category": "capability", "sources": ["vxf_datasheet"]},
            {"claim": "支持 OEM/ODM 与 BMC/BIOS 定制",
             "category": "capability", "sources": ["vxf_datasheet"]},
            {"claim": "为东南亚数据中心交付 120 台 GPU 服务器集群",
             "category": "case_study", "sources": ["vxf_case"]},
            {"claim": "提供 3 年质保与香港备件库",
             "category": "capability", "sources": ["vxf_datasheet", "vxf_linkedin"]},
            {"claim": "同时提供风冷与冷板式液冷方案",
             "category": "differentiation", "sources": ["vxf_datasheet"]},
            {"claim": "价格为按项目报价（on request）",
             "category": "price_commitment", "sources": ["vxf_datasheet"]},
        ],
    }


def _skylattice() -> dict:
    return {
        "id": "ENT-SKY-002",
        "brand": "SkyLattice",
        "company": "SkyLattice Computing (HK) Limited",
        "country": "Hong Kong",
        "city": "Hong Kong",
        "website": "https://www.skylattice.example.com",
        "same_as": [],
        "positioning": "香港 GPU 服务器 OEM/ODM 供应商，主打快速交付与转口贸易",
        "industries": ["Data Center / AI Computing", "Telecom"],
        "applications": ["AI inference", "Data center expansion", "Edge computing"],
        "target_markets": ["Hong Kong", "Singapore", "Malaysia", "Japan", "Vietnam"],
        "certifications": ["CE", "FCC", "RoHS"],
        "buyer_segments": ["System integrator", "Trading company", "Enterprise IT"],
        "decision_makers": ["Procurement Director", "IT Manager"],
        "compliance": ["CE", "FCC", "RoHS"],
        "capabilities": {
            "moq": "5 units", "lead_time_days": 14, "capacity": "1200 units/year",
            "incoterms": ["FOB Hong Kong", "EXW"], "price_hint": "on request",
            "customization": ["OEM", "ODM"], "sample_policy": "Sample available",
            "after_sales": ["2-year warranty", "Local HK support"],
            "local_service": True,
        },
        "supply_chain": {"raw_material": ["GPU module", "Server chassis"],
                         "distributor": ["Direct"], "importer": ["Buyer-side"]},
        "products": [{
            "name": "SkyLattice GPU Server",
            "category": "AI computing hardware",
            "description": "面向推理与中等规模训练集群的 GPU 服务器，支持 OEM/ODM 定制。",
            "models": [
                {"model": "SL-8200", "specs": {
                    "GPU": "8x NVIDIA HGX H100 80GB", "Form factor": "6U rack",
                    "CPU": "2x AMD EPYC Genoa", "Memory": "24x DDR5-4800 64GB",
                    "Storage": "6x NVMe U.2 3.84TB", "Network": "2x 200GbE",
                    "Power": "6x 3000W redundant PSU", "Cooling": "Air"}},
            ],
        }],
        "case_studies": [{
            "title": "香港金融机构推理集群扩容项目",
            "client": "HK Financial Institution (demo)",
            "result": "14 天交付 32 台（演示样例，需人工核验）",
        }],
        "third_party_sources": ["https://www.hktechpost.example.com/skylattice-oem"],
        "competitors": ["VertexForge", "NorthPeak Systems"],
        "languages": ["en", "zh"],
        "schema_ready": True,
        "direct_answer": "SkyLattice 是香港 GPU 服务器 OEM/ODM 供应商，主力型号 SL-8200。",
        "faq": [
            {"question": "SL-8200 的交期是多久？",
             "answer": "标称 14 天（香港仓），实际以订单确认为准。"},
        ],
        "content_assets": [
            {"type": "product_page", "title": "SL-8200 GPU Server"},
            {"type": "oem_odm_page", "title": "OEM/ODM Capability"},
        ],
        "_claims": [
            {"claim": "SL-8200 采用 8x NVIDIA HGX H100 80GB GPU 架构",
             "category": "technology", "sources": ["nvidia_hgx", "sky_datasheet"]},
            {"claim": "具备 CE / FCC / RoHS 合规声明",
             "category": "certification_claim", "sources": ["sky_cert", "ce_marking", "fcc_auth"]},
            {"claim": "香港本地仓 14 天快速交付",
             "category": "delivery_commitment", "sources": ["sky_datasheet", "sky_media"]},
            {"claim": "提供 OEM/ODM 定制服务",
             "category": "capability", "sources": ["sky_datasheet"]},
            {"claim": "为香港金融机构交付 32 台推理服务器",
             "category": "case_study", "sources": ["sky_cert"]},
            {"claim": "年产能 1200 台", "category": "capability", "sources": ["sky_datasheet"]},
        ],
    }


def _deepaxis() -> dict:
    return {
        "id": "ENT-AXS-003",
        "brand": "DeepAxis",
        "company": "Guangzhou DeepAxis Electronics Co., Ltd.",
        "country": "China",
        "city": "Guangzhou",
        "website": "https://www.deepaxis.example.com",
        "same_as": [],
        "positioning": "边缘 AI 推理一体机与小型算力节点供应商",
        "industries": ["Industrial Manufacturing", "Retail", "Logistics / Warehousing"],
        "applications": ["Edge computing", "Machine vision", "Retail analytics"],
        "target_markets": ["Vietnam", "Malaysia", "Indonesia", "Brazil", "Mexico"],
        "certifications": ["CE", "RoHS"],
        "buyer_segments": ["Factory automation integrator", "Retail chain", "Distributor"],
        "decision_makers": ["Plant Manager", "Automation Engineer"],
        "compliance": ["CE", "RoHS"],
        "capabilities": {
            "moq": "10 units", "lead_time_days": 30, "capacity": "8000 units/year",
            "incoterms": ["FOB Guangzhou"], "price_hint": "on request",
            "customization": ["OEM"], "sample_policy": "Sample available",
            "after_sales": ["1-year warranty", "Remote support"],
            "local_service": False,
        },
        "supply_chain": {"raw_material": ["Edge SoC module", "Industrial chassis"],
                         "distributor": ["Local agent"], "importer": ["Buyer-side"]},
        "products": [{
            "name": "DeepAxis Edge AI Appliance",
            "category": "Edge AI hardware",
            "description": "面向工厂与零售场景的边缘 AI 推理一体机。",
            "models": [
                {"model": "AX-200", "specs": {
                    "NPU": "4x Edge AI accelerator", "Form factor": "1U short-depth",
                    "CPU": "Intel Core i7", "Memory": "64GB DDR5",
                    "Storage": "2x NVMe 1TB", "Network": "2x 10GbE",
                    "Power": "2x 800W PSU", "Cooling": "Fanless option"}},
            ],
        }],
        "case_studies": [],
        "third_party_sources": ["https://www.edgeaiblog.example.com/deepaxis-review"],
        "competitors": ["VertexForge", "NorthPeak Systems"],
        "languages": ["en"],
        "schema_ready": False,
        "direct_answer": "DeepAxis 是广州边缘 AI 推理设备供应商，主力型号 AX-200。",
        "faq": [],
        "content_assets": [{"type": "product_page", "title": "AX-200 Edge Appliance"}],
        "_claims": [
            {"claim": "AX-200 为 1U 短深度边缘 AI 推理一体机",
             "category": "technology", "sources": ["axis_datasheet"]},
            {"claim": "具备 CE / RoHS 合规声明",
             "category": "certification_claim", "sources": ["axis_datasheet", "ce_marking"]},
            {"claim": "月产能可按项目扩展至 8000 台/年",
             "category": "capability", "sources": ["axis_datasheet"]},
            {"claim": "第三方评测提及 AX-200 部署案例",
             "category": "differentiation", "sources": ["axis_blog"]},
        ],
    }
