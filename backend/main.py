"""全球鹰 GEO 全球AI推荐系统 - OpenClaw Orchestrator 服务入口."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agents import (a10_schema, a12_visibility, a13_lead, a14_analytics,
                     a15_feedback, a02_market)
from .core import approval as approval_core
from .core import audit, evidence_graph
from .core.store import Store
from .core.util import now_iso, uid
from .orchestrator import Orchestrator, PIPELINE
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
            "llm_polish": bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")),
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


# ---------------- frontend ----------------
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")


@app.exception_handler(Exception)
async def unhandled(request, exc):  # noqa: ANN001
    return JSONResponse(status_code=500, content={"detail": str(exc)[:300]})
