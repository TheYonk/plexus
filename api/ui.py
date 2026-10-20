"""Plexus web UI: the read model behind web/ and a guarded shell.

Everything here is for a human at this machine, so every route answers
loopback clients only (the API itself binds 0.0.0.0 because the database
container calls /policy/search through host.docker.internal).

Routes:
  GET  /                      web/index.html (static files under /static)
  GET  /ui/state              tickets, the five conditions, the verdict
  GET  /ui/harness            triage_agent's harness and lessons
  POST /ui/reset              scenario/seed.sql (tickets only, harness kept)
  POST /ui/run                start synapse.execute in a worker thread
  GET  /ui/run                run status, elapsed, live feed, outcome
  GET  /ui/trajectory/{id}    synapse.trajectory() split into steps
  GET  /ui/tune               newest tuned/* run: rollouts, diff, lesson
  POST /ui/policy/compare     the same query as_of two dates
  GET  /ui/shell-token        token for the shell websocket
  WS   /ui/shell              bash in a PTY (only with PLEXUS_SHELL=1)
"""

from __future__ import annotations

import asyncio
import codecs
import difflib
import fcntl
import json
import os
import pathlib
import pty
import re
import secrets
import signal
import struct
import termios
import threading
import time
from typing import Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
WEB = ROOT / "web"
SCENARIO = ROOT / "scenario"
TUNED = ROOT / "tuned"
DSN = os.environ.get("PLEXUS_DSN", "postgresql://postgres:postgres@127.0.0.1:55441/plexus")
AGENT = "triage_agent"
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
SHELL_ENABLED = os.environ.get("PLEXUS_SHELL") == "1"
SHELL_TOKEN = secrets.token_urlsafe(24)


def loopback_only(request: Request) -> None:
    if (request.client.host if request.client else "") not in LOOPBACK:
        raise HTTPException(403, "the Plexus UI answers loopback clients only")


router = APIRouter(dependencies=[Depends(loopback_only)])


def q(sql: str, params: tuple | None = None) -> list[tuple]:
    with psycopg.connect(DSN, autocommit=True) as conn:
        return conn.execute(sql, params).fetchall()


# ----------------------------------------------------------------------------
# live feed: the agent's calls into this API while synapse.execute runs
# ----------------------------------------------------------------------------

_feed: list[dict[str, Any]] = []
_feed_lock = threading.Lock()


def record_feed(kind: str, **fields: Any) -> None:
    """Called by /policy/search; the run panel polls it."""
    with _feed_lock:
        _feed.append({"t": time.time(), "kind": kind, **fields})
        del _feed[:-200]


# ----------------------------------------------------------------------------
# static
# ----------------------------------------------------------------------------


@router.get("/")
def index():
    return FileResponse(WEB / "index.html")


# ----------------------------------------------------------------------------
# read model
# ----------------------------------------------------------------------------


@router.get("/ui/state")
def state():
    cols = ["id", "tier", "created", "charge_date", "subject", "category", "priority", "escalated", "refund_decision", "policy_version", "handled"]
    rows = q(
        "SELECT t.id, c.tier, t.created_at::date::text, t.charge_date::text, t.subject, t.category, t.priority,"
        " t.escalated, t.refund_decision, t.policy_version, t.handled_at IS NOT NULL"
        " FROM support.tickets t JOIN support.customers c ON c.id = t.customer_id ORDER BY t.id"
    )
    tickets = [dict(zip(cols, r)) for r in rows]
    audit = dict(q("SELECT ticket_id, count(*) FROM support.audit GROUP BY 1"))
    for t in tickets:
        t["audit_rows"] = audit.get(t["id"], 0)
    conditions = [{"name": n, "ok": bool(ok)} for n, ok in q((SCENARIO / "conditions.sql").read_text())]
    passed = q((SCENARIO / "assert.sql").read_text())[0][0]
    profile = q("SELECT provider, model, base_url FROM synapse.llm_profiles WHERE name = 'llm'")
    versions = dict(q("SELECT extname, extversion FROM pg_extension"))
    return {
        "tickets": tickets,
        "conditions": conditions,
        "passed": bool(passed),
        "llm": dict(zip(["provider", "model", "base_url"], profile[0])) if profile else None,
        "extensions": versions,
    }


