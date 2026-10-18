"""MCP-style tool registry: 7 graph tools, each backed by live OpenCypher / FalkorDB algorithms.

Every tool returns {data, cypher_executed, latency_ms, provenance_node_ids, algo_notes}.
"""
import json
import time
import hashlib
import threading
import db

_FORK_LOCK = threading.Lock()  # FalkorDB serves one GRAPH.COPY of a source graph at a time

PROD = db.PROD
SIM_PREFIX = "sim_extinction_"
# Continuity coefficients for the survivability metric
OWN_NATIVE = 1.0         # [:OWNS] by an active engineer
OWN_HEALED = 0.96        # [:AUTO_REASSIGNED_TO] swarm handoff (4% onboarding overhead)
FAILOVER_AVAIL = 0.96    # warm replica promoted in place of an extinct service
TIER_WEIGHT = {'TIER_0': 3.0, 'TIER_1': 2.0, 'TIER_2': 1.0}


def sim_name(session_id: str) -> str:
    return f"{SIM_PREFIX}{session_id}"


def signature(targets: list[str]) -> str:
    return "+".join(sorted(targets))


def _wrap(entries, data, prov, notes=None):
    return {
        "data": data,
        "cypher_executed": [{"cypher": e["cypher"], "ms": e["ms"], "graph": e["graph"]} for e in entries],
        "latency_ms": round(sum(e["ms"] for e in entries), 3),
        "provenance_node_ids": sorted(set(p for p in prov if p)),
        "algo_notes": notes or [],
    }


def _rel_types(graph_name):
    rs, _, _ = db.q(graph_name, "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType", tag="meta")
    return {r[0] for r in rs}


# ---------------------------------------------------------------------------
# 1. fork_chaos_sandbox
# ---------------------------------------------------------------------------
def fork_chaos_sandbox(session_id: str, target_node_ids: list[str], graph_name: str | None = None):
    name = graph_name or sim_name(session_id)
    with db.trace() as tr:
        db.delete_graph(name)
        with _FORK_LOCK:
            t0 = time.perf_counter()
            db.graph(PROD).copy(name)  # native FalkorDB GRAPH.COPY
        copy_ms = (time.perf_counter() - t0) * 1000
        tr.append({"graph": PROD, "cypher": f"GRAPH.COPY {PROD} {name}", "ms": round(copy_ms, 3), "tag": "fork"})
        marked, _ = db.rows(name, """
            MATCH (n) WHERE n.id IN $t
            SET n.status = 'EXTINCT', n.extinct_at = timestamp()
            RETURN n.id AS id, labels(n)[0] AS label, n.name AS name""", {"t": target_node_ids}, "fork")
        # Extinct engineers: their live ownership / assignment edges become inactive (active=false)
        db.q(name, """
            MATCH (e:Engineer {status:'EXTINCT'})-[r:OWNS]->(x)
            CREATE (e)-[:FORMERLY_OWNED {active:false, bus_factor_weight:r.bus_factor_weight}]->(x)
            DELETE r""", tag="fork")
        db.q(name, """
            MATCH (e:Engineer {status:'EXTINCT'})-[r:ASSIGNED_TO]->(x)
            CREATE (e)-[:FORMERLY_ASSIGNED {active:false}]->(x)
            DELETE r""", tag="fork")
    data = {"sandbox": name, "copy_ms": round(copy_ms, 3), "extinct": marked,
            "signature": signature(target_node_ids)}
    return _wrap(tr, data, [m["id"] for m in marked])


