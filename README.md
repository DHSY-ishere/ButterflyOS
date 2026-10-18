# BUTTERFLY//OS — The Chaos, Blast-Radius & Bus-Factor Time-Machine

> **SimCity for CTOs.** Click any combination of nodes — a Tier-0 KV store *and* the Staff Architect who built it — and watch FalkorDB compute the technical blast radius, the orphaned human knowledge, and an autonomous 4-agent swarm that rewires the organization to survive it.

Built for **Graph Hacks: Context for AI Agents** (FalkorDB). All three tracks.

---

## Neuro-Symbolic Agent Architecture

ButterflyOS separates *what is true* from *how it is explained*:

- **Symbolic core (FalkorDB):** deterministic graph reasoning over OpenCypher and GraphBLAS-backed algorithms (`algo.pageRank`, `algo.betweenness`, `algo.WCC`) with `graph.copy` multigraph sandboxes. Seven MCP tools execute these, and every result carries its Cypher, latency and `provenance_node_ids`.
- **"No Node, No Action" validation:** no conclusion or graph mutation is accepted unless every node in its `provenance_path` exists in FalkorDB.
- **Neural layer (pluggable):** an LLM synthesis layer (`OPENAI_API_KEY` / `GROQ_API_KEY` / `GEMINI_API_KEY`) turns verified graph facts into prose, constrained to the nodes the graph returned.

## 1. Problem: flat RAG fails in a crisis

Every CTO has two nightmares: *"What breaks if this service goes down?"* and *"What happens if our lead architect quits tomorrow?"*

Both are **graph questions** — answered by multi-hop traversal, not by nearest-neighbour text similarity:

| Question | Why vector RAG fails | What the graph does |
|---|---|---|
| What breaks if `svc_token_kv` dies? | The failing service's docs say nothing about its 5-hop callers | `(caller)-[:DEPENDS_ON*1..5]->(target)` + PageRank |
| Who is the only person who understands shard 14? | Slack and the commit are semantically distant | `Engineer→Commit→Repository←Service←Slack-[:EXPLAINS]` |
| Which commit violates which policy? | "Violation" is a *relationship* between a service, a DB, an ADR and a commit | `(Service)-[:DIRECT_WRITES_TO]->(Database)` vs `(ADR_Doc {rule_type})` |
| Can I safely test "what if"? | You can't mutate prod | `GRAPH.COPY` → isolated `sim_extinction_<id>` tenant in tens of ms |

FalkorDB (sparse-matrix GraphBLAS traversal, native `algo.*`, multigraph tenancy, `GRAPH.COPY`) is the **only** reason this works interactively. Remove FalkorDB and nothing in the app functions.

## 2. Track alignment

| Track | How ButterflyOS delivers |
|---|---|
| **01 · Agents That Act on Connected Data** | 4 agents call 7 MCP graph tools (`/mcp` JSON-RPC + `/api/mcp/call`); multi-hop Cypher, `algo.pageRank/betweenness/WCC`; actions (`AUTO_REASSIGNED_TO`, `FAILOVER_ROUTE`) are chosen by graph topology; every result carries `cypher_executed`, `latency_ms`, `provenance_node_ids`. |
| **02 · Agent Memory & Coordination** | **Episodic** `(:Episode)-[:STEP]->(:EpisodicStep)-[:HANDOFF_TO]->(:EpisodicStep)`; **Semantic** = the live org topology; **Procedural** `(:ProceduralPlaybook)` distilled from Session 1 and recalled in **one Cypher hop** in Session 2. Isolated multigraph tenancy per simulation. |
| **03 · Company Brain** | People, teams, repos, commits, ADRs, Slack, tickets in one graph. "Ask the Company Brain" turns questions into live Cypher; Tribal-Archaeologist writes cited handover dossiers; contradiction detection traces policy violations to commit → Slack → engineer. |

**"No Node, No Action" gatekeeper:** every agent conclusion and healing action must carry a `provenance_path` of node IDs; `agents.gate()` verifies each ID exists in FalkorDB before the step is accepted. If an optional LLM narrates a step and cites an unknown ID, its text is rejected and the deterministic narrative is used.

