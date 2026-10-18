"""Seed the prod_company graph: FinCore Cloud (people, infra, code, decisions, memory)."""
import db

ENGINEERS = [
    dict(id="eng_arjun", name="Arjun Mehta", role="Staff Systems Architect", tenure_years=5.2, status="ACTIVE", team="Core Infra", load=85, specialty="Lock-Free KV & Zero-Trust Auth"),
    dict(id="eng_devansh", name="Devansh Sahney", role="Senior Distributed Systems Engineer", tenure_years=2.4, status="ACTIVE", team="Core Infra", load=55, specialty="High-Concurrency Queues, Sharded KV & Go/C++"),
    dict(id="eng_sara", name="Sara Lin", role="Staff Payments Engineer", tenure_years=3.4, status="ACTIVE", team="Payments & Ledger", load=65, specialty="Double-Entry Ledger & Postgres MVCC"),
    dict(id="eng_priya", name="Priya Nair", role="Principal SRE", tenure_years=3.0, status="ACTIVE", team="Core Infra", load=60, specialty="Kubernetes, eBPF & Chaos Mesh"),
    dict(id="eng_vikram", name="Vikram Rao", role="Security & Cryptography Lead", tenure_years=1.9, status="ACTIVE", team="Security & Trust", load=50, specialty="HMAC Rotation & Zero-Trust Policy"),
    dict(id="eng_kabir", name="Kabir Sen", role="Product Backend Engineer", tenure_years=0.7, status="ACTIVE", team="Payments & Ledger", load=40, specialty="Merchant Webhooks & REST APIs"),
]
TEAMS = [
    dict(id="team_core", name="Core Infrastructure"),
    dict(id="team_pay", name="Payments & Ledger"),
    dict(id="team_sec", name="Security & Trust"),
]
SERVICES = [
    dict(id="svc_api_gw", name="Edge API Gateway", tier="TIER_0", rps=45000, sla="99.999%", status="HEALTHY"),
    dict(id="svc_auth", name="Zero-Trust Auth Engine", tier="TIER_0", rps=38000, sla="99.999%", status="HEALTHY"),
    dict(id="svc_token_kv", name="Sharded In-Memory Token KV Store", tier="TIER_0", rps=120000, sla="99.999%", status="HEALTHY"),
    dict(id="svc_payment", name="Payment Orchestrator", tier="TIER_1", rps=14500, sla="99.99%", status="HEALTHY"),
    dict(id="svc_ledger", name="Double-Entry Ledger Engine", tier="TIER_0", rps=16000, sla="99.999%", status="HEALTHY"),
    dict(id="svc_job_queue", name="Distributed Job Queue Engine", tier="TIER_1", rps=32000, sla="99.99%", status="HEALTHY"),
    dict(id="svc_fraud", name="Real-Time Fraud Graph Scorer", tier="TIER_1", rps=14500, sla="99.95%", status="HEALTHY"),
    dict(id="svc_webhook", name="Merchant Webhook Dispatcher", tier="TIER_2", rps=9500, sla="99.9%", status="HEALTHY"),
]
DATABASES = [
    dict(id="db_pg_ledger", name="PostgreSQL Ledger Cluster", status="HEALTHY"),
    dict(id="db_redis_ratelimit", name="Rate-Limit Cache Cluster", status="HEALTHY"),
]
REPOS = [
    dict(id="repo_sharded_kv", name="sharded-kv"),
    dict(id="repo_auth_core", name="auth-core"),
    dict(id="repo_job_queue", name="job-queue"),
    dict(id="repo_ledger_tx", name="ledger-tx"),
    dict(id="repo_webhook_svc", name="webhook-svc"),
]
COMMITS = [
    dict(id="commit_8f92a", hash="8f92a1c", message="hotfix(kv): bypass RWMutex on shard 14 during NTP clock skew > 12ms — DO NOT REMOVE", timestamp="2026-09-14T03:12:00Z", risk_level="CRITICAL"),
    dict(id="commit_3b11e", hash="3b11e09", message="feat(auth): wire zero-allocation RESP binary parser to token KV store", timestamp="2026-09-28T11:40:00Z", risk_level="HIGH"),
    dict(id="commit_7c44d", hash="7c44d82", message="perf(kv): implement FNV-1a 32-shard lock-free eviction ring", timestamp="2026-10-02T16:20:00Z", risk_level="MEDIUM"),
    dict(id="commit_bad_sync", hash="dead991", message="quickfix(webhook): direct synchronous SQL INSERT into db_pg_ledger to bypass queue delay", timestamp="2026-10-14T22:15:00Z", risk_level="VIOLATION"),
    dict(id="commit_ledger_mvcc", hash="a91c3d7", message="fix(ledger): serializable isolation on double-entry posting to prevent phantom reads", timestamp="2026-09-20T09:05:00Z", risk_level="HIGH"),
    dict(id="commit_queue_retry", hash="c20be4f", message="feat(queue): exponential backoff with jitter for poison-pill jobs", timestamp="2026-10-05T13:30:00Z", risk_level="MEDIUM"),
    dict(id="commit_wal_99", hash="99ab7e3", message="perf(ledger): tune Serializable Snapshot Isolation & WAL fsync batching", timestamp="2026-10-08T08:45:00Z", risk_level="MEDIUM"),
    dict(id="commit_hmac_rot", hash="5d0aa18", message="feat(auth): Ed25519 dual-key rotation scheduler (15 min)", timestamp="2026-09-02T10:00:00Z", risk_level="HIGH"),
]
ADRS = [
    dict(id="adr_001", title="ADR-001: Custom Epoch Offset & Lock-Free Ring on Shard 14", rule_type="MEMORY_ORDERING", summary="Shard 14 handles cross-DC replication leases and requires a +15ms monotonic clock offset."),
    dict(id="adr_002", title="ADR-002: Strict Async Queue Isolation for Ledger Writes", rule_type="FORBID_DIRECT_DB_WRITE", forbidden_target="db_pg_ledger", allowed_writer="svc_ledger", summary="No Tier-2 service may write directly to db_pg_ledger; all writes must route through svc_job_queue -> svc_ledger."),
    dict(id="adr_003", title="ADR-003: Dual-Key Ed25519 Token Rotation Every 15 Minutes", rule_type="CRYPTO_ROTATION", summary="svc_auth depends on svc_token_kv for sub-millisecond revocation lists."),
]
SLACK = [
    dict(id="slack_901", channel="#core-infra-incidents", author="Arjun Mehta", snippet="Heads up: if svc_token_kv shard 14 ever stalls during lease renewal, never restart with clean WAL—run `kvctl --realign-epoch 15ms` first or svc_auth will reject all active JWTs."),
    dict(id="slack_902", channel="#payments-eng", author="Kabir Sen", snippet="Pushed a temporary direct DB write from svc_webhook to db_pg_ledger for the merchant demo, will clean up later."),
    dict(id="slack_903", channel="#payments-eng", author="Sara Lin", snippet="Ledger postings must stay SERIALIZABLE — dropping to READ COMMITTED reintroduces phantom double-entries under load."),
]
TICKETS = [
    dict(id="ticket_p0_101", title="P0-101: Migrate Shard 14 Lease Table Before Q4 Traffic Peak", priority="P0", status="IN_PROGRESS"),
    dict(id="ticket_p1_202", title="P1-202: Add gRPC Backpressure to Job Queue Workers", priority="P1", status="IN_PROGRESS"),
    dict(id="ticket_p1_303", title="P1-303: Ledger Reconciliation Batch Window Tuning", priority="P1", status="IN_PROGRESS"),
]

