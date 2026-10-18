"""CEO war-room layer: existential blindspot discovery, 3-universe tournament, autonomous PR remediation."""
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import db
import mcp_tools as T

PROD = db.PROD

# Workload each newly-owned system adds to an engineer (percentage points of capacity).
LOAD_COST = {"Service": 14, "Repository": 7, "Ticket": 9, "Database": 11}


# ---------------------------------------------------------------------------
# Feature A: existential blindspot discovery (MCP tool #8)
# ---------------------------------------------------------------------------
def discover_existential_blindspot(graph_name: str = PROD, top_k: int = 3):
    """Rank every (Engineer, Service) K=2 extinction pair by compound lethality, entirely from live graph state."""
    notes = []
    with db.trace() as tr:
        svcs, _ = db.rows(graph_name, "MATCH (s:Service) WHERE s.replica_of IS NULL RETURN s.id AS id, s.name AS name", tag="blindspot")
        engs, _ = db.rows(graph_name, "MATCH (e:Engineer {status:'ACTIVE'}) RETURN e.id AS id, e.name AS name", tag="blindspot")
        callers, _ = db.rows(graph_name, """
            MATCH (c:Service)-[:DEPENDS_ON*1..5]->(t:Service) WHERE c.replica_of IS NULL
            RETURN t.id AS target, collect(DISTINCT c.id) AS callers""", tag="blindspot")
        contracts, _ = db.rows(graph_name, """
            MATCH (c:CustomerContract)-[:SLA_DEPENDS_ON]->(s:Service)
            RETURN c.id AS id, c.client AS client, c.arr_usd AS arr, c.penalty_per_min_usd AS pen, collect(s.id) AS services""",
                               tag="blindspot")
        owned, _ = db.rows(graph_name, """
            MATCH (x)<-[:OWNS|ASSIGNED_TO]-(e:Engineer {status:'ACTIVE'})
            WHERE x:Service OR x:Repository OR x:Database OR x:Ticket
            RETURN x.id AS asset, labels(x)[0] AS label, x.tier AS tier, x.priority AS priority, collect(DISTINCT e.id) AS owners""", tag="blindspot")
        try:
            pr_rows, _ = db.rows(graph_name, "CALL algo.pageRank('Service','DEPENDS_ON') YIELD node, score RETURN node.id AS id, score", tag="algo.pageRank")
            pr = {r["id"]: r["score"] for r in pr_rows}
            notes.append("algo.pageRank: native")
        except Exception:
            pr = {}
            notes.append("algo.pageRank unavailable; centrality uses betweenness only")
        types = T._rel_types(graph_name)
        bt = [t for t in ["DEPENDS_ON", "OWNS", "AUTHORED", "MODIFIED_IN", "DEPLOYED_FROM"] if t in types]
        try:
            import json as _json
            bw_rows, _ = db.rows(graph_name, """
                CALL algo.betweenness({nodeLabels: ['Service','Engineer','Repository','Commit'], relationshipTypes: %s,
                                       samplingSize: 64, samplingSeed: 42}) YIELD node, score
                RETURN node.id AS id, score""" % _json.dumps(bt), tag="algo.betweenness")
            bw = {r["id"]: r["score"] for r in bw_rows}
            notes.append("algo.betweenness: native (sampled, seed 42)")
        except Exception:
            bw = {}
            notes.append("algo.betweenness unavailable")

    n_svc = max(1, len(svcs))
    caller_map = {r["target"]: set(r["callers"]) for r in callers}
    total_arr = sum(c["arr"] for c in contracts) or 1
    sole = {e["id"]: [a["asset"] for a in owned if a["owners"] == [e["id"]]] for e in engs}  # bus_factor == 1 assets
    def weight(a):  # criticality of the knowledge that disappears with a sole owner
        if a["label"] == "Service":
            return {"TIER_0": 3.0, "TIER_1": 2.0}.get(a["tier"], 1.0)
        if a["label"] == "Ticket":
            return {"P0": 3.0, "P1": 1.5}.get(a["priority"], 1.0)
        return 1.0
    by_asset = {a["asset"]: a for a in owned}
    orph_w = {eid: sum(weight(by_asset[x]) for x in xs) for eid, xs in sole.items()}
    max_orph = max(list(orph_w.values()) + [1e-9])
    max_pr = max(list(pr.values()) + [1e-9])
    max_bw = max(list(bw.values()) + [1e-9])

    pairs = []
    for e in engs:
        for s in svcs:
            impacted = {s["id"]} | caller_map.get(s["id"], set())
            hit = [c for c in contracts if impacted & set(c["services"])]
            arr = sum(c["arr"] for c in hit)
            burn = sum(c["pen"] for c in hit)
            orph = sole[e["id"]]
            comp = {
                "arr": arr / total_arr,
                "cascade": len(impacted) / n_svc,
                "orphans": orph_w[e["id"]] / max_orph,
                "centrality": (pr.get(s["id"], 0) / max_pr + bw.get(s["id"], 0) / max_bw + bw.get(e["id"], 0) / max_bw) / 3,
            }
            score = 100 * (0.35 * comp["arr"] + 0.25 * comp["cascade"] + 0.25 * comp["orphans"] + 0.15 * comp["centrality"])
            pairs.append({
                "engineer": {"id": e["id"], "name": e["name"]}, "service": {"id": s["id"], "name": s["name"]},
                "lethality_score": round(score, 1), "arr_exposed_usd": arr, "burn_rate_per_min_usd": burn,
                "orphaned_artifacts": orph, "orphaned_count": len(orph), "impacted_services": sorted(impacted),
                "contracts": [{"id": c["id"], "client": c["client"], "arr_usd": c["arr"]} for c in hit],
                "components": {k: round(v, 3) for k, v in comp.items()},
            })
    pairs.sort(key=lambda p: -p["lethality_score"])
    top = pairs[:top_k]

    proof = """MATCH (e:Engineer {id: $eng}), (s:Service {id: $svc})
OPTIONAL MATCH (caller:Service)-[:DEPENDS_ON*1..5]->(s)
WITH e, s, collect(DISTINCT caller) + [s] AS hit
UNWIND hit AS h
OPTIONAL MATCH (c:CustomerContract)-[:SLA_DEPENDS_ON]->(h)
WITH e, s, hit, collect(DISTINCT c) AS cs
RETURN e.id AS engineer, s.id AS service, size(hit) AS services_down,
       reduce(a = 0, c IN cs | a + c.arr_usd) AS arr_exposed_usd,
       reduce(p = 0, c IN cs | p + c.penalty_per_min_usd) AS burn_per_min_usd"""
    verification = None
    if top:
        with db.trace() as tr_v:
            verification, _ = db.rows(graph_name, proof, {"eng": top[0]["engineer"]["id"], "svc": top[0]["service"]["id"]}, "blindspot.proof")
        tr.extend(tr_v)
        top[0]["verification_row"] = verification[0] if verification else None
    prov = []
    for p in top:
        prov += [p["engineer"]["id"], p["service"]["id"]] + p["orphaned_artifacts"] + [c["id"] for c in p["contracts"]]
    data = {
        "top": top, "pairs_evaluated": len(pairs), "blindspot": top[0] if top else None, "proof_cypher": proof,
        "weights": {"arr": 0.35, "cascade": 0.25, "orphans": 0.25, "centrality": 0.15},
        "orphan_weighting": "Tier-0 service 3, Tier-1 2, other 1; P0 ticket 3, P1 1.5",
    }
    return T._wrap(tr, data, prov, notes)