# ---------------------------------------------------------------------------
# 2. compute_technical_blast_radius
# ---------------------------------------------------------------------------
def compute_technical_blast_radius(graph_name: str, target_node_ids: list[str], mark_impacted: bool = True):
    notes = []
    with db.trace() as tr:
        tech, _ = db.rows(graph_name, """
            MATCH (n) WHERE n.id IN $t AND (n:Service OR n:Database) AND n.replica_of IS NULL
            RETURN n.id AS id, n.name AS name, labels(n)[0] AS label, coalesce(n.rps, 0) AS rps, n.tier AS tier, n.sla AS sla
        """, {"t": target_node_ids}, "blast")
        tech_ids = [t["id"] for t in tech]
        paths = []
        if tech_ids:
            paths, _ = db.rows(graph_name, """
                MATCH path = (caller:Service)-[:DEPENDS_ON*1..5]->(t)
                WHERE t.id IN $targets AND caller.replica_of IS NULL
                RETURN caller.id AS id, caller.name AS name, caller.rps AS rps, caller.tier AS tier, caller.sla AS sla,
                       t.id AS root, [n IN nodes(path) | n.id] AS path_ids, [n IN nodes(path) | n.name] AS path_names,
                       length(path) AS hops
                ORDER BY hops ASC""", {"targets": tech_ids}, "blast")
        # PageRank (native), with a Cypher in-degree fallback
        pr = {}
        try:
            rs, _ = db.rows(graph_name, """
                CALL algo.pageRank('Service', 'DEPENDS_ON') YIELD node, score
                RETURN node.id AS id, node.name AS name, score ORDER BY score DESC""", tag="algo.pageRank")
            pr = {r["id"]: r["score"] for r in rs}
            notes.append("algo.pageRank: native")
        except Exception as ex:
            notes.append(f"algo.pageRank failed ({str(ex)[:60]}); used in-degree fallback")
            rs, _ = db.rows(graph_name, """
                MATCH (s:Service) OPTIONAL MATCH (c:Service)-[:DEPENDS_ON]->(s)
                RETURN s.id AS id, count(c) AS score""", tag="fallback.degree")
            pr = {r["id"]: float(r["score"]) for r in rs}
        # Mark impacted services
        impacted_ids = sorted({p["id"] for p in paths} - set(tech_ids))
        if impacted_ids and mark_impacted:
            db.q(graph_name, "MATCH (s:Service) WHERE s.id IN $ids AND s.status <> 'EXTINCT' SET s.status = 'IMPACTED'",
                 {"ids": impacted_ids}, "blast")
    # Enterprise ARR ledger: customer contracts whose SLA depends on any failed or impacted service
    hit_ids = sorted(set(tech_ids) | set(impacted_ids))
    contracts = []
    if hit_ids:
        with db.trace() as tr2:
            crow, _ = db.rows(graph_name, """
                MATCH (c:CustomerContract)-[:SLA_DEPENDS_ON]->(s:Service) WHERE s.id IN $ids
                RETURN c.id AS id, c.client AS client, c.arr_usd AS arr_usd, c.penalty_per_min_usd AS penalty_per_min_usd,
                       c.sla_tier AS sla_tier, collect(DISTINCT s.id) AS services""", {"ids": hit_ids}, "arr")
        tr.extend(tr2)
        contracts = crow
    best = {}
    for p in paths:  # shortest path per impacted service
        if p["id"] not in best:
            best[p["id"]] = p
    impacted = []
    for sid, p in best.items():
        impacted.append({**p, "pagerank": round(pr.get(sid, 0), 5)})
    impacted.sort(key=lambda x: -x["pagerank"])
    tier0 = [i for i in impacted if i["tier"] == "TIER_0"] + [t for t in tech if t["tier"] == "TIER_0"]
    rps = sum(i["rps"] for i in impacted) + sum(t["rps"] for t in tech)
    top_pr = sorted(pr.items(), key=lambda kv: -kv[1])[:5]
    data = {
        "technical_targets": tech,
        "impacted_services": impacted,
        "rps_at_risk": rps,
        "tier0_sla_breaches": [{"id": t["id"], "name": t["name"], "sla": t["sla"]} for t in tier0],
        "pagerank_top": [{"id": k, "score": round(v, 5)} for k, v in top_pr],
        "chokepoint": top_pr[0][0] if top_pr else None,
        "contracts_at_risk": contracts,
        "total_arr_at_risk_usd": sum(c["arr_usd"] for c in contracts),
        "burn_rate_per_min_usd": sum(c["penalty_per_min_usd"] for c in contracts),
    }
    prov = tech_ids + [i for p in best.values() for i in p["path_ids"]] + [c["id"] for c in contracts]
    return _wrap(tr, data, prov, notes)


# ---------------------------------------------------------------------------
# 3. compute_orphaned_tribal_knowledge
# ---------------------------------------------------------------------------
ORPHAN_Q = """
MATCH (x)<-[:FORMERLY_OWNED|FORMERLY_ASSIGNED]-(old:Engineer)
WHERE x:Service OR x:Repository OR x:Ticket OR x:Database
OPTIONAL MATCH (x)<-[:OWNS|ASSIGNED_TO|AUTO_REASSIGNED_TO]-(e:Engineer {status:'ACTIVE'})
WITH x, collect(DISTINCT old.id) AS former_owners, count(DISTINCT e) AS bus_factor
WHERE bus_factor = 0
RETURN x.id AS id, x.name AS name, coalesce(x.title, x.name) AS title, labels(x)[0] AS label, former_owners, bus_factor
"""


