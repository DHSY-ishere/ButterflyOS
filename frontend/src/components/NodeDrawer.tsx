"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Any } from "@/lib/api";

interface Props {
  nodeId: string | null;
  graph: string;
  armed: boolean;
  onToggleArm: (id: string) => void;
  onOpen: (id: string) => void;
  onClose: () => void;
  onHighlight: (ids: string[]) => void;
}

export default function NodeDrawer({ nodeId, graph, armed, onToggleArm, onOpen, onClose, onHighlight }: Props) {
  const [d, setD] = useState<Any>(null);

  useEffect(() => {
    if (!nodeId) return;
    let live = true;
    api.node(nodeId, graph).then((r) => live && setD(r)).catch(() => live && setD(null));
    return () => { live = false; };
  }, [nodeId, graph]);

  if (!nodeId || !d || d.id !== nodeId) return null;
  const props = Object.entries(d.props ?? {}).filter(([k]) => !["plan_json", "snapshot_json"].includes(k));
  return (
    <div className="panel p-5 text-[13px] max-h-[340px] overflow-y-auto" style={{ background: "rgba(13,17,40,0.96)", backdropFilter: "blur(24px)" }}>
      <div className="flex justify-between items-start">
        <div>
          <span className="text-neon">{d.label}</span> <span className="text-slate-400">· {d.id}</span>
          <div className="text-slate-100 text-sm">{String(d.props?.name ?? d.props?.title ?? d.id)}</div>
        </div>
        <div className="flex gap-2">
          <button className={`btn ${armed ? "btn-ok" : "btn-danger"}`} onClick={() => onToggleArm(nodeId)}>
            {armed ? "Disarm Meteor" : "Arm Chaos Meteor"}
          </button>
          <button className="btn" onClick={onClose}>✕</button>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-x-4 mt-2 text-slate-300">
        {props.filter(([k]) => k !== "id").map(([k, v]) => (
          <div key={k} className="truncate" title={String(v)}><span className="text-slate-500">{k}:</span> {String(v)}</div>
        ))}
      </div>
      <div className="mt-2 text-slate-500">Neighborhood provenance (1 hop):</div>
      <div className="flex flex-wrap gap-1 mt-1">
        {d.neighbors.map((n: Any, i: number) => (
          <span key={i} className="pill" title={n.name} onClick={() => { onOpen(n.id); onHighlight([nodeId, n.id]); }}>
            {n.outgoing ? "→" : "←"} {n.rel} {n.id}
          </span>
        ))}
      </div>
      <details className="mt-2">
        <summary className="cursor-pointer text-neon/80">Cypher</summary>
        {d.cypher_executed.map((c: Any, i: number) => <pre key={i} className="bg-black/30 p-1 rounded-xl whitespace-pre-wrap text-slate-300">{c.ms}ms {c.cypher}</pre>)}
      </details>
    </div>
  );
}