T.TOOLS["discover_existential_blindspot"] = {
    "fn": discover_existential_blindspot,
    "description": "Rank every Engineer+Service K=2 extinction pair by compound lethality (ARR exposure, cascade, bus factor, PageRank/betweenness).",
    "input_schema": {"type": "object", "properties": {"graph_name": {"type": "string"}}, "required": ["graph_name"]},
}


# ---------------------------------------------------------------------------
# Feature B: 3-universe parallel multigraph tournament
# ---------------------------------------------------------------------------
STRATEGIES = {
    "alpha": {"prefix": "univ_alpha_hero", "title": "Strategy A · Single-Hero Concentration",
              "blurb": "Give every orphaned system to the single highest-scoring engineer."},
    "beta": {"prefix": "univ_beta_naive", "title": "Strategy B · Naive Lowest-Load",
             "blurb": "Give every orphaned system to whoever has the lowest workload."},
    "gamma": {"prefix": "univ_gamma_pareto", "title": "Strategy C · Pareto-Optimal Guild",
              "blurb": "Topology + load + ADR-compliance matcher, with a secondary owner on critical assets."},
}


def _apply_assignments(graph_name: str, assigns: list[dict]):
    if not assigns:
        return
    db.q(graph_name, """
        UNWIND $items AS i
        MATCH (s:Engineer {id: i.s}), (o {id: i.o})
        CREATE (s)-[:AUTO_REASSIGNED_TO {confidence: i.c, score: i.sc, role: i.role, timestamp: timestamp()}]->(o)""",
         {"items": assigns}, "tournament.apply")


