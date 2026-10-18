"""4-agent recovery swarm, in-graph handoffs, gatekeeper and Company Brain Q&A."""
import json
import os
import re
import time
import httpx
import db
import mcp_tools as T

AGENTS = ["Shockwave-Triage-Agent", "BusFactor-Detector-Agent", "Tribal-Archaeologist-Agent", "Continuity-Healer-Agent"]


# ---------------------------------------------------------------------------
# "No Node, No Action" deterministic gatekeeper
# ---------------------------------------------------------------------------
def gate(graph_name: str, provenance: list[str]):
    ids = sorted(set(p for p in provenance if p))
    if not ids:
        return {"ok": False, "reason": "empty provenance_path", "checked": 0}
    rs, _ = db.rows(graph_name, "MATCH (n) WHERE n.id IN $ids RETURN collect(n.id) AS found", {"ids": ids}, "gatekeeper")
    found = set(rs[0]["found"])
    missing = [i for i in ids if i not in found]
    return {"ok": not missing, "reason": f"unknown node ids: {missing}" if missing else "all provenance nodes exist in FalkorDB",
            "checked": len(ids)}


# ---------------------------------------------------------------------------
# Optional live-LLM narration (deterministic engine is always the source of truth)
# ---------------------------------------------------------------------------
def _llm_provider():
    if os.getenv("OPENAI_API_KEY"):
        return ("https://api.openai.com/v1/chat/completions", os.environ["OPENAI_API_KEY"], os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    if os.getenv("GROQ_API_KEY"):
        return ("https://api.groq.com/openai/v1/chat/completions", os.environ["GROQ_API_KEY"], os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"))
    if os.getenv("GEMINI_API_KEY"):
        return ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", os.environ["GEMINI_API_KEY"], os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
    return None


def narrate(agent: str, facts: str, fallback: str, allowed_ids: list[str]) -> tuple[str, str]:
    """Return (text, engine). The LLM may only rephrase; any unknown node id in its output rejects it."""
    prov = _llm_provider()
    if not prov:
        return fallback, "deterministic-graph-engine"
    url, key, model = prov
    try:
        r = httpx.post(url, headers={"Authorization": f"Bearer {key}"}, timeout=8, json={
            "model": model, "temperature": 0.1,
            "messages": [
                {"role": "system", "content": f"You are {agent}. Summarize the graph findings in <=3 sentences. Only cite node ids from the facts."},
                {"role": "user", "content": facts}]})
        text = r.json()["choices"][0]["message"]["content"].strip()
        cited = set(re.findall(r"\b(?:svc|eng|repo|db|commit|adr|slack|ticket|team)_[a-z0-9_]+", text))
        if cited - set(allowed_ids):
            return fallback, "deterministic-graph-engine (LLM output rejected by gatekeeper)"
        return text, f"llm:{model}"
    except Exception:
        return fallback, "deterministic-graph-engine (LLM unavailable)"


# ---------------------------------------------------------------------------
# Episodic memory: (:Episode)-[:STEP]->(:EpisodicStep)-[:HANDOFF_TO]->(:EpisodicStep)
# ---------------------------------------------------------------------------
class Episode:
    def __init__(self, session_id, signature):
        self.sid, self.sig, self.seq, self.prev = session_id, signature, 0, None
        self.id = f"ep_{session_id}"
        db.q(db.PROD, "MERGE (e:Episode {id:$id}) SET e.session_id=$sid, e.signature=$sig, e.created_at=timestamp()",
             {"id": self.id, "sid": session_id, "sig": signature}, "episodic")

    def step(self, agent, action, summary, n_queries, latency_ms, provenance, plan=None, snapshot=None):
        self.seq += 1
        sid = f"{self.id}_s{self.seq}"
        db.q(db.PROD, """
            MATCH (e:Episode {id:$eid})
            CREATE (s:EpisodicStep {id:$id, agent:$agent, action:$action, summary:$summary, seq:$seq,
                                    n_queries:$nq, latency_ms:$ms, provenance:$prov, plan_json:$plan, snapshot_json:$snap})
            CREATE (e)-[:STEP]->(s)""",
             {"eid": self.id, "id": sid, "agent": agent, "action": action, "summary": summary[:400], "seq": self.seq,
              "nq": n_queries, "ms": round(latency_ms, 3), "prov": provenance[:40],
              "plan": json.dumps(plan) if plan is not None else None,
              "snap": json.dumps(snapshot) if snapshot is not None else None}, "episodic")
        if self.prev:
            db.q(db.PROD, "MATCH (a:EpisodicStep {id:$a}), (b:EpisodicStep {id:$b}) CREATE (a)-[:HANDOFF_TO {at: timestamp()}]->(b)",
                 {"a": self.prev, "b": sid}, "episodic")
        self.prev = sid
        return sid


def _event_step(agent, tool, narrative, engine, res, gate_res, handoff=None, extra=None):
    return {"type": "step", "agent": agent, "tool": tool, "narrative": narrative, "engine": engine,
            "cypher": res["cypher_executed"], "latency_ms": res["latency_ms"], "provenance": res["provenance_node_ids"],
            "algo_notes": res.get("algo_notes", []), "gate": gate_res, "handoff_to": handoff, **(extra or {})}


# ---------------------------------------------------------------------------
# Dossier composition (deterministic, cited)
# ---------------------------------------------------------------------------
def compose_runbook(orphan, sources):
    lines = [f"EMERGENCY HANDOVER · {orphan['name']} ({orphan['id']})"]
    for s in sources:
        if s["type"] == "SlackThread":
            lines.append(f"• {s['by']} warned in Slack [{s['id']}]: “{s['quote']}”")
        elif s["type"] == "Commit":
            flag = " — flagged " + s["risk"] if s.get("risk") in ("CRITICAL", "VIOLATION", "HIGH") else ""
            lines.append(f"• Commit [{s['id']}] by {s.get('by') or 'unknown'}{flag}: {s['quote']}")
        elif s["type"] == "ADR_Doc":
            lines.append(f"• Policy [{s['id']}] {s['title']}: {s['quote']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The swarm
# ---------------------------------------------------------------------------
def run_swarm(session_id: str, targets: list[str]):
    """Generator of events. Final event: {'type':'done', 'result': {...}}."""
    sim = T.sim_name(session_id)
    sig = T.signature(targets)
    t_start = time.perf_counter()
    if not db.graph_exists(sim):
        yield {"type": "log", "message": f"No sandbox for {session_id}; forking first."}
        T.fork_chaos_sandbox(session_id, targets)
    ep = Episode(session_id, sig)

    # ---- Coordinator: 1-hop procedural-memory lookup ----------------------
    pb, lookup_ms = T.lookup_playbook(sig)
    cypher_lookup = [{"cypher": db.QUERY_LOG[-1]["cypher"], "ms": round(lookup_ms, 3), "graph": db.PROD}]
    if pb and pb["plan_json"]:
        plan = json.loads(pb["plan_json"])
        snap = json.loads(pb["snapshot_json"] or "{}")
        for a in AGENTS:
            yield {"type": "agent_status", "agent": a, "status": "FAST_PATH_HIT"}
        yield {"type": "step", "agent": "Coordinator", "tool": "procedural_memory_lookup",
               "narrative": f"Failure signature '{sig}' matched ProceduralPlaybook {pb['id']} in 1 Cypher hop "
                            f"({lookup_ms:.2f} ms). Skipping multi-agent deliberation and executing learned playbook.",
               "engine": "procedural-memory", "cypher": cypher_lookup, "latency_ms": round(lookup_ms, 3),
               "provenance": [pb["id"]] + targets, "algo_notes": [], "gate": {"ok": True, "reason": "playbook node exists", "checked": 1},
               "handoff_to": None}
        t0 = time.perf_counter()
        tech = [t for t in targets if t in snap.get("technical_ids", [])]
        tr = T.apply_healing(sim, plan, tech, snap.get("impacted_ids", []))
        apply_ms = (time.perf_counter() - t0) * 1000
        surv = T.survivability(sim)
        ep.step("Coordinator", "procedural_fast_path", f"Replayed playbook {pb['id']}", 1, lookup_ms, [pb["id"]] + targets)
        yield {"type": "step", "agent": "Continuity-Healer-Agent", "tool": "apply_learned_playbook",
               "narrative": f"Replayed {len(plan)} learned reassignments + failover routes onto {sim}. Survivability {surv['score']}%.",
               "engine": "procedural-memory", "cypher": [{"cypher": e["cypher"], "ms": e["ms"], "graph": e["graph"]} for e in tr],
               "latency_ms": round(apply_ms, 3), "provenance": [p["successor"] for p in plan if p.get("successor")] + [p["orphan"] for p in plan],
               "algo_notes": [], "gate": {"ok": True, "reason": "plan nodes validated at distillation time", "checked": len(plan)}, "handoff_to": None}
        result = {**snap, "fast_path_hit": True, "playbook_id": pb["id"], "lookup_ms": round(lookup_ms, 3),
                  "apply_ms": round(apply_ms, 3), "reasoning_queries": 1, "survivability": surv,
                  "plan": plan, "total_ms": round((time.perf_counter() - t_start) * 1000, 2), "session_id": session_id,
                  "sandbox": sim, "session1_queries": pb["session1_queries"]}
        yield {"type": "done", "result": result}
        return

    q_total = 0

    # ---- Agent 1: Shockwave-Triage -------------------------------------
    yield {"type": "agent_status", "agent": AGENTS[0], "status": "TRAVERSING"}
    blast = T.compute_technical_blast_radius(sim, targets)
    g1 = gate(sim, blast["provenance_node_ids"])
    b = blast["data"]
    fb = (f"{len(b['impacted_services'])} upstream services cascade-fail from {', '.join(t['id'] for t in b['technical_targets']) or 'no technical target'}; "
          f"{b['rps_at_risk']:,} RPS at risk, {len(b['tier0_sla_breaches'])} Tier-0 SLAs breached. "
          f"PageRank chokepoint: {b['chokepoint']}.")
    text, eng = narrate(AGENTS[0], fb, fb, blast["provenance_node_ids"])
    q_total += len(blast["cypher_executed"])
    ep.step(AGENTS[0], "compute_technical_blast_radius", text, len(blast["cypher_executed"]), blast["latency_ms"], blast["provenance_node_ids"])
    yield _event_step(AGENTS[0], "compute_technical_blast_radius", text, eng, blast, g1, AGENTS[1], {"result": b})
    yield {"type": "agent_status", "agent": AGENTS[0], "status": "HANDOFF_COMMITTED"}

    # ---- Agent 2: BusFactor-Detector -------------------------------------
    yield {"type": "agent_status", "agent": AGENTS[1], "status": "TRAVERSING"}
    orph = T.compute_orphaned_tribal_knowledge(sim, targets)
    contra = T.detect_organizational_contradictions(sim)
    o = orph["data"]
    c = contra["data"]
    g2 = gate(sim, orph["provenance_node_ids"] + contra["provenance_node_ids"])
    fb = (f"{o['orphan_count']} systems now have bus_factor = 0: {', '.join(x['id'] for x in o['orphans']) or 'none'}. "
          f"WCC found {len(o['orphan_components'])} ownerless subgraph(s). "
          f"{c['count']} policy contradiction(s) detected" +
          (f": {c['contradictions'][0]['service']} → {c['contradictions'][0]['database']} violates {c['contradictions'][0]['adr_id']} via {c['contradictions'][0]['commit_id']}." if c["count"] else "."))
    text, eng = narrate(AGENTS[1], fb, fb, orph["provenance_node_ids"] + contra["provenance_node_ids"])
    merged = {**orph, "cypher_executed": orph["cypher_executed"] + contra["cypher_executed"],
              "latency_ms": round(orph["latency_ms"] + contra["latency_ms"], 3),
              "provenance_node_ids": sorted(set(orph["provenance_node_ids"] + contra["provenance_node_ids"]))}
    q_total += len(merged["cypher_executed"])
    ep.step(AGENTS[1], "compute_orphaned_tribal_knowledge+detect_organizational_contradictions", text, len(merged["cypher_executed"]),
            merged["latency_ms"], merged["provenance_node_ids"])
    yield _event_step(AGENTS[1], "compute_orphaned_tribal_knowledge + detect_organizational_contradictions", text, eng, merged, g2,
                      AGENTS[2], {"result": {"orphans": o, "contradictions": c}})
    yield {"type": "agent_status", "agent": AGENTS[1], "status": "HANDOFF_COMMITTED"}

    # ---- Agent 3: Tribal-Archaeologist -----------------------------------
    yield {"type": "agent_status", "agent": AGENTS[2], "status": "TRAVERSING"}
    orphan_ids = [x["id"] for x in o["orphans"] if x["label"] in ("Service", "Repository", "Ticket", "Database")]
    ctx = T.reconstruct_tribal_context(sim, orphan_ids) if orphan_ids else T._wrap([], {"dossiers": []}, [])
    g3 = gate(sim, ctx["provenance_node_ids"]) if orphan_ids else {"ok": True, "reason": "nothing orphaned", "checked": 0}
    by_id = {x["id"]: x for x in o["orphans"]}
    runbooks = []
    for d in ctx["data"]["dossiers"]:
        orp = by_id[d["orphan_id"]]
        runbooks.append({**d, "name": orp["name"], "label": orp["label"], "runbook": compose_runbook(orp, d["sources"])})
    n_src = sum(len(r["sources"]) for r in runbooks)
    fb = f"Reconstructed {len(runbooks)} handover dossier(s) citing {n_src} sources (Slack, commits, ADRs) via 1..3-hop traversal."
    text, eng = narrate(AGENTS[2], fb, fb, ctx["provenance_node_ids"])
    q_total += len(ctx["cypher_executed"])
    ep.step(AGENTS[2], "reconstruct_tribal_context", text, len(ctx["cypher_executed"]), ctx["latency_ms"], ctx["provenance_node_ids"])
    yield _event_step(AGENTS[2], "reconstruct_tribal_context", text, eng, ctx, g3, AGENTS[3], {"result": {"dossiers": runbooks}})
    yield {"type": "agent_status", "agent": AGENTS[2], "status": "HANDOFF_COMMITTED"}

    # ---- Agent 4: Continuity-Healer --------------------------------------
    yield {"type": "agent_status", "agent": AGENTS[3], "status": "TRAVERSING"}
    succ = T.find_optimal_successors(sim, orphan_ids) if orphan_ids else T._wrap([], {"matches": []}, [])
    g4 = gate(sim, succ["provenance_node_ids"]) if orphan_ids else {"ok": True, "reason": "nothing to heal", "checked": 0}
    plan = []
    if g4["ok"]:
        plan = T.balanced_plan(succ["data"]["matches"])
        for m in succ["data"]["matches"]:  # keep the UI winner consistent with the balanced plan
            p = next((x for x in plan if x["orphan"] == m["orphan_id"]), None)
            if p:
                w = next((r for r in m["ranked"] if r["id"] == p["successor"]), m["winner"])
                m["winner"] = {**w, "score": p["score"], "compatibility": round(p["confidence"] * 100, 1)}
    tech_targets = [t["id"] for t in b["technical_targets"]]
    impacted_ids = [i["id"] for i in b["impacted_services"]]
    heal_tr = T.apply_healing(sim, plan, tech_targets, impacted_ids) if g4["ok"] else []
    surv = T.survivability(sim)
    g4b = gate(sim, [p["successor"] for p in plan] + [p["orphan"] for p in plan] + [t + "_replica" for t in tech_targets])
    top = plan[0] if plan else None
    fb = (f"Rewired {len(plan)} orphaned systems with [:AUTO_REASSIGNED_TO]" +
          (f"; top match {top['successor_name']} ({top['confidence']*100:.0f}% compatibility for {top['orphan']})" if top else "") +
          f". Promoted {len(tech_targets)} [:FAILOVER_REPLICA] route(s). Survivability → {surv['score']}%.")
    text, eng = narrate(AGENTS[3], fb, fb, succ["provenance_node_ids"] + [t + "_replica" for t in tech_targets])
    all_cy = succ["cypher_executed"] + [{"cypher": e["cypher"], "ms": e["ms"], "graph": e["graph"]} for e in heal_tr]
    heal_ms = round(succ["latency_ms"] + sum(e["ms"] for e in heal_tr), 3)
    q_total += len(all_cy)
    snapshot = {"blast": b, "orphans": o, "contradictions": c, "dossiers": runbooks, "successors": succ["data"],
                "technical_ids": tech_targets, "impacted_ids": impacted_ids}
    ep.step(AGENTS[3], "find_optimal_successors+apply_healing", text, len(all_cy), heal_ms,
            succ["provenance_node_ids"], plan=plan, snapshot=snapshot)
    merged = {"cypher_executed": all_cy, "latency_ms": heal_ms, "provenance_node_ids": sorted(set(succ["provenance_node_ids"] + [t + "_replica" for t in tech_targets])), "algo_notes": []}
    yield _event_step(AGENTS[3], "find_optimal_successors + apply_healing", text, eng, merged, g4b, None,
                      {"result": {"plan": plan, "successors": succ["data"]}})
    yield {"type": "agent_status", "agent": AGENTS[3], "status": "HANDOFF_COMMITTED"}

    result = {**snapshot, "fast_path_hit": False, "plan": plan, "survivability": surv, "reasoning_queries": q_total,
              "total_ms": round((time.perf_counter() - t_start) * 1000, 2), "session_id": session_id, "sandbox": sim,
              "episode_id": ep.id}
    yield {"type": "done", "result": result}


# ---------------------------------------------------------------------------
# Company Brain: natural-language -> live Cypher
# ---------------------------------------------------------------------------
STOP = set("who what which is are the a an of to in on for if goes down about knows know how does do this that and or with when where why break breaks".split())


def ask(question: str, graph_name: str = db.PROD):
    ql = question.lower()
    t0 = time.perf_counter()
    with db.trace() as tr:
        answer, prov, kind = "", [], "search"
        svcs, _ = db.rows(graph_name, "MATCH (s:Service) WHERE s.replica_of IS NULL RETURN s.id AS id, s.name AS name", tag="brain")
        match = None
        for s in svcs:
            toks = [w for w in re.split(r"[^a-z0-9]+", s["name"].lower()) if len(w) > 2 and w not in ("engine", "service", "store")]
            if s["id"] in ql or s["name"].lower() in ql or (toks and sum(t in ql for t in toks) >= min(2, len(toks))):
                match = s
                break
        if ("violat" in ql or "contradict" in ql or "drift" in ql) :
            kind = "contradictions"
            res = T.detect_organizational_contradictions(graph_name)
            rows = res["data"]["contradictions"]
            answer = "; ".join(f"{r['commit_id']} by {r['author']} makes {r['service']} write directly to {r['database']}, violating {r['adr_id']}" for r in rows) or "No ADR violations found."
            prov = res["provenance_node_ids"]
        elif match and re.search(r"break|fail|down|impact|outage|blast", ql):
            kind = "blast"
            res = T.compute_technical_blast_radius(graph_name, [match["id"]], mark_impacted=False)
            d = res["data"]
            answer = (f"If {match['name']} goes down, {len(d['impacted_services'])} upstream services fail "
                      f"({', '.join(i['id'] for i in d['impacted_services'])}); {d['rps_at_risk']:,} RPS at risk.")
            prov = res["provenance_node_ids"]
        elif re.search(r"\bwho\b.*\b(own|owns|owner|responsible)", ql) and match:
            kind = "ownership"
            rs, _ = db.rows(graph_name, "MATCH (e:Engineer)-[:OWNS]->(s {id:$id}) RETURN e.id AS id, e.name AS name, e.role AS role", {"id": match["id"]}, "brain")
            answer = f"{match['name']} is owned by " + (", ".join(f"{r['name']} ({r['role']})" for r in rs) or "nobody") + "."
            prov = [match["id"]] + [r["id"] for r in rs]
        else:
            toks = [w for w in re.split(r"[^a-z0-9\-]+", ql) if len(w) > 2 and w not in STOP]
            rs, _ = db.rows(graph_name, """
                MATCH (n) WHERE (n:SlackThread OR n:Commit OR n:ADR_Doc OR n:Ticket)
                WITH n, toLower(coalesce(n.snippet, '') + ' ' + coalesce(n.message, '') + ' ' + coalesce(n.summary, '') + ' ' + coalesce(n.title, '')) AS txt
                WITH n, txt, reduce(h = 0, t IN $toks | h + CASE WHEN txt CONTAINS t THEN 1 ELSE 0 END) AS hits
                WHERE hits > 0
                OPTIONAL MATCH (a:Engineer)-[:POSTED_IN|AUTHORED|REVIEWED]->(n)
                RETURN n.id AS id, labels(n)[0] AS label, coalesce(n.snippet, n.message, n.summary, n.title) AS text,
                       hits, collect(DISTINCT a.name) AS people
                ORDER BY hits DESC LIMIT 4""", {"toks": toks}, "brain")
            kind = "knowledge-search"
            if rs:
                people = sorted({p for r in rs for p in r["people"]})
                answer = f"Most relevant sources point to {', '.join(people) or 'no one'}. Top evidence [{rs[0]['id']}]: “{rs[0]['text']}”"
                prov = [r["id"] for r in rs]
            else:
                answer = "No matching knowledge found in the graph."
    return {"question": question, "kind": kind, "answer": answer, "provenance": sorted(set(prov)),
            "cypher_executed": [{"cypher": e["cypher"], "ms": e["ms"], "graph": e["graph"]} for e in tr],
            "latency_ms": round(sum(e["ms"] for e in tr), 3)}