CONTRACTS = [
    dict(id="contract_stripe", client="Stripe Global Treasury", arr_usd=8400000, penalty_per_min_usd=6500, sla_tier="99.999%"),
    dict(id="contract_novabank", client="NovaBank Core Clearing", arr_usd=6200000, penalty_per_min_usd=4800, sla_tier="99.999%"),
    dict(id="contract_apex", client="Apex Quant Liquidity", arr_usd=4900000, penalty_per_min_usd=3200, sla_tier="99.99%"),
]
SLA_DEPENDS = [
    ("contract_stripe", "svc_api_gw"), ("contract_stripe", "svc_auth"), ("contract_stripe", "svc_ledger"),
    ("contract_novabank", "svc_payment"), ("contract_novabank", "svc_ledger"), ("contract_novabank", "svc_token_kv"),
    ("contract_apex", "svc_auth"), ("contract_apex", "svc_token_kv"), ("contract_apex", "svc_job_queue"),
]

DEPENDS = [
    ("svc_api_gw", "svc_auth"), ("svc_api_gw", "svc_payment"), ("svc_api_gw", "svc_webhook"),
    ("svc_api_gw", "db_redis_ratelimit"),
    ("svc_auth", "svc_token_kv"),
    ("svc_payment", "svc_auth"), ("svc_payment", "svc_fraud"), ("svc_payment", "svc_ledger"), ("svc_payment", "svc_job_queue"),
    ("svc_ledger", "db_pg_ledger"), ("svc_ledger", "svc_token_kv"),
    ("svc_webhook", "svc_job_queue"), ("svc_webhook", "db_pg_ledger"),
    ("svc_fraud", "svc_token_kv"),
    ("svc_job_queue", "svc_auth"),
]
OWNS = [
    ("eng_arjun", "svc_token_kv"), ("eng_arjun", "svc_auth"), ("eng_arjun", "repo_sharded_kv"), ("eng_arjun", "repo_auth_core"),
    ("eng_devansh", "svc_job_queue"), ("eng_devansh", "repo_job_queue"),
    ("eng_sara", "svc_ledger"), ("eng_sara", "svc_payment"), ("eng_sara", "repo_ledger_tx"), ("eng_sara", "db_pg_ledger"),
    ("eng_priya", "svc_api_gw"), ("eng_priya", "svc_fraud"), ("eng_priya", "db_redis_ratelimit"),
    ("eng_kabir", "svc_webhook"), ("eng_kabir", "repo_webhook_svc"),
]
AUTHORED = [
    ("eng_arjun", "commit_8f92a"), ("eng_arjun", "commit_3b11e"), ("eng_devansh", "commit_7c44d"),
    ("eng_kabir", "commit_bad_sync"), ("eng_sara", "commit_ledger_mvcc"), ("eng_devansh", "commit_queue_retry"),
    ("eng_vikram", "commit_hmac_rot"), ("eng_sara", "commit_wal_99"),
]
REVIEWED = [
    ("eng_devansh", "commit_3b11e"), ("eng_devansh", "commit_8f92a"), ("eng_vikram", "commit_3b11e"),
    ("eng_arjun", "commit_7c44d"), ("eng_priya", "commit_7c44d"), ("eng_priya", "commit_queue_retry"),
    ("eng_sara", "commit_bad_sync"), ("eng_vikram", "commit_8f92a"),
    ("eng_devansh", "commit_wal_99"),
    ("eng_kabir", "commit_3b11e"), ("eng_kabir", "commit_hmac_rot"),  # Kabir reviews auth-core: a genuine contender
]
MODIFIED_IN = [
    ("commit_8f92a", "repo_sharded_kv"), ("commit_3b11e", "repo_sharded_kv"), ("commit_3b11e", "repo_auth_core"),
    ("commit_7c44d", "repo_sharded_kv"), ("commit_bad_sync", "repo_webhook_svc"),
    ("commit_ledger_mvcc", "repo_ledger_tx"), ("commit_queue_retry", "repo_job_queue"),
    ("commit_hmac_rot", "repo_auth_core"), ("commit_wal_99", "repo_ledger_tx"),
]
DEPLOYED_FROM = [
    ("svc_token_kv", "repo_sharded_kv"), ("svc_auth", "repo_auth_core"), ("svc_job_queue", "repo_job_queue"),
    ("svc_ledger", "repo_ledger_tx"), ("svc_webhook", "repo_webhook_svc"),
]
ASSIGNED = [("eng_arjun", "ticket_p0_101"), ("eng_devansh", "ticket_p1_202"), ("eng_sara", "ticket_p1_303")]
BLOCKS = [("ticket_p0_101", "svc_token_kv"), ("ticket_p1_202", "svc_job_queue"), ("ticket_p1_303", "svc_ledger")]
POSTED = [("eng_arjun", "slack_901"), ("eng_kabir", "slack_902"), ("eng_sara", "slack_903")]
EXPLAINS = [("slack_901", "commit_8f92a"), ("slack_901", "svc_token_kv"), ("slack_902", "commit_bad_sync"),
            ("slack_902", "svc_webhook"), ("slack_903", "commit_ledger_mvcc"), ("slack_903", "svc_ledger")]