def _metrics(graph_name: str):
    loads, _ = db.rows(graph_name, """
        MATCH (e:Engineer {status:'ACTIVE'})
        OPTIONAL MATCH (e)-[r:AUTO_REASSIGNED_TO]->(x)
        RETURN e.id AS id, e.name AS name, e.load AS base_load, count(x) AS assigned,
               sum(CASE WHEN r IS NULL THEN 0
                        WHEN x:Service THEN 14 WHEN x:Repository THEN 7 WHEN x:Ticket THEN 9 ELSE 11 END
                   * CASE WHEN r.role = 'secondary' THEN 0.5 ELSE 1.0 END) AS added_load
        ORDER BY e.id""", tag="tournament.metrics")
    for l in loads:
        l["load"] = round(l["base_load"] + (l["added_load"] or 0), 1)
    peak = max(loads, key=lambda l: l["load"])
    bf, _ = db.rows(graph_name, """
        MATCH (x)<-[:AUTO_REASSIGNED_TO]-(e:Engineer) WITH x, count(DISTINCT e) AS owners
        RETURN count(x) AS assets, sum(CASE WHEN owners = 1 THEN 1 ELSE 0 END) AS bf1""", tag="tournament.metrics")
    pol, _ = db.rows(graph_name, """
        MATCH (e:Engineer)-[:AUTO_REASSIGNED_TO {role:'primary'}]->(x)
        OPTIONAL MATCH (e)-[:AUTHORED]->(v:Commit {risk_level:'VIOLATION'})
        WITH x, e, count(v) AS viol
        RETURN count(x) AS total, sum(CASE WHEN viol > 0 THEN 1 ELSE 0 END) AS violating,
               collect(DISTINCT CASE WHEN viol > 0 THEN e.name END) AS violators""", tag="tournament.metrics")
    tm, _ = db.rows(graph_name, "MATCH ()-[r:AUTO_REASSIGNED_TO {role:'primary'}]->() RETURN avg(r.confidence) AS m", tag="tournament.metrics")
    orphans = T.orphan_rows(graph_name)
    total = pol[0]["total"] or 0
    violating = pol[0]["violating"] or 0
    return {
        "tech_match_pct": round((tm[0]["m"] or 0) * 100, 1),
        "peak_load_pct": peak["load"], "peak_engineer": peak["name"], "peak_engineer_id": peak["id"],
        "bus_factor_1_assets": int(bf[0]["bf1"] or 0), "assets_reassigned": int(bf[0]["assets"] or 0),
        "policy_compliance_pct": round(100 * (total - violating) / total, 1) if total else 100.0,
        "policy_violators": [v for v in pol[0]["violators"] if v],
        "orphans_remaining": len(orphans),
        "engineer_loads": [{"id": l["id"], "name": l["name"], "load": l["load"], "assigned": l["assigned"]} for l in loads],
    }


