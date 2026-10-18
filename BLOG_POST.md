# Why Flat Context Fails During Outages: Building a Speculative Chaos Time-Machine & 0.6ms Procedural Agent Memory on FalkorDB

*A write-up of **ButterflyOS**, a neuro-symbolic agent system built on FalkorDB for Graph Hacks: Context for AI Agents. All numbers below come from live runs against a FalkorDB container on a laptop; where they vary between runs, the range is given.*

---

## The 3 a.m. problem

Two sentences keep CTOs awake:

1. *"What breaks if this service goes down?"*
2. *"What happens if our lead architect quits tomorrow?"*

They look like different questions. They are the same question asked of two different graphs — the **runtime dependency graph** and the **knowledge-ownership graph** — and the worst incidents happen when both fail at once: the sharded token store stalls on a clock-skew edge case, and the one person who knows the `kvctl --realign-epoch 15ms` incantation left last Friday.

We built ButterflyOS to let you *rehearse* that nightmare. Click a Tier-0 service **and** the Staff Architect who owns it, press **Simulate Extinction**, and a swarm of agents tells you what burns, who is now an orphan of knowledge, who should inherit it, and which policy the "fix" would violate.

## Why LLM agents hallucinate during cascading failures

Give a vanilla RAG agent the incident channel, the runbooks and the wiki, and ask *"what is the blast radius of losing `svc_token_kv`?"* It will produce something fluent. It will also be wrong in the specific, dangerous way fluent text is wrong:

- **The answer is a path, not a passage.** `svc_payment → svc_ledger → svc_token_kv` is not in any document. Nobody wrote it down; it exists only as the *composition* of two `DEPENDS_ON` edges. Embeddings retrieve text that looks like the question; they cannot compose edges.
- **The critical fact is semantically far from the question.** The Slack warning about shard 14 mentions neither "bus factor" nor "token store outage". It is connected to the commit that fixed it (`commit_8f92a`), which is connected to the repository, which is connected to the service. The link is structural.
- **"Violation" is a relationship.** ADR-002 forbids Tier-2 services from writing directly to the ledger database. Whether `svc_webhook` violates it depends on a `DIRECT_WRITES_TO` edge, an ADR node, and the commit that created the edge. No single chunk contains that.
- **You can't test on prod.** Any "what if" that mutates the live graph is a non-starter.

Every one of those is a graph traversal. So we stopped giving the agents documents and gave them a graph and a small set of tools.

## Architecture: neuro-symbolic by construction

```
┌──────────────── Next.js command center ────────────────┐
│ Swarm terminal (SSE) · Force graph + Diff Mode · Panels │
└───────────────────────────┬─────────────────────────────┘
                            │ REST / SSE / MCP JSON-RPC
┌───────────────────────────▼─────────────────────────────┐
│ FastAPI                                                  │
│  Coordinator ─► Shockwave-Triage ─► BusFactor-Detector   │
│                 ─► Tribal-Archaeologist ─► Continuity-   │
│                    Healer          (each hand-off is a   │
│                                     node in the graph)   │
│  "No Node, No Action" gatekeeper (provenance_path check) │
│  7 MCP tools → {data, cypher_executed, latency_ms,       │
│                 provenance_node_ids}                     │
└───────────────────────────┬─────────────────────────────┘
                            │ falkordb-py
        ┌───────────────────▼──────────────────────┐
        │ FalkorDB                                  │
        │  prod_company         (org + memory)      │
        │  sim_extinction_<id>  (GRAPH.COPY fork)   │
        └───────────────────────────────────────────┘
```

The graph models a fictional fintech, "FinCore Cloud": 45 nodes and ~100 edges spanning engineers, teams, services, databases, repositories, commits, ADRs, Slack threads, tickets — plus the agents' own memory (`Episode`, `EpisodicStep`, `ProceduralPlaybook`). It's small on purpose; the point is the *shape*.

