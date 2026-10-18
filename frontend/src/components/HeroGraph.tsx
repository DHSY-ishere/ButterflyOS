/** Decorative animated mini-graph for the landing hero: a failure spreads, the swarm heals it. */
const N = {
  gw: { x: 260, y: 56, c: "#8B8CFF", l: "Edge Gateway" },
  auth: { x: 130, y: 150, c: "#8B8CFF", l: "Auth Engine" },
  pay: { x: 392, y: 150, c: "#8B8CFF", l: "Payments" },
  kv: { x: 130, y: 262, c: "#FF5D8F", l: "Token KV", dead: true },
  led: { x: 392, y: 262, c: "#8B8CFF", l: "Ledger" },
  arjun: { x: 40, y: 340, c: "#4a1030", l: "Architect", dead: true },
  dev: { x: 250, y: 352, c: "#7CC4FF", l: "Successor" },
  rep: { x: 262, y: 236, c: "#42F5C2", l: "Warm replica" },
} as const;
type K = keyof typeof N;

const DEP: [K, K][] = [["gw", "auth"], ["gw", "pay"], ["auth", "kv"], ["pay", "auth"], ["pay", "led"], ["led", "kv"]];

function Edge({ a, b, color, dash, w = 1.6, op = 0.6, particle }: { a: K; b: K; color: string; dash?: string; w?: number; op?: number; particle?: number }) {
  const A = N[a], B = N[b];
  return (
    <g>
      <line x1={A.x} y1={A.y} x2={B.x} y2={B.y} stroke={color} strokeWidth={w} strokeOpacity={op} strokeDasharray={dash} />
      {particle !== undefined && (
        <circle r="3" fill={color}>
          <animateMotion dur={`${2 + particle * 0.4}s`} repeatCount="indefinite" path={`M${A.x},${A.y} L${B.x},${B.y}`} begin={`${particle * 0.3}s`} />
        </circle>
      )}
    </g>
  );
}

export default function HeroGraph() {
  return (
    <svg viewBox="0 0 520 420" className="w-full h-auto" role="img" aria-label="Animated dependency graph showing a failure and the swarm healing it">
      <defs>
        <filter id="hg-glow" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="5" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      {DEP.map(([a, b], i) => (
        <Edge key={i} a={a} b={b} color={b === "kv" ? "#FF5D8F" : "#8B8CFF"} op={b === "kv" ? 0.9 : 0.55} dash={b === "kv" ? "6 5" : undefined} particle={i} />
      ))}
      <Edge a="arjun" b="kv" color="#FF5D8F" dash="3 5" op={0.7} />
      <Edge a="dev" b="kv" color="#42F5C2" w={2.4} op={0.95} dash="8 5" particle={2} />
      <Edge a="kv" b="rep" color="#42F5C2" w={1.8} op={0.9} dash="4 4" />
      <Edge a="pay" b="rep" color="#42F5C2" w={1.8} op={0.9} dash="4 4" particle={4} />
      {(Object.keys(N) as K[]).map((k) => {
        const n = N[k] as { x: number; y: number; c: string; l: string; dead?: boolean };
        return (
          <g key={k} transform={`translate(${n.x},${n.y})`}>
            {n.dead && <circle r="30" fill="#FF5D8F" opacity="0.18"><animate attributeName="r" values="22;38;22" dur="2.4s" repeatCount="indefinite" /></circle>}
            {k === "dev" && <circle r="28" fill="#42F5C2" opacity="0.18" />}
            <circle r="15" fill={n.c} fillOpacity={n.dead && k === "arjun" ? 0.9 : 0.92} stroke="rgba(255,255,255,0.55)" strokeWidth="1.2" filter="url(#hg-glow)" />
            <g transform="translate(0,28)">
              <rect x={-(n.l.length * 3.2 + 9)} y="-9" width={n.l.length * 6.4 + 18} height="18" rx="9" fill="rgba(12,16,38,0.72)" stroke="rgba(255,255,255,0.22)" />
              <text textAnchor="middle" y="4" fontSize="10.5" fill="#EAF0FF" fontWeight="500">{n.l}</text>
            </g>
          </g>
        );
      })}
    </svg>
  );
}