def _verdict(m: dict):
    reasons = []
    if m["orphans_remaining"] > 0:
        reasons.append(f"{m['orphans_remaining']} orphans remain")
    if m["peak_load_pct"] > 100:
        reasons.append(f"{m['peak_engineer']} at {m['peak_load_pct']}% load (burnout risk)")
    if m["policy_compliance_pct"] < 100:
        reasons.append("governance breach: " + ", ".join(m["policy_violators"]) + " violates ADR-002")
    if m["bus_factor_1_assets"] and m["bus_factor_1_assets"] >= 4 and m["peak_load_pct"] > 85:
        reasons.append(f"creates {m['bus_factor_1_assets']} new single points of failure")
    return ("REJECTED" if reasons else "ACCEPTED"), reasons


def _run_universe(key: str, sid: str, targets: list[str]):
    st = STRATEGIES[key]
    name = f"{st['prefix']}_{sid}"
    t0 = time.perf_counter()
    with db.trace() as tr:
        fork = T.fork_chaos_sandbox(sid, targets, graph_name=name)
        fork_ms = fork["data"]["copy_ms"]
        orphans = T.orphan_rows(name)
        oids = [o["id"] for o in orphans if o["label"] in ("Service", "Repository", "Ticket", "Database")]
        succ = T.find_optimal_successors(name, oids) if oids else {"data": {"matches": []}}
        matches = succ["data"]["matches"]
        by_orphan = {m["orphan_id"]: {r["id"]: r for r in m["ranked"]} for m in matches}
        assigns = []

        def item(o, eng_id, role="primary"):
            r = by_orphan.get(o, {}).get(eng_id)
            conf = round(min(100.0, max(0.0, r["score"]) / T.MAX_SCORE * 100) / 100, 3) if r else 0.0
            return {"s": eng_id, "o": o, "c": conf, "sc": r["score"] if r else 0.0, "role": role}

        if key == "alpha":
            totals: dict[str, float] = {}
            for m in matches:
                for r in m["ranked"]:
                    totals[r["id"]] = totals.get(r["id"], 0) + r["score"]
            hero = max(totals, key=totals.get) if totals else None
            assigns = [item(o, hero) for o in oids] if hero else []
        elif key == "beta":
            lows, _ = db.rows(name, "MATCH (e:Engineer {status:'ACTIVE'}) RETURN e.id AS id ORDER BY e.load ASC LIMIT 1", tag="tournament.pick")
            assigns = [item(o, lows[0]["id"]) for o in oids] if lows else []
        else:
            # load-aware Pareto matcher: topology score, minus a steep penalty once projected load passes 80%
            base, _ = db.rows(name, "MATCH (e:Engineer {status:'ACTIVE'}) RETURN e.id AS id, e.load AS load", tag="tournament.pick")
            proj = {b["id"]: float(b["load"]) for b in base}
            label = {o["id"]: o["label"] for o in orphans}
            order = sorted(matches, key=lambda m: -max([r["score"] for r in m["ranked"]] + [0]))
            prim = {}
            for m in order:
                cost = LOAD_COST.get(label.get(m["orphan_id"], "Service"), 10)
                cands = [r for r in m["ranked"] if not r["violations"]]
                if not cands:
                    continue
                def value(r):
                    after = proj[r["id"]] + cost
                    return r["score"] - max(0.0, after - 80.0) * 1.5
                w_ = max(cands, key=value)
                proj[w_["id"]] += cost
                prim[m["orphan_id"]] = w_["id"]
                assigns.append({"s": w_["id"], "o": m["orphan_id"], "c": round(min(100.0, max(0.0, w_["score"]) / T.MAX_SCORE * 100) / 100, 3),
                                "sc": w_["score"], "role": "primary"})
            # secondary owner on critical (Service / Repository) assets: next-best compliant engineer with headroom
            for m in order:
                if label.get(m["orphan_id"]) not in ("Service", "Repository") or m["orphan_id"] not in prim:
                    continue
                cost = LOAD_COST.get(label[m["orphan_id"]], 10) * 0.5
                alt = next((r for r in sorted(m["ranked"], key=lambda r: -r["score"])
                            if not r["violations"] and r["id"] != prim[m["orphan_id"]] and r["score"] > 0 and proj[r["id"]] + cost <= 85), None)
                if alt:
                    proj[alt["id"]] += cost
                    assigns.append({"s": alt["id"], "o": m["orphan_id"], "c": round(min(100.0, max(0.0, alt["score"]) / T.MAX_SCORE * 100) / 100, 3),
                                    "sc": alt["score"], "role": "secondary"})
        _apply_assignments(name, assigns)
        metrics = _metrics(name)
    verdict, reasons = _verdict(metrics)
    return {
        "key": key, "graph": name, "title": st["title"], "blurb": st["blurb"], "fork_ms": round(fork_ms, 2),
        "eval_ms": round((time.perf_counter() - t0) * 1000, 2), "queries": len(tr), "metrics": metrics,
        "assignments": [{"orphan": a["o"], "engineer": a["s"], "role": a["role"], "confidence": a["c"]} for a in assigns],
        "verdict": verdict, "reasons": reasons,
        "cypher_executed": [{"cypher": e["cypher"], "ms": e["ms"], "graph": e["graph"]} for e in tr[-6:]],
    }