def orphan_rows(graph_name):
    rs, _ = db.rows(graph_name, ORPHAN_Q, tag="orphans")
    return rs


def compute_orphaned_tribal_knowledge(graph_name: str, target_node_ids: list[str]):
    notes = []
    with db.trace() as tr:
        orphans = orphan_rows(graph_name)
        types = _rel_types(graph_name)
        bt = [t for t in ["DEPENDS_ON", "OWNS", "AUTHORED", "MODIFIED_IN", "DEPLOYED_FROM"] if t in types]
        betw = []
        try:
            betw, _ = db.rows(graph_name, """
                CALL algo.betweenness({nodeLabels: ['Service','Engineer','Repository','Commit'],
                                       relationshipTypes: $rt, samplingSize: 64, samplingSeed: 42})
                YIELD node, score
                RETURN labels(node)[0] AS label, node.id AS id, node.name AS name, score
                ORDER BY score DESC LIMIT 6""".replace("$rt", json.dumps(bt)), tag="algo.betweenness")
            notes.append("algo.betweenness: native (sampled, seed 42)")
        except Exception as ex:
            notes.append(f"algo.betweenness failed ({str(ex)[:60]}); used degree fallback")
            betw, _ = db.rows(graph_name, """
                MATCH (n) WHERE n:Service OR n:Engineer OR n:Repository
                OPTIONAL MATCH (n)-[r]-() RETURN labels(n)[0] AS label, n.id AS id, n.name AS name, count(r) AS score
                ORDER BY score DESC LIMIT 6""", tag="fallback.degree")
        wt = [t for t in ["OWNS", "DEPLOYED_FROM", "ASSIGNED_TO", "AUTO_REASSIGNED_TO"] if t in types]
        comps = []
        try:
            comps, _ = db.rows(graph_name, """
                CALL algo.WCC({nodeLabels: ['Service','Engineer','Repository','Ticket','Database'], relationshipTypes: %s})
                YIELD node, componentId
                RETURN componentId, collect({id: node.id, label: labels(node)[0], status: node.status}) AS members, count(node) AS size
                ORDER BY size DESC""" % json.dumps(wt), tag="algo.WCC")
            notes.append("algo.WCC: native over ownership edges")
        except Exception as ex:
            notes.append(f"algo.WCC failed ({str(ex)[:60]}); skipped")
    orphan_components = []
    for c in comps:
        members = c["members"]
        has_active = any(m["label"] == "Engineer" and m["status"] == "ACTIVE" for m in members)
        non_eng = [m for m in members if m["label"] != "Engineer"]
        if not has_active and non_eng:
            orphan_components.append({"component": c["componentId"], "node_ids": [m["id"] for m in members], "size": c["size"]})
    ownable = 18
    data = {
        "orphans": orphans,
        "orphan_count": len(orphans),
        "bus_factor_zero_ratio": round(len(orphans) / ownable, 3),
        "betweenness_top": [{**b, "score": round(b["score"], 3)} for b in betw],
        "wcc_components": len(comps),
        "orphan_components": orphan_components,
    }
    prov = [o["id"] for o in orphans] + [o for oo in orphans for o in oo["former_owners"]] + [b["id"] for b in betw]
    return _wrap(tr, data, prov + target_node_ids, notes)