## Trick #1 — `GRAPH.COPY` as a copy-on-write chaos sandbox

The feature that makes "speculative" possible is FalkorDB's native multigraph tenancy. Forking production is one call:

```python
db.graph("prod_company").copy(f"sim_extinction_{session_id}")   # ~30–80 ms on our seed
```

Then we kill things — in the *fork*:

```cypher
MATCH (n) WHERE n.id IN $targets
SET n.status = 'EXTINCT', n.extinct_at = timestamp()

// an extinct engineer's ownership stops counting
MATCH (e:Engineer {status:'EXTINCT'})-[r:OWNS]->(x)
CREATE (e)-[:FORMERLY_OWNED {active:false}]->(x)
DELETE r
```

Production is never touched. A judge (or an SRE) can open the tenant switcher, pick `sim_extinction_*`, and use **Graph Diff Mode**: severed edges render dashed crimson, rewired edges glow emerald, everything else fades. The diff *is* the answer.

## Trick #2 — two shockwaves, three native algorithms

**Wave 1: technical blast radius.** Multi-hop upstream traversal, weighted by PageRank:

```cypher
MATCH path = (caller:Service)-[:DEPENDS_ON*1..5]->(t)
WHERE t.id IN $targets
RETURN caller.id, caller.rps, caller.tier,
       [n IN nodes(path) | n.id] AS path_ids, length(path) AS hops

CALL algo.pageRank('Service', 'DEPENDS_ON') YIELD node, score
RETURN node.id, score ORDER BY score DESC
```

Losing the token KV plus its owner cascades into 7 services and **289,500 RPS at risk**, with 4 Tier-0 SLAs breached. PageRank names `svc_token_kv` the chokepoint — the node everything transitively leans on.

**Wave 2: human bus factor.** An asset is *orphaned* when every owner is extinct and nobody has taken over:

```cypher
MATCH (x)<-[:FORMERLY_OWNED|FORMERLY_ASSIGNED]-(old:Engineer)
WHERE x:Service OR x:Repository OR x:Ticket OR x:Database
OPTIONAL MATCH (x)<-[:OWNS|ASSIGNED_TO|AUTO_REASSIGNED_TO]-(e:Engineer {status:'ACTIVE'})
WITH x, collect(DISTINCT old.id) AS former, count(DISTINCT e) AS bus_factor
WHERE bus_factor = 0
RETURN x.id, x.name, labels(x)[0], former
```

Then `algo.betweenness` (sampled, seeded) finds the brokers who hold the graph together, and `algo.WCC` over the ownership edges reveals *ownerless subgraphs* — components with no active engineer in them. In Scenario 1, that is five systems: the token KV, auth, two repositories and the P0 lease-migration ticket.

Two details we learned the hard way, in case they save you an afternoon:

- `algo.betweenness` rejects relationship types that don't exist in the graph. We intersect our list with `CALL db.relationshipTypes()` first.
- `shortestPath` currently has to be *directed* and live in a `WITH`/`RETURN`. Every `algo.*` call has a logged Cypher fallback, so a version difference degrades the demo instead of breaking it.

## Trick #3 — "No Node, No Action"

LLM agents are persuasive, so we made persuasion irrelevant. Every agent step must carry a `provenance_path` — a list of node IDs. Before a conclusion is accepted or a healing edge is written, a gatekeeper asks FalkorDB whether those nodes exist:

```cypher
MATCH (n) WHERE n.id IN $ids RETURN collect(n.id) AS found
```

If any ID is missing, the step is rejected. If an optional LLM is configured to *narrate* a step and cites an ID that wasn't in the facts, its prose is discarded and the deterministic, graph-derived narrative is used. This is the neuro-symbolic split: FalkorDB (Cypher, `algo.pageRank`, `algo.betweenness`, `algo.WCC`, `graph.copy`) decides what is true; a pluggable LLM synthesis layer (`OPENAI_API_KEY` / `GROQ_API_KEY` / `GEMINI_API_KEY`) only phrases it. The graph is always the source of truth.

