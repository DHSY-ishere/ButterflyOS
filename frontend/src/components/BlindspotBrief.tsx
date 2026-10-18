"use client";
import Modal from "@/components/Modal";
import type { Any } from "@/lib/api";

const usd = (n: number) => (n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : `$${n.toLocaleString()}`);

export default function BlindspotBrief({ data, open, onClose, onSimulate }: { data: Any; open: boolean; onClose: () => void; onSimulate: () => void }) {
  const d = data?.data;
  const top = d?.blindspot;
  return (
    <Modal open={open && !!top} onClose={onClose} title="CEO Existential Risk Brief" eyebrow="Auto-discovered blindspot" width={920}>
      {top && (
        <div className="space-y-8">
          <div className="grid md:grid-cols-[auto_1fr] gap-8 items-center">
            <div className="relative w-[148px] h-[148px] mx-auto">
              <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
                <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="9" />
                <circle cx="60" cy="60" r="52" fill="none" stroke="url(#lethal)" strokeWidth="9" strokeLinecap="round"
                  strokeDasharray={`${(top.lethality_score / 100) * 326.7} 326.7`} />
                <defs><linearGradient id="lethal" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#FFC46B" /><stop offset="1" stopColor="#FF5D8F" /></linearGradient></defs>
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <div className="text-[34px] font-semibold tabular-nums text-white leading-none">{top.lethality_score}</div>
                <div className="text-[11.5px] text-white/50 mt-1">lethality / 100</div>
              </div>
            </div>
            <div>
              <div className="text-[13px] text-white/50">#1 lethal K=2 extinction pair, out of {d.pairs_evaluated} evaluated</div>
              <div className="mt-2 text-[26px] font-semibold tracking-tight text-white">
                {top.engineer.name} <span className="text-white/35">+</span> {top.service.name}
              </div>
              <p className="mt-3 text-[14.5px] leading-[1.65] text-white/62">
                Losing this engineer and this service together exposes {usd(top.arr_exposed_usd)} of ARR, cascades through{" "}
                {top.impacted_services.length} services and orphans {top.orphaned_count} artifacts that nobody else owns.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="panel-flat p-5"><div className="text-[12px] text-white/50">ARR exposed</div><div className="mt-1 text-[26px] font-semibold text-crimson tabular-nums">{usd(top.arr_exposed_usd)}</div></div>
            <div className="panel-flat p-5"><div className="text-[12px] text-white/50">SLA burn rate</div><div className="mt-1 text-[26px] font-semibold text-amber tabular-nums">${top.burn_rate_per_min_usd.toLocaleString()}<span className="text-[13px] text-white/45">/min</span></div></div>
            <div className="panel-flat p-5"><div className="text-[12px] text-white/50">Orphaned artifacts</div><div className="mt-1 text-[26px] font-semibold text-neon tabular-nums">{top.orphaned_count}</div></div>
          </div>

          <div>
            <div className="text-[12px] font-semibold tracking-[0.1em] uppercase text-white/45 mb-3">Orphaned artifacts</div>
            <div className="flex flex-wrap gap-2">{top.orphaned_artifacts.map((a: string) => <span key={a} className="pill">{a}</span>)}</div>
          </div>

          <div>
            <div className="text-[12px] font-semibold tracking-[0.1em] uppercase text-white/45 mb-3">Top lethal pairs</div>
            <div className="space-y-2">
              {d.top.map((p: Any, i: number) => (
                <div key={i} className="panel-flat px-5 py-3 flex items-center gap-4 text-[14px]">
                  <span className="text-white/40 w-5">{i + 1}</span>
                  <span className="flex-1 text-white">{p.engineer.name} + {p.service.name}</span>
                  <span className="text-white/50 text-[12.5px]">{usd(p.arr_exposed_usd)} · {p.orphaned_count} orphans</span>
                  <span className="font-semibold tabular-nums text-amber w-12 text-right">{p.lethality_score}</span>
                </div>
              ))}
            </div>
          </div>

          <details className="panel-flat px-5 py-4">
            <summary className="cursor-pointer text-[13px] font-medium text-neon">Exact Cypher proof · {data.latency_ms} ms · {data.algo_notes?.join(" · ")}</summary>
            <pre className="mt-4 whitespace-pre-wrap text-slate-200 bg-black/30 rounded-xl p-4">{d.proof_cypher}</pre>
            {top.verification_row && <div className="mt-3 text-[12.5px] text-emerald">Verified live: {JSON.stringify(top.verification_row)}</div>}
            <div className="mt-3 text-[12.5px] text-white/45">Score = 100 × (0.35·ARR + 0.25·cascade + 0.25·orphan-weight + 0.15·centrality). {d.orphan_weighting}</div>
          </details>

          <div className="flex justify-end gap-3">
            <button className="btn" onClick={onClose}>Not now</button>
            <button className="btn btn-danger" onClick={onSimulate}>Simulate this extinction</button>
          </div>
        </div>
      )}
    </Modal>
  );
}