# ---------------------------------------------------------------------------
# 4. reconstruct_tribal_context
# ---------------------------------------------------------------------------
def reconstruct_tribal_context(graph_name: str, orphaned_node_ids: list[str]):
    dossiers = []
    prov = list(orphaned_node_ids)
    with db.trace() as tr:
        for oid in orphaned_node_ids:
            commits, _ = db.rows(graph_name, """
                MATCH (o {id: $oid})-[:BLOCKS|DEPLOYED_FROM*0..2]->(r:Repository)<-[:MODIFIED_IN]-(c:Commit)
                OPTIONAL MATCH (a:Engineer)-[:AUTHORED]->(c)
                RETURN DISTINCT c.id AS id, c.hash AS hash, c.message AS message, c.risk_level AS risk, c.timestamp AS ts,
                       r.id AS repo, a.id AS author_id, a.name AS author
                ORDER BY c.timestamp DESC""", {"oid": oid}, "context")
            related = {oid} | {c["id"] for c in commits} | {c["repo"] for c in commits}
            more, _ = db.rows(graph_name, """
                MATCH (o {id: $oid})-[:BLOCKS|DEPLOYED_FROM*0..2]->(x) RETURN collect(DISTINCT x.id) AS ids""",
                {"oid": oid}, "context")
            related |= set(more[0]["ids"] if more else [])
            slack, _ = db.rows(graph_name, """
                MATCH (s:SlackThread)-[:EXPLAINS]->(y) WHERE y.id IN $ids
                RETURN DISTINCT s.id AS id, s.channel AS channel, s.author AS author, s.snippet AS snippet, collect(DISTINCT y.id) AS explains""",
                {"ids": list(related)}, "context")
            adrs, _ = db.rows(graph_name, """
                MATCH (y)-[:GOVERNED_BY]->(a:ADR_Doc) WHERE y.id IN $ids
                RETURN DISTINCT a.id AS id, a.title AS title, a.summary AS summary, a.rule_type AS rule_type""",
                {"ids": list(related)}, "context")
            sources = (
                [{"id": s["id"], "type": "SlackThread", "quote": s["snippet"], "by": s["author"]} for s in slack]
                + [{"id": c["id"], "type": "Commit", "quote": c["message"], "by": c["author"], "risk": c["risk"]} for c in commits]
                + [{"id": a["id"], "type": "ADR_Doc", "quote": a["summary"], "title": a["title"]} for a in adrs]
            )
            p = [oid] + [s["id"] for s in sources]
            prov += p
            dossiers.append({"orphan_id": oid, "sources": sources, "provenance_path": p})
    return _wrap(tr, {"dossiers": dossiers}, prov)


# ---------------------------------------------------------------------------
# 5. find_optimal_successors
# ---------------------------------------------------------------------------
SUCCESSOR_Q = """
MATCH (e:Engineer {status:'ACTIVE'})
OPTIONAL MATCH (e)-[:AUTHORED]->(ca:Commit)-[:MODIFIED_IN]->(r:Repository) WHERE r.id IN $repos
WITH e, count(DISTINCT ca) AS authored
OPTIONAL MATCH (e)-[:REVIEWED]->(cr:Commit)-[:MODIFIED_IN]->(r2:Repository) WHERE r2.id IN $repos
WITH e, authored, count(DISTINCT cr) AS reviewed
OPTIONAL MATCH (e)-[:OWNS]->(s:Service)-[:DEPENDS_ON*0..2]-(f:Service) WHERE f.id IN $svcs
WITH e, authored, reviewed, count(DISTINCT s) AS adjacent
OPTIONAL MATCH (e)-[:MEMBER_OF]->(t:Team)<-[:MEMBER_OF]-(x:Engineer) WHERE x.id IN $former
WITH e, authored, reviewed, adjacent, count(DISTINCT x) AS teammates
OPTIONAL MATCH (e)-[:AUTHORED]->(v:Commit {risk_level:'VIOLATION'})
WITH e, authored, reviewed, adjacent, teammates, count(DISTINCT v) AS violations
OPTIONAL MATCH (e)-[:MAINTAINED_BY_SRE|AUDITS|REVIEWED|MODIFIED_IN|DEPLOYED_FROM*1..3]-(z) WHERE z.id IN $reach
WITH e, authored, reviewed, adjacent, teammates, violations, count(DISTINCT z) AS path_hits
WITH e, authored, reviewed, adjacent, teammates, violations, path_hits,
     CASE WHEN path_hits > 0 THEN 30.0 ELSE 0.0 END AS multihop_pts,
     40.0 * CASE WHEN (authored * 2 + reviewed) / 3.0 > 1.0 THEN 1.0 ELSE (authored * 2 + reviewed) / 3.0 END AS commit_pts,
     CASE WHEN adjacent > 0 THEN 25.0 ELSE 0.0 END AS adjacency_pts,
     CASE WHEN teammates > 0 THEN 20.0 ELSE 0.0 END AS team_pts,
     0.3 * e.load + 30.0 * CASE WHEN violations > 0 THEN 1.0 ELSE 0.0 END AS load_penalty
RETURN e.id AS id, e.name AS name, e.role AS role, e.team AS team, e.load AS load, authored, reviewed, adjacent,
       violations, path_hits, commit_pts, adjacency_pts, team_pts, multihop_pts, load_penalty,
       commit_pts + adjacency_pts + team_pts + multihop_pts - load_penalty AS score
ORDER BY score DESC
"""
MAX_SCORE = 115.0  # 40 commits + 25 adjacency + 20 team + 30 multi-hop