## 3. Architecture

```
┌───────────────────────────── Next.js 15 Command Center (:3001) ─────────────────────────────┐
│  SwarmTerminal (SSE)      GraphCanvas (force-directed SVG)      IntelligencePanel (3 tabs)   │
└───────────────▲──────────────────────────▲───────────────────────────▲────────────────────────┘
                │ REST / SSE               │                           │
┌───────────────┴──────────────────────────┴───────────────────────────┴────────────────────────┐
│ FastAPI (:8000)  /api/graph /simulate /heal(/stream) /vaccinate /contradictions /ask /memory    │
│                  /mcp (JSON-RPC)  /api/mcp/{tools,call}                                         │
│  agents.py  Coordinator → Triage → BusFactor → Archaeologist → Healer   (+ gate, + episodes)    │
│  mcp_tools.py  7 tools, each returns {data, cypher_executed, latency_ms, provenance_node_ids}   │
└───────────────────────────────────────────┬─────────────────────────────────────────────────────┘
                                            │ falkordb-py
                       ┌────────────────────▼────────────────────┐
                       │ FalkorDB :6379                           │
                       │  prod_company (baseline + memory)        │
                       │  sim_extinction_<id> (GRAPH.COPY forks)  │
                       └──────────────────────────────────────────┘
```

### Graph data model (`prod_company`, FinCore Cloud)

```
(:Engineer {id,name,role,team,load,status,specialty,tenure_years})
(:Team) (:Service {tier,rps,sla,status}) (:Database) (:Repository)
(:Commit {hash,message,risk_level,timestamp}) (:ADR_Doc {rule_type,forbidden_target,allowed_writer})
(:SlackThread {channel,author,snippet}) (:Ticket {priority,status})
(:Episode)-[:STEP]->(:EpisodicStep)-[:HANDOFF_TO]->(:EpisodicStep)    (:ProceduralPlaybook {signature,plan_json,...})

(Service)-[:DEPENDS_ON {criticality,latency_budget_ms}]->(Service|Database)
(Service)-[:DIRECT_WRITES_TO {via}]->(Database)           ← the ADR-002 violation
(Engineer)-[:OWNS]->(Service|Repository|Database)         (Engineer)-[:AUTHORED|REVIEWED]->(Commit)
(Commit)-[:MODIFIED_IN]->(Repository)<-[:DEPLOYED_FROM]-(Service)
(Engineer)-[:ASSIGNED_TO]->(Ticket)-[:BLOCKS]->(Service)  (Engineer)-[:POSTED_IN]->(SlackThread)-[:EXPLAINS]->(Commit|Service)
(Service|Repository|Database)-[:GOVERNED_BY]->(ADR_Doc)  (Engineer)-[:MEMBER_OF]->(Team)
  -- written by the swarm into the sandbox --
(Engineer)-[:AUTO_REASSIGNED_TO {confidence,score}]->(orphan)
(Service)-[:FAILOVER_REPLICA]->(replica)  (caller)-[:FAILOVER_ROUTE]->(replica)
(Engineer)-[:FORMERLY_OWNED {active:false}]->(x)           ← extinct owners' OWNS edges, deactivated
```

Seed size: **49 nodes, 117 edges** (engineers, teams, services, databases, repositories, commits, ADRs, Slack threads, tickets, three enterprise `:CustomerContract` nodes, plus the memory baseline).

## 4. The exact Cypher & algorithms

**Fork (native copy-on-write):** `GRAPH.COPY prod_company sim_extinction_<id>` then
`MATCH (n) WHERE n.id IN $t SET n.status='EXTINCT', n.extinct_at=timestamp()`; extinct engineers' `OWNS` → `FORMERLY_OWNED {active:false}`.