### The 30 points that stopped a policy violator inheriting the ledger

The Continuity-Healer picks a successor for each orphan with a deterministic Cypher score:

| Signal | Points |
|---|---|
| Authored/reviewed commits in the orphan's repos | up to +40 |
| Owns a service within 2 `DEPENDS_ON` hops | +25 |
| Same team as the lost owner | +20 |
| Any 1..3-hop `MAINTAINED_BY_SRE` / `AUDITS` / `REVIEWED` path to the orphan | +30 |
| Workload | −0.3 × load |
| **Authored a `VIOLATION` commit** | **−30** |

Kabir Sen is on the same team as the engineer who owns the ledger, has low load, and reviews auth-core commits. On raw proximity he is a genuine contender: for `svc_auth` he would have scored 69.7, above the engineer who was ultimately chosen. Then one clause intervenes: `OPTIONAL MATCH (e)-[:AUTHORED]->(:Commit {risk_level:'VIOLATION'})`. Kabir wrote `commit_bad_sync`, the quick fix that made the webhook service write straight into the ledger database in violation of ADR-002. The graph docked him 30 points, he dropped down the ranking, and the UI shows a **BLOCKED BY GRAPH POLICY (ADR-002)** badge with the reason and the score he *would* have had. The badge only appears when the pre-penalty score was positive, so it always marks a real promotion that the policy prevented. No prompt told the system to do that. A relationship did.

In both demo scenarios, 5 of 5 orphans are re-homed with `[:AUTO_REASSIGNED_TO]` edges. Survivability is a plain weighted mean of asset continuity (native `[:OWNS]` = 1.0, swarm-healed `[:AUTO_REASSIGNED_TO]` = 0.96 for a 4 % onboarding overhead, tier-weighted over services and repositories) and lands at **98.2 %** with no tuning.

## Trick #4 — memory that compresses itself

Agent memory is usually "a vector store of past chats." We stored it as what it actually is — a graph of what happened and who handed what to whom:

```
(:Episode)-[:STEP]->(:EpisodicStep)-[:HANDOFF_TO]->(:EpisodicStep)
```

Each agent action is a node; each hand-off between agents is an edge. After Session 1, **Vaccinate** fuses those steps into a permanent procedural node:

```cypher
MERGE (p:ProceduralPlaybook {id: $pid})
SET p.signature = $sig,            // sorted target ids, e.g. 'eng_arjun+svc_token_kv'
    p.plan_json = $plan,           // the learned reassignments
    p.snapshot_json = $snapshot
WITH p MATCH (ep:Episode {session_id: $sid})
MERGE (ep)-[:DISTILLED_INTO]->(p)
```

In Session 2 the Coordinator's first move is a single hop:

```cypher
MATCH (p:ProceduralPlaybook {signature: $sig}) RETURN p.plan_json, p.snapshot_json
```

### Benchmarks from our runs

| | Session 1 — cold, episodic swarm | Session 2 — vaccinated recall |
|---|---|---|
| Cypher queries for reasoning | **44** (43 in our first run; the fixed seed grew by one edge set) | **1** |
| Agents coordinated via graph hand-offs | 4 | — (playbook replay) |
| Lookup latency | ~40 ms total DB time across the swarm | **0.6 ms** best case, 0.6–1.4 ms observed |
| Replaying the plan onto the fresh fork | — | ~2.4–8 ms |
| Query reduction | — | **97.7 %** (1 vs 44) |

Measurement notes: the 0.6 ms figure is the playbook *lookup*, one query, with the Python round-trip included (server-side time is lower still). Forking the sandbox (~30–80 ms) and replaying the plan onto it are reported separately in the UI rather than folded into a headline number. The graph is small; the transferable result is the ratio of queries, not the absolute milliseconds.