def find_optimal_successors(graph_name: str, orphaned_node_ids: list[str]):
    matches = []
    prov = list(orphaned_node_ids)
    with db.trace() as tr:
        vrows, _ = db.rows(graph_name, """
            MATCH (e:Engineer)-[:AUTHORED]->(c:Commit {risk_level:'VIOLATION'})
            OPTIONAL MATCH (:Service)-[v:DIRECT_WRITES_TO {via: c.id}]->(d:Database)
            OPTIONAL MATCH (adr:ADR_Doc {rule_type:'FORBID_DIRECT_DB_WRITE'}) WHERE adr.forbidden_target = d.id
            RETURN e.id AS eid, c.id AS commit, adr.id AS adr""", tag="successor")
        viol_by = {r["eid"]: {"commit": r["commit"], "adr": r["adr"] or "ADR",
                              "adr_label": (r["adr"] or "ADR").upper().replace("ADR_", "ADR-")} for r in vrows}
        for oid in orphaned_node_ids:
            ctx, _ = db.rows(graph_name, """
                MATCH (o {id:$oid})
                OPTIONAL MATCH (o)-[:BLOCKS|DEPLOYED_FROM*0..2]->(x)
                OPTIONAL MATCH (f:Engineer)-[:FORMERLY_OWNED|FORMERLY_ASSIGNED]->(o)
                RETURN collect(DISTINCT x.id) AS reach, collect(DISTINCT f.id) AS former""", {"oid": oid}, "successor")
            reach = [r for r in (ctx[0]["reach"] if ctx else []) if r] + [oid]
            former = ctx[0]["former"] if ctx else []
            ranked, _ = db.rows(graph_name, SUCCESSOR_Q,
                                {"repos": reach, "svcs": reach, "former": former, "reach": reach}, "successor")
            for r in ranked:
                r["compatibility"] = round(min(100.0, max(0.0, r["score"]) / MAX_SCORE * 100), 1)
                r["score"] = round(r["score"], 2)
            top = next((r for r in ranked if not r["violations"]), ranked[0] if ranked else None)
            disq = []
            for r in ranked:
                if r["violations"] and r["score"] + 30 > 0:  # base_score > 0: a genuine contender actively blocked
                    would = round(r["score"] + 30, 2)
                    disq.append({"id": r["id"], "name": r["name"], "would_have_scored": would,
                                 "reason": f"Penalized -30 pts: authored {viol_by.get(r['id'], {}).get('commit', 'a VIOLATION commit')} "
                                           f"violating {viol_by.get(r['id'], {}).get('adr', 'an ADR')} (Direct DB Write)",
                                 "badge": "BLOCKED BY GRAPH POLICY (" + viol_by.get(r["id"], {}).get("adr_label", "ADR") + ")"})
                    prov += [r["id"]] + [x for x in viol_by.get(r["id"], {}).values() if isinstance(x, str) and "_" in x and " " not in x]
            matches.append({"orphan_id": oid, "former_owners": former, "ranked": ranked[:5], "winner": top,
                            "disqualified_candidates": disq,
                            "proof_path": [oid] + ([top["id"]] if top else [])})
            prov += [oid] + [r["id"] for r in ranked[:5]] + former
    return _wrap(tr, {"matches": matches}, prov)


