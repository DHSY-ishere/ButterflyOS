/* eslint-disable @typescript-eslint/no-explicit-any */
export const API = process.env.NEXT_PUBLIC_API ?? "http://localhost:8000";

export type Any = any;

async function j(path: string, init?: RequestInit): Promise<Any> {
  const r = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!r.ok) throw new Error(`${path}: ${r.status} ${await r.text()}`);
  return r.json();
}

const post = (path: string, body: unknown) => j(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  graphs: () => j("/api/graphs"),
  graph: (name: string) => j(`/api/graph?name=${encodeURIComponent(name)}`),
  node: (id: string, graph: string) => j(`/api/node/${id}?graph=${encodeURIComponent(graph)}`),
  simulate: (targets: string[], session_id?: string) => post("/api/simulate", { targets, session_id }),
  vaccinate: (targets: string[], session_id: string) => post("/api/vaccinate", { targets, session_id }),
  contradictions: (graph: string) => j(`/api/contradictions?graph=${encodeURIComponent(graph)}`),
  ask: (question: string, graph: string) => post("/api/ask", { question, graph }),
  memory: () => j("/api/memory"),
  reset: (hard = false) => j(`/api/reset?hard=${hard}`, { method: "POST" }),
  health: () => j("/api/health"),
  blindspot: (graph = "prod_company") => j(`/api/blindspot?graph=${encodeURIComponent(graph)}`),
  tournament: (targets: string[]) => post("/api/tournament", { targets }),
  remediate: (graph: string, apply = false) => post("/api/remediate-pr", { graph, apply }),
  cypher: (graph: string, query: string) => post("/api/cypher", { graph, query }),
  schema: (graph: string) => j(`/api/schema?graph=${encodeURIComponent(graph)}`),
  mcpTools: () => j("/api/mcp/tools"),
};

/** Streams the 4-agent swarm over SSE, invoking onEvent for each event. */
export async function streamHeal(targets: string[], session_id: string, onEvent: (e: Any) => void) {
  const r = await fetch(`${API}/api/heal/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ targets, session_id }),
  });
  if (!r.ok || !r.body) throw new Error(`heal stream failed: ${r.status}`);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      if (chunk.startsWith("data: ")) onEvent(JSON.parse(chunk.slice(6)));
    }
  }
}
