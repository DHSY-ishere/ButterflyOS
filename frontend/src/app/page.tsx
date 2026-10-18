import Link from "next/link";
import Reveal from "@/components/Reveal";
import HeroGraph from "@/components/HeroGraph";

function Logo({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden>
      <defs>
        <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#7CC4FF" />
          <stop offset="0.5" stopColor="#B793FF" />
          <stop offset="1" stopColor="#FF5D8F" />
        </linearGradient>
      </defs>
      <path d="M20 20 C 8 4, 1 12, 5 22 C 8 29, 15 28, 20 20 Z" fill="url(#lg)" opacity="0.95" />
      <path d="M20 20 C 32 4, 39 12, 35 22 C 32 29, 25 28, 20 20 Z" fill="url(#lg)" opacity="0.75" />
      <path d="M20 21 C 12 24, 9 34, 15 36 C 19 37, 20 29, 20 21 Z" fill="url(#lg)" opacity="0.6" />
      <path d="M20 21 C 28 24, 31 34, 25 36 C 21 37, 20 29, 20 21 Z" fill="url(#lg)" opacity="0.45" />
    </svg>
  );
}

const STEPS = [
  { n: "01", t: "Fork", d: "GRAPH.COPY clones production into an isolated sandbox tenant in tens of milliseconds. Production is never touched.", c: "#7CC4FF" },
  { n: "02", t: "Shockwave", d: "Multi-hop Cypher and algo.pageRank trace the cascade. algo.betweenness and algo.WCC expose ownerless subgraphs.", c: "#B793FF" },
  { n: "03", t: "Heal", d: "Four agents call graph tools over MCP, reconstruct tribal knowledge, and rewire ownership with auditable edges.", c: "#42F5C2" },
  { n: "04", t: "Vaccinate", d: "The episode is distilled into a procedural playbook. The next identical failure is recalled with a single query.", c: "#FFC46B" },
];

const AGENTS = [
  { t: "Shockwave-Triage", d: "Maps the failure cascade, ranks chokepoints, totals RPS at risk and breached SLAs." },
  { t: "BusFactor-Detector", d: "Finds systems whose only expert is gone and flags code that contradicts policy." },
  { t: "Tribal-Archaeologist", d: "Walks commits, Slack and ADRs to write a cited handover for every orphan." },
  { t: "Continuity-Healer", d: "Scores successors in Cypher and rewires ownership, blocked by policy where needed." },
];

const TRACKS = [
  { k: "Track 01", t: "Agents that act on connected data", d: "Seven MCP tools. Every action is chosen by graph topology and returns its Cypher, latency and provenance." },
  { k: "Track 02", t: "Agent memory & coordination", d: "Episodic hand-offs, live semantic topology and procedural playbooks, in isolated multigraph tenants." },
  { k: "Track 03", t: "Company brain", d: "People, repos, commits, decisions and chats in one graph. Ask who owns what and trace every answer to its source." },
];

