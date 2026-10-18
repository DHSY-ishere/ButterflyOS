"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Any } from "@/lib/api";

const PAD = 36;

export const LABEL_STYLE: Record<string, { color: string; r: number; shape: string }> = {
  Engineer: { color: "#7CC4FF", r: 15, shape: "hex" },
  Service: { color: "#8B8CFF", r: 16, shape: "circle" },
  Database: { color: "#B793FF", r: 15, shape: "rect" },
  Repository: { color: "#A5B4FC", r: 11, shape: "rect" },
  ADR_Doc: { color: "#FFC46B", r: 12, shape: "shield" },
  Commit: { color: "#64748B", r: 7, shape: "circle" },
  SlackThread: { color: "#CBD5E1", r: 7, shape: "circle" },
  Ticket: { color: "#FB923C", r: 9, shape: "diamond" },
  Team: { color: "#2DD4BF", r: 10, shape: "circle" },
  ProceduralPlaybook: { color: "#42F5C2", r: 14, shape: "star" },
  CustomerContract: { color: "#FFD27A", r: 10, shape: "diamond" },
};

const EDGE_STYLE: Record<string, { color: string; w: number; dash?: string; op: number }> = {
  DEPENDS_ON: { color: "#8B8CFF", w: 1.6, op: 0.75 },
  OWNS: { color: "#7CC4FF", w: 1.2, op: 0.5 },
  DIRECT_WRITES_TO: { color: "#FF5D8F", w: 2.2, dash: "4 3", op: 1 },
  AUTO_REASSIGNED_TO: { color: "#42F5C2", w: 2.6, op: 1 },
  FAILOVER_ROUTE: { color: "#42F5C2", w: 2, op: 0.9 },
  FAILOVER_REPLICA: { color: "#42F5C2", w: 1.5, dash: "2 3", op: 0.8 },
  SLA_DEPENDS_ON: { color: "#FFD27A", w: 1, dash: "2 4", op: 0.45 },
  REMEDIATED_BY_PR: { color: "#42F5C2", w: 1.6, dash: "3 4", op: 0.85 },
  FORMERLY_OWNED: { color: "#FF5D8F", w: 1.6, dash: "5 4", op: 0.9 },
  FORMERLY_ASSIGNED: { color: "#FF5D8F", w: 1.6, dash: "5 4", op: 0.9 },
};
const PARTICLE_TYPES = new Set(["DEPENDS_ON", "OWNS", "AUTO_REASSIGNED_TO"]);
const HEAL_TYPES = new Set(["AUTO_REASSIGNED_TO", "FAILOVER_ROUTE", "FAILOVER_REPLICA"]);
const SEVER_TYPES = new Set(["FORMERLY_OWNED", "FORMERLY_ASSIGNED"]);
const STRUCTURAL = new Set(["Engineer", "Service", "Database", "Repository", "ProceduralPlaybook"]);

function shapePath(shape: string, r: number): string {
  if (shape === "hex")
    return Array.from({ length: 6 }, (_, i) => {
      const a = (Math.PI / 3) * i;
      return `${i ? "L" : "M"}${(r * Math.cos(a)).toFixed(1)},${(r * Math.sin(a)).toFixed(1)}`;
    }).join("") + "Z";
  if (shape === "diamond") return `M0,${-r}L${r},0L0,${r}L${-r},0Z`;
  if (shape === "shield") return `M0,${-r}L${r},${-r * 0.5}L${r * 0.8},${r * 0.6}L0,${r}L${-r * 0.8},${r * 0.6}L${-r},${-r * 0.5}Z`;
  if (shape === "star")
    return Array.from({ length: 10 }, (_, i) => {
      const a = (Math.PI / 5) * i - Math.PI / 2;
      const rr = i % 2 ? r * 0.45 : r;
      return `${i ? "L" : "M"}${(rr * Math.cos(a)).toFixed(1)},${(rr * Math.sin(a)).toFixed(1)}`;
    }).join("") + "Z";
  return "";
}