# ---------------------------------------------------------------------------
# 6. detect_organizational_contradictions
# ---------------------------------------------------------------------------
def detect_organizational_contradictions(graph_name: str):
    with db.trace() as tr:
        rows, _ = db.rows(graph_name, """
            MATCH (s:Service)-[v:DIRECT_WRITES_TO]->(d:Database)
            MATCH (adr:ADR_Doc {rule_type:'FORBID_DIRECT_DB_WRITE'})
            WHERE adr.forbidden_target = d.id AND s.id <> adr.allowed_writer
            OPTIONAL MATCH (c:Commit {id: v.via})
            OPTIONAL MATCH (a:Engineer)-[:AUTHORED]->(c)
            OPTIONAL MATCH (sl:SlackThread)-[:EXPLAINS]->(c)
            RETURN s.id AS service, s.name AS service_name, s.tier AS tier, d.id AS database, d.name AS database_name,
                   adr.id AS adr_id, adr.title AS adr_title, adr.summary AS adr_summary,
                   c.id AS commit_id, c.hash AS hash, c.message AS commit_message, c.timestamp AS ts,
                   a.id AS author_id, a.name AS author, sl.id AS slack_id, sl.snippet AS slack_snippet""",
            tag="contradictions")
    with db.trace() as tr3:
        resolved, _ = db.rows(graph_name, """
            MATCH (s:Service)-[r:REMEDIATED_BY_PR]->(d:Database)
            OPTIONAL MATCH (adr:ADR_Doc {rule_type:'FORBID_DIRECT_DB_WRITE'}) WHERE adr.forbidden_target = d.id
            RETURN s.id AS service, d.id AS database, adr.id AS adr_id, adr.title AS adr_title, r.pr AS pr, r.at AS at""",
                              tag="contradictions")
    tr.extend(tr3)
    prov = [i for r in rows for i in (r["service"], r["database"], r["adr_id"], r["commit_id"], r["author_id"], r["slack_id"])]
    return _wrap(tr, {"contradictions": rows, "count": len(rows), "resolved": resolved}, prov)


def balanced_plan(matches: list[dict]) -> list[dict]:
    """Pareto-style assignment: best non-violating candidate per orphan, with an 8-pt penalty per system already taken."""
    plan, taken = [], {}
    for m in matches:
        cands = [r for r in m["ranked"] if not r["violations"]] or m["ranked"]
        if not cands:
            continue
        w = max(cands, key=lambda r: r["score"] - 8 * taken.get(r["id"], 0))
        adj = w["score"] - 8 * taken.get(w["id"], 0)
        taken[w["id"]] = taken.get(w["id"], 0) + 1
        plan.append({"orphan": m["orphan_id"], "successor": w["id"], "successor_name": w["name"], "score": round(adj, 2),
                     "confidence": round(max(0.0, adj) / MAX_SCORE, 3), "proof_path": [m["orphan_id"], w["id"]]})
    return plan


# ---------------------------------------------------------------------------
# healing helper (used by Continuity-Healer and tool 7)
# ---------------------------------------------------------------------------
def apply_healing(graph_name: str, plan: list[dict], extinct_tech: list[str], impacted_ids: list[str]):
    """Rewire the sandbox: AUTO_REASSIGNED_TO for orphans, FAILOVER_REPLICA/ROUTE for dead services."""
    with db.trace() as tr:
        items = [{"s": p["successor"], "o": p["orphan"], "c": p["confidence"], "sc": p["score"]} for p in plan if p.get("successor")]
        if items:
            db.q(graph_name, """
                UNWIND $items AS i
                MATCH (s:Engineer {id: i.s}), (o {id: i.o})
                CREATE (s)-[:AUTO_REASSIGNED_TO {confidence: i.c, score: i.sc, timestamp: timestamp()}]->(o)""",
                 {"items": items}, "heal")
        if extinct_tech:
            db.q(graph_name, """
                MATCH (t) WHERE t.id IN $ids AND (t:Service OR t:Database)
                CREATE (r:Service {id: t.id + '_replica', name: 'Warm Replica · ' + t.name, status: 'WARM_STANDBY',
                                   tier: coalesce(t.tier, 'TIER_1'), rps: 0, replica_of: t.id})
                CREATE (t)-[:FAILOVER_REPLICA {promoted_at: timestamp()}]->(r)
                SET t.failover = true""", {"ids": extinct_tech}, "heal")
            db.q(graph_name, """
                MATCH (c:Service)-[:DEPENDS_ON]->(t) WHERE t.id IN $ids AND c.replica_of IS NULL
                MATCH (r:Service {replica_of: t.id})
                CREATE (c)-[:FAILOVER_ROUTE {via: t.id}]->(r)""", {"ids": extinct_tech}, "heal")
        if impacted_ids:
            db.q(graph_name, "MATCH (s:Service) WHERE s.id IN $ids AND s.status = 'IMPACTED' SET s.status = 'RECOVERED'",
                 {"ids": impacted_ids}, "heal")
    return tr