export default function Landing() {
  return (
    <div className="relative overflow-x-clip">
      {/* nav */}
      <nav className="mx-auto max-w-[1180px] px-6 pt-6">
        <div className="panel flex items-center justify-between px-5 py-3" style={{ borderRadius: 999 }}>
          <Link href="/" className="flex items-center gap-3">
            <Logo />
            <span className="text-[17px] font-semibold tracking-tight text-white">Butterfly<span className="text-white/50 font-medium">OS</span></span>
          </Link>
          <div className="hidden md:flex items-center gap-8 text-[13.5px] text-white/65">
            <a href="#problem" className="hover:text-white transition-colors">Why graphs</a>
            <a href="#how" className="hover:text-white transition-colors">How it works</a>
            <a href="#agents" className="hover:text-white transition-colors">Agents</a>
            <a href="#tracks" className="hover:text-white transition-colors">Tracks</a>
            <a href="#architecture" className="hover:text-white transition-colors">Architecture</a>
          </div>
          <Link href="/console" className="btn btn-sm">Open console</Link>
        </div>
      </nav>

      {/* hero */}
      <header className="mx-auto max-w-[1180px] px-6 pt-24 pb-32 grid lg:grid-cols-[1.05fr_1fr] gap-16 items-center">
        <div>
          <span className="chip"><i className="dot" />Neuro-symbolic agents on FalkorDB</span>
          <h1 className="mt-8 text-[clamp(44px,6.2vw,76px)] font-semibold leading-[1.02] tracking-[-0.035em] text-white">
            Rehearse the outage <span className="gradient-text">before it happens.</span>
          </h1>
          <p className="mt-8 max-w-[540px] text-[18px] leading-[1.6] text-white/65">
            ButterflyOS forks your production graph, takes down any combination of services and people, and lets a swarm of agents
            compute the blast radius, find the knowledge that just walked out the door, and heal the organization, all in milliseconds.
          </p>
          <div className="mt-12 flex flex-wrap items-center gap-4">
            <Link href="/console" className="btn btn-ok" style={{ padding: "13px 26px", fontSize: 15 }}>Launch the console</Link>
            <a href="#how" className="btn" style={{ padding: "13px 26px", fontSize: 15 }}>See how it works</a>
          </div>
          <div className="mt-14 flex flex-wrap gap-x-10 gap-y-4 text-[13px] text-white/50">
            <span>Cypher + GraphBLAS algorithms</span>
            <span>MCP tool execution</span>
            <span>No Node, No Action provenance</span>
          </div>
        </div>
        <div className="relative">
          <div className="panel p-8" style={{ borderRadius: 32 }}>
            <HeroGraph />
          </div>
          <div className="panel absolute -left-6 top-10 px-5 py-3 hidden sm:block rise" style={{ borderRadius: 18 }}>
            <div className="text-[11.5px] text-white/50">RPS at risk</div>
            <div className="text-[22px] font-semibold text-crimson tabular-nums">289,500</div>
          </div>
          <div className="panel absolute -right-6 top-8 px-5 py-3 hidden sm:block rise" style={{ borderRadius: 18, animationDelay: "0.15s" }}>
            <div className="text-[11.5px] text-white/50">Survivability after heal</div>
            <div className="text-[22px] font-semibold text-emerald tabular-nums">98.2%</div>
          </div>
          <div className="panel absolute left-10 -bottom-6 px-5 py-3 hidden sm:block rise" style={{ borderRadius: 18, animationDelay: "0.3s" }}>
            <div className="text-[11.5px] text-white/50">Session 2 playbook recall</div>
            <div className="text-[22px] font-semibold text-neon tabular-nums">1 query</div>
          </div>
        </div>
      </header>

      {/* stats */}
      <section className="mx-auto max-w-[1180px] px-6 pb-32">
        <Reveal>
          <div className="panel grid grid-cols-2 lg:grid-cols-4" style={{ borderRadius: 32 }}>
            {[
              ["~30–80 ms", "to fork production into a sandbox"],
              ["44 → 1", "Cypher queries, cold start vs. vaccinated"],
              ["5 of 5", "orphaned systems re-homed per scenario"],
              ["0", "invented nodes. Every claim is verified"],
            ].map(([v, l], i) => (
              <div key={v} className={`px-8 py-10 ${i ? "lg:border-l border-white/10" : ""} ${i === 2 ? "border-t lg:border-t-0 border-white/10" : ""} ${i === 3 ? "border-t lg:border-t-0 border-white/10" : ""}`}>
                <div className="text-[34px] font-semibold tracking-tight text-white tabular-nums">{v}</div>
                <div className="mt-2 text-[14px] text-white/55 leading-snug">{l}</div>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      {/* problem */}
      <section id="problem" className="mx-auto max-w-[1180px] px-6 pb-36">
        <Reveal>
          <p className="eyebrow">Why graphs</p>
          <h2 className="h2 max-w-[760px]">Two nightmares. One connected question.</h2>
          <p className="lead max-w-[640px]">
            “What breaks if this service goes down?” and “What happens if our lead architect quits?” are traversals,
            not text searches. Flat retrieval can&apos;t compose the edges that matter.
          </p>
        </Reveal>
        <div className="mt-16 grid md:grid-cols-2 gap-8">
          <Reveal>
            <div className="panel p-10 h-full" style={{ borderRadius: 28 }}>
              <div className="text-[13px] font-semibold text-crimson tracking-[0.1em] uppercase">Technical blast radius</div>
              <h3 className="mt-4 text-[24px] font-semibold tracking-tight text-white">The cascade nobody wrote down</h3>
              <p className="mt-4 text-[15.5px] leading-[1.7] text-white/60">
                Payments → Ledger → Token KV is not in any document. It exists only as the composition of two dependency edges.
                PageRank names the chokepoint; multi-hop Cypher gives the exact failure path.
              </p>
            </div>
          </Reveal>
          <Reveal delay={120}>
            <div className="panel p-10 h-full" style={{ borderRadius: 28 }}>
              <div className="text-[13px] font-semibold text-amber tracking-[0.1em] uppercase">Human bus factor</div>
              <h3 className="mt-4 text-[24px] font-semibold tracking-tight text-white">The expert who left on Friday</h3>
              <p className="mt-4 text-[15.5px] leading-[1.7] text-white/60">
                The one warning about shard 14 sits in a Slack thread linked to a commit, a repository and a service.
                Components analysis finds the orphaned subgraphs; agents rebuild the context and pick a successor.
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* how it works */}
      <section id="how" className="mx-auto max-w-[1180px] px-6 pb-36">
        <Reveal>
          <p className="eyebrow">How it works</p>
          <h2 className="h2 max-w-[760px]">From “what if” to a rewired organization.</h2>
        </Reveal>
        <div className="mt-16 grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {STEPS.map((s, i) => (
            <Reveal key={s.n} delay={i * 90}>
              <div className="panel p-8 h-full" style={{ borderRadius: 26 }}>
                <div className="text-[13px] font-semibold tabular-nums" style={{ color: s.c }}>{s.n}</div>
                <h3 className="mt-5 text-[22px] font-semibold tracking-tight text-white">{s.t}</h3>
                <p className="mt-3 text-[14.5px] leading-[1.65] text-white/58">{s.d}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* agents */}
      <section id="agents" className="mx-auto max-w-[1180px] px-6 pb-36">
        <Reveal>
          <p className="eyebrow">The swarm</p>
          <h2 className="h2 max-w-[760px]">Four agents. Every hand-off is a node in the graph.</h2>
          <p className="lead max-w-[640px]">
            No conclusion is accepted unless every node in its provenance path exists in FalkorDB. No Node, No Action.
          </p>
        </Reveal>
        <div className="mt-16 grid md:grid-cols-2 gap-6">
          {AGENTS.map((a, i) => (
            <Reveal key={a.t} delay={(i % 2) * 100}>
              <div className="panel p-9 flex gap-6 items-start h-full" style={{ borderRadius: 26 }}>
                <div className="shrink-0 w-12 h-12 rounded-2xl grid place-items-center text-[15px] font-semibold text-white"
                  style={{ background: "linear-gradient(135deg, rgba(124,196,255,0.5), rgba(183,147,255,0.45))", border: "1px solid rgba(255,255,255,0.3)" }}>
                  {i + 1}
                </div>
                <div>
                  <h3 className="text-[19px] font-semibold tracking-tight text-white">{a.t}</h3>
                  <p className="mt-2 text-[14.5px] leading-[1.65] text-white/58">{a.d}</p>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* tracks */}
      <section id="tracks" className="mx-auto max-w-[1180px] px-6 pb-36">
        <Reveal>
          <p className="eyebrow">Built for all three tracks</p>
          <h2 className="h2 max-w-[760px]">One graph, three ways to make agents useful.</h2>
        </Reveal>
        <div className="mt-16 grid lg:grid-cols-3 gap-6">
          {TRACKS.map((t, i) => (
            <Reveal key={t.k} delay={i * 100}>
              <div className="panel p-9 h-full" style={{ borderRadius: 26 }}>
                <span className="chip">{t.k}</span>
                <h3 className="mt-6 text-[21px] font-semibold tracking-tight text-white leading-snug">{t.t}</h3>
                <p className="mt-3 text-[14.5px] leading-[1.65] text-white/58">{t.d}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* architecture */}
      <section id="architecture" className="mx-auto max-w-[1180px] px-6 pb-36">
        <Reveal>
          <p className="eyebrow">Architecture</p>
          <h2 className="h2 max-w-[760px]">Neuro-symbolic by construction.</h2>
          <p className="lead max-w-[660px]">
            The graph decides what is true. A pluggable language model only phrases it, and is rejected the moment it cites a node that doesn&apos;t exist.
          </p>
        </Reveal>
        <Reveal delay={100}>
          <div className="mt-16 panel p-10 lg:p-14" style={{ borderRadius: 32 }}>
            <div className="grid lg:grid-cols-[1fr_auto_1fr] gap-8 items-stretch">
              <div className="rounded-3xl p-8" style={{ background: "rgba(66,245,194,0.07)", border: "1px solid rgba(66,245,194,0.28)" }}>
                <div className="text-[12.5px] font-semibold tracking-[0.1em] uppercase text-emerald">Symbolic core · FalkorDB</div>
                <ul className="mt-5 space-y-3 text-[15px] text-white/75">
                  <li>OpenCypher traversals and scoring</li>
                  <li>algo.pageRank · algo.betweenness · algo.WCC</li>
                  <li>graph.copy multigraph sandboxes</li>
                  <li>MCP tools with provenance_node_ids</li>
                  <li>Episodic → procedural memory</li>
                </ul>
              </div>
              <div className="hidden lg:flex flex-col items-center justify-center text-white/40 text-[12px] gap-2">
                <span>verified facts</span>
                <svg width="46" height="14" viewBox="0 0 46 14"><path d="M0 7h42M36 1l7 6-7 6" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>
                <span>gatekeeper</span>
              </div>
              <div className="rounded-3xl p-8" style={{ background: "rgba(124,196,255,0.07)", border: "1px solid rgba(124,196,255,0.28)" }}>
                <div className="text-[12.5px] font-semibold tracking-[0.1em] uppercase text-neon">Neural layer · pluggable</div>
                <ul className="mt-5 space-y-3 text-[15px] text-white/75">
                  <li>OpenAI, Groq or Gemini synthesis</li>
                  <li>Constrained to nodes the graph returned</li>
                  <li>Output validated before it is shown</li>
                  <li>Deterministic narrative as the fallback</li>
                </ul>
              </div>
            </div>
          </div>
        </Reveal>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-[1180px] px-6 pb-28">
        <Reveal>
          <div className="panel px-8 py-20 text-center" style={{ borderRadius: 40 }}>
            <h2 className="text-[clamp(32px,4.4vw,52px)] font-semibold tracking-[-0.03em] leading-[1.08] text-white">
              Break production <span className="gradient-text">safely.</span>
            </h2>
            <p className="mt-6 mx-auto max-w-[520px] text-[17px] leading-[1.6] text-white/60">
              Pick a scenario, press simulate, and watch the organization heal itself.
            </p>
            <div className="mt-10">
              <Link href="/console" className="btn btn-ok" style={{ padding: "14px 30px", fontSize: 15.5 }}>Launch the console</Link>
            </div>
          </div>
        </Reveal>
      </section>

      <footer className="mx-auto max-w-[1180px] px-6 pb-12 flex flex-wrap items-center justify-between gap-4 text-[13px] text-white/40">
        <div className="flex items-center gap-3"><Logo size={22} /> ButterflyOS · Graph Hacks: Context for AI Agents</div>
        <div>Powered by FalkorDB · Built with Claude Code</div>
      </footer>
    </div>
  );
}
