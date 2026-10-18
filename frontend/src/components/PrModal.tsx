"use client";
import { useState } from "react";
import Modal from "@/components/Modal";
import type { Any } from "@/lib/api";

function DiffLine({ n, line }: { n: number; line: string }) {
  let bg = "transparent", fg = "#c9d3ee";
  if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("diff") || line.startsWith("index")) fg = "rgba(200,210,240,0.5)";
  else if (line.startsWith("@@")) { bg = "rgba(124,196,255,0.10)"; fg = "#9fd2ff"; }
  else if (line.startsWith("+")) { bg = "rgba(66,245,194,0.12)"; fg = "#9dffe0"; }
  else if (line.startsWith("-")) { bg = "rgba(255,93,143,0.13)"; fg = "#ffb3c8"; }
  return (
    <div className="flex" style={{ background: bg }}>
      <span className="select-none w-10 shrink-0 text-right pr-3 text-white/25">{n}</span>
      <span className="whitespace-pre" style={{ color: fg }}>{line || " "}</span>
    </div>
  );
}

export default function PrModal({ brief, open, applying, onClose, onApply }: { brief: Any; open: boolean; applying: boolean; onClose: () => void; onApply: () => void }) {
  const [view, setView] = useState<"pr" | "memo">("pr");
  const resolved = brief && brief.status?.startsWith("RESOLVED");
  const pr = brief?.pr;
  return (
    <Modal open={open && !!brief} onClose={onClose} title={pr?.title ?? "Remediation"} eyebrow="Autonomous remediation" width={1080}>
      {brief && (
        <div className="space-y-7">
          <div className="flex flex-wrap items-center gap-3">
            <span className={`chip ${resolved ? "" : "chip-bad"}`} style={resolved ? { background: "rgba(66,245,194,0.15)", borderColor: "rgba(66,245,194,0.5)", color: "#b9ffe9" } : { background: "rgba(255,93,143,0.14)", borderColor: "rgba(255,93,143,0.45)", color: "#ffd0de" }}>
              <i className="dot" />{resolved ? "ADR-002 · RESOLVED (100% COMPLIANT)" : "ADR-002 · VIOLATION"}
            </span>
            {pr && <span className="text-[13px] text-white/50">{pr.branch} → {pr.base} · {pr.files_changed} file changed</span>}
            <div className="flex-1" />
            <div className="seg" style={{ margin: 0, minWidth: 260 }}>
              <button className={view === "pr" ? "on" : ""} onClick={() => setView("pr")}>Pull request</button>
              <button className={view === "memo" ? "on" : ""} onClick={() => setView("memo")}>Executive memo</button>
            </div>
          </div>

          {view === "pr" && pr && (
            <>
              <div className="grid md:grid-cols-2 gap-5">
                <div className="panel-flat p-5">
                  <div className="text-[12px] font-semibold tracking-[0.1em] uppercase text-white/45 mb-3">Violation vs. prescribed route</div>
                  <div className="text-[13.5px] text-crimson">({brief.violation?.service})-[:DIRECT_WRITES_TO]-&gt;({brief.violation?.database})</div>
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-[12.5px]">
                    {brief.route.map((r: string, i: number) => {
                      const hop = brief.hops[i];
                      return (
                        <span key={r} className="flex items-center gap-2">
                          <span className="pill">{r}</span>
                          {hop && <span className={hop.exists ? "text-emerald" : "text-amber"} title={hop.exists ? "edge exists" : "edge added by this PR"}>{hop.exists ? "→" : "⇢ new"}</span>}
                        </span>
                      );
                    })}
                  </div>
                  <div className="mt-3 text-[12.5px] text-white/45">Authored by {brief.violation?.author} in {brief.violation?.commit_id}. Hops marked “new” are created when the patch is applied.</div>
                </div>
                <div className="panel-flat p-5">
                  <div className="text-[12px] font-semibold tracking-[0.1em] uppercase text-white/45 mb-3">Reviewers · from [:OWNS] edges</div>
                  <div className="flex flex-wrap gap-2">
                    {pr.reviewers.map((r: Any) => <span key={r.id} className="chip" title={`owns ${r.owns.join(", ")}`}>{r.handle}</span>)}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">{pr.labels.map((l: string) => <span key={l} className="pill">{l}</span>)}</div>
                  <div className="mt-3 text-[12.5px] text-white/45">{pr.note}</div>
                </div>
              </div>
              <div className="rounded-2xl overflow-hidden border border-white/10" style={{ background: "rgba(4,6,16,0.6)" }}>
                <div className="px-5 py-3 text-[12.5px] text-white/55 border-b border-white/10 font-mono">repo_webhook_svc/dispatcher.py</div>
                <div className="py-3 font-mono text-[12.5px] leading-[1.7] overflow-x-auto">
                  {pr.diff.split("\n").map((l: string, i: number) => <DiffLine key={i} n={i + 1} line={l} />)}
                </div>
              </div>
            </>
          )}
          {view === "memo" && (
            <pre className="whitespace-pre-wrap font-sans text-[14.5px] leading-[1.75] text-white/80 panel-flat p-7" style={{ fontFamily: "inherit" }}>{brief.memo}</pre>
          )}
          {view === "memo" && (
            <div className="grid grid-cols-2 gap-4">
              <div className="panel-flat p-5"><div className="text-[12px] text-white/50">ARR behind the ledger path</div><div className="text-[24px] font-semibold text-crimson tabular-nums">${(brief.arr_exposed_usd / 1e6).toFixed(1)}M</div></div>
              <div className="panel-flat p-5"><div className="text-[12px] text-white/50">SLA penalty burn</div><div className="text-[24px] font-semibold text-amber tabular-nums">${brief.burn_rate_per_min_usd.toLocaleString()}/min</div></div>
            </div>
          )}
          <div className="flex items-center justify-end gap-3">
            {resolved && <span className="text-[13px] text-emerald">Patch applied · [:DIRECT_WRITES_TO] removed · [:REMEDIATED_BY_PR] recorded</span>}
            <button className="btn btn-ok" disabled={applying || resolved} onClick={onApply}>{applying ? "Applying…" : resolved ? "Applied to graph" : "Apply Patch to Graph"}</button>
          </div>
        </div>
      )}
    </Modal>
  );
}