def survivability(graph_name: str):
    """Tier-weighted mean continuity of every active Service and owned Repository.

    continuity(asset) = availability x ownership
      availability: 1.0 healthy/recovered, FAILOVER_AVAIL if extinct but a replica was promoted, 0 if extinct/impacted
      ownership:    OWN_NATIVE (1.0) via [:OWNS], OWN_HEALED (0.96) via [:AUTO_REASSIGNED_TO], 0 if orphaned
    weights: Tier-0 service 3, Tier-1 2, Tier-2 1, Repository 1.
    """
    with db.trace() as tr:
        assets, _ = db.rows(graph_name, """
            MATCH (a) WHERE (a:Service AND a.replica_of IS NULL) OR a:Repository
            OPTIONAL MATCH (a)<-[:OWNS]-(o:Engineer {status:'ACTIVE'})
            WITH a, count(DISTINCT o) AS owned
            OPTIONAL MATCH (a)<-[:AUTO_REASSIGNED_TO]-(h:Engineer {status:'ACTIVE'})
            RETURN a.id AS id, labels(a)[0] AS label, a.tier AS tier, a.status AS status,
                   coalesce(a.failover, false) AS failover, owned, count(DISTINCT h) AS healed""", tag="survivability")
        orphans = orphan_rows(graph_name)
    num = den = 0.0
    down = rec = n_svc = 0
    for a in assets:
        w = TIER_WEIGHT.get(a["tier"], 1.0) if a["label"] == "Service" else 1.0
        st = a["status"]
        if st in ("EXTINCT", "IMPACTED"):
            avail = FAILOVER_AVAIL if a["failover"] else 0.0
        else:
            avail = 1.0
        own = OWN_NATIVE if a["owned"] else (OWN_HEALED if a["healed"] else 0.0)
        num += w * avail * own
        den += w
        if a["label"] == "Service":
            n_svc += 1
            if st in ("EXTINCT", "IMPACTED") and not a["failover"]:
                down += 1
            if st == "RECOVERED" or a["failover"]:
                rec += 1
    score = round(100 * num / den, 1) if den else 100.0
    return {"score": score, "services_total": n_svc, "services_down": down, "services_recovered": rec,
            "orphans": len(orphans), "queries": len(tr)}


# ---------------------------------------------------------------------------
# 7. consolidate_episodic_to_procedural_memory
# ---------------------------------------------------------------------------
def consolidate_episodic_to_procedural_memory(session_id: str, target_node_ids: list[str]):
    sig = signature(target_node_ids)
    sim = sim_name(session_id)
    with db.trace() as tr:
        healed = db.rows(sim, "MATCH ()-[r:AUTO_REASSIGNED_TO]->() RETURN count(r) AS c", tag="consolidate")[0][0]["c"]
        steps, _ = db.rows(PROD, """
            MATCH (ep:Episode {session_id: $sid})-[:STEP]->(s:EpisodicStep)
            RETURN s.id AS id, s.agent AS agent, s.action AS action, s.seq AS seq, s.n_queries AS nq, s.latency_ms AS ms,
                   s.plan_json AS plan, s.snapshot_json AS snap
            ORDER BY s.seq""", {"sid": session_id}, "consolidate")
        plan_json = next((s["plan"] for s in reversed(steps) if s["plan"]), None)
        snap_json = next((s["snap"] for s in reversed(steps) if s["snap"]), None)
        if plan_json is None:
            # fast-path sessions carry no learned plan: never overwrite an existing playbook with an empty one
            return _wrap(tr, {"playbook_id": None, "signature": sig, "episodic_steps_fused": 0, "reassignments_applied": healed,
                              "session1_queries": 0, "version": None, "skipped": "session has no deliberation steps to distill"}, [])
        n_queries = sum(s["nq"] or 0 for s in steps)
        total_ms = sum(s["ms"] or 0 for s in steps)
        pid = "proc_" + hashlib.sha1(sig.encode()).hexdigest()[:10]
        pb, _ = db.rows(PROD, """
            MERGE (p:ProceduralPlaybook {id: $pid})
            ON CREATE SET p.version = 1, p.hits = 0
            ON MATCH SET p.version = p.version + 1
            SET p.signature = $sig, p.name = $name, p.confidence = $conf, p.avg_latency_ms = $ms,
                p.steps = $steps, p.session1_queries = $nq, p.plan_json = $plan, p.snapshot_json = $snap,
                p.source_session = $sid, p.created_at = timestamp()
            WITH p
            MATCH (ep:Episode {session_id: $sid})
            MERGE (ep)-[:DISTILLED_INTO]->(p)
            RETURN p.id AS id, p.version AS version""",
                        {"pid": pid, "sig": sig, "sid": session_id,
                         "name": "Chaos Vaccine · " + " + ".join(sorted(target_node_ids)),
                         "conf": 0.97, "ms": round(total_ms, 2), "steps": len(steps), "nq": n_queries,
                         "plan": plan_json, "snap": snap_json}, "consolidate")
        db.q(PROD, """
            MATCH (p:ProceduralPlaybook {id: $pid}) MATCH (n) WHERE n.id IN $t
            MERGE (p)-[:APPLIES_TO]->(n)""", {"pid": pid, "t": target_node_ids}, "consolidate")
    data = {"playbook_id": pid, "signature": sig, "episodic_steps_fused": len(steps), "reassignments_applied": healed,
            "session1_queries": n_queries, "version": pb[0]["version"] if pb else 1}
    return _wrap(tr, data, [pid] + target_node_ids + [s["id"] for s in steps])