@router.get("/ui/harness")
def harness():
    h = json.loads(q("SELECT synapse.agent_harness(%s)::text", (AGENT,))[0][0])
    lessons = q(
        "SELECT lesson_id, cue, lesson, confidence, source_execution::text, evidence FROM synapse.lessons"
        " WHERE agent = %s AND status = 'active' ORDER BY lesson_id",
        (AGENT,),
    )
    h["lessons"] = [dict(zip(["id", "cue", "lesson", "confidence", "source_execution", "evidence"], r)) for r in lessons]
    return h


@router.post("/ui/reset")
def reset():
    if _run["status"] == "running":
        raise HTTPException(409, "a run is in progress")
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute((SCENARIO / "seed.sql").read_text())
    with _feed_lock:
        _feed.clear()
    return {"ok": True}


class Compare(BaseModel):
    query: str = "refund window days after charge"
    dates: list[str] = ["2026-05-20", "2026-07-20"]


@router.post("/ui/policy/compare")
async def policy_compare(req: Compare):
    from app import PolicySearch, search_policy

    out = []
    for d in req.dates:
        res = await search_policy(PolicySearch(query=req.query, as_of=d, k=1))
        top = res["chunks"][0] if res["chunks"] else {}
        out.append({"as_of": d, "policy_in_force": res["policy_in_force"], "top": top})
    return {"query": req.query, "results": out}


# ----------------------------------------------------------------------------
# runs
# ----------------------------------------------------------------------------

_run: dict[str, Any] = {"status": "idle"}
_run_lock = threading.Lock()


def _worker(task: str, started: float) -> None:
    try:
        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute("SET statement_timeout = '900s'")
            raw = conn.execute("SELECT synapse.execute(%s, %s)::text", (AGENT, task)).fetchone()[0]
        out = json.loads(raw)
        keep = ("status", "iterations", "tokens_in", "tokens_out", "duration_ms", "error", "execution_id", "output")
        res = {k: out.get(k) for k in keep}
        res["tool_calls"] = len(out.get("tool_calls") or [])
        if res.get("execution_id"):
            (ROOT / ".last_execution").write_text(res["execution_id"])
        _run.update(status="done", finished=time.time(), outcome=res)
    except Exception as exc:  # surfaced to the UI as data
        _run.update(status="failed", finished=time.time(), error=str(exc))


@router.post("/ui/run")
def run_start():
    with _run_lock:
        if _run["status"] == "running":
            raise HTTPException(409, "a run is in progress")
        with _feed_lock:
            _feed.clear()
        started = time.time()
        _run.clear()
        _run.update(status="running", started=started)
        task = (SCENARIO / "task.txt").read_text()
        threading.Thread(target=_worker, args=(task, started), daemon=True).start()
    return {"ok": True, "started": started}


@router.get("/ui/run")
def run_status():
    r = dict(_run)
    if "started" in r:
        r["elapsed_s"] = round((r.get("finished") or time.time()) - r["started"], 1)
    with _feed_lock:
        r["feed"] = list(_feed)
    if r["status"] == "idle":
        last = ROOT / ".last_execution"
        r["last_execution"] = last.read_text().strip() if last.exists() else None
    return r


# ----------------------------------------------------------------------------
# trajectory
# ----------------------------------------------------------------------------

_STEP = re.compile(r"^\[(EXECUTION|SYSTEM|USER|ACTION|OBSERVATION|ERROR|ASSISTANT|EVENT)\]\s?(.*)$")


@router.get("/ui/trajectory/{execution_id}")
def trajectory(execution_id: str, width: int = 400):
    if not re.fullmatch(r"[0-9a-f-]{36}", execution_id):
        raise HTTPException(400, "execution_id must be a uuid")
    text = q("SELECT synapse.trajectory(%s::uuid, %s)", (execution_id, width))[0][0] or ""
    steps: list[dict[str, Any]] = []
    for line in text.splitlines():
        m = _STEP.match(line)
        if m:
            steps.append({"kind": m.group(1).lower(), "head": m.group(2), "body": []})
        elif steps:
            if line.startswith("HINT:"):
                steps[-1]["hint"] = line[5:].strip()
            else:
                steps[-1]["body"].append(line)
    for s in steps:
        s["body"] = "\n".join(s["body"]).strip()
    return {"execution_id": execution_id, "steps": steps}


