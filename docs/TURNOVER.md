# Turnover: Plexus demo and the pg-synapse `harness2-borrowings` branch

Written 2026-10-19 07:35 EST at the end of one long session. Everything
below was verified on this box unless marked otherwise.

## What exists now

| Where | What | State |
| --- | --- | --- |
| `pg-synapse` branch `harness2-borrowings` | 3 commits (`8c3264d`, `db85f29`, phase 2), not pushed, on top of `main` `3d02378` | fmt, clippy (workspace + pgrx crate), 422 tests green (`--exclude pg_synapse_pgrx`) |
| `pg-synapse/docs/harness2-comparison.md` | the harness2 vs pg_synapse evaluation and the ranked borrowing list | done |
| `pg-synapse/docs/harness2-borrowings-plan.md` | design doc with todo (B1 to B12 all checked), implementation notes, gaps | done |
| `plexus/` (local git repo, `main`) | the combined demo: Dockerfile, API, scenario, Makefile, docs | works end to end; see `RUN.md` |
| `plexus/docs/DESIGN.md` | Part B (stele / chunkshop / pg-raggraph evaluation for harness2) and Part C (demo design, todo P1 to P6) | P1 to P4, P6 done; P5 captured in `RUN.md` with the tuning run still finishing |
| `plexus/RUN.md` | pasted real output of every `make` target | tune section partial (below) |
| `plexus-db:dev` Docker image | pgvector/pgvector:pg17 + pg_synapse from the branch's final commit | rebuilt 07:08 |

## The tuning run (finished 07:36)

`make tune K=2`, output dir `plexus/tuned/20261019-070455/`. All 8
rollouts failed the full assertion; `agg1` adopted provisionally and
applied to `triage_agent`; `synapse.lessons` row 1 written (see `RUN.md`
for the lesson and the two edit-table rows that matter). `make run` on the tuned harness (09:52): still FAIL overall, but 3 of
the 5 assertion conditions now pass versus 1 at baseline (escalation and
audit fixed; policy lookup and placeholder discipline still broken). Recorded
in `RUN.md`.

Rollout table so far (iters = LLM turns, tokens = in+out):

```
base1  23  93655+1287  FAIL      base2  23  93746+1316  FAIL
inv1   12  35076+921   FAIL      dom1   21  76325+1152  FAIL
inv2   24  84022+1560  FAIL      dom2   20  14580+2174  FAIL
agg1   13  39367+750   FAIL      agg2   21  76626+1306  FAIL
```

Read it honestly: the 4B model does not pass the eight-ticket scenario
with any of these harnesses in one pass, and the tuner said so instead of
claiming a win. inv1 and agg1 cut tokens by more than half. The per-ticket
decisions in each `rollouts/<label>.md` show which conditions moved
(audit rows, policy_version, escalation); the next step is a partial
score in `select()` (fraction of assertion conditions met) so the tuner
can climb rather than only accept a full pass. See "Next steps".

## How to bring it back up

```bash
# Ollama must bind all interfaces with a large context (default 4k breaks agent loops)
pkill -x ollama; OLLAMA_HOST=0.0.0.0:11434 OLLAMA_CONTEXT_LENGTH=32768 setsid -f ollama serve
cd /home/yonk/yonk-tools/plexus
make up && make ingest && make seed      # DB is ephemeral: `make down` wipes it
make run; make veto; make memory; make trajectories
make tune K=2                             # ~30 min; improver = claude CLI (OAuth, no API key)
```

API log: `plexus/api/api.log`. Postgres: `psql postgresql://postgres:postgres@127.0.0.1:55441/plexus`.
Useful SQL: `select synapse.agent_harness('triage_agent')`,
`select synapse.trajectory('<execution_id>'::uuid)`,
`select * from synapse.lessons`.

## Traps that cost time this session (avoid repeating)

- `cd` inside a compound Bash command is silently dropped by this
  harness; use absolute paths, `git -C`, `make -C`, `docker build ... <ctx>`.
- `pkill -f <pattern>` kills the calling shell when the pattern appears in
  its own command line (exit 144). Use `pkill -x name` or `pkill -f "[p]attern"`.
- A plain `&` inside a make recipe keeps make's stdout pipe open; use
  `setsid -f`.
- pg-raggraph `as_of` only filters when the instance is built with
  `evolution_tier="structural"`; the per-query flag can only turn it off.
- stele `as_of` is belief time, not event time.
- A pg_synapse run that hits the wall clock returns `timed_out` with no
  messages and no execution id (gap below).
- Nested Claude CLI works if `CLAUDECODE` and `CLAUDE_CODE_ENTRYPOINT` are
  unset (tune.py does this).

## Next steps, in order

Phase 2 (10:10 to 10:25 EST) closed items 2, 3, 6 and 7, and the
12:45 to 13:30 session closed 4 and 5; details in
`pg-synapse/docs/harness2-phase2-plan.md` and the last section of `RUN.md`.

1. ~~Run `make run` on the applied harness~~ done: 3/5 conditions.
2. ~~Partial scoring in `tune.py::select`~~ done: optional
   `scenario/conditions.sql`; a final is adopted on score only if it beats
   the best base rollout. Plexus has the file; `make run` prints it.
3. ~~Keep the trajectory on timeout~~ done: `ProgressSink` on
   `ExecutionContext`; verified live (execution id, messages, trajectory).
4. ~~Re-run `make tune K=2`~~ done (12:57 to 13:27) on Qwen3.6: every
   rollout passed, `agg1` adopted as the cheapest pass (133k input tokens
   vs 195k to 227k for the base), lesson 2 written. Partial scoring was not
   exercised because nothing failed; it still needs a run where the model
   is the ceiling (the 4B one).
5. ~~Try a stronger local model~~ done: Qwen3.6-35B-A3B NVFP4 on vLLM at
   `http://192.168.1.133:8000/v1` (`qwen36-nvfp4`). Needed one pg-synapse
   fix (`http_post` decodes a JSON-encoded string body). Tuned harness:
   **5/5, PASS**, 24 iterations, 86 s. See the last two sections of
   `RUN.md`. Coder-Next int4 is still untried (its weights are not on .133).
6. ~~Upgrade script~~ done: `pg_synapse_pgrx--0.1.1--0.2.0.sql`, workspace
   at 0.2.0, verified 0.1.1 -> 0.2.0 catalog equals a fresh install.
   Still open: sidecar parity for skills, hints, lessons.
7. ~~`git init` plexus~~ done (local repo, branch `main`, no remote).
8. **Push the branch** and open a PR against `yonk-labs/pg-synapse`
   (waiting on the owner's go). The README there still describes v0.1.1.
9. Optional: stele as the lessons store (supersession + `stele://`
   evidence) instead of `synapse.lessons`, per Part B of `DESIGN.md`.

## Files touched outside the two project dirs

- `~/.claude/projects/-home-yonk-yonk-tools/memory/plexus-and-harness2-branch.md`
  plus one line in `MEMORY.md` (project memory with the traps above).
- Ollama model pulled: `qwen3:4b-instruct-2507-q4_K_M` (2.5 GB).
- Isolated cargo-pgrx 0.18.0 installed under
  `~/.local/share/pgrx-toolchains/0.18.0`, pgrx initialized against the
  system PG 17 (`~/.pgrx`).
- `plexus/api/.venv` (stele, pg-raggraph, chunkshop editable from siblings).
