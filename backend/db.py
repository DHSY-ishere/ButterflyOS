"""FalkorDB connection, tenant switching and query timing."""
import os
import time
import threading
from contextvars import ContextVar
from falkordb import FalkorDB

HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6379"))
PROD = "prod_company"

_db = None
_lock = threading.Lock()
# Rolling log of every query executed (surfaced to the UI terminal)
QUERY_LOG: list[dict] = []
LAST_LATENCY_MS = 0.0


_trace: ContextVar = ContextVar("trace", default=None)


class trace:
    """Context manager collecting every query executed inside it."""

    def __enter__(self):
        self.entries: list[dict] = []
        self._tok = _trace.set(self.entries)
        return self.entries

    def __exit__(self, *a):
        _trace.reset(self._tok)


def client() -> FalkorDB:
    global _db
    with _lock:
        if _db is None:
            _db = FalkorDB(host=HOST, port=PORT, max_connections=32)
        return _db


def graph(name: str = PROD):
    return client().select_graph(name)


def q(graph_name: str, cypher: str, params: dict | None = None, tag: str = ""):
    """Run a Cypher query, returning (rows, header, latency_ms)."""
    global LAST_LATENCY_MS
    g = graph(graph_name)
    t0 = time.perf_counter()
    res = g.query(cypher, params=params or {})
    ms = (time.perf_counter() - t0) * 1000
    LAST_LATENCY_MS = ms
    entry = {"graph": graph_name, "cypher": cypher.strip(), "ms": round(ms, 3), "tag": tag}
    QUERY_LOG.append(entry)
    del QUERY_LOG[:-200]
    tr = _trace.get()
    if tr is not None:
        tr.append(entry)
    header = [h[1] if isinstance(h, (list, tuple)) else h for h in res.header]
    return res.result_set, header, ms


def rows(graph_name: str, cypher: str, params: dict | None = None, tag: str = ""):
    """Like q() but returns list[dict] and latency."""
    rs, header, ms = q(graph_name, cypher, params, tag)
    return [dict(zip(header, r)) for r in rs], ms


def list_graphs() -> list[str]:
    return sorted(client().list_graphs())


def delete_graph(name: str):
    try:
        graph(name).delete()
    except Exception:
        pass


def graph_exists(name: str) -> bool:
    return name in client().list_graphs()
