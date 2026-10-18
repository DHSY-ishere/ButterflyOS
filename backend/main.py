"""ButterflyOS FastAPI server: REST + SSE + MCP (JSON-RPC) over FalkorDB."""
import json
import os
import time
import uuid
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import db
import seed as seeder
import mcp_tools as T
import agents
import war_room

app = FastAPI(title="ButterflyOS", version="1.0")

# --- public demo hardening ------------------------------------------------
DEMO_MODE = os.getenv("DEMO_MODE") == "1"
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
MAX_SANDBOXES = 18  # cap on sim_extinction_* / univ_* tenants kept alive at once
_recent: list[str] = []


def _track(*names: str):
    """Remember newly created sandbox graphs and garbage-collect the oldest beyond the cap."""
    _recent.extend(names)
    live = [g for g in db.list_graphs() if g.startswith((T.SIM_PREFIX, "univ_"))]
    if len(live) <= MAX_SANDBOXES:
        return
    order = {n: i for i, n in enumerate(_recent)}
    for g in sorted(live, key=lambda g: order.get(g, -1))[: len(live) - MAX_SANDBOXES]:
        db.delete_graph(g)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class SimReq(BaseModel):
    targets: list[str]
    session_id: str | None = None


class HealReq(BaseModel):
    targets: list[str]
    session_id: str


class AskReq(BaseModel):
    question: str
    graph: str = db.PROD


class CypherReq(BaseModel):
    graph: str = db.PROD
    query: str


class TournamentReq(BaseModel):
    targets: list[str]
    session_id: str | None = None


class RemediateReq(BaseModel):
    graph: str = db.PROD
    apply: bool = False


class McpCall(BaseModel):
    tool: str
    arguments: dict = {}


@app.on_event("startup")
def _startup():
    if not db.graph_exists(db.PROD):
        seeder.seed()


def _clean(entries):
    return [{"cypher": e["cypher"], "ms": e["ms"], "graph": e["graph"]} for e in entries]


@app.get("/api/health")
def health():
    t0 = time.perf_counter()
    graphs = db.list_graphs()
    return {"ok": True, "falkordb": True, "graphs": graphs, "ping_ms": round((time.perf_counter() - t0) * 1000, 2),
            "llm": "configured" if agents._llm_provider() else "deterministic-graph-engine", "demo_mode": DEMO_MODE}


@app.get("/api/graphs")
def graphs():
    return {"graphs": db.list_graphs(), "prod": db.PROD}


@app.get("/api/graph")
def get_graph(name: str = db.PROD):
    if not db.graph_exists(name):
        raise HTTPException(404, f"graph {name} not found")
    with db.trace() as tr:
        nodes, _ = db.rows(name, """
            MATCH (n) WHERE NOT n:Episode AND NOT n:EpisodicStep
            RETURN n.id AS id, labels(n)[0] AS label, properties(n) AS props""", tag="graph")
        ids = {n["id"] for n in nodes}
        edges, _ = db.rows(name, """
            MATCH (a)-[r]->(b) WHERE NOT a:Episode AND NOT a:EpisodicStep AND NOT b:EpisodicStep AND NOT b:Episode
            RETURN a.id AS source, type(r) AS type, b.id AS target, properties(r) AS props""", tag="graph")
    edges = [e for e in edges if e["source"] in ids and e["target"] in ids]
    for n in nodes:
        n["props"] = {k: v for k, v in n["props"].items() if k not in ("plan_json", "snapshot_json")}
    surv = T.survivability(name)
    return {"graph": name, "nodes": nodes, "edges": edges, "survivability": surv,
            "orphans": T.orphan_rows(name), "last_query_ms": db.LAST_LATENCY_MS, "cypher_executed": _clean(tr)}


@app.get("/api/node/{node_id}")
def node_detail(node_id: str, graph: str = db.PROD):
    with db.trace() as tr:
        node, _ = db.rows(graph, "MATCH (n {id:$id}) RETURN labels(n)[0] AS label, properties(n) AS props", {"id": node_id}, "drawer")
        if not node:
            raise HTTPException(404, "node not found")
        nb, _ = db.rows(graph, """
            MATCH (n {id:$id})-[r]-(m) WHERE NOT m:EpisodicStep AND NOT m:Episode
            RETURN type(r) AS rel, startNode(r).id = n.id AS outgoing, m.id AS id, labels(m)[0] AS label,
                   coalesce(m.name, m.title, m.hash, m.id) AS name""", {"id": node_id}, "drawer")
    return {"id": node_id, **node[0], "neighbors": nb, "cypher_executed": _clean(tr)}