# ----------------------------------------------------------------------------
# tuner output
# ----------------------------------------------------------------------------


@router.get("/ui/tune")
def tune(run: str | None = None):
    runs = sorted(p.name for p in TUNED.glob("*/summary.json") for p in [p.parent])
    if not runs:
        raise HTTPException(404, "no tuned/* run with a summary.json")
    name = run if run in runs else runs[-1]
    d = TUNED / name
    s = json.loads((d / "summary.json").read_text())
    keep = ("label", "passed", "score", "tokens_in", "tokens_out", "iterations", "wall_s", "conditions")
    rollouts = [{k: r.get(k) for k in keep} | {"stage": "base"} for r in s["base"]]
    for label, r in s["probes"].items():
        rollouts.append({k: r.get(k) for k in keep} | {"stage": re.sub(r"\d+$", "", label)})

    def read(rel: str) -> str:
        p = d / rel
        text = p.read_text() if p.exists() else ""
        return text if not text or text.endswith("\n") else text + "\n"

    diffs = []
    for rel in ("system_prompt.md", "memory.md", "guardrails.md", "tool_hints.json"):
        a, b = read(f"harnesses/base/{rel}"), read(f"adopted/{rel}")
        if a != b:
            diffs.append(
                {
                    "file": rel,
                    "diff": "".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), "base/" + rel, "adopted/" + rel, n=1)),
                }
            )
    return {
        "run": name,
        "runs": runs,
        "model": s.get("llm_model"),
        "k": s.get("k"),
        "adopted": s.get("adopted"),
        "why": s.get("why"),
        "rollouts": rollouts,
        "diffs": diffs,
        "edits": s.get("experience", {}).get("edits"),
        "lesson": {k: s.get("experience", {}).get(k) for k in ("cue", "lesson", "confidence")},
        "lesson_id": s.get("lesson_id"),
    }


# ----------------------------------------------------------------------------
# shell
# ----------------------------------------------------------------------------


@router.get("/ui/shell-token")
def shell_token():
    if not SHELL_ENABLED:
        return {"enabled": False}
    return {"enabled": True, "token": SHELL_TOKEN}


async def shell_ws(ws: WebSocket):
    """Bash in a PTY. Registered on the app directly (routers' HTTP
    dependencies do not cover websockets), so the guards are checked here."""
    host = ws.client.host if ws.client else ""
    origin = ws.headers.get("origin", "")
    ok_origin = re.match(r"^https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$", origin) is not None
    if not SHELL_ENABLED or host not in LOOPBACK or not ok_origin or not secrets.compare_digest(ws.query_params.get("token", ""), SHELL_TOKEN):
        await ws.close(code=4403)
        return
    await ws.accept()
    pid, fd = pty.fork()
    if pid == 0:  # child
        os.chdir(ROOT)
        env = {**os.environ, "DSN": DSN, "PAGER": "cat", "PSQL_PAGER": "cat", "TERM": "xterm-256color", "PS1": r"\[\e[1;36m\]plexus\[\e[0m\]:\[\e[1;34m\]\W\[\e[0m\]$ "}
        os.execvpe("bash", ["bash", "--noprofile", "--norc", "-i"], env)
    loop = asyncio.get_running_loop()
    out: asyncio.Queue[bytes] = asyncio.Queue()
    decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def readable() -> None:
        try:
            data = os.read(fd, 65536)
        except OSError:
            data = b""
        out.put_nowait(data)
        if not data:
            loop.remove_reader(fd)

    loop.add_reader(fd, readable)

    async def pump() -> None:
        while True:
            data = await out.get()
            if not data:
                await ws.close()
                return
            text = decoder.decode(data)
            if text:
                await ws.send_text(text)

    task = asyncio.create_task(pump())
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            if msg.get("type") == "input":
                os.write(fd, msg["data"].encode())
            elif msg.get("type") == "resize":
                fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", int(msg["rows"]), int(msg["cols"]), 0, 0))
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        task.cancel()
        try:
            loop.remove_reader(fd)
        except Exception:
            pass
        try:
            os.kill(pid, signal.SIGHUP)
            os.waitpid(pid, 0)
        except OSError:
            pass
        os.close(fd)
