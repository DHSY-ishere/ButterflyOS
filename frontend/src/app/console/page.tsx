"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import GraphCanvas from "@/components/GraphCanvas";
import SwarmTerminal, { AGENT_NAMES } from "@/components/SwarmTerminal";
import IntelligencePanel from "@/components/IntelligencePanel";
import NodeDrawer from "@/components/NodeDrawer";
import CypherInspector from "@/components/CypherInspector";
import BlindspotBrief from "@/components/BlindspotBrief";
import TournamentModal from "@/components/TournamentModal";
import PrModal from "@/components/PrModal";
import { api, streamHeal } from "@/lib/api";
import type { Any } from "@/lib/api";

const PROD = "prod_company";
const S1 = ["eng_arjun", "svc_token_kv"];
const S2 = ["svc_ledger", "svc_payment", "eng_sara"];

const idleStatuses = () => Object.fromEntries(AGENT_NAMES.map((a) => [a, "IDLE"]));

export default function Page() {
  const [graphs, setGraphs] = useState<string[]>([PROD]);
  const [graphName, setGraphName] = useState(PROD);
  const [data, setData] = useState<Any>({ nodes: [], edges: [], survivability: null, orphans: [] });
  const [targets, setTargets] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<Set<string>>(new Set());
  const [shockKey, setShockKey] = useState(0);
  const [codeLayer, setCodeLayer] = useState(true);
  const [sim, setSim] = useState<Any>(null);
  const [heal, setHeal] = useState<Any>(null);
  const [events, setEvents] = useState<Any[]>([]);
  const [statuses, setStatuses] = useState<Record<string, string>>(idleStatuses());
  const [queryLog, setQueryLog] = useState<Any[]>([]);
  const [contradictions, setContradictions] = useState<Any>(null);
  const [memory, setMemory] = useState<Any>(null);
  const [asks, setAsks] = useState<Any[]>([]);
  const [bench, setBench] = useState<{ s1Queries: number | null; s1Ms: number | null; s2Queries: number | null; s2Ms: number | null; s2ApplyMs: number | null }>({ s1Queries: null, s1Ms: null, s2Queries: null, s2Ms: null, s2ApplyMs: null });
  const [tab, setTab] = useState(0);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [lastMs, setLastMs] = useState<number | null>(null);
  const [online, setOnline] = useState(true);
  const [inspector, setInspector] = useState(false);
  const [blind, setBlind] = useState<Any>(null);
  const [briefOpen, setBriefOpen] = useState(false);
  const [reticle, setReticle] = useState<Set<string>>(new Set());
  const [tournament, setTournament] = useState<Any>(null);
  const [tourOpen, setTourOpen] = useState(false);
  const [tourMsg, setTourMsg] = useState("");
  const [prBrief, setPrBrief] = useState<Any>(null);
  const [prOpen, setPrOpen] = useState(false);
  const [prApplying, setPrApplying] = useState(false);
  const sessionRef = useRef<{ id: string; targets: string[] } | null>(null);

  const log = useCallback((entries: Any[] | undefined) => {
    if (!entries?.length) return;
    setQueryLog((l) => [...l, ...entries].slice(-200));
    setLastMs(entries[entries.length - 1].ms);
  }, []);

  const refreshGraph = useCallback(async (name: string) => {
    const g = await api.graph(name);
    setData(g);
    log(g.cypher_executed);
  }, [log]);

  const refreshMemory = useCallback(async () => {
    const m = await api.memory();
    setMemory(m);
    log(m.cypher_executed);
    return m;
  }, [log]);

  const refreshGraphs = useCallback(async () => setGraphs((await api.graphs()).graphs), []);

  useEffect(() => {
    (async () => {
      try {
        await api.health();
        await Promise.all([refreshGraph(PROD), refreshMemory(), refreshGraphs()]);
      } catch {
        setOnline(false);
      }
    })();
  }, [refreshGraph, refreshMemory, refreshGraphs]);

  const toggleTarget = (id: string) =>
    setTargets((t) => {
      const n = new Set(t);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });

  const hl = (ids: string[]) => setHighlight(new Set(ids));

  const guard = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setNotice("");
    try { await fn(); } catch (e) { setNotice(String(e)); } finally { setBusy(""); }
  };

  const doSimulate = async (tg: string[]) => {
    const r = await api.simulate(tg);
    setSim(r);
    setHeal(null);
    setEvents([]);
    setStatuses(idleStatuses());
    setHighlight(new Set());
    sessionRef.current = { id: r.session_id, targets: tg };
    setGraphName(r.sandbox);
    log(r.cypher_executed);
    await Promise.all([refreshGraph(r.sandbox), refreshGraphs()]);
    setShockKey((k) => k + 1);
    return r;
  };

  const doSwarm = async (sid: string, tg: string[]) => {
    setEvents([]);
    setStatuses(idleStatuses());
    let result: Any = null;
    await streamHeal(tg, sid, (ev) => {
      if (ev.type === "agent_status") setStatuses((s) => ({ ...s, [ev.agent]: ev.status }));
      else if (ev.type === "step") { setEvents((e) => [...e, ev]); log(ev.cypher); }
      else if (ev.type === "done") result = ev.result;
    });
    if (!result) throw new Error("swarm returned no result");
    setHeal(result);
    if (result.fast_path_hit) {
      setBench((b) => ({ ...b, s1Queries: result.session1_queries ?? b.s1Queries, s2Queries: 1, s2Ms: result.lookup_ms, s2ApplyMs: result.apply_ms }));
    } else {
      setBench((b) => ({ ...b, s1Queries: result.reasoning_queries, s1Ms: result.total_ms }));
      const v = await api.vaccinate(tg, sid);
      log(v.cypher_executed);
      setNotice(`Vaccinated · ${v.data.episodic_steps_fused} steps distilled into a playbook`);
    }
    await Promise.all([refreshGraph(T_SIM(sid)), refreshMemory()]);
    setShockKey((k) => k + 1);
  };
  const T_SIM = (sid: string) => `sim_extinction_${sid}`;

  const simulateClick = () => guard("simulate", async () => {
    if (targets.size === 0) throw new Error("Pick at least one node on the graph first (click nodes to arm chaos meteors).");
    await doSimulate([...targets]);
    setTab(0);
  });

  const swarmClick = () => guard("swarm", async () => {
    const s = sessionRef.current;
    if (!s) throw new Error("Run SIMULATE EXTINCTION first.");
    await doSwarm(s.id, s.targets);
  });

  const scenario = (n: 1 | 2 | 3) => guard(`scenario${n}`, async () => {
    const tg = n === 2 ? S2 : S1;
    setTargets(new Set(tg));
    const r = await doSimulate(tg);
    setTab(0);
    if (n === 3) {
      if (!r.playbook_available) {
        setNotice("No procedural playbook for this failure signature yet. Run Scenario 1 → Run Swarm Heal & Vaccinate first, then repeat Scenario 3.");
        return;
      }
      setTab(2);
      await doSwarm(r.session_id, tg);
    }
  });

  const audit = () => guard("audit", async () => {
    const c = await api.contradictions(graphName);
    setContradictions(c);
    log(c.cypher_executed);
    const first = c.data.contradictions[0];
    if (first) hl([first.service, first.database, first.commit_id, first.author_id, first.adr_id, first.slack_id]);
    setTab(1);
  });

  const reset = () => guard("reset", async () => {
    await api.reset(false);
    setGraphName(PROD); setTargets(new Set()); setSim(null); setHeal(null); setEvents([]); setStatuses(idleStatuses());
    setHighlight(new Set()); setOpen(null); setContradictions(null); setReticle(new Set()); sessionRef.current = null;
    await Promise.all([refreshGraph(PROD), refreshGraphs(), refreshMemory()]);
  });

  const vaccinate = () => guard("vaccinate", async () => {
    const s = sessionRef.current;
    if (!s) return;
    const v = await api.vaccinate(s.targets, s.id);
    log(v.cypher_executed);
    setNotice(`Playbook ${v.data.playbook_id} v${v.data.version} distilled from ${v.data.episodic_steps_fused} steps`);
    await refreshMemory();
  });

  const onAsk = async (q: string) => {
    const r = await api.ask(q, PROD);
    log(r.cypher_executed);
    setAsks((a) => [r, ...a]);
    hl(r.provenance);
  };

  const findBlindspot = () => guard("blindspot", async () => {
    const r = await api.blindspot(PROD);
    log(r.cypher_executed);
    const p = r.data.blindspot;
    const pair = [p.engineer.id, p.service.id];
    setBlind(r);
    setTargets(new Set(pair));
    setReticle(new Set(pair));
    setBriefOpen(true);
  });

  const simulateBlindspot = () => {
    const p = blind?.data?.blindspot;
    if (!p) return;
    setBriefOpen(false);
    guard("simulate", async () => {
      await doSimulate([p.engineer.id, p.service.id]);
      setReticle(new Set());
      setTab(0);
    });
  };

  const runTournament = () => guard("tournament", async () => {
    setTourMsg("");
    let tg = sessionRef.current?.targets ?? [...targets];
    if (tg.length === 0) {
      tg = S1;
      setTargets(new Set(S1));
      setTourMsg("No scenario was selected, so the tournament used Scenario 1 (Arjun quits + Token KV dies).");
    }
    try {
      const t = await api.tournament(tg);
      setTournament(t);
      setTourOpen(true);
      setTab(3);
      await refreshGraphs();
    } catch (e) {
      const m = String(e);
      setTourMsg(m.includes("429") ? "Too many requests right now. Wait a few seconds and try again." : `Tournament failed: ${m}`);
    }
  });

  const openPr = () => guard("remediate", async () => {
    const b = await api.remediate(graphName, false);
    log(b.cypher_executed);
    if (b.status !== "VIOLATION") { setNotice(b.status); return; }
    setPrBrief(b);
    setPrOpen(true);
  });

  const applyPr = async () => {
    setPrApplying(true);
    try {
      const res = await api.remediate(graphName, true);
      log(res.cypher_executed);
      setPrBrief((b: Any) => ({ ...b, status: res.status }));
      const g = res.graph;
      if (res.forked_from_prod) { setGraphName(g); await refreshGraphs(); }
      await refreshGraph(g);
      const c = await api.contradictions(g);
      setContradictions(c);
      setNotice(`ADR-002 ${res.status}${res.forked_from_prod ? " (applied on a sandbox fork; production untouched)" : ""}`);
    } catch (e) { setNotice(String(e)); } finally { setPrApplying(false); }
  };

  const switchGraph = (name: string) => guard("switch", async () => { setGraphName(name); await refreshGraph(name); });

  const surv = data.survivability?.score;
  const rps = (heal?.blast ?? sim?.blast)?.rps_at_risk ?? 0;
  const blastNow = heal?.blast ?? sim?.blast;
  const arr = blastNow?.total_arr_at_risk_usd ?? 0;
  const burn = blastNow?.burn_rate_per_min_usd ?? 0;
  const orphanCount = data.orphans?.length ?? 0;
  const kpis: { k: string; v: string; c: string; bar?: number; sub?: string }[] = [
    { k: "Org survivability", v: surv != null ? `${surv}%` : "—", c: surv != null && surv < 60 ? "text-crimson" : "text-emerald", bar: surv ?? 0 },
    { k: "ARR at risk", v: arr ? `$${(arr / 1e6).toFixed(1)}M` : "$0", c: arr ? "text-crimson" : "text-white/80", sub: arr ? `$${burn.toLocaleString()}/min SLA burn` : "no contracts exposed" },
    { k: "RPS at risk", v: rps.toLocaleString(), c: rps ? "text-crimson" : "text-white/80" },
    { k: "Orphaned systems · bus factor 0", v: String(orphanCount), c: orphanCount ? "text-amber" : "text-emerald" },
    { k: "Last FalkorDB query", v: lastMs != null ? `${lastMs.toFixed(2)} ms` : "—", c: "text-neon" },
  ];

  return (
    <main className="min-h-screen flex flex-col px-6 py-6 gap-6 max-w-[1720px] w-full mx-auto">
      {/* header */}
      <header className="panel px-6 py-4 flex flex-wrap items-center gap-x-5 gap-y-3">
        <Link href="/" className="flex items-center gap-3" title="Back to home">
          <svg width="34" height="34" viewBox="0 0 40 40" aria-hidden>
            <defs>
              <linearGradient id="bf" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stopColor="#7CC4FF" />
                <stop offset="0.5" stopColor="#B793FF" />
                <stop offset="1" stopColor="#FF5D8F" />
              </linearGradient>
            </defs>
            <path d="M20 20 C 8 4, 1 12, 5 22 C 8 29, 15 28, 20 20 Z" fill="url(#bf)" opacity="0.95" />
            <path d="M20 20 C 32 4, 39 12, 35 22 C 32 29, 25 28, 20 20 Z" fill="url(#bf)" opacity="0.75" />
            <path d="M20 21 C 12 24, 9 34, 15 36 C 19 37, 20 29, 20 21 Z" fill="url(#bf)" opacity="0.6" />
            <path d="M20 21 C 28 24, 31 34, 25 36 C 21 37, 20 29, 20 21 Z" fill="url(#bf)" opacity="0.45" />
          </svg>
          <div className="leading-tight">
            <div className="text-[19px] font-semibold tracking-tight text-white">Butterfly<span className="text-white/50 font-medium">OS</span></div>
            <div className="text-[11.5px] text-white/45 hidden 2xl:block">Chaos, blast-radius &amp; bus-factor time-machine</div>
          </div>
        </Link>
        <span className={`chip ${online ? "" : "chip-bad"}`}><i className="dot" />{online ? "FalkorDB engine active" : "Backend offline"}</span>
        <select value={graphName} onChange={(e) => switchGraph(e.target.value)} className="field" aria-label="Graph tenant">
          {graphs.map((g) => <option key={g} value={g}>{g === PROD ? "prod_company (baseline)" : g}</option>)}
        </select>
        <label className="text-[12.5px] text-white/60 flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={codeLayer} onChange={(e) => setCodeLayer(e.target.checked)} /> Code &amp; comms
        </label>
        <div className="flex-1" />
        <button className="btn btn-sm btn-amber" disabled={!!busy} onClick={findBlindspot}>Auto-Find #1 Existential Blindspot</button>
        <button className="btn btn-sm" onClick={() => setInspector(true)}>Cypher &amp; MCP Inspector</button>
        <button className="btn btn-sm" disabled={!!busy} onClick={audit}>Audit Policy Contradictions</button>
      </header>
      <div className="flex flex-wrap items-stretch gap-4">
        <button className="scn scn-1" disabled={!!busy} onClick={() => scenario(1)}>
          <b>Scenario 1: Dual Extinction</b><span>Arjun quits + Token KV dies</span>
        </button>
        <button className="scn scn-2" disabled={!!busy} onClick={() => scenario(2)}>
          <b>Scenario 2: Ledger &amp; Payment Cascade</b><span>Ledger, payments and their owner go dark</span>
        </button>
        <button className="scn scn-3" disabled={!!busy} onClick={() => scenario(3)}>
          <b>Scenario 3: Session 2 Replay</b><span>Procedural-memory fast path</span>
        </button>
        <div className="flex-1 flex items-center gap-2 min-w-[120px]">
          {busy && <span data-busy className="chip chip-warn"><i className="dot" />{busy}…</span>}
          {notice && !busy && <span className="chip max-w-[460px] truncate" title={notice}>{notice}</span>}
        </div>
        <button className="btn btn-sm self-center" disabled={!!busy} onClick={reset}>Reset Graph</button>
        <button className="btn btn-danger self-center" disabled={!!busy} onClick={simulateClick}>Simulate Extinction ({targets.size})</button>
        <button className="btn btn-ok self-center" disabled={!!busy || !sim} onClick={swarmClick}>Run Autonomous Swarm Heal &amp; Vaccinate</button>
      </div>
      {/* KPIs */}
      <div className="grid grid-cols-5 gap-5">
        {kpis.map((m) => (
          <div key={m.k} className="panel kpi rise">
            <div className="k">{m.k}</div>
            <div className={`v truncate ${m.c}`}>{m.v}</div>
            {m.bar != null && <div className="bar"><i style={{ width: `${m.bar}%` }} /></div>}
            {m.sub && <div className="text-[12px] text-white/50 mt-1">{m.sub}</div>}
          </div>
        ))}
      </div>
      {/* graph: one wide canvas, comfortable height */}
      <section className="panel relative overflow-hidden" style={{ height: "clamp(520px, calc(100vh - 372px), 900px)" }}>
        <GraphCanvas nodes={data.nodes} edges={data.edges} targets={targets} highlight={highlight} reticle={reticle} showCodeLayer={codeLayer}
          shockKey={shockKey} isSim={graphName !== PROD} onToggleTarget={toggleTarget} onOpen={setOpen} />
        {highlight.size > 0 && (
          <button className="btn btn-sm absolute bottom-4 left-1/2 -translate-x-1/2" onClick={() => setHighlight(new Set())}>Clear highlight</button>
        )}
        {heal?.fast_path_hit && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 chip" style={{ background: "rgba(66,245,194,0.14)", borderColor: "rgba(66,245,194,0.5)", color: "#b9ffe9" }}>
            <i className="dot" />FAST_PATH_HIT · playbook recalled in {heal.lookup_ms} ms (1 Cypher query) vs {heal.session1_queries} queries in Session 1
          </div>
        )}
        {open && (
          <div className="absolute top-4 right-4 z-10 w-[380px] max-w-[calc(100%-32px)]">
            <NodeDrawer nodeId={open} graph={graphName} armed={targets.has(open)} onToggleArm={toggleTarget}
              onOpen={setOpen} onClose={() => setOpen(null)} onHighlight={hl} />
          </div>
        )}
      </section>
      {/* detail row: agents on the left, intelligence on the right */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] auto-rows-[700px] gap-6">
        <SwarmTerminal statuses={statuses} events={events} queryLog={queryLog} onHighlight={hl} />
        <IntelligencePanel sim={sim} heal={heal} contradictions={contradictions} memory={memory} asks={asks} bench={bench}
          canVaccinate={!!heal && !heal.fast_path_hit && !busy} onVaccinate={vaccinate} onAsk={onAsk} onHighlight={hl}
          tab={tab} onTab={setTab} onRemediate={openPr} onTournament={runTournament} tournament={tournament}
          tourBusy={busy === "tournament"} tourMsg={tourMsg} onReopenTournament={() => setTourOpen(true)} />
      </div>
      <BlindspotBrief data={blind} open={briefOpen} onClose={() => setBriefOpen(false)} onSimulate={simulateBlindspot} />
      <TournamentModal data={tournament} open={tourOpen} onClose={() => setTourOpen(false)}
        onOpenGraph={(g) => { setTourOpen(false); switchGraph(g); }} />
      <PrModal brief={prBrief} open={prOpen} applying={prApplying} onClose={() => setPrOpen(false)} onApply={applyPr} />
      <CypherInspector open={inspector} graph={graphName} onClose={() => setInspector(false)} />
    </main>
  );
}