def lookup_playbook(sig: str):
    """Single 1-hop Cypher match used for the procedural fast path."""
    rs, ms = db.rows(PROD, """
        MATCH (p:ProceduralPlaybook {signature: $sig})
        SET p.hits = coalesce(p.hits, 0) + 1
        RETURN p.id AS id, p.name AS name, p.plan_json AS plan_json, p.snapshot_json AS snapshot_json,
               p.session1_queries AS session1_queries, p.hits AS hits, p.confidence AS confidence""",
                     {"sig": sig}, "procedural-lookup")
    return (rs[0] if rs else None), ms


TOOLS = {
    "fork_chaos_sandbox": {
        "fn": fork_chaos_sandbox,
        "description": "Clone prod_company into an isolated sim_extinction_<session> tenant (graph.copy) and mark targets EXTINCT.",
        "input_schema": {"type": "object", "properties": {"session_id": {"type": "string"}, "target_node_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["session_id", "target_node_ids"]},
    },
    "compute_technical_blast_radius": {
        "fn": compute_technical_blast_radius,
        "description": "Multi-hop upstream failure cascade + algo.pageRank weighting, RPS at risk, Tier-0 SLA breaches.",
        "input_schema": {"type": "object", "properties": {"graph_name": {"type": "string"}, "target_node_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["graph_name", "target_node_ids"]},
    },
    "compute_orphaned_tribal_knowledge": {
        "fn": compute_orphaned_tribal_knowledge,
        "description": "Find bus_factor==0 services/repos/tickets; algo.betweenness + algo.WCC for org fragmentation.",
        "input_schema": {"type": "object", "properties": {"graph_name": {"type": "string"}, "target_node_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["graph_name", "target_node_ids"]},
    },
    "reconstruct_tribal_context": {
        "fn": reconstruct_tribal_context,
        "description": "Traverse commits, Slack threads and ADRs around orphaned nodes to recover undocumented operational knowledge.",
        "input_schema": {"type": "object", "properties": {"graph_name": {"type": "string"}, "orphaned_node_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["graph_name", "orphaned_node_ids"]},
    },
    "find_optimal_successors": {
        "fn": find_optimal_successors,
        "description": "Deterministic Cypher Topological Successor Match Score across surviving engineers.",
        "input_schema": {"type": "object", "properties": {"graph_name": {"type": "string"}, "orphaned_node_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["graph_name", "orphaned_node_ids"]},
    },
    "detect_organizational_contradictions": {
        "fn": detect_organizational_contradictions,
        "description": "Find DIRECT_WRITES_TO edges that violate FORBID_DIRECT_DB_WRITE ADRs and trace to commit/Slack/engineer.",
        "input_schema": {"type": "object", "properties": {"graph_name": {"type": "string"}}, "required": ["graph_name"]},
    },
    "consolidate_episodic_to_procedural_memory": {
        "fn": consolidate_episodic_to_procedural_memory,
        "description": "Fuse a session's EpisodicSteps into a permanent ProceduralPlaybook keyed by the failure signature.",
        "input_schema": {"type": "object", "properties": {"session_id": {"type": "string"}, "target_node_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["session_id", "target_node_ids"]},
    },
}