/** Human-readable health state used by the label pills. */
function health(label: string, status: string): { text: string; icon: string; color: string } | null {
  if (status === "EXTINCT") return { text: "EXTINCT", icon: "☠", color: "#FF5D8F" };
  if (status === "IMPACTED") return { text: "DEGRADED", icon: "⚠", color: "#FFC46B" };
  if (status === "RECOVERED" || status === "WARM_STANDBY") return { text: "HEALED", icon: "✚", color: "#42F5C2" };
  if (label === "Service" || label === "Database") return { text: "HEALTHY", icon: "✓", color: "#42F5C2" };
  return null;
}

type P = { x: number; y: number; vx: number; vy: number };
type View = { k: number; x: number; y: number };

interface Props {
  nodes: Any[];
  edges: Any[];
  targets: Set<string>;
  highlight: Set<string>;
  reticle: Set<string>;
  showCodeLayer: boolean;
  shockKey: number;
  isSim: boolean;
  onToggleTarget: (id: string) => void;
  onOpen: (id: string) => void;
}

export default function GraphCanvas({ nodes, edges, targets, highlight, reticle, showCodeLayer, shockKey, isSim, onToggleTarget, onOpen }: Props) {
  const pos = useRef<Map<string, P>>(new Map());
  const svgRef = useRef<SVGSVGElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const [sz, setSz] = useState({ w: 900, h: 560 });
  const szRef = useRef(sz);
  szRef.current = sz;
  const W = sz.w;
  const H = sz.h;
  const [, setTick] = useState(0);
  const [hover, setHover] = useState<string | null>(null);
  const [view, setView] = useState<View>({ k: 1, x: 0, y: 0 });
  const [diff, setDiff] = useState(true);
  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      if (r.width > 50 && r.height > 50) setSz({ w: Math.round(r.width), h: Math.round(r.height) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const raf = useRef<number>(0);
  const drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);
  const moved = useRef(false);

  const vis = useMemo(() => {
    const ns = nodes.filter((n) => showCodeLayer || STRUCTURAL.has(n.label));
    const ids = new Set(ns.map((n) => n.id));
    return { ns, es: edges.filter((e) => ids.has(e.source) && ids.has(e.target)) };
  }, [nodes, edges, showCodeLayer]);

  const fit = useCallback(() => {
    const pts = vis.ns.map((n) => pos.current.get(n.id)).filter(Boolean) as P[];
    if (!pts.length) return;
    const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
    const minX = Math.min(...xs) - 95, maxX = Math.max(...xs) + 95, minY = Math.min(...ys) - 40, maxY = Math.max(...ys) + 50;
    const k = Math.min(W / (maxX - minX), H / (maxY - minY), 2.6);
    setView({ k, x: (W - (maxX + minX) * k) / 2, y: (H - (maxY + minY) * k) / 2 });
  }, [vis, W, H]);

  const zoomBy = useCallback((f: number, cx = W / 2, cy = H / 2) => {
    setView((v) => {
      const k = Math.min(4, Math.max(0.3, v.k * f));
      return { k, x: cx - ((cx - v.x) / v.k) * k, y: cy - ((cy - v.y) / v.k) * k };
    });
  }, [W, H]);

  // Force-directed layout with boundary clamping; critically damped so it settles in ~1.5 s.
  useEffect(() => {
    const m = pos.current;
    const W = szRef.current.w, H = szRef.current.h;
    const sc = Math.min(W / 1000, H / 680) * 1.15 + 0.35;
    const groups = ["Engineer", "Service", "Database", "Repository", "Commit", "SlackThread", "ADR_Doc", "Ticket", "Team", "ProceduralPlaybook"];
    vis.ns.forEach((n, i) => {
      if (!m.has(n.id)) {
        const gi = Math.max(0, groups.indexOf(n.label));
        const a = (gi / groups.length) * Math.PI * 2 + i * 0.37;
        m.set(n.id, { x: W / 2 + Math.cos(a) * W * 0.32 + (Math.random() - 0.5) * 60, y: H / 2 + Math.sin(a) * H * 0.3 + (Math.random() - 0.5) * 60, vx: 0, vy: 0 });
      }
    });
    const TOTAL = 96; // ~1.6 s at 60 fps
    const linked = new Set<string>();
    for (const e of vis.es) { linked.add(e.source); linked.add(e.target); }
    const loose = new Set(vis.ns.filter((n) => !linked.has(n.id)).map((n) => n.id));
    let frames = 0;
    const step = () => {
      const arr = vis.ns.map((n) => ({ id: n.id, p: m.get(n.id)!, r: LABEL_STYLE[n.label]?.r ?? 8 }));
      const idx = new Map(arr.map((a) => [a.id, a]));
      for (let i = 0; i < arr.length; i++)
        for (let j = i + 1; j < arr.length; j++) {
          const a = arr[i], b = arr[j];
          let dx = a.p.x - b.p.x, dy = a.p.y - b.p.y;
          let d2 = dx * dx + dy * dy;
          if (d2 < 1) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; d2 = 1; }
          const d = Math.sqrt(d2);
          const f = Math.min(40, (4200 * sc * sc) / d2);
          a.p.vx += (dx / d) * f; a.p.vy += (dy / d) * f;
          b.p.vx -= (dx / d) * f; b.p.vy -= (dy / d) * f;
        }
      for (const e of vis.es) {
        const a = idx.get(e.source), b = idx.get(e.target);
        if (!a || !b) continue;
        const dx = b.p.x - a.p.x, dy = b.p.y - a.p.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const len = (e.type === "DEPENDS_ON" ? 140 : 105) * sc;
        const f = (d - len) * 0.014;
        a.p.vx += (dx / d) * f; a.p.vy += (dy / d) * f;
        b.p.vx -= (dx / d) * f; b.p.vy -= (dy / d) * f;
      }
      const t = frames / TOTAL;
      const damp = 0.78 - 0.3 * t; // smoothly increasing friction
      const cool = Math.max(0.05, 1 - t);
      for (const a of arr) {
        const g = loose.has(a.id) ? 12 : 1; // edge-less nodes (playbook stars) hug the centre
        a.p.vx += (W / 2 - a.p.x) * 0.003 * g; a.p.vy += (H / 2 - a.p.y) * 0.004 * g;
        a.p.vx *= damp; a.p.vy *= damp;
        const sp = Math.hypot(a.p.vx, a.p.vy);
        const cap = 18 * cool + 1;
        if (sp > cap) { a.p.vx *= cap / sp; a.p.vy *= cap / sp; }
        let nx = a.p.x + a.p.vx * cool, ny = a.p.y + a.p.vy * cool;
        if (nx < PAD) { nx = PAD; a.p.vx = Math.abs(a.p.vx) * 0.2; }
        if (nx > W - PAD) { nx = W - PAD; a.p.vx = -Math.abs(a.p.vx) * 0.2; }
        if (ny < PAD) { ny = PAD; a.p.vy = Math.abs(a.p.vy) * 0.2; }
        if (ny > H - PAD - 14) { ny = H - PAD - 14; a.p.vy = -Math.abs(a.p.vy) * 0.2; }
        a.p.x = nx; a.p.y = ny;
      }
      frames++;
      setTick((x) => x + 1);
      if (frames < TOTAL) raf.current = requestAnimationFrame(step);
      else for (const a of arr) { a.p.vx = 0; a.p.vy = 0; }
    };
    cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(step);
    const tm = setTimeout(fit, 1750); // auto-fit once the layout has settled
    return () => { cancelAnimationFrame(raf.current); clearTimeout(tm); };
  }, [vis]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { const t = setTimeout(fit, 250); return () => clearTimeout(t); }, [W, H]); // eslint-disable-line react-hooks/exhaustive-deps

  const byId = useMemo(() => new Map(vis.ns.map((n) => [n.id, n])), [vis]);
  const status = (id: string): string => byId.get(id)?.props?.status ?? "";
  const hot = (id: string) => ["EXTINCT", "IMPACTED"].includes(status(id));
  const diffOn = isSim && diff;

  // non-overlapping label pills: greedy vertical dodge
  const labels = (() => {
    const out: { id: string; x: number; y: number; w: number; text: string; h: ReturnType<typeof health> }[] = [];
    const items = vis.ns
      .filter((n) => STRUCTURAL.has(n.label) || hover === n.id)
      .map((n) => ({ n, p: pos.current.get(n.id)! }))
      .filter((o) => o.p)
      .sort((a, b) => a.p.y - b.p.y);
    const placed: { x: number; y: number; w: number }[] = [];
    for (const { n, p } of items) {
      const h = health(n.label, n.props?.status ?? "");
      const text = String(n.props?.name ?? n.props?.title ?? n.id).slice(0, 34);
      const w = text.length * 5.6 + 14 + (h ? 14 : 0);
      const r = LABEL_STYLE[n.label]?.r ?? 8;
      let y = p.y + r + 6;
      for (let t = 0; t < 8; t++) {
        const hit = placed.find((q) => Math.abs(q.x - p.x) < (q.w + w) / 2 + 2 && Math.abs(q.y - y) < 14);
        if (!hit) break;
        y += 14;
      }
      placed.push({ x: p.x, y, w });
      out.push({ id: n.id, x: p.x, y, w, text, h });
    }
    return out;
  })();

  const toSvg = (cx: number, cy: number) => {
    const r = svgRef.current!.getBoundingClientRect();
    const s = Math.max(W / r.width, H / r.height);
    return { x: (cx - r.left) * s, y: (cy - r.top) * s, s };
  };

  return (
    <div ref={boxRef} className="relative w-full h-full">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet"
        className="w-full h-full select-none touch-none"
        style={{ cursor: drag.current ? "grabbing" : "grab" }}
        onWheel={(e) => { const p = toSvg(e.clientX, e.clientY); zoomBy(e.deltaY < 0 ? 1.12 : 1 / 1.12, p.x, p.y); }}
        onPointerDown={(e) => { drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y }; moved.current = false; (e.target as Element).setPointerCapture?.(e.pointerId); }}
        onPointerMove={(e) => {
          if (!drag.current) return;
          const s = toSvg(0, 0).s;
          const dx = (e.clientX - drag.current.x) * s, dy = (e.clientY - drag.current.y) * s;
          if (Math.abs(dx) + Math.abs(dy) > 4) moved.current = true;
          setView((v) => ({ ...v, x: drag.current!.vx + dx, y: drag.current!.vy + dy }));
        }}
        onPointerUp={() => { drag.current = null; }}
      >
        <defs>
          {Object.entries({ ...EDGE_STYLE, default: { color: "#475569", w: 1, op: 0.35 } }).map(([k, s]) => (
            <marker key={k} id={`arr-${k}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M0,0L10,5L0,10z" fill={s.color} opacity={s.op} />
            </marker>
          ))}
          <filter id="glow-em" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2.5" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <g transform={`translate(${view.x},${view.y}) scale(${view.k})`}>
          {/* edges */}
          {vis.es.map((e, i) => {
            const a = pos.current.get(e.source), b = pos.current.get(e.target);
            if (!a || !b) return null;
            const st = EDGE_STYLE[e.type] ?? { color: "#475569", w: 1, op: 0.3 };
            const heal = HEAL_TYPES.has(e.type);
            const severed = SEVER_TYPES.has(e.type) || (["DEPENDS_ON", "OWNS", "DIRECT_WRITES_TO"].includes(e.type) && (status(e.source) === "EXTINCT" || status(e.target) === "EXTINCT"));
            const shock = !heal && (e.type === "DEPENDS_ON" || e.type === "OWNS") && (hot(e.source) || hot(e.target)) && status(e.source) !== "RECOVERED";
            let dim = highlight.size > 0 && !(highlight.has(e.source) && highlight.has(e.target));
            if (diffOn && !heal && !severed) dim = true;
            const color = heal ? "#42F5C2" : severed && diffOn ? "#FF5D8F" : shock ? "#FF5D8F" : st.color;
            const dash = severed && diffOn ? "7 5" : st.dash;
            return (
              <g key={`${e.source}-${e.type}-${e.target}-${i}`}>
                <line
                  key={shock ? `s${shockKey}` : "n"}
                  x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke={color}
                  strokeWidth={(diffOn && (heal || severed) ? st.w + 1 : shock ? st.w + 0.8 : st.w)}
                  strokeOpacity={dim ? 0.07 : shock || heal || (severed && diffOn) ? 1 : st.op}
                  strokeDasharray={dash}
                  className={heal ? "edge-heal" : shock ? "edge-shock" : undefined}
                  filter={diffOn && heal ? "url(#glow-em)" : undefined}
                  markerEnd={`url(#arr-${EDGE_STYLE[e.type] ? e.type : "default"})`}
                />
                {PARTICLE_TYPES.has(e.type) && !dim && (
                  <circle r={e.type === "AUTO_REASSIGNED_TO" ? 3 : 2} fill={heal ? "#42F5C2" : shock ? "#FF5D8F" : st.color} opacity={0.95}
                    filter={heal ? "url(#glow-em)" : undefined}>
                    <animateMotion dur={`${heal ? 1.4 : 2.4 + (i % 5) * 0.3}s`} repeatCount="indefinite"
                      path={`M${a.x},${a.y} L${b.x},${b.y}`} begin={`${(i % 7) * 0.2}s`} />
                  </circle>
                )}
              </g>
            );
          })}
          {/* nodes */}
          {vis.ns.map((n) => {
            const p = pos.current.get(n.id);
            if (!p) return null;
            const ls = LABEL_STYLE[n.label] ?? { color: "#64748B", r: 8, shape: "circle" };
            const s = status(n.id);
            const isTarget = targets.has(n.id);
            const dim = (highlight.size > 0 && !highlight.has(n.id));
            const fill = s === "EXTINCT" ? "#4a1030" : ls.color;
            const stroke = s === "EXTINCT" ? "#FF5D8F" : s === "IMPACTED" ? "#FFC46B" : s === "RECOVERED" || s === "WARM_STANDBY" ? "#42F5C2" : "rgba(255,255,255,0.35)";
            return (
              <g key={n.id} transform={`translate(${p.x},${p.y})`} opacity={dim ? 0.18 : 1} style={{ cursor: "pointer" }}
                onPointerDown={(e) => e.stopPropagation()}
                onClick={() => { onToggleTarget(n.id); onOpen(n.id); }}
                onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)}>
                {reticle.has(n.id) && (
                  <g className="reticle" pointerEvents="none">
                    <circle r={ls.r + 16} fill="none" stroke="#FFC46B" strokeWidth={2} strokeDasharray="10 6" />
                    <path d={`M${-ls.r - 26},0H${-ls.r - 10}M${ls.r + 10},0H${ls.r + 26}M0,${-ls.r - 26}V${-ls.r - 10}M0,${ls.r + 10}V${ls.r + 26}`} stroke="#FF5D8F" strokeWidth={2} />
                  </g>
                )}
                {isTarget && <circle className="meteor-ring" r={16} fill="none" stroke="#FF5D8F" strokeWidth={2} />}
                {isTarget && <circle r={ls.r + 7} fill="none" stroke="#FF5D8F" strokeWidth={1.5} strokeDasharray="3 3" />}
                {s === "IMPACTED" && <circle className="glow" r={ls.r + 9} fill="#FFC46B" opacity={0.25} />}
                {(s === "RECOVERED" || s === "WARM_STANDBY") && <circle className="glow" r={ls.r + 8} fill="#42F5C2" opacity={0.22} />}
                {s === "EXTINCT" && <circle r={ls.r + 8} fill="#FF5D8F" opacity={0.2} />}
                {ls.shape === "circle" && <circle r={ls.r} fill={fill} stroke={stroke} strokeWidth={s ? 2.2 : 1} fillOpacity={0.9} />}
                {ls.shape === "rect" && <rect x={-ls.r} y={-ls.r * 0.75} width={ls.r * 2} height={ls.r * 1.5} rx={3} fill={fill} stroke={stroke} strokeWidth={s ? 2.2 : 1} fillOpacity={0.9} />}
                {!["circle", "rect"].includes(ls.shape) && <path d={shapePath(ls.shape, ls.r)} fill={fill} stroke={stroke} strokeWidth={s ? 2.2 : 1} fillOpacity={0.9} />}
                {s === "EXTINCT" && <text textAnchor="middle" y={4} fontSize={12} fill="#FF5D8F">☠</text>}
              </g>
            );
          })}
          {/* label pills (drawn above nodes, never intercept clicks) */}
          {labels.map((l) => (
            <g key={`l-${l.id}`} transform={`translate(${l.x},${l.y})`} style={{ pointerEvents: "none" }}
              opacity={highlight.size > 0 && !highlight.has(l.id) ? 0.25 : 1}>
              <rect x={-l.w / 2} y={-1} width={l.w} height={13} rx={6.5} fill="rgba(12,16,38,0.78)" stroke={l.h?.color ?? "rgba(0,240,255,0.35)"} strokeOpacity={0.6} strokeWidth={0.8} />
              <text x={l.h ? -l.w / 2 + 14 : 0} y={9} textAnchor={l.h ? "start" : "middle"} fontSize={9} fill="#e6efff" fontWeight={500}>{l.text}</text>
              {l.h && <text x={-l.w / 2 + 7} y={9.5} textAnchor="middle" fontSize={9} fill={l.h.color}>{l.h.icon}</text>}
            </g>
          ))}
        </g>
        {/* legend (screen-space) */}
        <g transform="translate(14,16)" fontSize={10} fill="#aab6d8" style={{ pointerEvents: "none" }}>
          {["Engineer", "Service", "Database", "Repository", "ADR_Doc", "Ticket", "ProceduralPlaybook"].map((l, i) => (
            <g key={l} transform={`translate(0,${i * 15})`}>
              <rect width={9} height={9} rx={2} fill={LABEL_STYLE[l].color} />
              <text x={14} y={9}>{l}</text>
            </g>
          ))}
        </g>
      </svg>
      {/* floating controls */}
      <div className="absolute right-2 bottom-2 flex flex-col gap-1">
        <button aria-label="zoom in" className="btn" onClick={() => zoomBy(1.25)}>＋</button>
        <button aria-label="zoom out" className="btn" onClick={() => zoomBy(1 / 1.25)}>－</button>
        <button aria-label="fit to screen" className="btn" title="Fit to screen" onClick={fit}>⤢</button>
        <button aria-label="center graph" className="btn" title="Center graph" onClick={() => setView({ k: 1, x: 0, y: 0 })}>◎</button>
      </div>
      <div className="absolute left-2 bottom-2 flex flex-col gap-1 items-start">
        {isSim && (
          <label className="panel px-2 py-1 text-[12.5px] flex items-center gap-2 cursor-pointer" style={{ borderColor: diff ? "#42F5C2" : undefined }}>
            <input type="checkbox" checked={diff} onChange={(e) => setDiff(e.target.checked)} />
            Graph Diff Mode
            <span className="text-[#FF5D8F]">┅ severed</span>
            <span className="text-[#42F5C2]">━ rewired</span>
          </label>
        )}
      </div>
    </div>
  );
}