@app.post("/api/simulate")
def simulate(req: SimReq):
    if not req.targets:
        raise HTTPException(400, "pick at least one target node")
    sid = req.session_id or uuid.uuid4().hex[:8]
    fork = T.fork_chaos_sandbox(sid, req.targets)
    sim = T.sim_name(sid)
    _track(sim)
    blast = T.compute_technical_blast_radius(sim, req.targets)
    orph = T.compute_orphaned_tribal_knowledge(sim, req.targets)
    surv = T.survivability(sim)
    pb, lookup_ms = T.lookup_playbook(T.signature(req.targets))
    # lookup bumps hits; undo so the session-2 counter stays honest
    if pb:
        db.q(db.PROD, "MATCH (p:ProceduralPlaybook {id:$id}) SET p.hits = p.hits - 1", {"id": pb["id"]}, "procedural-lookup")
    return {"session_id": sid, "sandbox": sim, "fork": fork["data"], "blast": blast["data"], "orphans": orph["data"],
            "survivability": surv, "playbook_available": bool(pb), "algo_notes": blast["algo_notes"] + orph["algo_notes"],
            "cypher_executed": fork["cypher_executed"] + blast["cypher_executed"] + orph["cypher_executed"],
            "last_query_ms": db.LAST_LATENCY_MS}


@app.post("/api/heal/stream")
def heal_stream(req: HealReq):
    def gen():
        for ev in agents.run_swarm(req.session_id, req.targets):
            yield f"data: {json.dumps(ev, default=str)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/api/heal")
def heal(req: HealReq):
    events = list(agents.run_swarm(req.session_id, req.targets))
    return {"events": events, "result": events[-1]["result"]}


@app.post("/api/vaccinate")
def vaccinate(req: HealReq):
    res = T.consolidate_episodic_to_procedural_memory(req.session_id, req.targets)
    return res


@app.get("/api/contradictions")
def contradictions(graph: str = db.PROD):
    return T.detect_organizational_contradictions(graph)


@app.post("/api/ask")
def ask(req: AskReq):
    return agents.ask(req.question, req.graph)


@app.get("/api/memory")
def memory():
    with db.trace() as tr:
        eps, _ = db.rows(db.PROD, """
            MATCH (e:Episode) OPTIONAL MATCH (e)-[:STEP]->(s:EpisodicStep)
            RETURN e.id AS id, e.session_id AS session_id, e.signature AS signature, e.created_at AS created_at,
                   collect({id: s.id, agent: s.agent, action: s.action, summary: s.summary, seq: s.seq,
                            n_queries: s.n_queries, latency_ms: s.latency_ms}) AS steps
            ORDER BY e.created_at""", tag="memory")
        hand, _ = db.rows(db.PROD, "MATCH (a:EpisodicStep)-[:HANDOFF_TO]->(b:EpisodicStep) RETURN a.id AS a, b.id AS b", tag="memory")
        pbs, _ = db.rows(db.PROD, """
            MATCH (p:ProceduralPlaybook)
            RETURN p.id AS id, p.name AS name, p.signature AS signature, p.confidence AS confidence,
                   p.avg_latency_ms AS avg_latency_ms, p.steps AS steps, p.hits AS hits, p.version AS version,
                   p.session1_queries AS session1_queries ORDER BY p.created_at DESC""", tag="memory")
        sem, _ = db.rows(db.PROD, "MATCH (n) WHERE NOT n:Episode AND NOT n:EpisodicStep AND NOT n:ProceduralPlaybook RETURN count(n) AS nodes", tag="memory")
        rels, _ = db.rows(db.PROD, "MATCH ()-[r]->() RETURN count(r) AS c", tag="memory")
    for e in eps:
        e["steps"] = sorted([s for s in e["steps"] if s["id"]], key=lambda s: s["seq"])
    return {"episodes": eps, "handoffs": hand, "playbooks": pbs,
            "semantic": {"nodes": sem[0]["nodes"], "edges": rels[0]["c"]}, "cypher_executed": _clean(tr)}


@app.post("/api/reset")
def reset(hard: bool = False, x_admin_token: str | None = Header(default=None)):
    if DEMO_MODE:
        if hard and not (ADMIN_TOKEN and x_admin_token == ADMIN_TOKEN):
            raise HTTPException(403, "hard reset is disabled in public demo mode")
        if not hard:  # sandboxes are shared infrastructure here; the client just resets its own view
            return {"ok": True, "hard": False, "demo": True, "graphs": db.list_graphs()}
    for g in db.list_graphs():
        if g.startswith(T.SIM_PREFIX) or g.startswith("univ_"):
            db.delete_graph(g)
    if hard:
        seeder.seed()
    return {"ok": True, "hard": hard, "graphs": db.list_graphs()}


