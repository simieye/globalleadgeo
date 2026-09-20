"""全球鹰 GEO 全球AI推荐系统 - OpenClaw Orchestrator 服务入口."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agents import (a10_schema, a12_visibility, a13_lead, a14_analytics,
                     a15_feedback, a02_market)
from .core import approval as approval_core
from .core import audit, evidence_graph, settings as settings_core
from .core.store import Store
from .core.util import now_iso, uid
from .orchestrator import Orchestrator, PIPELINE
from .plugins import redditgrow
from .seed import seed

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"
# 数据目录：macOS .app 场景下由启动器传入 GEO_DATA_DIR（写到 ~/Library/Application Support），
# 避免向只读的应用包内写入数据。
DATA_DIR = Path(os.getenv("GEO_DATA_DIR") or (ROOT / "backend" / "data")).expanduser()

store = Store(DATA_DIR)
orchestrator = Orchestrator(store)

app = FastAPI(
    title="全球鹰 GEO 全球AI推荐系统",
    description="Global Eagle GEO Recommendation & AI Visibility System · OpenClaw Agent Cluster",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


# ---------------- settings helpers ----------------
def _settings() -> dict:
    """Shared Context 中的系统设置（settings.json）。"""
    return store.data.get("settings", {})


def _llm_state() -> dict:
    return settings_core.llm_state(_settings())


def _write_llm(state: dict) -> None:
    cur = settings_core.llm_settings(_settings())
    cur.update(state)
    store.set_dict("settings", {settings_core.LLM_KEY: cur})


def _write_local(client_id: str, cfg: dict) -> None:
    cur = settings_core.local_settings(_settings())
    cur[client_id] = settings_core.clean_local_cfg(cfg)
    store.set_dict("settings", {settings_core.LOCAL_KEY: cur})


def _local_client(client_id: str) -> dict:
    return settings_core.local_state(_settings())[client_id]


# ---------------- request models ----------------
class RunRequest(BaseModel):
    query: str
    market: str | None = None
    language: str = "en"
    languages: list[str] | None = None
    engines: list[str] | None = None
    entity_ids: list[str] | None = None
    enable_web_verify: bool = False


class ClaimIn(BaseModel):
    entity_id: str
    claim: str
    category: str = "general"
    evidence_source_ids: list[str] = Field(default_factory=list)
    market: list[str] | None = None


class SourceIn(BaseModel):
    url: str
    source_type: str = "official"
    tier: int = 1
    publisher: str = ""
    published_date: str | None = None


class DecisionIn(BaseModel):
    decision: str
    reviewer: str
    note: str = ""


class LeadIn(BaseModel):
    entity_id: str | None = None
    query: str | None = None
    market: str | None = None
    target_market: str | None = None
    product: str | None = None
    intent: list[str] | str | None = None
    buyer_stage: str = "Consideration"
    ai_platform: str | None = None
    landing_page: str | None = None
    campaign: str | None = None
    conversation: list[str] = Field(default_factory=list)
    company_name: str | None = None
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    country: str | None = None
    quantity: str | None = None
    certification: list[str] = Field(default_factory=list)
    timeline: str | None = None
    incoterm: str | None = None
    language: str = "en"
    lead_source: str = "GEO"


class FeedbackIn(BaseModel):
    signal: str
    entity_id: str | None = None
    query: str | None = None
    market: str | None = None
    value: float | None = None
    ai_platform: str | None = None
    note: str | None = None


class ProbeIn(BaseModel):
    queries: list[str]
    engines: list[str] | None = None
    market: str | None = None
    language: str = "en"
    entity_ids: list[str] | None = None


# ---------------- system ----------------
@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "system": "全球鹰 GEO 全球AI推荐系统",
        "english_name": "Global Eagle GEO Recommendation & AI Visibility System",
        "version": "1.0.0",
        "agents": 15,
        "pipeline_steps": len(PIPELINE),
        "counts": {
            "entities": len(store.all("entities")),
            "sources": len(store.all("sources")),
            "claims": len(store.all("claims")),
            "runs": len(store.all("runs")),
            "leads": len(store.all("leads")),
            "approvals_pending": len([a for a in store.all("approvals")
                                      if a.get("status") == "pending"]),
        },
        "connectors": {
            "web_search": bool(os.getenv("TAVILY_API_KEY") or os.getenv("SERPER_API_KEY")),
            "ai_engine_probe": bool(os.getenv("OPENAI_API_KEY")
                                    or os.getenv("PERPLEXITY_API_KEY")
                                    or os.getenv("ANTHROPIC_API_KEY")),
            "llm_polish": bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
                               or _llm_state().get("active")),
            "redditgrow": _redditgrow_status().get("enabled", False),
            "local_cli_ready": len([c for c in settings_core.local_state(_settings()).values()
                                    if c["ready"]]),
            "local_cli_total": len(settings_core.LOCAL_CLIENTS),
        },
        "demo_notice": store.data.get("settings", {}).get("demo_notice"),
    }


@app.post("/api/seed")
def seed_data(force: bool = False):
    result = seed(store, force=force)
    audit.log(store, "system.seed", "admin", result, "medium")
    return result


# ---------------- shared context ----------------
@app.get("/api/context")
def shared_context() -> dict[str, Any]:
    entities = store.all("entities")
    return {
        "company": store.data.get("company", {}),
        "brand": {},
        "entities": entities,
        "products": [p.get("name") for e in entities for p in e.get("products", [])],
        "product_models": [m.get("model") for e in entities for p in e.get("products", [])
                           for m in p.get("models", [])],
        "industries": sorted({i for e in entities for i in e.get("industries", [])}),
        "target_markets": sorted({m for e in entities for m in e.get("target_markets", [])}),
        "certifications": sorted({c for e in entities for c in e.get("certifications", [])}),
        "buyer_segments": sorted({b for e in entities for b in e.get("buyer_segments", [])}),
        "case_studies": [c.get("title") for e in entities for c in e.get("case_studies", [])],
        "third_party_sources": sorted({s for e in entities for s in e.get("third_party_sources", [])}),
        "approved_claims": [c["claim"] for c in store.all("claims")
                            if c.get("human_approval") == "approved"],
        "restricted_claims": [c["claim"] for c in store.all("claims")
                              if c.get("verification_status") != "verified"],
        "geo_history": [{"id": r["id"], "query": r["query"], "created_at": r["created_at"],
                         "score": r.get("output", {}).get("geo_score", {}).get("overall")}
                        for r in store.all("runs")[-10:]],
        "weights": store.data.get("weights", {}),
    }


@app.get("/api/markets")
def markets():
    return {"markets": a02_market.known_markets()}


# ---------------- entities ----------------
@app.get("/api/entities")
def list_entities():
    return {"entities": store.all("entities")}


@app.get("/api/entities/{entity_id}")
def get_entity(entity_id: str):
    entity = store.get("entities", entity_id)
    if not entity:
        raise HTTPException(404, "entity not found")
    return {"entity": entity, "claims": store.claims_for_entity(entity_id)}


@app.post("/api/entities")
def create_entity(entity: dict):
    entity.setdefault("id", uid("ENT"))
    entity.setdefault("created_at", now_iso())
    entity.setdefault("is_demo", False)
    store.add("entities", entity)
    audit.log(store, "entity.create", "api", {"id": entity["id"]}, "medium")
    return entity


@app.get("/api/graph")
def graph():
    from .core import entity_graph
    return {
        "entity_graph": entity_graph.build(store),
        "evidence_graph": evidence_graph.build_graph(store),
    }


@app.get("/api/schema/{entity_id}")
def schema_for(entity_id: str):
    entity = store.get("entities", entity_id)
    if not entity:
        raise HTTPException(404, "entity not found")
    ctx = {"ranked_entities": [{"entity_id": entity_id}],
           "ai_answer_ready_content": []}
    return a10_schema.run(store, ctx)


# ---------------- pipeline ----------------
@app.post("/api/pipeline/run")
def run_pipeline(req: RunRequest):
    if not req.query.strip():
        raise HTTPException(400, "query is required")
    audit.log(store, "api.pipeline.run", "user", {"query": req.query}, "low")
    return orchestrator.run(req.model_dump())


@app.get("/api/runs")
def list_runs():
    runs = sorted(store.all("runs"), key=lambda r: r.get("created_at", ""), reverse=True)
    return {"runs": [{"id": r["id"], "query": r["query"], "created_at": r["created_at"],
                      "market": r.get("market"), "duration_ms": r.get("duration_ms"),
                      "score": r.get("output", {}).get("geo_score", {}).get("overall")}
                     for r in runs[:50]]}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    run = store.get("runs", run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return run


# ---------------- evidence ----------------
@app.get("/api/sources")
def list_sources():
    return {"sources": store.all("sources")}


@app.post("/api/sources")
def create_source(src: SourceIn):
    created = evidence_graph.add_source(store, **src.model_dump())
    audit.log(store, "source.create", "api", {"url": src.url}, "low")
    return created


@app.get("/api/claims")
def list_claims(entity_id: str | None = None):
    claims = store.claims_for_entity(entity_id) if entity_id else store.all("claims")
    return {"claims": claims}


@app.post("/api/claims")
def create_claim(claim: ClaimIn):
    created = evidence_graph.add_claim(store, **claim.model_dump())
    audit.log(store, "claim.create", "api", {"id": created["id"]}, "medium")
    return created


@app.post("/api/claims/verify")
def verify_claims(entity_id: str | None = None, enable_web: bool = False):
    from .core.web_research import verify_url
    claims = store.claims_for_entity(entity_id) if entity_id else store.all("claims")
    for c in claims:
        evidence_graph.verify_claim(store, c, enable_web=enable_web,
                                    verify_fn=verify_url if enable_web else None)
    conflicts = evidence_graph.detect_conflicts(store, entity_id)
    audit.log(store, "claim.verify", "api",
              {"count": len(claims), "enable_web": enable_web}, "medium")
    return {
        "verified": len([c for c in store.all("claims")
                         if c.get("verification_status") == "verified"]),
        "unverified": len([c for c in store.all("claims")
                           if c.get("verification_status") == "unverified"]),
        "conflicts": conflicts,
    }


# ---------------- approvals ----------------
@app.get("/api/approvals")
def list_approvals(status: str | None = None):
    return {"approvals": approval_core.queue(store, status),
            "required_categories": sorted(approval_core.REQUIRED_CATEGORIES)}


@app.post("/api/approvals/{approval_id}/decision")
def decide(approval_id: str, body: DecisionIn):
    result = approval_core.decide(store, approval_id, body.decision, body.reviewer, body.note)
    if not result:
        raise HTTPException(404, "approval not found")
    audit.log(store, "approval.decision", body.reviewer,
              {"id": approval_id, "decision": body.decision}, "high")
    return result


# ---------------- monitoring ----------------
@app.post("/api/monitoring/probe")
def probe(body: ProbeIn):
    result = a12_visibility.probe(store, body.model_dump())
    audit.log(store, "monitoring.probe", "api",
              {"queries": len(body.queries)}, "low")
    return result


@app.get("/api/monitoring/dashboard")
def monitoring_dashboard():
    return a12_visibility.dashboard(store)


# ---------------- leads / crm ----------------
@app.get("/api/leads")
def list_leads(status: str | None = None):
    return {"leads": a13_lead.pipeline(store, status), "rfqs": store.all("rfqs")}


@app.post("/api/leads")
def create_lead(body: LeadIn):
    lead = a13_lead.create_lead(store, body.model_dump())
    audit.log(store, "lead.create", "api", {"id": lead["id"], "score": lead["qualification_score"]},
              "medium")
    return lead


@app.post("/api/leads/{lead_id}/rfq")
def create_rfq(lead_id: str, items: list[dict] | None = None):
    rfq = a13_lead.to_rfq(store, lead_id, items)
    if not rfq:
        raise HTTPException(404, "lead not found")
    audit.log(store, "rfq.create", "api", {"id": rfq["id"]}, "medium")
    return rfq


# ---------------- analytics / feedback ----------------
@app.get("/api/analytics")
def analytics():
    return a14_analytics.metrics(store)


@app.post("/api/feedback")
def feedback(body: FeedbackIn):
    event = a15_feedback.record(store, body.model_dump())
    weights = a15_feedback.tune(store, store.data.get("weights"))
    store.set_dict("weights", weights)
    audit.log(store, "feedback.record", "api",
              {"signal": body.signal, "weights": weights}, "medium")
    return {"event": event, "weights": weights, "loop": a15_feedback.learning_loop(store)}


@app.get("/api/feedback/loop")
def feedback_loop():
    return a15_feedback.learning_loop(store)


@app.get("/api/audit")
def audit_log(limit: int = 200, run_id: str | None = None):
    items = audit.for_run(store, run_id) if run_id else audit.tail(store, limit)
    return {"audit": items, "summary": audit.summary(store)}


# ---------------- plugins: RedditGrow ----------------
PLUGIN_KEY = "redditgrow"


def _plugin_settings() -> dict:
    return store.data.get("settings", {}).get(PLUGIN_KEY, {})


def _redditgrow_status() -> dict:
    return redditgrow.status(_plugin_settings())


class RedditGrowConfigIn(BaseModel):
    api_key: str | None = None
    mcp_url: str | None = None
    webhook_secret: str | None = None


class RedditGrowSyncIn(BaseModel):
    min_score: float = 7.0
    limit: int = 10
    project_id: str | None = None
    entity_id: str | None = None


class RedditGrowToolIn(BaseModel):
    keyword: str | None = None
    project_id: str | None = None
    mention_type: str | None = None
    opportunity_id: str | None = None
    tone: str = "professional"
    length: str = "medium"


@app.get("/api/plugins")
def list_plugins():
    return {"plugins": [_redditgrow_status()]}


@app.get("/api/plugins/redditgrow/status")
def redditgrow_status():
    return _redditgrow_status()


@app.post("/api/plugins/redditgrow/config")
def redditgrow_config(body: RedditGrowConfigIn):
    patch = {k: v for k, v in body.model_dump().items() if v}
    settings = dict(_plugin_settings())
    settings.update(patch)
    store.set_dict("settings", {PLUGIN_KEY: settings})
    redditgrow.reset_session()
    audit.log(store, "plugin.redditgrow.config", "api",
              {"updated_fields": sorted(patch.keys())}, "medium")
    return _redditgrow_status()


@app.post("/api/plugins/redditgrow/opportunities")
def redditgrow_opportunities(body: RedditGrowSyncIn):
    result = redditgrow.find_opportunities(min_score=body.min_score, limit=body.limit,
                                           project_id=body.project_id, settings=_plugin_settings())
    return {"result": result, "opportunities": redditgrow.extract_opportunities(result)}


@app.post("/api/plugins/redditgrow/sync")
def redditgrow_sync(body: RedditGrowSyncIn):
    """拉取 RedditGrow 机会并以 lead_source='RedditGrow' 写入询盘管道。"""
    result = redditgrow.find_opportunities(min_score=body.min_score, limit=body.limit,
                                           project_id=body.project_id, settings=_plugin_settings())
    if result.get("mode") != "live":
        return {"mode": result.get("mode"), "note": result.get("note") or result.get("error"),
                "imported": 0, "leads": []}
    opportunities = redditgrow.extract_opportunities(result)
    created = []
    for op in opportunities:
        payload = redditgrow.normalize_opportunity(op)
        payload["entity_id"] = body.entity_id
        if not payload.get("query"):
            continue
        created.append(a13_lead.create_lead(store, payload))
    audit.log(store, "plugin.redditgrow.sync", "api",
              {"fetched": len(opportunities), "imported": len(created),
               "min_score": body.min_score}, "medium")
    return {"mode": "live", "fetched": len(opportunities), "imported": len(created),
            "leads": created,
            "note": "导入线索默认 verification_status=unverified，需人工核验后方可作为结论。"}


@app.post("/api/plugins/redditgrow/ai-visibility")
def redditgrow_ai_visibility(body: RedditGrowToolIn):
    return redditgrow.check_ai_visibility(body.project_id, _plugin_settings())


@app.post("/api/plugins/redditgrow/mentions")
def redditgrow_mentions(body: RedditGrowToolIn):
    return redditgrow.list_brand_mentions(body.mention_type, settings=_plugin_settings())


@app.post("/api/plugins/redditgrow/serp")
def redditgrow_serp(body: RedditGrowToolIn):
    if not body.keyword:
        raise HTTPException(status_code=400, detail="keyword 必填")
    return redditgrow.check_serp(body.keyword, _plugin_settings())


@app.post("/api/plugins/redditgrow/reply-draft")
def redditgrow_reply_draft(body: RedditGrowToolIn):
    """生成 Reddit 回复草稿：只落草稿，发布必须人工审核。"""
    if not body.opportunity_id:
        raise HTTPException(status_code=400, detail="opportunity_id 必填")
    result = redditgrow.generate_reply_draft(body.opportunity_id, body.tone, body.length,
                                             _plugin_settings())
    audit.log(store, "plugin.redditgrow.reply_draft", "api",
              {"opportunity_id": body.opportunity_id, "mode": result.get("mode")}, "low")
    return result


@app.post("/api/plugins/redditgrow/webhook")
async def redditgrow_webhook(request: Request):
    """接收 RedditGrow Webhook（HMAC-SHA256 签名头 X-RedditGrow-Signature）。"""
    raw = await request.body()
    signature = request.headers.get("X-RedditGrow-Signature")
    secret = redditgrow.config(_plugin_settings()).get("webhook_secret", "")
    if not redditgrow.verify_webhook(raw, signature, secret):
        audit.log(store, "plugin.redditgrow.webhook.rejected", "redditgrow",
                  {"reason": "signature_invalid"}, "high")
        raise HTTPException(status_code=401, detail="webhook signature invalid")
    try:
        event = json.loads(raw.decode("utf-8", "ignore"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid json") from None
    payload = redditgrow.ingest_webhook_event(event)
    lead = None
    if payload and payload.get("query"):
        lead = a13_lead.create_lead(store, payload)
    audit.log(store, "plugin.redditgrow.webhook", "redditgrow",
              {"event": event.get("event") or event.get("type"),
               "lead_id": lead["id"] if lead else None}, "low")
    return {"received": True, "lead": lead}


# ---------------- system settings ----------------
class LLMProviderIn(BaseModel):
    id: str | None = None
    name: str | None = None
    type: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    env_var: str | None = None
    enabled: bool | None = None


class LLMDefaultIn(BaseModel):
    provider_id: str


class LocalClientIn(BaseModel):
    enabled: bool | None = None
    command: str | None = None
    probe_args: str | None = None
    workdir: str | None = None
    timeout: int | None = None
    env: dict[str, str] | None = None


class LocalRunIn(BaseModel):
    args: str | None = None
    timeout: int | None = None


@app.get("/api/settings")
def get_settings():
    """系统设置总览：大模型提供商 + 本地 CLI 连接器（Key 只返回掩码）。"""
    return {"llm": _llm_state(), "local": settings_core.local_state(_settings())}


@app.post("/api/settings/llm/providers")
def upsert_llm_provider(body: LLMProviderIn):
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(400, "没有可更新的字段")
    cur = settings_core.llm_settings(_settings())
    providers = cur["providers"]
    if not payload.get("id") and not payload.get("name") and not payload.get("base_url"):
        raise HTTPException(400, "新增提供商需提供 name 或 base_url")
    if payload.get("enabled") is None and not any(
            p.get("id") == payload.get("id") for p in providers):
        payload["enabled"] = True  # 新增默认启用，避免「配了却没生效」
    provider = settings_core.upsert_provider(providers, payload)
    if not cur.get("default"):
        cur["default"] = provider["id"]
    _write_llm({"providers": providers, "default": cur.get("default")})
    audit.log(store, "settings.llm.upsert", "api",
              {"id": provider["id"], "type": provider.get("type"),
               "fields": sorted(k for k in payload if k != "api_key")}, "medium")
    return _llm_state()


@app.delete("/api/settings/llm/providers/{provider_id}")
def delete_llm_provider(provider_id: str):
    if provider_id in settings_core.BUILTIN_IDS:
        raise HTTPException(400, "内置提供商不可删除，可将其停用")
    cur = settings_core.llm_settings(_settings())
    providers = cur["providers"]
    kept = [p for p in providers if p.get("id") != provider_id]
    if len(kept) == len(providers):
        raise HTTPException(404, "provider not found")
    default = None if cur.get("default") == provider_id else cur.get("default")
    _write_llm({"providers": kept, "default": default})
    audit.log(store, "settings.llm.delete", "api", {"id": provider_id}, "medium")
    return _llm_state()


@app.post("/api/settings/llm/default")
def set_default_provider(body: LLMDefaultIn):
    cur = settings_core.llm_settings(_settings())
    if body.provider_id not in settings_core.provider_ids(_settings()):
        raise HTTPException(404, "provider not found")
    _write_llm({"providers": cur["providers"], "default": body.provider_id})
    audit.log(store, "settings.llm.default", "api", {"id": body.provider_id}, "low")
    return _llm_state()


@app.post("/api/settings/llm/test")
def test_llm_provider(body: LLMProviderIn):
    """连通性测试：可测试已保存配置（传 id），也可先测未保存的配置。"""
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    cfg = dict(payload)
    if cfg.get("id"):
        stored = settings_core.provider_by_id(cfg["id"], _settings())
        if stored:
            cfg = {**stored, **payload}
    result = settings_core.test_provider(cfg)
    audit.log(store, "settings.llm.test", "api",
              {"id": cfg.get("id"), "ok": result.get("ok")}, "low")
    return result


@app.post("/api/settings/local/{client_id}")
def save_local_client(client_id: str, body: LocalClientIn):
    if client_id not in settings_core.LOCAL_CLIENTS:
        raise HTTPException(404, f"未知本地 CLI：{client_id}")
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    # 以「内置默认 + 已存配置」为底，避免只提交 enabled 时把 command 覆盖为空
    cfg = {**settings_core.client_cfg(client_id, _settings()), **patch}
    _write_local(client_id, cfg)
    audit.log(store, "settings.local.save", "api",
              {"client": client_id, "fields": sorted(patch.keys())}, "medium")
    return {"client": _local_client(client_id)}


@app.post("/api/settings/local/{client_id}/probe")
def probe_local_client(client_id: str):
    """探测本地 CLI 是否可用（默认执行 `--version`）。"""
    if client_id not in settings_core.LOCAL_CLIENTS:
        raise HTTPException(404, f"未知本地 CLI：{client_id}")
    result = settings_core.probe_local(client_id, _settings())
    cfg = settings_core.client_cfg(client_id, _settings())
    cfg["last_probe"] = settings_core.probe_summary(result)
    _write_local(client_id, cfg)
    audit.log(store, "settings.local.probe", "api",
              {"client": client_id, "ok": result.get("ok")}, "low")
    result["client_state"] = _local_client(client_id)
    return result


@app.post("/api/settings/local/{client_id}/run")
def run_local_client(client_id: str, body: LocalRunIn):
    """执行本地 CLI（shell=False）。输出仅作为草稿，verification_status=unverified。"""
    if client_id not in settings_core.LOCAL_CLIENTS:
        raise HTTPException(404, f"未知本地 CLI：{client_id}")
    result = settings_core.run_local(client_id, _settings(), args=body.args,
                                     timeout=body.timeout)
    audit.log(store, "settings.local.run", "api",
              {"client": client_id, "ok": result.get("ok"),
               "exit_code": result.get("exit_code"),
               "args": (body.args or "")[:120]}, "medium")
    return result


# ---------------- frontend ----------------
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")


@app.exception_handler(Exception)
async def unhandled(request, exc):  # noqa: ANN001
    return JSONResponse(status_code=500, content={"detail": str(exc)[:300]})