def run_tournament(targets: list[str], session_id: str | None = None):
    sid = session_id or uuid.uuid4().hex[:8]
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {k: ex.submit(_run_universe, k, sid, targets) for k in STRATEGIES}
        universes = {k: f.result() for k, f in futs.items()}
    wall_ms = round((time.perf_counter() - t0) * 1000, 2)
    ordered = [universes[k] for k in ("alpha", "beta", "gamma")]
    ok = [u for u in ordered if u["verdict"] == "ACCEPTED"]
    winner = max(ok, key=lambda u: u["metrics"]["tech_match_pct"] - u["metrics"]["peak_load_pct"] * 0.5) if ok else None
    for u in ordered:
        u["is_winner"] = bool(winner and u["key"] == winner["key"])
        if u["is_winner"]:
            u["verdict"] = "WINNER"
    return {"session_id": sid, "targets": targets, "universes": ordered, "winner": winner["key"] if winner else None,
            "parallel_wall_ms": wall_ms, "sequential_sum_ms": round(sum(u["eval_ms"] for u in ordered), 2),
            "graphs": [u["graph"] for u in ordered]}


# ---------------------------------------------------------------------------
# Feature C: autonomous PR remediation + CEO board dossier
# ---------------------------------------------------------------------------
PR_NO = "#1042"


def _diff(commit_hash: str, author: str):
    return f"""diff --git a/repo_webhook_svc/dispatcher.py b/repo_webhook_svc/dispatcher.py
index {commit_hash[:7]}..4c1e9fa 100644
--- a/repo_webhook_svc/dispatcher.py
+++ b/repo_webhook_svc/dispatcher.py
@@ -41,14 +41,12 @@ def dispatch_merchant_event(event: MerchantEvent) -> None:
     payload = build_payload(event)
     deliver(event.endpoint, payload)

-    # quickfix: write the settlement row straight to the ledger to bypass queue delay
-    with psycopg2.connect(LEDGER_DSN) as conn, conn.cursor() as cur:
-        cur.execute(
-            "INSERT INTO ledger_entries (merchant_id, amount_minor, currency, ref) "
-            "VALUES (%s, %s, %s, %s)",
-            (event.merchant_id, event.amount_minor, event.currency, event.ref),
-        )
+    # ADR-002: ledger writes are asynchronous and routed through the job queue -> ledger engine
+    job_queue_client.enqueue_ledger_tx(
+        idempotency_key=f"wh:{{event.ref}}",
+        merchant_id=event.merchant_id,
+        amount_minor=event.amount_minor,
+        currency=event.currency,
+    )
"""