**Blast radius**
```cypher
MATCH path = (caller:Service)-[:DEPENDS_ON*1..5]->(t) WHERE t.id IN $targets
RETURN caller.id, caller.rps, caller.tier, [n IN nodes(path) | n.id] AS path_ids, length(path) AS hops
```
**PageRank** — `CALL algo.pageRank('Service','DEPENDS_ON') YIELD node, score RETURN node.id, score ORDER BY score DESC`
**Betweenness** — `CALL algo.betweenness({nodeLabels:['Service','Engineer','Repository','Commit'], relationshipTypes:[…existing types…], samplingSize:64, samplingSeed:42}) YIELD node, score`
(FalkorDB rejects relationship types not present in the graph, so the list is intersected with `db.relationshipTypes()` first.)
**WCC** — `CALL algo.WCC({nodeLabels:[…], relationshipTypes:['OWNS','DEPLOYED_FROM','ASSIGNED_TO','AUTO_REASSIGNED_TO']}) YIELD node, componentId` — components with no ACTIVE engineer are *ownerless subgraphs*.
If any `algo.*` call fails, a Cypher degree fallback runs and both are logged (`algo_notes`).

**Shortest path** — FalkorDB only supports *directed* `shortestPath` in `WITH`/`RETURN`:
`MATCH (a {id:$src}),(b {id:$dst}) WITH shortestPath((a)-[*..8]->(b)) AS p RETURN [n IN nodes(p)|n.id], length(p)`

**Orphans (bus_factor = 0)**
```cypher
MATCH (x)<-[:FORMERLY_OWNED|FORMERLY_ASSIGNED]-(old:Engineer) WHERE x:Service OR x:Repository OR x:Ticket OR x:Database
OPTIONAL MATCH (x)<-[:OWNS|ASSIGNED_TO|AUTO_REASSIGNED_TO]-(e:Engineer {status:'ACTIVE'})
WITH x, collect(DISTINCT old.id) AS former_owners, count(DISTINCT e) AS bus_factor WHERE bus_factor = 0 RETURN …
```
**Successor match score** (`mcp_tools.SUCCESSOR_Q`): up to **+40** commits authored/reviewed in the orphan's repos (`min(1,(2·authored+reviewed)/3)`), **+25** owning a service within 2 `DEPENDS_ON` hops, **+20** same team as the lost owner, **+30** for any 1..3-hop `MAINTAINED_BY_SRE | AUDITS | REVIEWED | MODIFIED_IN | DEPLOYED_FROM` path to the orphan, **−0.3·load**, **−30** if the engineer authored a `VIOLATION` commit. An engineer is reported in `disqualified_candidates` (rendered as a *BLOCKED BY GRAPH POLICY (ADR-002)* badge) only when their pre-penalty score was positive, i.e. the policy actively prevented a genuine contender from being promoted. Compatibility % = score / 115. The swarm adds an 8-pt penalty per extra system already given to the same person.

**Contradictions**
```cypher
MATCH (s:Service)-[v:DIRECT_WRITES_TO]->(d:Database)
MATCH (adr:ADR_Doc {rule_type:'FORBID_DIRECT_DB_WRITE'}) WHERE adr.forbidden_target = d.id AND s.id <> adr.allowed_writer
OPTIONAL MATCH (c:Commit {id:v.via}) OPTIONAL MATCH (a:Engineer)-[:AUTHORED]->(c) OPTIONAL MATCH (sl:SlackThread)-[:EXPLAINS]->(c)
RETURN s.id, d.id, adr.id, c.id, a.name, sl.id
```
**Procedural distillation / recall** — `MERGE (p:ProceduralPlaybook {id:$pid}) SET p.signature=$sig, p.plan_json=…` linked `(Episode)-[:DISTILLED_INTO]->(p)`; recall is a single `MATCH (p:ProceduralPlaybook {signature:$sig}) RETURN p…`.

### Survivability metric
`survivability = 100 × Σ(wᵢ · availabilityᵢ · ownershipᵢ) / Σwᵢ` over every active Service and Repository, with weights Tier-0 = 3, Tier-1 = 2, Tier-2 / Repository = 1.
Availability is 1.0 for healthy or recovered assets, 0.96 for an extinct service whose warm replica was promoted, 0 for an unrecovered extinct/impacted one.
Ownership is **1.0** for a native `[:OWNS]`, **0.96** for a swarm `[:AUTO_REASSIGNED_TO]` (a 4 % onboarding handoff overhead) and 0 for an orphan. The score is computed live by Cypher; no cap or tuning is applied. Healing all five orphans in either demo scenario yields 98.2 %.