# --- CEO war-room ---------------------------------------------------------
@app.get("/api/blindspot")
def blindspot(graph: str = db.PROD):
    return war_room.discover_existential_blindspot(graph)


@app.post("/api/tournament")
def tournament(req: TournamentReq):
    if not req.targets:
        raise HTTPException(400, "pick at least one target node")
    res = war_room.run_tournament(req.targets, req.session_id)
    _track(*res["graphs"])
    return res


@app.post("/api/remediate-pr")
def remediate_pr(req: RemediateReq):
    graph = req.graph
    if req.apply:
        forked = None
        if graph == db.PROD:  # never mutate the production baseline: apply on a sandbox fork
            forked = f"{T.SIM_PREFIX}rem{uuid.uuid4().hex[:6]}"
            with T._FORK_LOCK:
                db.graph(db.PROD).copy(forked)
            _track(forked)
            graph = forked
        res = war_room.apply_remediation(graph)
        res["forked_from_prod"] = bool(forked)
        res["brief"] = war_room.remediation_brief(graph)
        return res
    return war_room.remediation_brief(graph)


# --- Cypher & MCP inspector -------------------------------------------------
import re as _re

_WRITE = _re.compile(r"\b(create|merge|delete|detach|set|remove|drop|load\s+csv|foreach)\b", _re.I)


@app.post("/api/cypher")
def cypher(req: CypherReq):
    """Read-only OpenCypher playground (uses GRAPH.RO_QUERY, so writes are rejected by FalkorDB itself too)."""
    if not db.graph_exists(req.graph):
        raise HTTPException(404, "graph not found")
    if len(req.query) > 2000:
        raise HTTPException(400, "query too long")
    if _WRITE.search(req.query):
        raise HTTPException(400, "read-only: write clauses are not allowed")
    t0 = time.perf_counter()
    try:
        res = db.graph(req.graph).ro_query(req.query, timeout=3000)
    except Exception as ex:
        raise HTTPException(400, str(ex)[:300])
    ms = round((time.perf_counter() - t0) * 1000, 3)
    def cell(v):
        if hasattr(v, "properties"):
            return {"labels": getattr(v, "labels", None), "type": getattr(v, "relation", None), **v.properties}
        return v
    header = [h[1] if isinstance(h, (list, tuple)) else h for h in res.header]
    rows_ = [[cell(c) for c in r] for r in res.result_set[:200]]
    return {"graph": req.graph, "columns": header, "rows": rows_, "row_count": len(res.result_set), "latency_ms": ms,
            "server_reported_ms": getattr(res, "run_time_ms", None)}


@app.get("/api/schema")
def schema(graph: str = db.PROD):
    labels, _ = db.rows(graph, "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC", tag="schema")
    rels, _ = db.rows(graph, "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count ORDER BY count DESC", tag="schema")
    return {"graph": graph, "labels": labels, "relationships": rels}


# --- MCP ------------------------------------------------------------------
@app.get("/api/mcp/tools")
def mcp_tools():
    return {"tools": [{"name": k, "description": v["description"], "inputSchema": v["input_schema"]} for k, v in T.TOOLS.items()]}


@app.post("/api/mcp/call")
def mcp_call(req: McpCall):
    tool = T.TOOLS.get(req.tool)
    if not tool:
        raise HTTPException(404, f"unknown tool {req.tool}")
    return tool["fn"](**req.arguments)


@app.post("/mcp")
def mcp_jsonrpc(body: dict):
    """Minimal MCP JSON-RPC 2.0 endpoint (initialize, tools/list, tools/call)."""
    m, rid, params = body.get("method"), body.get("id"), body.get("params", {})
    if m == "initialize":
        result = {"protocolVersion": "2024-11-05", "serverInfo": {"name": "butterfly-os", "version": "1.0"}, "capabilities": {"tools": {}}}
    elif m == "tools/list":
        result = mcp_tools()
    elif m == "tools/call":
        tool = T.TOOLS.get(params.get("name"))
        if not tool:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "unknown tool"}}
        out = tool["fn"](**params.get("arguments", {}))
        result = {"content": [{"type": "text", "text": json.dumps(out, default=str)}]}
    else:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}}
    return {"jsonrpc": "2.0", "id": rid, "result": result}
