"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Any } from "@/lib/api";

const PRESETS: [string, string][] = [
  ["Run PageRank", "CALL algo.pageRank('Service', 'DEPENDS_ON') YIELD node, score\nRETURN node.id AS id, node.name AS name, score ORDER BY score DESC"],
  ["Run Betweenness Centrality", "CALL algo.betweenness({nodeLabels: ['Service','Engineer','Repository','Commit'], relationshipTypes: ['DEPENDS_ON','OWNS','AUTHORED','MODIFIED_IN','DEPLOYED_FROM'], samplingSize: 64, samplingSeed: 42}) YIELD node, score\nRETURN labels(node)[0] AS label, node.id AS id, node.name AS name, score ORDER BY score DESC LIMIT 10"],
  ["Run WCC Components", "CALL algo.WCC({nodeLabels: ['Service','Engineer','Repository','Ticket','Database'], relationshipTypes: ['OWNS','DEPLOYED_FROM','ASSIGNED_TO','AUTO_REASSIGNED_TO']}) YIELD node, componentId\nRETURN componentId, collect(node.id) AS node_ids, count(node) AS size ORDER BY size DESC"],
  ["Inspect Agent Handoff Nodes", "MATCH (a:EpisodicStep)-[h:HANDOFF_TO]->(b:EpisodicStep)\nRETURN a.agent AS from_agent, b.agent AS to_agent, a.id AS from_step, b.id AS to_step, a.n_queries AS queries ORDER BY a.id"],
  ["Show Procedural Playbooks", "MATCH (p:ProceduralPlaybook)\nRETURN p.id AS id, p.name AS name, p.signature AS signature, p.confidence AS confidence, p.steps AS steps, p.hits AS hits, p.session1_queries AS session1_queries"],
];

function fmt(v: Any): string {
  if (v === null || v === undefined) return "∅";
  if (typeof v === "object") return JSON.stringify(v);
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(5);
  return String(v);
}

export default function CypherInspector({ open, graph, onClose }: { open: boolean; graph: string; onClose: () => void }) {
  const [q, setQ] = useState(PRESETS[0][1]);
  const [res, setRes] = useState<Any>(null);
  const [err, setErr] = useState("");
  const [schema, setSchema] = useState<Any>(null);
  const [tools, setTools] = useState<Any[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    api.schema(graph).then(setSchema).catch(() => setSchema(null));
    api.mcpTools().then((r) => setTools(r.tools)).catch(() => setTools([]));
  }, [open, graph]);

  if (!open) return null;

  const run = async (query: string) => {
    setBusy(true);
    setErr("");
    try {
      setRes(await api.cypher(graph, query));
    } catch (e) {
      setErr(String(e).replace(/^Error: /, ""));
      setRes(null);
    }
    setBusy(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60" onClick={onClose}>
      <aside role="dialog" aria-label="Cypher and MCP Inspector" className="panel h-full w-[760px] max-w-full p-3 overflow-y-auto space-y-3 text-[12.5px]" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center">
          <div>
            <span className="text-neon tracking-[0.12em] font-semibold">CYPHER & MCP INSPECTOR</span> <span className="text-slate-500">· live against</span> <span className="text-amber">{graph}</span>
          </div>
          <button className="btn" onClick={onClose}>✕ close</button>
        </div>
        <div className="flex flex-wrap gap-1">
          {PRESETS.map(([name, query]) => (
            <button key={name} className="btn" onClick={() => { setQ(query); run(query); }}>{name}</button>
          ))}
        </div>
        <textarea value={q} onChange={(e) => setQ(e.target.value)} spellCheck={false} rows={6}
          className="w-full bg-black/30 border border-neon/30 rounded-xl p-2 text-slate-100 outline-none focus:border-neon font-mono" />
        <div className="flex items-center gap-3">
          <button className="btn btn-ok" disabled={busy} onClick={() => run(q)}>▶ Run read-only query</button>
          <span className="text-slate-500">writes rejected · executed via GRAPH.RO_QUERY</span>
          {res && <span className="text-amber ml-auto">{res.row_count} rows · {res.latency_ms} ms round-trip · {res.server_reported_ms?.toFixed?.(3)} ms server</span>}
        </div>
        {err && <div className="text-crimson border border-crimson/45 rounded-xl p-2">{err}</div>}
        {res && (
          <div className="border border-white/10 rounded-xl max-h-[320px] overflow-auto">
            <table className="w-full">
              <thead className="sticky top-0 bg-[#0D111C] text-neon">
                <tr>{res.columns.map((c: string) => <th key={c} className="text-left px-2 py-1">{c}</th>)}</tr>
              </thead>
              <tbody>
                {res.rows.map((r: Any[], i: number) => (
                  <tr key={i} className="border-t border-white/5">
                    {r.map((c, k) => <td key={k} className="px-2 py-1 text-slate-200 align-top">{fmt(c)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="text-slate-400 tracking-[0.12em] font-semibold">GRAPH SCHEMA · {graph}</div>
        {schema && (
          <div className="grid grid-cols-2 gap-2">
            <div className="border border-white/10 rounded-xl p-2">
              <div className="text-neon mb-1">Labels</div>
              {schema.labels.map((l: Any) => <div key={l.label} className="flex justify-between"><span>(:{l.label})</span><span className="text-amber">{l.count}</span></div>)}
            </div>
            <div className="border border-white/10 rounded-xl p-2">
              <div className="text-neon mb-1">Relationships</div>
              {schema.relationships.map((l: Any) => <div key={l.type} className="flex justify-between"><span>[:{l.type}]</span><span className="text-amber">{l.count}</span></div>)}
            </div>
          </div>
        )}
        <div className="text-slate-400 tracking-[0.12em] font-semibold">MCP TOOL REGISTRY · POST /mcp (JSON-RPC) · POST /api/mcp/call</div>
        <div className="space-y-1">
          {tools.map((t) => (
            <div key={t.name} className="border border-white/10 rounded-xl p-2">
              <span className="text-emerald">{t.name}</span>
              <span className="text-slate-500"> ({Object.keys(t.inputSchema.properties).join(", ")})</span>
              <div className="text-slate-400">{t.description}</div>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