## 5. Quickstart

```bash
docker compose up -d                       # falkordb/falkordb:latest on :6379 (browser UI :3000)
python -m venv .venv && .venv/Scripts/pip install -r backend/requirements.txt   # Linux/mac: .venv/bin/pip
cd backend && ../.venv/Scripts/python seed.py                                   # seeds prod_company
../.venv/Scripts/python -m uvicorn main:app --port 8000                          # API (auto-seeds if empty)
cd ../frontend && npm install && npm run dev     # landing: http://localhost:3001  ·  console: http://localhost:3001/console
```

**Pluggable LLM synthesis layer:** set `OPENAI_API_KEY`, `GROQ_API_KEY` or `GEMINI_API_KEY` in `backend/.env` and each agent's narration is synthesised by that model. Reasoning never depends on it: every number, path, score and graph mutation is produced by FalkorDB, and any LLM output that cites a node the graph does not contain is rejected by the gatekeeper and replaced by the deterministic graph-derived narrative.

### Demo script
1. **Scenario 1** (Arjun + Token KV) → red shockwave, 5 orphaned systems, `bus_factor = 0` cards.
2. **Run Autonomous Swarm Heal & Vaccinate** → watch the 4 agents; emerald dashed `AUTO_REASSIGNED_TO` edges appear; playbook is distilled automatically.
3. **Reset Graph**, then **Scenario 3** → `FAST_PATH_HIT`: the playbook is recalled with one Cypher query.
4. Memory tab → Session 1 vs Session 2 benchmark. Company Brain tab → ask questions, audit contradictions.

## 5b. Live deployment (AWS Lightsail, one command)

```bash
pip install boto3
aws configure --profile personal                       # your own AWS account; keys stay on your machine
python deploy/deploy_lightsail.py --profile personal   # creates the VPS, ships the code, builds, prints the URL
python deploy/deploy_lightsail.py --profile personal --update    # redeploy new code
python deploy/deploy_lightsail.py --profile personal --destroy   # delete everything and stop billing
```

The script creates a 2 GB Ubuntu Lightsail instance (about $12/month), opens port 80 publicly and SSH to your IP only,
attaches a static IP, uploads the code over SSH and runs `docker-compose.prod.yml` (FalkorDB, API, frontend, nginx).
Any Docker host works too: `docker compose -f docker-compose.prod.yml up -d --build`.

The public stack runs in **demo mode** (`DEMO_MODE=1`): the hard reset requires an `X-Admin-Token`, sandbox graphs are capped at 18 and
garbage-collected oldest-first, the Cypher playground is read-only with a 3 s timeout, and nginx rate-limits fork-heavy endpoints.

## 6. Measured on a local run (not marketing numbers)

| Metric | Value |
|---|---|
| `GRAPH.COPY` fork of `prod_company` | ~30–80 ms |
| Session 1 (full deliberation) | **44** Cypher queries, ~40 ms of DB time |
| Session 2 playbook recall | **1** Cypher query, **0.6–1.4 ms** (replaying the plan onto the fork adds ~2.5–8 ms) → 97.7 % fewer queries |
| Top successor for `svc_token_kv` | Devansh Sahney, ~72 % compatibility; both scenarios re-home 5/5 orphans and reach 98.2 % survivability |

## 6b. Phase 2 additions
- **Graph Diff Mode** (canvas toggle on `sim_extinction_*` tenants): severed edges dashed crimson, rewired edges glowing emerald, the rest faded; zoom / fit / centre controls; health-state label pills.
- **Cypher & MCP Inspector** (top bar): one-click PageRank / Betweenness / WCC / handoff / playbook presets, free-form **read-only** Cypher (`GET /api/blindspot` · `POST /api/tournament` · `POST /api/remediate-pr` · `POST /api/cypher`, executed with `GRAPH.RO_QUERY`), schema counts (`GET /api/schema`) and the MCP tool registry.
- **Policy Gatekeeper Rejection** callout for engineers penalised by ADR-002, and a Session 1 vs Session 2 telemetry card in the Memory tab.
- `BLOG_POST.md` — the technical write-up.