GOVERNED = [("svc_token_kv", "adr_001"), ("repo_sharded_kv", "adr_001"), ("svc_webhook", "adr_002"),
            ("svc_ledger", "adr_002"), ("db_pg_ledger", "adr_002"), ("svc_auth", "adr_003"), ("svc_token_kv", "adr_003")]
MEMBER = [("eng_arjun", "team_core"), ("eng_devansh", "team_core"), ("eng_priya", "team_core"),
          ("eng_sara", "team_pay"), ("eng_kabir", "team_pay"), ("eng_vikram", "team_sec")]
TEAM_OWNS = [("team_core", "svc_token_kv"), ("team_core", "svc_job_queue"), ("team_core", "svc_api_gw"),
             ("team_pay", "svc_payment"), ("team_pay", "svc_ledger"), ("team_pay", "svc_webhook"),
             ("team_sec", "svc_auth")]


def _nodes(graph_name, label, items):
    db.q(graph_name, f"UNWIND $items AS p CREATE (n:{label}) SET n = p", {"items": items}, "seed")


def _edges(graph_name, a_label, b_label, rel, pairs, props=None):
    items = [{"a": a, "b": b} for a, b in pairs]
    prop_str = ""
    if props:
        prop_str = " {" + ", ".join(f"{k}: {v!r}" if isinstance(v, str) else f"{k}: {str(v).lower() if isinstance(v, bool) else v}" for k, v in props.items()) + "}"
    a_m = f":{a_label}" if a_label else ""
    b_m = f":{b_label}" if b_label else ""
    db.q(graph_name,
         f"UNWIND $items AS e MATCH (a{a_m} {{id: e.a}}), (b{b_m} {{id: e.b}}) CREATE (a)-[:{rel}{prop_str}]->(b)",
         {"items": items}, "seed")