## Trick #5 — put a dollar figure on the blast radius

Technical impact is easy to wave away; revenue isn't. We added three enterprise contracts to the graph, `(:CustomerContract)-[:SLA_DEPENDS_ON {penalty_per_min_usd}]->(:Service)`, and extended the blast-radius traversal so the same multi-hop walk that finds failing services also finds the contracts standing on them:

```cypher
MATCH (c:CustomerContract)-[:SLA_DEPENDS_ON]->(s:Service) WHERE s.id IN $impacted
RETURN c.id, c.client, c.arr_usd, c.penalty_per_min_usd, collect(DISTINCT s.id)
```

Losing the token KV and its architect puts **$19.5M of ARR** and **$14,500 per minute** of SLA penalties on the table. The console shows both next to the RPS figure, so the answer to "what breaks?" arrives in the unit a board cares about.

## Trick #6 — let the graph find the nightmare you didn't think to click

Nobody should have to guess which engineer-plus-service pair is the lethal one. `discover_existential_blindspot` evaluates all 48 Engineer + Service pairs from live graph state: ARR exposure through `SLA_DEPENDS_ON`, the failure cascade, sole-ownership (bus factor 1) weighted by asset criticality, and PageRank/betweenness centrality. Its first run produced a surprise: two pairs tied exactly, because engineers are leaf nodes with zero betweenness and the raw count of orphaned assets was identical. Weighting orphaned knowledge by criticality (Tier-0 services and P0 tickets count more) broke the tie in the right direction. The #1 pair is Arjun Mehta plus the token KV store at **92.8 / 100**, with the Cypher that reproduces its $19.5M exposure returned as proof.

## Trick #7 — a tournament of parallel universes

Because forking is cheap, we can ask a better question than "what is the plan?": *which of several plans survives contact with the graph?* The tournament forks `prod_company` into three isolated tenants, applies a different strategy in each, and measures the resulting graphs with Cypher:

- **Single hero:** everything goes to the best-matching engineer. Peak load 106 %, five new single points of failure. Rejected.
- **Naive lowest-load:** everything goes to whoever is least busy. Policy compliance 0 %, because that engineer is the author of the ADR-002 violation. Rejected.
- **Pareto guild:** a load-aware, ADR-compliant matcher that adds secondary owners on critical assets. Peak load 85 %, 100 % compliance, zero orphans. Winner.

One engineering note: FalkorDB serves a single `GRAPH.COPY` of a given source at a time, so the three forks run back-to-back (about 30–100 ms each here) and the three evaluations run concurrently. We report both numbers rather than call the whole thing parallel.

## Trick #8 — from finding to fix

The same graph that detected the ADR-002 violation can draft the remedy. It reads the forbidden `DIRECT_WRITES_TO` edge, the prescribed async route, the owners of that route (the PR's reviewers, taken from `[:OWNS]` edges) and the ARR sitting behind the ledger, then produces a unified diff and a one-page executive memo. Applying the patch deletes the forbidden edge, records `[:REMEDIATED_BY_PR]`, and the contradiction flips to resolved on screen. The patch body is a template filled from graph facts and is labelled as such; a human still reviews and merges.

## What we'd build next

- Weight `DEPENDS_ON` with live traffic so PageRank reflects load, not just topology.
- Decay and re-validate playbooks when the topology under their signature changes (a stale vaccine is worse than none).
- Run the swarm continuously against the production graph and page a human when `bus_factor = 0` appears *before* anyone resigns.

## The one-paragraph takeaway

Flat context answers "what does this document say?" Incidents ask "what is connected to what, who knows it, and what did we do last time?" Those are traversals, centrality scores, component analyses and subgraph forks — and FalkorDB makes all of them cheap enough to run interactively. Remove FalkorDB from ButterflyOS and nothing works; that is the point.

---

*Built with Claude Code (Anthropic); see the README for the disclosure. Source, seed, and quickstart are in the repository.*