## 6c. CEO war-room layer

**ARR blast-radius ledger.** Three `(:CustomerContract)-[:SLA_DEPENDS_ON {penalty_per_min_usd}]->(:Service)` contracts ($19.5M ARR, $14,500/min SLA burn at full exposure) are traversed by `compute_technical_blast_radius`. The console shows live ARR at risk and burn rate in the KPI bar and the Blast Radius tab.

**Existential blindspot auto-discovery** (`GET /api/blindspot`, MCP tool `discover_existential_blindspot`). Evaluates every Engineer + Service pair (K=2) from live graph state and ranks them by compound lethality:
`100 x (0.35 ARR exposure + 0.25 cascade + 0.25 criticality-weighted sole-owned assets + 0.15 centrality)`, using `algo.pageRank`, `algo.betweenness`, bus-factor-1 ownership and `SLA_DEPENDS_ON` exposure. The #1 pair on the seed is **Arjun Mehta + the Token KV store: lethality 92.8/100, $19.5M ARR, $14,500/min, 5 orphaned artifacts**, with a runnable Cypher proof returned alongside.

**3-universe multigraph tournament** (`POST /api/tournament`). Forks `prod_company` into three isolated tenants, applies a different recovery strategy in each, and scores the *resulting graphs* with Cypher:

| Universe | Strategy | Result on Scenario 1 |
|---|---|---|
| `univ_alpha_hero_*` | everything to the single best-scoring engineer | peak load 106 %, 5 new single points of failure: rejected |
| `univ_beta_naive_*` | everything to the lowest-load engineer | 0 % policy compliance (ADR-002 violator): rejected |
| `univ_gamma_pareto_*` | load-aware, ADR-compliant matcher with secondary owners | peak load 85 %, 100 % compliance, 0 orphans, 1 bus-factor-1 asset: **winner** |

`GRAPH.COPY` forks are issued back-to-back (FalkorDB serves one copy of a given source at a time) and the three evaluations then run concurrently; the UI reports wall-clock and serial-sum time. Load model: each reassigned Service adds 14 points of workload, Repository 7, Ticket 9, Database 11 (secondary owners count half).

**Autonomous remediation PR** (`POST /api/remediate-pr`). Queries FalkorDB for the violating `DIRECT_WRITES_TO` path, the prescribed `svc_webhook -> svc_job_queue -> svc_ledger -> db_pg_ledger` route, the reviewers (owners of the route's services, from `[:OWNS]` edges) and the ARR behind the ledger. It renders a unified diff plus an executive memo. **Apply Patch to Graph** removes the forbidden edge, records `[:REMEDIATED_BY_PR {pr:'#1042'}]`, adds the queue-to-ledger route, and flips the contradiction to *RESOLVED (100% COMPLIANT)*. Applying from the production tenant forks a sandbox first, so the baseline is never mutated.

## 7. API surface
`GET /api/graph?name=` · `POST /api/simulate` · `POST /api/heal` · `POST /api/heal/stream` (SSE) · `POST /api/vaccinate` · `GET /api/contradictions` · `POST /api/ask` · `GET /api/memory` · `POST /api/reset?hard=` · `GET /api/mcp/tools` · `POST /api/mcp/call` · `GET /api/blindspot` · `POST /api/tournament` · `POST /api/remediate-pr` · `POST /api/cypher` · `GET /api/schema` · `POST /mcp` (JSON-RPC `initialize`, `tools/list`, `tools/call`).

Note: the MCP endpoint is a minimal JSON-RPC implementation of the tool protocol (no `mcp` SDK dependency).

## 8. AI coding assistant disclosure (Rule 11)
This project was designed and implemented with **Claude Code** (Anthropic). The build prompt, architecture and all code were produced in collaboration with the AI assistant and verified by running the backend against a live FalkorDB container and building the frontend with zero TypeScript errors.
