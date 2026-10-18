"use client";
import Modal from "@/components/Modal";
import type { Any } from "@/lib/api";

function Row({ k, v, tone }: { k: string; v: React.ReactNode; tone?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-2.5 border-b border-white/[0.07] text-[13.5px]">
      <span className="text-white/55">{k}</span>
      <span className={`font-semibold tabular-nums text-right ${tone ?? "text-white"}`}>{v}</span>
    </div>
  );
}

export default function TournamentModal({ data, open, onClose, onOpenGraph }: { data: Any; open: boolean; onClose: () => void; onOpenGraph: (g: string) => void }) {
  return (
    <Modal open={open && !!data} onClose={onClose} title="Multiverse Strategy Tournament" eyebrow="3 isolated FalkorDB universes" width={1240}>
      {data && (
        <div className="space-y-8">
          <div className="flex flex-wrap items-center gap-x-8 gap-y-3 text-[14px]">
            <div><span className="text-white/50">Fork + evaluate, 3 universes: </span><b className="text-emerald tabular-nums">{data.parallel_wall_ms} ms</b></div>
            <div className="text-white/45 text-[13px]">
              GRAPH.COPY forks run back-to-back (FalkorDB serves one copy of a source at a time); the three evaluations run concurrently.
              Serial sum would be {data.sequential_sum_ms} ms.
            </div>
          </div>
          <div className="grid lg:grid-cols-3 gap-6">
            {data.universes.map((u: Any) => {
              const m = u.metrics;
              const win = u.is_winner;
              const loadTone = m.peak_load_pct > 100 ? "text-crimson" : m.peak_load_pct > 85 ? "text-amber" : "text-emerald";
              return (
                <div key={u.key} className="rounded-3xl p-6 flex flex-col"
                  style={{
                    background: win ? "linear-gradient(160deg, rgba(66,245,194,0.14), rgba(255,255,255,0.04))" : "rgba(255,255,255,0.045)",
                    border: `1px solid ${win ? "rgba(66,245,194,0.55)" : "rgba(255,255,255,0.12)"}`,
                    boxShadow: win ? "0 0 40px -12px rgba(66,245,194,0.55)" : undefined,
                  }}>
                  <div className="text-[12.5px] font-semibold text-white/55">{u.title}</div>
                  <div className="mt-1 font-mono text-[11.5px] text-neon truncate" title={u.graph}>{u.graph}</div>
                  <div className={`mt-4 inline-flex self-start items-center rounded-full px-3 py-1 text-[12px] font-bold tracking-wide ${win ? "bg-emerald text-black" : "bg-crimson/90 text-black"}`}>
                    {win ? "WINNER · PARETO-OPTIMAL" : "REJECTED"}
                  </div>
                  <p className="mt-4 text-[13px] leading-[1.55] text-white/55">{u.blurb}</p>
                  <div className="mt-3">
                    <Row k="Tech match" v={`${m.tech_match_pct}%`} />
                    <Row k={`Peak engineer load · ${m.peak_engineer}`} v={`${m.peak_load_pct}%`} tone={loadTone} />
                    <Row k="Policy compliance" v={`${m.policy_compliance_pct}%`} tone={m.policy_compliance_pct < 100 ? "text-crimson" : "text-emerald"} />
                    <Row k="Bus-factor-1 bottlenecks" v={m.bus_factor_1_assets} tone={m.bus_factor_1_assets >= 4 ? "text-amber" : "text-emerald"} />
                    <Row k="Orphans remaining" v={m.orphans_remaining} tone={m.orphans_remaining ? "text-crimson" : "text-emerald"} />
                    <Row k="Fork · evaluate" v={`${u.fork_ms} ms · ${u.eval_ms} ms`} tone="text-white/80" />
                  </div>
                  <div className="mt-4 space-y-1.5">
                    {m.engineer_loads.filter((l: Any) => l.assigned > 0).map((l: Any) => (
                      <div key={l.id}>
                        <div className="flex justify-between text-[12px] text-white/55"><span>{l.name} · {l.assigned} systems</span><span className="tabular-nums">{l.load}%</span></div>
                        <div className="bar" style={{ marginTop: 3 }}>
                          <i style={{ width: `${Math.min(100, l.load)}%`, background: l.load > 100 ? "linear-gradient(90deg,#FF5D8F,#ff2f6d)" : l.load > 85 ? "linear-gradient(90deg,#FFC46B,#ff9f43)" : undefined }} />
                        </div>
                      </div>
                    ))}
                  </div>
                  {u.reasons.length > 0 && (
                    <ul className="mt-4 space-y-1.5 text-[12.5px] text-crimson/90 list-disc pl-4">{u.reasons.map((r: string) => <li key={r}>{r}</li>)}</ul>
                  )}
                  <div className="mt-auto pt-5">
                    <button className="btn btn-sm w-full justify-center" onClick={() => onOpenGraph(u.graph)}>Open this universe</button>
                  </div>
                </div>
              );
            })}
          </div>
          <details className="panel-flat px-5 py-4">
            <summary className="cursor-pointer text-[13px] font-medium text-neon">Executed Cypher (sample from each universe)</summary>
            <div className="mt-4 grid lg:grid-cols-3 gap-4">
              {data.universes.map((u: Any) => (
                <div key={u.key}>
                  <div className="text-[12px] text-white/45 mb-2">{u.graph} · {u.queries} queries</div>
                  {u.cypher_executed.slice(-3).map((c: Any, i: number) => <pre key={i} className="whitespace-pre-wrap bg-black/30 rounded-xl p-3 mb-2 text-slate-300">{c.ms} ms · {c.cypher}</pre>)}
                </div>
              ))}
            </div>
          </details>
        </div>
      )}
    </Modal>
  );
}
