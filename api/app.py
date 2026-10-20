"""Plexus API: the Python half of the demo.

pg_synapse runs the agent inside Postgres. The three Python projects it
leans on (pg-raggraph for versioned retrieval, stele for evidence-backed
memory, chunkshop for ingest) are reached through this small FastAPI
service, which the agent calls with pg_synapse's `http_post` tool.

Endpoints:
  GET  /health
  POST /policy/ingest              load scenario/policy/*.md into pg-raggraph
                                   (with effective dates + supersession) and
                                   into a chunkshop sink table
  POST /policy/search              {query, as_of?, k?} -> policy in force
  POST /memory/remember            {user_id, text, kind, evidence, supersedes?}
  POST /memory/recall              {user_id, query, as_of?}
  POST /trajectories/ingest        chunkshop pg_table cell over synapse runs
  POST /trajectories/search        {query, k?} -> similar past runs
  GET  /  and /ui/*                the web UI (api/ui.py, loopback only)

Run:  PLEXUS_DSN=postgresql://postgres:postgres@127.0.0.1:55441/plexus \
      .venv/bin/uvicorn app:app --host 0.0.0.0 --port 8766
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import pathlib
import re
import subprocess
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import ui

HERE = pathlib.Path(__file__).resolve().parent
DSN = os.environ.get("PLEXUS_DSN", "postgresql://postgres:postgres@127.0.0.1:55441/plexus")
POLICY_DIR = pathlib.Path(os.environ.get("PLEXUS_POLICY_DIR", HERE.parent / "scenario" / "policy"))
CELLS_DIR = HERE / "cells"
POLICY_NS = "policy"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384

app = FastAPI(title="Plexus API", version="0.1.0")
app.include_router(ui.router)
app.add_api_websocket_route("/ui/shell", ui.shell_ws)
app.mount("/static", StaticFiles(directory=HERE.parent / "web"), name="static")

_rag = None
_stele = None
_embedder = None
_lock = asyncio.Lock()


# ----------------------------------------------------------------------------
# lazy singletons
# ----------------------------------------------------------------------------


async def rag():
    global _rag
    async with _lock:
        if _rag is None:
            from pg_raggraph import GraphRAG

            r = GraphRAG(
                DSN,
                namespace=POLICY_NS,
                skip_extraction=True,  # no LLM needed; retrieval is vector + BM25 + evolution
                embedding_model=EMBED_MODEL,
                embedding_dim=EMBED_DIM,
                # Time-travel is the point: honor effective windows, prefer the
                # version in force, keep retracted docs visible but flagged.
                evolution_tier="structural",
                supersession_behavior="prefer_new",
                retracted_behavior="flag",
            )
            await r.connect()
            _rag = r
    return _rag


def stele():
    global _stele
    if _stele is None:
        from stele import Stele

        _stele = Stele.from_config({"backend": {"type": "postgres", "dsn": DSN}})
    return _stele


def embedder():
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding

        _embedder = TextEmbedding(EMBED_MODEL)
    return _embedder


def parse_as_of(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    v = value.strip().replace("Z", "+00:00")
    try:
        d = dt.datetime.fromisoformat(v)
    except ValueError:
        try:
            d = dt.datetime.strptime(v[:10], "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(400, f"as_of must be ISO-8601, got {value!r}") from exc
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d


def read_policy_docs() -> list[dict[str, Any]]:
    docs = []
    for p in sorted(POLICY_DIR.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
        if not m:
            continue
        fm = dict((k.strip(), v.strip()) for k, _, v in (ln.partition(":") for ln in m.group(1).splitlines() if ":" in ln))
        docs.append({"file": p.name, "body": m.group(2).strip(), **fm})
    return docs


def iso_day(d: str | None, end: bool = False) -> str | None:
    if not d:
        return None
    return f"{d}T{'23:59:59' if end else '00:00:00'}+00:00"


# ----------------------------------------------------------------------------
# models
# ----------------------------------------------------------------------------


class PolicySearch(BaseModel):
    query: str
    as_of: str | None = None
    k: int = 3


class Remember(BaseModel):
    user_id: str
    text: str
    kind: str = "decision"  # fact | preference | decision | instruction | commitment | issue | summary
    evidence: str
    supersedes: list[str] | None = None
    agent_id: str = "triage_agent"


class Recall(BaseModel):
    user_id: str
    query: str
    as_of: str | None = None
    include_superseded: bool = False
    agent_id: str = "triage_agent"


class TrajSearch(BaseModel):
    query: str
    k: int = 3


# ----------------------------------------------------------------------------
# endpoints
# ----------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"ok": True, "dsn_host": re.sub(r"//.*@", "//", DSN), "policy_dir": str(POLICY_DIR)}


@app.post("/policy/ingest")
async def policy_ingest():
    docs = read_policy_docs()
    if not docs:
        raise HTTPException(404, f"no policy docs under {POLICY_DIR}")
    r = await rag()
    records = []
    for d in docs:
        md: dict[str, Any] = {"version_label": d.get("version_label"), "file": d["file"]}
        if d.get("effective_from"):
            md["effective_from"] = iso_day(d["effective_from"])
        if d.get("effective_to"):
            md["effective_to"] = iso_day(d["effective_to"], end=True)
        records.append({"text": d["body"], "source_id": d["source_id"], "metadata": md, "skip_llm": True})
    await r.ingest_records(records, namespace=POLICY_NS)
    superseded = []
    for d in docs:
        if d.get("supersedes"):
            res = await r.supersede(
                old_source_path=d["supersedes"],
                new_source_path=d["source_id"],
                reason=f"{d['source_id']} replaces {d['supersedes']}",
                effective_at=parse_as_of(iso_day(d.get("effective_from"))),
                namespace=POLICY_NS,
            )
            superseded.append({"old": d["supersedes"], "new": d["source_id"], **res})
    # chunkshop sink: the same corpus as a flat vector table (plexus.policy_chunks)
    cell = run_cell("policy.yaml")
    status = await r.status(POLICY_NS)
    return {"ingested": [d["source_id"] for d in docs], "superseded": superseded, "graph": status, "chunkshop": cell}


@app.post("/policy/search")
async def policy_search(req: PolicySearch):
    res = await search_policy(req)
    ui.record_feed("policy_search", query=req.query, as_of=res["as_of"], policy_in_force=res["policy_in_force"])
    return res


async def search_policy(req: PolicySearch) -> dict[str, Any]:
    r = await rag()
    as_of = parse_as_of(req.as_of)
    res = await r.query(req.query, mode="naive", namespace=POLICY_NS, as_of=as_of, evolution_aware=True)
    chunks = []
    for c in res.chunks[: max(1, req.k)]:
        chunks.append(
            {
                "score": round(c.score, 3),
                "source": c.document_source,
                "version": c.version_label,
                "effective_from": c.effective_from.date().isoformat() if c.effective_from else None,
                "effective_to": c.effective_to.date().isoformat() if c.effective_to else None,
                "superseded": bool(c.superseded_by_id),
                "text": c.content[:1200],
            }
        )
    in_force = next((c["version"] for c in chunks if c["version"]), None)
    return {
        "as_of": as_of.date().isoformat() if as_of else None,
        "policy_in_force": in_force,
        "chunks": chunks,
        "note": "Apply the version named in policy_in_force; it is the one effective on as_of." if as_of else "No as_of given; results are the newest versions.",
    }


@app.post("/memory/remember")
async def memory_remember(req: Remember):
    from stele.core.memory_record import MemoryScope

    st = stele()
    stored = st.store(content=req.evidence, namespace="support", metadata={"user_id": req.user_id, "agent_id": req.agent_id})
    scope = MemoryScope(user_id=req.user_id, agent_id=req.agent_id, namespace="support")
    res = st.memory.add(text=req.text, kind=req.kind, source_refs=[stored.reference], scope=scope, supersedes=req.supersedes)
    return {
        "memory_id": res.record.id,
        "status": res.record.status,
        "evidence_ref": stored.reference,
        "superseded_ids": res.superseded_ids,
        "duplicate_of": res.duplicate_of,
    }


@app.post("/memory/recall")
async def memory_recall(req: Recall):
    from stele.core.memory_record import MemoryQuery, MemoryScope

    st = stele()
    scope = MemoryScope(user_id=req.user_id, agent_id=req.agent_id, namespace="support")
    hits = st.memory.search(MemoryQuery(query=req.query, scope=scope, as_of=parse_as_of(req.as_of), include_superseded=req.include_superseded, limit=10))
    return {
        "as_of": req.as_of,
        "memories": [
            {
                "id": h.id,
                "text": h.text,
                "kind": h.kind,
                "status": h.status,
                "created_at": h.created_at.isoformat() if getattr(h, "created_at", None) else None,
                "supersedes": list(getattr(h, "supersedes", []) or []),
                "evidence": list(h.source_refs),
            }
            for h in hits
        ],
    }


@app.post("/trajectories/ingest")
async def trajectories_ingest():
    return run_cell("trajectories.yaml")


@app.post("/trajectories/search")
async def trajectories_search(req: TrajSearch):
    import psycopg

    vec = list(embedder().embed([req.query]))[0].tolist()
    with psycopg.connect(DSN) as conn:
        rows = conn.execute(
            "SELECT doc_id, original_content, 1 - (embedding <=> %s::vector) AS score "
            "FROM plexus.trajectory_chunks ORDER BY embedding <=> %s::vector LIMIT %s",
            (str(vec), str(vec), max(1, req.k)),
        ).fetchall()
    return {"hits": [{"execution_id": r[0], "score": round(float(r[2]), 3), "text": r[1][:1500]} for r in rows]}


def run_cell(name: str) -> dict[str, Any]:
    """Run one chunkshop cell with the CLI from this venv."""
    exe = pathlib.Path(os.environ.get("VIRTUAL_ENV", HERE / ".venv")) / "bin" / "chunkshop"
    if not exe.exists():
        exe = HERE / ".venv" / "bin" / "chunkshop"
    env = {**os.environ, "PG_DSN": DSN, "PLEXUS_POLICY_DIR": str(POLICY_DIR)}
    proc = subprocess.run([str(exe), "ingest", "--config", str(CELLS_DIR / name)], capture_output=True, text=True, env=env, timeout=900)
    return {"cell": name, "exit": proc.returncode, "stdout": proc.stdout[-1500:], "stderr": proc.stderr[-1500:]}