def remediation_brief(graph_name: str):
    with db.trace() as tr:
        viol, _ = db.rows(graph_name, """
            MATCH (s:Service)-[v:DIRECT_WRITES_TO]->(d:Database)
            MATCH (adr:ADR_Doc {rule_type:'FORBID_DIRECT_DB_WRITE'}) WHERE adr.forbidden_target = d.id AND s.id <> adr.allowed_writer
            OPTIONAL MATCH (c:Commit {id: v.via}) OPTIONAL MATCH (a:Engineer)-[:AUTHORED]->(c)
            OPTIONAL MATCH (sl:SlackThread)-[:EXPLAINS]->(c)
            RETURN s.id AS service, s.name AS service_name, d.id AS database, d.name AS database_name, adr.id AS adr_id,
                   adr.title AS adr_title, adr.allowed_writer AS allowed_writer, c.id AS commit_id, c.hash AS hash,
                   c.message AS commit_message, a.id AS author_id, a.name AS author, sl.id AS slack_id, sl.snippet AS slack""",
                         tag="remediate")
        resolved, _ = db.rows(graph_name, """
            MATCH (s:Service)-[r:REMEDIATED_BY_PR]->(d:Database)
            RETURN s.id AS service, d.id AS database, r.pr AS pr, r.at AS at""", tag="remediate")
        if not viol:
            return {"status": "RESOLVED (100% COMPLIANT)" if resolved else "NO VIOLATION", "resolved": resolved,
                    "cypher_executed": [{"cypher": e["cypher"], "ms": e["ms"], "graph": e["graph"]} for e in tr]}
        v = viol[0]
        route_ids = [v["service"], "svc_job_queue", v["allowed_writer"], v["database"]]
        hops, _ = db.rows(graph_name, """
            UNWIND range(0, size($route) - 2) AS i
            OPTIONAL MATCH (a {id: $route[i]})-[r:DEPENDS_ON]->(b {id: $route[i + 1]})
            RETURN i AS hop, $route[i] AS src, $route[i + 1] AS dst, r IS NOT NULL AS exists""", {"route": route_ids}, "remediate")
        reviewers, _ = db.rows(graph_name, """
            MATCH (e:Engineer)-[:OWNS]->(s:Service) WHERE s.id IN $route AND e.id <> $author
            RETURN DISTINCT e.id AS id, e.name AS name, collect(DISTINCT s.id) AS owns""",
                               {"route": route_ids, "author": v["author_id"]}, "remediate")
        exposure, _ = db.rows(graph_name, """
            MATCH (c:CustomerContract)-[:SLA_DEPENDS_ON]->(s:Service) WHERE s.id IN [$svc, $writer]
            RETURN DISTINCT c.id AS id, c.client AS client, c.arr_usd AS arr, c.penalty_per_min_usd AS pen""",
                              {"svc": v["service"], "writer": v["allowed_writer"]}, "remediate")
    arr = sum(c["arr"] for c in exposure)
    burn = sum(c["pen"] for c in exposure)
    handles = [r["name"].replace(" ", "_") for r in reviewers]
    memo = f"""EXECUTIVE MEMO · BOARD DOSSIER
Subject: Architectural governance breach on the ledger write path ({v['adr_id'].upper().replace('_', '-')})

What happened: {v['author']} shipped {v['commit_id']} ({v['hash']}), which makes {v['service_name']} write directly into {v['database_name']}.
{v['adr_title']} forbids this: every ledger write must route {' -> '.join(route_ids[:-1])} -> {route_ids[-1]}.
The change was acknowledged in Slack ({v['slack_id']}): "{v['slack']}"

Why it matters: the ledger underpins {len(exposure)} enterprise contracts totalling ${arr:,.0f} ARR ({', '.join(c['client'] for c in exposure)}).
An unmanaged synchronous write path bypasses queue back-pressure and idempotency; an incident here costs up to ${burn:,.0f} per minute in SLA penalties.

Remediation: PR {PR_NO} replaces the synchronous INSERT with an idempotent enqueue through {route_ids[1]}. Reviewers are the owners of the correct route: {', '.join('@' + h for h in handles)}.
Status: awaiting merge. Applying the patch removes the forbidden [:DIRECT_WRITES_TO] edge from the graph and records [:REMEDIATED_BY_PR].
Source: every figure above was read from live FalkorDB nodes: {', '.join(i for i in [v['service'], v['database'], v['adr_id'], v['commit_id'], v['author_id']] if i)}."""
    return {
        "status": "VIOLATION", "violation": v, "route": route_ids, "hops": hops,
        "missing_hops": [h for h in hops if not h["exists"]],
        "pr": {
            "number": PR_NO, "title": f"PR {PR_NO}: Fix ADR-002 Direct Ledger Write Violation", "branch": "autofix/adr-002-async-ledger-write",
            "base": "main", "labels": ["governance", "adr-002", "auto-generated"],
            "reviewers": [{"id": r["id"], "name": r["name"], "handle": "@" + r["name"].replace(" ", "_"), "owns": r["owns"]} for r in reviewers],
            "diff": _diff(v["hash"], v["author"]), "files_changed": 1,
            "note": "Patch body is generated from graph facts and a fixed template; review before merging.",
        },
        "memo": memo, "arr_exposed_usd": arr, "burn_rate_per_min_usd": burn,
        "cypher_executed": [{"cypher": e["cypher"], "ms": e["ms"], "graph": e["graph"]} for e in tr],
    }


