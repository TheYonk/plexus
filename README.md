# Plexus

One Postgres that runs an LLM agent, stores its trajectories, holds the
versioned knowledge it retrieves over, keeps its evidence-backed memory,
and tunes the agent's own harness from its own history. Five yonk-tools
projects wired through a single database:

| Project | Role here |
| --- | --- |
| [pg_synapse](../pg-synapse) (branch `harness2-borrowings`) | the agent runtime: `SELECT synapse.execute(...)`, tools, triggers, harness components, lessons |
| [harness2](../harness2) (ideas, not code) | the Propose-Probe-Compose tuner and the cost-tiered harness model, reimplemented inside pg_synapse |
| [pg-raggraph](../pg-raggraph) | retrieval over the policy corpus with effective dates: `as_of` returns the version in force |
| [stele](../stele) | memory with evidence: every decision cites a `stele://` artifact, corrections supersede, `as_of` shows what was believed |
| [chunkshop](../chunkshop) | ingest: the corpus and the agent's past runs as vector tables in the same database |

Design and build log: [`docs/DESIGN.md`](docs/DESIGN.md). Captured output
from a real run: [`RUN.md`](RUN.md). Handoff: [`docs/TURNOVER.md`](docs/TURNOVER.md).

## What it does that nothing else does

1. **Self-tuning with an audit trail in SQL.** `make tune` improves
   `triage_agent` from its own `synapse.messages`. Every adopted edit and
   every lesson row cites the execution it came from, and
   `synapse.trajectory(id)` shows the moment. Agent frameworks have no
   optimizer; harness2 has no runtime.
2. **Policy-as-of-date decisions.** The agent asks for the refund policy in
   force on the ticket's date, not the newest one, and records the version
   it applied. No RAG stack exposes `as_of` to a tool-calling agent inside
   the database.
3. **Transactional veto with retrieval.** An inline trigger agent rejects a
   refund INSERT that violates the policy in force; the write rolls back
   with the agent's reason as the Postgres error. Nothing outside Postgres
   can do this.
4. **Memory that supersedes instead of accumulating.** Decisions become
   stele memories scoped by customer. A correction supersedes the earlier
   one, and `as_of` returns what the agent believed at that instant.

## Run it

Host requirements: Docker, `psql`, `curl`, `python3`, `uv`, Ollama, and the
Claude CLI (the tuner's improver). The agent model is a 4B local model:

```bash
ollama pull qwen3:4b-instruct-2507-q4_K_M
OLLAMA_HOST=0.0.0.0:11434 OLLAMA_CONTEXT_LENGTH=32768 ollama serve &
```

Then, from this directory:

```bash
make venv      # one venv with stele, pg-raggraph and chunkshop from the sibling checkouts
make up        # builds pgvector/pgvector:pg17 + pg_synapse (~3 min warm), starts the API
make ingest    # policy corpus -> pg-raggraph (v2 supersedes v1 on 2026-07-01) + chunkshop sink
make seed      # scenario tables, agents, skills, hints, the inline veto trigger
make run       # triage_agent handles 8 tickets; prints decisions and the assertion
make veto      # a 61-day refund is rejected inside the transaction; a 22-day one lands
make memory    # remember, supersede, recall now vs as_of
make trajectories   # past runs -> chunkshop -> plexus.trajectory_chunks, then search them
make tune K=2  # Propose-Probe-Compose; lessons land in synapse.lessons
make down
```

### Web UI and recorded walkthrough

```bash
make ui          # restarts the API with the shell dock on; open http://127.0.0.1:8766/
make demo-video  # ElevenLabs narration + Playwright recording -> demo/out/plexus-demo.mp4
make exec-video  # the executive cut (customer outcome, http://127.0.0.1:8766/exec) -> demo/out/exec/plexus-exec.mp4
```

The UI shows the stack, policy time-travel, the harness as data, a live run
(the agent's policy calls stream in while `synapse.execute` runs), the
trajectory, and the tuner's last run, next to a real shell on this machine.
`/exec` is the business version: a large retailer's refund queue, a live
veto of a bad refund, one decision explained end to end, the measured
tuning saving, Plexus against harness2 and a typical agent stack, and a
value calculator whose assumptions are on screen.
Every UI route answers loopback clients only; the shell also needs
`PLEXUS_SHELL=1` (set by `make ui`) and a per-process token. `demo-video`
needs `ELEVENLABS_API_KEY`; the narration lives in `demo/script.py`. Design
and notes: `docs/webapp-demo-design.md`.

A stronger agent model is one profile row away, e.g. Qwen3.6-35B-A3B on
vLLM: `select synapse.llm_profile_set('llm','openai','qwen36-nvfp4','http://<host>:8000/v1',NULL,'{}')`.

Ports: Postgres `55441`, API `8766`. The database reaches Ollama and the
API through `host.docker.internal`; `PG_SYNAPSE_HTTP_ALLOW` on the
container lets `http_post` past pg_synapse's SSRF guard.

## The scenario

Support triage under a changing refund policy. Eight tickets; four are
refund requests whose correct answer depends on which policy version was
in force on the ticket date (v1: 14-day window until 30 June 2026; v2:
30-day window from 1 July 2026). The rest exercise the escalation rule
(enterprise AND urgent, nothing else). `scenario/assert.sql` checks all of
it plus exactly one audit row per ticket.

The agent is deliberately plain at the start (`scenario/agents.sql`): a
short system prompt, an evidence-boundary guardrail, two on-demand skills
(`refund_policy`, `escalation`), the four default tool hints. The tuner's
job is to make it pass.

## Where the pieces live

```
db/            Dockerfile: pgvector/pgvector:pg17 + pg_synapse; initdb creates the three extensions
api/           FastAPI: /policy/search (pg-raggraph, as_of), /policy/ingest, /memory/*, /trajectories/*
api/cells/     chunkshop cells: policy corpus; past runs via a pg_table source over synapse.executions
scenario/      policy/*.md with effective dates, seed.sql, agents.sql, task.txt, assert.sql
scripts/       run_triage.sh
Makefile       the demo driver
```

## What is borrowed from where

- From harness2: the component model (always-on vs on-demand vs in-loop),
  "every edit must trace to a trajectory moment", KEEP_BASE as a valid
  answer, the evidence boundary, the `cue / lesson / evidence` lesson
  shape, the trajectory grammar. All reimplemented in pg_synapse's kernel,
  SQL surface and `bench/tune.py`; no harness2 code is used.
- From pg-raggraph: `ingest_records` with `effective_from` /
  `effective_to` / `version_label`, `supersede()`, `query(as_of=...)` with
  `evolution_tier="structural"`.
- From stele: `store()` for evidence, `memory.add(supersedes=...)`,
  `memory.search(as_of=...)`.
- From chunkshop: a `files` cell for the corpus and a `pg_table` cell
  over a view that renders each execution with `synapse.trajectory()`.
