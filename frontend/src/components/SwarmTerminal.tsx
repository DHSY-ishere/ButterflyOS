"use client";
import type { Any } from "@/lib/api";

export const AGENT_NAMES = ["Shockwave-Triage-Agent", "BusFactor-Detector-Agent", "Tribal-Archaeologist-Agent", "Continuity-Healer-Agent"];

const BADGE: Record<string, string> = {
  IDLE: "text-slate-400 border-slate-600",
  TRAVERSING: "text-amber border-amber animate-pulse",
  HANDOFF_COMMITTED: "text-emerald border-emerald",
  FAST_PATH_HIT: "text-neon border-neon animate-pulse",
};

interface Props {
  statuses: Record<string, string>;
  events: Any[];
  queryLog: Any[];
  onHighlight: (ids: string[]) => void;
}

export default function SwarmTerminal({ statuses, events, queryLog, onHighlight }: Props) {
  const steps = events.filter((e) => e.type === "step");
  return (
    <div className="panel h-full flex flex-col overflow-hidden">
      <div className="px-5 py-4 border-b border-white/10 text-neon text-xs tracking-[0.12em] font-semibold">MULTI-AGENT SWARM · MCP</div>
      <div className="px-5 py-4 grid grid-cols-1 gap-2.5">
        {AGENT_NAMES.map((a, i) => {
          const s = statuses[a] ?? "IDLE";
          return (
            <div key={a} className="flex items-center justify-between text-[12.5px]">
              <span className="text-slate-300">{i + 1}. {a.replace("-Agent", "")}</span>
              <span className={`border rounded-xl px-1.5 py-0.5 text-[11.5px] ${BADGE[s]}`}>{s}</span>
            </div>
          );
        })}
      </div>
      <div className="px-5 py-2.5 border-y border-white/10 text-[11.5px] text-slate-400 tracking-[0.12em] font-semibold">LIVE CYPHER TRACE</div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-[12.5px]">
        {steps.length === 0 && (
          <div className="text-slate-500">
            No agent activity yet. Select nodes on the graph (or pick a scenario) → <span className="text-crimson">Simulate Extinction</span> → <span className="text-emerald">Run Swarm</span>.
          </div>
        )}
        {steps.map((s, i) => (
          <div key={i} className="border border-white/10 rounded-2xl p-4 bg-black/25">
            <div className="flex justify-between">
              <span className="text-neon">{s.agent}</span>
              <span className="text-amber">{s.latency_ms} ms · {s.cypher.length}q</span>
            </div>
            <div className="text-slate-400 text-[11.5px]">{s.tool}</div>
            <div className="text-slate-200 mt-1 whitespace-pre-wrap">{s.narrative}</div>
            <div className="mt-1 flex gap-2 text-[11.5px]">
              <span className={s.gate?.ok ? "text-emerald" : "text-crimson"}>
                {s.gate?.ok ? "✓ NO-NODE-NO-ACTION PASSED" : "✗ GATE REJECTED"} ({s.gate?.checked} nodes)
              </span>
              <span className="text-slate-500">{s.engine}</span>
            </div>
            <details className="mt-1">
              <summary className="cursor-pointer text-neon/80 hover:text-neon">View Executed Cypher & Provenance Path</summary>
              <div className="mt-1 space-y-1">
                {s.algo_notes?.map((n: string, k: number) => <div key={k} className="text-emerald/80">⚙ {n}</div>)}
                {s.cypher.map((c: Any, k: number) => (
                  <div key={k}>
                    <div className="text-amber">{c.ms} ms · {c.graph}</div>
                    <pre className="whitespace-pre-wrap text-slate-300 bg-black/30 p-1 rounded-xl overflow-x-auto">{c.cypher}</pre>
                  </div>
                ))}
                <div className="text-slate-400">provenance_path:</div>
                <div className="flex flex-wrap gap-1">
                  {s.provenance.map((id: string) => <span key={id} className="pill" onClick={() => onHighlight([id])}>{id}</span>)}
                </div>
              </div>
            </details>
            {s.handoff_to && <div className="text-[11.5px] text-emerald mt-1">⇢ HANDOFF_TO {s.handoff_to} (stored in FalkorDB)</div>}
          </div>
        ))}
      </div>
      <div className="border-t border-white/10 px-5 py-3 h-24 overflow-y-auto text-[11.5px] text-slate-500">
        {queryLog.slice(-30).reverse().map((q, i) => (
          <div key={i} className="truncate"><span className="text-amber">{q.ms}ms</span> {q.cypher.replace(/\s+/g, " ").slice(0, 80)}</div>
        ))}
      </div>
    </div>
  );
}
