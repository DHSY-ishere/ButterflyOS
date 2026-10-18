"use client";
import { useState } from "react";
import type { Any } from "@/lib/api";

interface Props {
  sim: Any;
  heal: Any;
  contradictions: Any;
  memory: Any;
  asks: Any[];
  bench: { s1Queries: number | null; s1Ms: number | null; s2Queries: number | null; s2Ms: number | null; s2ApplyMs: number | null };
  canVaccinate: boolean;
  onVaccinate: () => void;
  onAsk: (q: string) => Promise<void>;
  onHighlight: (ids: string[]) => void;
  tab: number;
  onTab: (t: number) => void;
  onRemediate: () => void;
  onTournament: () => void;
  tournament: Any;
  tourBusy: boolean;
  tourMsg: string;
  onReopenTournament: () => void;
}

const SUGGESTIONS = [
  "Who knows about the shard 14 clock skew hack?",
  "What breaks if Zero-Trust Auth goes down?",
  "Which commits violate ADR policies?",
];

export default function IntelligencePanel({ sim, heal, contradictions, memory, asks, bench, canVaccinate, onVaccinate, onAsk, onHighlight, tab: active, onTab, onRemediate, onTournament, tournament, tourBusy, tourMsg, onReopenTournament }: Props) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [quote, setQuote] = useState<Any>(null);

  const blast = heal?.blast ?? sim?.blast;
  const orphans: Any[] = (heal?.orphans ?? sim?.orphans)?.orphans ?? [];
  const matches: Any[] = heal?.successors?.matches ?? [];
  const dossiers: Any[] = heal?.dossiers ?? [];
  const contra: Any[] = contradictions?.data?.contradictions ?? heal?.contradictions?.contradictions ?? [];

  const ask = async (text: string) => {
    if (!text.trim()) return;
    setBusy(true);
    await onAsk(text);
    setBusy(false);
    setQ("");
  };

  return (
    <div className="panel h-full flex flex-col overflow-hidden">
      <div className="seg">
        {["Blast Radius", "Company Brain", "Memory", "Multiverse"].map((t, i) => (
          <button key={t} onClick={() => onTab(i)} className={active === i ? "on" : ""}>{t}</button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto p-5 text-[13px] space-y-5">
        {/* ---------------- TAB 1 ---------------- */}
        {active === 0 && (
          <>
            {!blast && <div className="text-slate-500">Select nodes and press <b className="text-crimson">SIMULATE EXTINCTION</b> to fork a sandbox tenant and compute the shockwave.</div>}
            {blast && (
              <>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="border border-crimson/40 rounded-2xl p-3.5"><div className="text-crimson text-lg">{blast.rps_at_risk.toLocaleString()}</div>RPS at risk</div>
                  <div className="border border-amber/40 rounded-2xl p-3.5"><div className="text-amber text-lg">{blast.tier0_sla_breaches.length}</div>Tier-0 SLAs breached</div>
                  <div className="border border-neon/40 rounded-2xl p-3.5"><div className="text-neon text-lg">{blast.chokepoint ?? "—"}</div>PageRank chokepoint</div>
                </div>
                {blast.contracts_at_risk?.length > 0 && (
                  <div className="panel-flat p-4">
                    <div className="flex items-baseline justify-between">
                      <div className="text-[12px] font-semibold tracking-[0.1em] uppercase text-white/45">Enterprise ARR ledger</div>
                      <div className="text-[12.5px] text-amber tabular-nums">${blast.burn_rate_per_min_usd.toLocaleString()}/min SLA burn</div>
                    </div>
                    <div className="mt-1 text-[26px] font-semibold text-crimson tabular-nums">${(blast.total_arr_at_risk_usd / 1e6).toFixed(1)}M <span className="text-[13px] text-white/45 font-normal">ARR at risk</span></div>
                    <div className="mt-3 space-y-1.5">
                      {blast.contracts_at_risk.map((c: Any) => (
                        <div key={c.id} className="flex justify-between text-[12.5px] cursor-pointer hover:text-white" onClick={() => onHighlight([c.id, ...c.services])}>
                          <span className="text-slate-200">{c.client} <span className="text-white/35">· {c.sla_tier}</span></span>
                          <span className="tabular-nums text-white/70">${(c.arr_usd / 1e6).toFixed(1)}M · ${c.penalty_per_min_usd.toLocaleString()}/min</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <table className="w-full">
                  <thead className="text-slate-500 text-left"><tr><th>Service</th><th>RPS</th><th>Tier</th><th>PR</th><th>Failure path</th></tr></thead>
                  <tbody>
                    {blast.impacted_services.map((s: Any) => (
                      <tr key={s.id} className="border-t border-white/5 hover:bg-white/5 cursor-pointer" onClick={() => onHighlight(s.path_ids)}>
                        <td className="py-1 text-slate-200">{s.name}</td>
                        <td className="text-amber">{s.rps.toLocaleString()}</td>
                        <td className={s.tier === "TIER_0" ? "text-crimson" : "text-slate-300"}>{s.tier.replace("TIER_", "T")}</td>
                        <td className="text-neon">{s.pagerank}</td>
                        <td className="text-slate-400">{s.path_ids.join(" → ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
            {orphans.length > 0 && (
              <>
                <div className="text-crimson tracking-[0.12em] font-semibold mt-2">ORPHANED SYSTEMS · BUS FACTOR = 0</div>
                {orphans.map((o) => {
                  const m = matches.find((x: Any) => x.orphan_id === o.id);
                  return (
                    <div key={o.id} className="border border-crimson/30 rounded-2xl p-3.5 bg-crimson/5">
                      <div className="flex justify-between">
                        <span className="text-slate-100 cursor-pointer" onClick={() => onHighlight([o.id, ...o.former_owners])}>{o.title} <span className="text-slate-500">({o.id})</span></span>
                        <span className="text-slate-500">{o.label} · lost: {o.former_owners.join(", ")}</span>
                      </div>
                      {m?.winner ? (
                        <div className="mt-1 text-emerald">
                          ⇢ Successor: <b>{m.winner.name}</b> — {m.winner.compatibility}% match
                          <div className="text-slate-400">
                            commits +{m.winner.commit_pts.toFixed(1)} ({m.winner.authored} authored / {m.winner.reviewed} reviewed) · adjacency +{m.winner.adjacency_pts} · team +{m.winner.team_pts} · load/policy-risk −{m.winner.load_penalty.toFixed(1)}
                          </div>
                          <div className="text-slate-500">runners-up: {m.ranked.filter((r: Any) => r.id !== m.winner.id).slice(0, 3).map((r: Any) => `${r.name} ${r.compatibility}%`).join(" · ")}</div>
                          <div className="mt-1 text-slate-500">
                            Cypher proof path:{" "}
                            <span className="pill" onClick={() => onHighlight([...m.proof_path, ...m.former_owners])}>
                              (:Engineer {"{"}id:'{m.winner.id}'{"}"})-[:AUTHORED|REVIEWED|MAINTAINED_BY_SRE|AUDITS|OWNS*1..3]-({m.orphan_id})
                            </span>
                            <span className="text-slate-600"> · multi-hop +{m.winner.multihop_pts ?? 0} ({m.winner.path_hits ?? 0} paths)</span>
                          </div>
                        </div>
                      ) : <div className="text-slate-500 mt-1">Run the swarm to compute topological successor matches.</div>}
                      {m?.disqualified_candidates?.map((d: Any) => (
                        <div key={d.id} className="mt-2 border border-crimson rounded-2xl p-3.5 bg-crimson/10">
                          <span className="bg-crimson text-black font-bold px-1.5 py-0.5 rounded-xl text-[11.5px]">{d.badge}</span>{" "}
                          <b className="text-crimson">Policy Gatekeeper Rejection · {d.name}</b>
                          <div className="text-slate-300 mt-1">{d.reason}. Without the penalty the graph would have scored {d.name} at {d.would_have_scored}.</div>
                        </div>
                      ))}
                    </div>
                  );
                })}
                {(heal?.orphans ?? sim?.orphans)?.orphan_components?.length > 0 && (
                  <div className="text-slate-400">
                    WCC: {(heal?.orphans ?? sim?.orphans).orphan_components.length} ownerless subgraph(s) ·{" "}
                    betweenness top: {(heal?.orphans ?? sim?.orphans).betweenness_top.slice(0, 3).map((b: Any) => `${b.id} (${b.score})`).join(", ")}
                  </div>
                )}
              </>
            )}
          </>
        )}
        {/* ---------------- TAB 2 ---------------- */}
        {active === 1 && (
          <>
            <div className="text-neon tracking-[0.12em] font-semibold">ASK THE COMPANY BRAIN</div>
            <div className="flex gap-1">
              <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask(q)}
                placeholder="Who knows about…? What breaks if…?"
                className="flex-1 bg-black/30 border border-neon/30 rounded-xl px-2 py-1 text-slate-100 outline-none focus:border-neon" />
              <button className="btn" disabled={busy} onClick={() => ask(q)}>{busy ? "…" : "Ask"}</button>
            </div>
            <div className="flex flex-wrap gap-1">{SUGGESTIONS.map((s) => <span key={s} className="pill" onClick={() => ask(s)}>{s}</span>)}</div>
            {asks.map((a, i) => (
              <div key={i} className="border border-white/10 rounded-2xl p-3.5">
                <div className="text-slate-400">Q: {a.question}</div>
                <div className="text-slate-100 mt-1">{a.answer}</div>
                <div className="flex flex-wrap gap-1 mt-1">
                  {a.provenance.map((id: string) => <span key={id} className="pill" onClick={() => onHighlight(a.provenance)}>{id}</span>)}
                </div>
                <details className="mt-1"><summary className="cursor-pointer text-neon/70">{a.kind} · {a.latency_ms} ms · Cypher</summary>
                  {a.cypher_executed.map((c: Any, k: number) => <pre key={k} className="bg-black/30 p-1 rounded-xl whitespace-pre-wrap text-slate-300">{c.cypher}</pre>)}
                </details>
              </div>
            ))}
            <div className="text-amber tracking-[0.12em] font-semibold mt-2">ARCHITECTURAL DRIFT & CONTRADICTIONS</div>
            {contra.length === 0 && !(contradictions?.data?.resolved?.length) && <div className="text-slate-500">Press “Audit Policy Contradictions” to run the ADR check.</div>}
            {contradictions?.data?.resolved?.map((r: Any, i: number) => (
              <div key={`res${i}`} className="border border-emerald/45 rounded-2xl p-3.5 bg-emerald/5">
                <div className="text-emerald font-semibold">RESOLVED (100% COMPLIANT) · {r.service} → {r.database}</div>
                <div className="text-slate-300">{r.adr_title} · remediated by PR {r.pr}</div>
              </div>
            ))}
            {contra.map((c: Any, i: number) => (
              <div key={i} className="border border-crimson/45 rounded-2xl p-3.5 bg-crimson/5">
                <div className="text-crimson">⚠ {c.service} → {c.database} violates {c.adr_id}</div>
                <div className="text-slate-300">{c.adr_title}</div>
                <div className="text-slate-400 mt-1">Commit <span className="pill" onClick={() => onHighlight([c.service, c.database, c.commit_id, c.author_id, c.adr_id])}>{c.commit_id}</span> by <b>{c.author}</b>: “{c.commit_message}”</div>
                <div className="text-slate-400">Slack <span className="pill" onClick={() => setQuote({ id: c.slack_id, quote: c.slack_snippet })}>{c.slack_id}</span>: “{c.slack_snippet}”</div>
                <div className="mt-3"><button className="btn btn-sm btn-amber" style={{ animation: "none" }} onClick={onRemediate}>Auto-Generate Remediation PR &amp; Executive Memo</button></div>
              </div>
            ))}
            <div className="text-emerald tracking-[0.12em] font-semibold mt-2">EMERGENCY HANDOVER DOSSIERS</div>
            {dossiers.length === 0 && <div className="text-slate-500">Run the swarm to have the Tribal-Archaeologist reconstruct undocumented knowledge for orphaned systems.</div>}
            {dossiers.map((d) => (
              <div key={d.orphan_id} className="border border-emerald/30 rounded-2xl p-3.5">
                <pre className="whitespace-pre-wrap text-slate-200 font-mono">{d.runbook}</pre>
                <div className="flex flex-wrap gap-1 mt-1">
                  {d.sources.map((s: Any) => (
                    <span key={s.id} className="pill" onClick={() => { setQuote(s); onHighlight(d.provenance_path); }}>{s.id}</span>
                  ))}
                </div>
              </div>
            ))}
            {quote && (
              <div className="border border-neon/45 rounded-2xl p-3.5 bg-neon/5">
                <div className="text-neon">{quote.id} <span className="cursor-pointer text-slate-500" onClick={() => setQuote(null)}>✕</span></div>
                <div className="text-slate-100">“{quote.quote}”</div>
              </div>
            )}
          </>
        )}
        {/* ---------------- TAB 4 ---------------- */}
        {active === 3 && (
          <>
            <div className="text-neon tracking-[0.12em] font-semibold">MULTIVERSE STRATEGY TOURNAMENT</div>
            <p className="text-slate-300 leading-[1.7]">
              Fork the production graph into three isolated FalkorDB universes, apply a different recovery strategy in each, then
              compare the resulting graphs on tech match, engineer load, policy compliance and new single points of failure.
            </p>
            <button className="btn btn-ok" disabled={tourBusy} onClick={onTournament}>{tourBusy ? "Running tournament…" : "Run 3-Universe FalkorDB Tournament"}</button>
            {tourMsg && <div className="text-amber leading-[1.6]">{tourMsg}</div>}
            {tournament && (
              <div className="space-y-3">
                <div className="text-slate-400">
                  {tournament.parallel_wall_ms} ms for 3 universes · winner{" "}
                  <b className="text-emerald">{tournament.universes.find((u: Any) => u.is_winner)?.title ?? "none"}</b>
                </div>
                <button className="btn btn-sm" onClick={onReopenTournament}>Open full comparison</button>
                {tournament.universes.map((u: Any) => (
                  <div key={u.key} className={`rounded-2xl p-3.5 border ${u.is_winner ? "border-emerald/45 bg-emerald/5" : "border-white/10"}`}>
                    <div className="flex justify-between"><span className="text-slate-100">{u.title}</span><span className={u.is_winner ? "text-emerald" : "text-crimson"}>{u.is_winner ? "WINNER" : "REJECTED"}</span></div>
                    <div className="text-slate-400 mt-1">tech {u.metrics.tech_match_pct}% · peak load {u.metrics.peak_load_pct}% · policy {u.metrics.policy_compliance_pct}% · SPOFs {u.metrics.bus_factor_1_assets}</div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
        {/* ---------------- TAB 3 ---------------- */}
        {active === 2 && (
          <>
            <div className="flex justify-between items-center">
              <div className="text-neon tracking-[0.12em] font-semibold">COGNITIVE MEMORY</div>
              <button className="btn btn-ok btn-sm" disabled={!canVaccinate} onClick={onVaccinate}>Vaccinate Organization (Consolidate Memory)</button>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="border border-white/10 rounded-2xl p-3.5"><div className="text-slate-400">SEMANTIC</div><div className="text-lg text-neon">{memory?.semantic?.nodes ?? "—"}</div>nodes · {memory?.semantic?.edges ?? "—"} edges (live org topology)</div>
              <div className="border border-white/10 rounded-2xl p-3.5"><div className="text-slate-400">EPISODIC</div><div className="text-lg text-amber">{memory?.episodes?.length ?? 0}</div>episodes · {memory?.handoffs?.length ?? 0} handoffs</div>
              <div className="border border-white/10 rounded-2xl p-3.5"><div className="text-slate-400">PROCEDURAL</div><div className="text-lg text-emerald">{memory?.playbooks?.length ?? 0}</div>playbooks</div>
            </div>
            <div className="text-slate-400 tracking-[0.12em] font-semibold">LIVE TELEMETRY · SESSION 1 vs SESSION 2</div>
            <div className="grid grid-cols-2 gap-2">
              <div className="border border-amber/45 rounded-2xl p-3.5 bg-amber/5">
                <div className="text-amber font-bold">SESSION 1 · EPISODIC SWARM (Cold Start)</div>
                <div className="text-2xl text-amber mt-1">{bench.s1Queries ?? "—"}</div>
                <div className="text-slate-200">Cypher Queries Executed{bench.s1Ms != null && ` · ${bench.s1Ms} ms`}</div>
                <div className="text-slate-400 mt-1">4 Agents Coordinated via Graph Handoffs</div>
                <div className="text-slate-400">Full Multi-Hop Traversal</div>
              </div>
              <div className="border border-emerald/45 rounded-2xl p-3.5 bg-emerald/5">
                <div className="text-emerald font-bold">SESSION 2 · PROCEDURAL FAST-PATH (Vaccinated)</div>
                <div className="text-2xl text-emerald mt-1">{bench.s2Queries ?? "—"}</div>
                <div className="text-slate-200">Cypher Query Lookup{bench.s2Ms != null && ` (${bench.s2Ms} ms)`}{bench.s2ApplyMs != null && ` + ${bench.s2ApplyMs} ms Fork Replay`}</div>
                <div className="text-emerald mt-1 font-bold">{bench.s1Queries && bench.s2Queries ? `${((1 - bench.s2Queries / bench.s1Queries) * 100).toFixed(1)}% Query Reduction` : "— Query Reduction"}</div>
                <div className="text-slate-400">1-Hop (:ProceduralPlaybook) Match</div>
              </div>
            </div>
            <div className="h-3 bg-amber/70 rounded-xl" title="Session 1 queries" style={{ width: bench.s1Queries ? "100%" : "0%" }} />
            <div className="h-3 bg-emerald rounded-xl" title="Session 2 queries" style={{ width: bench.s1Queries && bench.s2Queries ? `${Math.max(1.5, (bench.s2Queries / bench.s1Queries) * 100)}%` : "0%" }} />
            <div className="text-slate-400 tracking-[0.12em] font-semibold">PROCEDURAL PLAYBOOKS</div>
            {memory?.playbooks?.map((p: Any) => (
              <div key={p.id} className="border border-emerald/30 rounded-2xl p-3.5">
                <div className="text-emerald">★ {p.name}</div>
                <div className="text-slate-400">signature: {p.signature} · confidence {p.confidence} · {p.steps} fused steps · hits {p.hits ?? 0}{p.session1_queries ? ` · distilled from ${p.session1_queries} queries` : ""}</div>
              </div>
            ))}
            <div className="text-slate-400 tracking-[0.12em] font-semibold">EPISODIC TIMELINE</div>
            {memory?.episodes?.map((e: Any) => (
              <div key={e.id} className="border border-white/10 rounded-2xl p-3.5">
                <div className="text-amber">{e.id} <span className="text-slate-500">· {e.signature}</span></div>
                {e.steps.map((s: Any, i: number) => (
                  <div key={s.id} className="text-slate-300 truncate">
                    {i > 0 && <span className="text-emerald">⇢ HANDOFF_TO </span>}[{s.seq}] {s.agent} · {s.action}{s.n_queries != null && ` · ${s.n_queries}q`}
                  </div>
                ))}
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