def seed(graph_name: str = db.PROD):
    db.delete_graph(graph_name)
    g = db.graph(graph_name)
    for label, items in [("Engineer", ENGINEERS), ("Team", TEAMS), ("Service", SERVICES), ("Database", DATABASES),
                         ("Repository", REPOS), ("Commit", COMMITS), ("ADR_Doc", ADRS), ("SlackThread", SLACK),
                         ("Ticket", TICKETS), ("CustomerContract", CONTRACTS)]:
        _nodes(graph_name, label, items)
    for idx in ["Engineer", "Service", "Database", "Repository", "Commit", "ADR_Doc", "SlackThread", "Ticket", "Team", "CustomerContract", "Episode", "EpisodicStep", "ProceduralPlaybook"]:
        try:
            g.query(f"CREATE INDEX FOR (n:{idx}) ON (n.id)")
        except Exception:
            pass

    # DEPENDS_ON (Service -> Service|Database)
    for a, b in DEPENDS:
        db.q(graph_name, "MATCH (a:Service {id:$a}), (b {id:$b}) CREATE (a)-[:DEPENDS_ON {criticality:'HARD', latency_budget_ms:2}]->(b)", {"a": a, "b": b}, "seed")
    db.q(graph_name, "MATCH (a:Service {id:'svc_webhook'}), (b:Database {id:'db_pg_ledger'}) CREATE (a)-[:DIRECT_WRITES_TO {since:'2026-10-14T22:15:00Z', via:'commit_bad_sync'}]->(b)", tag="seed")
    # OWNS (Engineer -> Service|Repository|Database)
    for a, b in OWNS:
        db.q(graph_name, "MATCH (a:Engineer {id:$a}), (b {id:$b}) CREATE (a)-[:OWNS {bus_factor_weight:1.0, active:true}]->(b)", {"a": a, "b": b}, "seed")
    _edges(graph_name, "Engineer", "Commit", "AUTHORED", AUTHORED)
    _edges(graph_name, "Engineer", "Commit", "REVIEWED", REVIEWED)
    _edges(graph_name, "Commit", "Repository", "MODIFIED_IN", MODIFIED_IN)
    _edges(graph_name, "Service", "Repository", "DEPLOYED_FROM", DEPLOYED_FROM)
    _edges(graph_name, "Engineer", "Ticket", "ASSIGNED_TO", ASSIGNED, {"active": True})
    _edges(graph_name, "Ticket", "Service", "BLOCKS", BLOCKS)
    _edges(graph_name, "Engineer", "SlackThread", "POSTED_IN", POSTED)
    for a, b in EXPLAINS:
        db.q(graph_name, "MATCH (a:SlackThread {id:$a}), (b {id:$b}) CREATE (a)-[:EXPLAINS]->(b)", {"a": a, "b": b}, "seed")
    for a, b in GOVERNED:
        db.q(graph_name, "MATCH (a {id:$a}), (b:ADR_Doc {id:$b}) CREATE (a)-[:GOVERNED_BY]->(b)", {"a": a, "b": b}, "seed")
    db.q(graph_name, "MATCH (e:Engineer {id:'eng_priya'}), (d:Database {id:'db_pg_ledger'}) CREATE (e)-[:MAINTAINED_BY_SRE {role:'Patroni Failover & Replica Lead'}]->(d)", tag="seed")
    for tgt in ("svc_ledger", "db_pg_ledger"):
        db.q(graph_name, "MATCH (e:Engineer {id:'eng_vikram'}), (x {id:$t}) CREATE (e)-[:AUDITS {role:'Security Auditor'}]->(x)", {"t": tgt}, "seed")
    for c, sv in SLA_DEPENDS:
        db.q(graph_name, "MATCH (c:CustomerContract {id:$c}), (s:Service {id:$s}) CREATE (c)-[:SLA_DEPENDS_ON {penalty_per_min_usd: c.penalty_per_min_usd}]->(s)", {"c": c, "s": sv}, "seed")
    _edges(graph_name, "Engineer", "Team", "MEMBER_OF", MEMBER)
    _edges(graph_name, "Team", "Service", "RESPONSIBLE_FOR", TEAM_OWNS)

    # Baseline memory
    db.q(graph_name, """
      CREATE (e:Episode {id:'ep_hist_001', session_id:'hist_001', signature:'db_redis_ratelimit', created_at:'2026-08-01T00:00:00Z', n_steps:3})
      CREATE (s1:EpisodicStep {id:'ep_hist_001_s1', agent:'Shockwave-Triage-Agent', action:'compute_technical_blast_radius', seq:1})
      CREATE (s2:EpisodicStep {id:'ep_hist_001_s2', agent:'BusFactor-Detector-Agent', action:'compute_orphaned_tribal_knowledge', seq:2})
      CREATE (s3:EpisodicStep {id:'ep_hist_001_s3', agent:'Continuity-Healer-Agent', action:'find_optimal_successors', seq:3})
      CREATE (p:ProceduralPlaybook {id:'proc_hist_001', signature:'db_redis_ratelimit', name:'Rate-Limit Failover Runbook', confidence:0.96, avg_latency_ms:3.8, source_session:'hist_001', steps:3})
      CREATE (e)-[:STEP]->(s1), (e)-[:STEP]->(s2), (e)-[:STEP]->(s3),
             (s1)-[:HANDOFF_TO]->(s2), (s2)-[:HANDOFF_TO]->(s3), (e)-[:DISTILLED_INTO]->(p)
    """, tag="seed")
    return stats(graph_name)


def stats(graph_name: str = db.PROD):
    n, _ = db.rows(graph_name, "MATCH (n) RETURN count(n) AS c")
    r, _ = db.rows(graph_name, "MATCH ()-[r]->() RETURN count(r) AS c")
    return {"nodes": n[0]["c"], "edges": r[0]["c"]}


if __name__ == "__main__":
    print("Seeded:", seed())
