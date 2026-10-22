# Plexus

One Postgres that runs an LLM agent, stores its trajectories, holds the
versioned knowledge it retrieves over, keeps its evidence-backed memory,
and tunes the agent's own harness from its own history. Five yonk-tools
projects wired through a single database:

| Project | Role here |
| --- | --- |
| [pg_synapse](https://github.com/yonk-labs/pg-synapse/tree/harness2-borrowings) (branch `harness2-borrowings`) | the agent runtime: `SELECT synapse.execute(...)`, tools, triggers, harness components, lessons |
| [harness2](https://github.com/google-research/harness2) (ideas, not code) | the Propose-Probe-Compose tuner and the cost-tiered harness model, reimplemented inside pg_synapse |
| [pg-raggraph](https://github.com/yonk-labs/pg-raggraph) | retrieval over the policy corpus with effective dates: `as_of` returns the version in force |
| [stele](https://github.com/yonk-labs/stele) | memory with evidence: every decision cites a `stele://` artifact, corrections supersede, `as_of` shows what was believed |
| [chunkshop](https://github.com/yonk-labs/chunkshop) | ingest: the corpus and the agent's past runs as vector tables in the same database |

Watch it and click through the presentation: **https://theyonk.github.io/plexus/**

Design and build log: [`docs/DESIGN.md`](docs/DESIGN.md). Presenting the deck:
[`docs/deck.md`](docs/deck.md). Videos and .pptx: [`demo/README.md`](demo/README.md). Captured output
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

Host requirements: Docker (with Compose v2), `psql`, `curl`, `git`,
Python 3.12, `uv`, and Ollama. `make tune` also needs the Claude CLI (the
tuner's improver); the videos need an ElevenLabs key. The agent model is a
4B local model by default:

```bash
ollama pull qwen3:4b-instruct-2507-q4_K_M
OLLAMA_HOST=0.0.0.0:11434 OLLAMA_CONTEXT_LENGTH=32768 ollama serve &
```

### Quick start from a fresh clone

```bash
git clone https://github.com/TheYonk/plexus && cd plexus
make deps      # clones pg-synapse, stele, pg-raggraph, chunkshop next to this checkout, at the commits in deps.lock
make venv      # one venv with stele, pg-raggraph and chunkshop (editable, from those checkouts)
make up        # builds pgvector/pgvector:pg17 + pg_synapse (a few minutes the first time), starts the API
make ingest    # policy corpus -> pg-raggraph (v2 supersedes v1 on 2026-07-01) + chunkshop sink
make seed      # scenario tables, agents, skills, hints, the inline veto trigger
make run       # triage_agent handles 8 tickets; prints decisions and the assertion
make veto      # a 61-day refund is rejected inside the transaction; a 22-day one lands
make memory    # remember, supersede, recall now vs as_of
make trajectories   # past runs -> chunkshop -> plexus.trajectory_chunks, then search them
make tune K=2  # Propose-Probe-Compose; lessons land in synapse.lessons
make down
```

`make deps` leaves an existing checkout alone and says so if it is not at
the pinned commit. Put the siblings elsewhere with `DEPS=/some/dir` on every
`make` call. Other ports: `PG_PORT=...` and `API_PORT=...` (seeding points
the agent at the API port you chose).

**About the model.** The default 4B model fits a laptop and gets the
policy lookups and the veto right, but it fails the full 8-ticket
assertion more often than not (it tops out at 3 of 5 runs, and runs
sometimes stop early). The numbers in the deck and the videos come from
Qwen3.6-35B-A3B on vLLM. Any OpenAI-compatible endpoint works; give it to
the agent when seeding, as seen from inside the database container:

```bash
make seed LLM_MODEL=<model name> LLM_BASE_URL=http://<host>:8000/v1
```

The tuning numbers the UI and the deck show (37% fewer tokens per ticket)
are from a committed reference run, `results/tune-reference/`, until your
own `make tune` writes one to `tuned/`.

### Web UI and recorded walkthrough

```bash
make ui          # restarts the API with the shell dock on; open http://127.0.0.1:8766/
make demo-video  # ElevenLabs narration + Playwright recording -> demo/out/plexus-demo.mp4
make exec-video  # the executive cut (customer outcome, http://127.0.0.1:8766/exec) -> demo/out/exec/plexus-exec.mp4
make deck-video  # the presentation (http://127.0.0.1:8766/deck), narrated -> demo/out/deck/plexus-deck.mp4
make deck-pptx   # the presentation as a .pptx with speaker notes -> demo/out/deck/plexus-deck.pptx
```

The UI shows the stack, policy time-travel, the harness as data, a live run
(the agent's policy calls stream in while `synapse.execute` runs), the
trajectory, and the tuner's last run, next to a real shell on this machine.
`/exec` is the business version: a large retailer's refund queue, a live
veto of a bad refund, one decision explained end to end, the measured
tuning saving, Plexus against harness2 and a typical agent stack, and a
value calculator whose assumptions are on screen.
`/deck` is a 12-slide presentation to give live: arrows or space to move,
`S` for a presenter window with notes and a timer, `F` for fullscreen. Its
centrepiece is a live policy change: a refund passes under v2, refund
policy v3 (`scenario/policy-next/`) is published as one document, the same
refund is vetoed under v3, and a July ticket is still judged by v2. "Reset
to v2" puts everything back. Presenter guide: [`docs/deck.md`](docs/deck.md);
design and notes: `docs/deck-design.md`. How the videos and the .pptx are
made, and how to write a new cut: [`demo/README.md`](demo/README.md).
Every UI route answers loopback clients only; the shell also needs
`PLEXUS_SHELL=1` (set by `make ui`) and a per-process token. `demo-video`
needs `ELEVENLABS_API_KEY`, and `PLEXUS_VOICE_ID` for a voice of your own
(the default is a premade ElevenLabs voice); the narration lives in
`demo/script.py`. `make site` builds the GitHub Pages site (the videos, the
deck replaying a recorded run, the .pptx) into `site/_build`, and
`make site-publish` pushes it to the `gh-pages` branch. Design
and notes: `docs/webapp-demo-design.md`.

A stronger agent model is one profile row away (this is what `make seed
LLM_MODEL=... LLM_BASE_URL=...` writes), e.g. Qwen3.6-35B-A3B on vLLM:
`select synapse.llm_profile_set('llm','openai','qwen36-nvfp4','http://<host>:8000/v1',NULL,'{}')`.

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
deps.lock      the sibling projects and the commits Plexus is tested with (make deps)
results/       the reference tune run the UI and the deck quote
site/          the GitHub Pages site: landing page, build script, the deck's recorded run
db/            Dockerfile: pgvector/pgvector:pg17 + pg_synapse; initdb creates the three extensions
api/           FastAPI: /policy/search (pg-raggraph, as_of), /policy/ingest, /memory/*, /trajectories/*
api/cells/     chunkshop cells: policy corpus; past runs via a pg_table source over synapse.executions
scenario/      policy/*.md with effective dates, seed.sql, agents.sql, task.txt, assert.sql
scripts/       run_triage.sh
web/           the UI (/), the executive page (/exec) and the deck (/deck)
demo/          narration, Playwright recording, mux, .pptx export (see demo/README.md)
docs/          design docs, the deck guide, turnover
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

## License

Apache-2.0, see [`LICENSE`](LICENSE). pg_synapse, pg-raggraph, stele and
chunkshop are separate projects under their own licenses; `make deps`
fetches them, nothing of theirs is vendored here.