def apply_remediation(graph_name: str):
    """Mutate the graph: drop the forbidden edge, record the PR, and add the prescribed queue->ledger route."""
    with db.trace() as tr:
        before, _ = db.rows(graph_name, "MATCH ()-[v:DIRECT_WRITES_TO]->() RETURN count(v) AS c", tag="remediate.apply")
        db.q(graph_name, """
            MATCH (s:Service)-[v:DIRECT_WRITES_TO]->(d:Database)
            MATCH (adr:ADR_Doc {rule_type:'FORBID_DIRECT_DB_WRITE'}) WHERE adr.forbidden_target = d.id AND s.id <> adr.allowed_writer
            CREATE (s)-[:REMEDIATED_BY_PR {pr: $pr, at: timestamp(), adr: adr.id}]->(d)
            DELETE v""", {"pr": PR_NO}, "remediate.apply")
        db.q(graph_name, """
            MATCH (q:Service {id:'svc_job_queue'}), (l:Service {id:'svc_ledger'})
            WHERE NOT (q)-[:DEPENDS_ON]->(l)
            CREATE (q)-[:DEPENDS_ON {criticality:'HARD', latency_budget_ms: 2, via: $pr}]->(l)""", {"pr": PR_NO}, "remediate.apply")
        after, _ = db.rows(graph_name, "MATCH ()-[v:DIRECT_WRITES_TO]->() RETURN count(v) AS c", tag="remediate.apply")
    return {"graph": graph_name, "violations_before": before[0]["c"], "violations_after": after[0]["c"],
            "status": "RESOLVED (100% COMPLIANT)" if after[0]["c"] == 0 else "VIOLATION",
            "cypher_executed": [{"cypher": e["cypher"], "ms": e["ms"], "graph": e["graph"]} for e in tr]}
