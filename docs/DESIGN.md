# Plexus: design and build plan

Date: 2026-10-19. Plexus is the working name for the combined demo of five
yonk-tools projects: **pg_synapse** (agent runtime in Postgres),
**harness2** (recursive harness optimization, borrowed into pg_synapse on
the `harness2-borrowings` branch), **stele** (source-backed memory with
supersession), **chunkshop** (chunk, embed, sink), and **pg-raggraph**
(vector + BM25 + graph retrieval with time-travel). A plexus is a braided
network of nerves; the demo is those five wired through one Postgres.

## Part B: are stele, chunkshop and pg-raggraph useful with harness2?

Short answer: yes for all three, but in different roles, and only one of
them (stele) is a natural fit for harness2's own loop. The other two are
what the agent under optimization should be using, which makes them part
of the harness that gets tuned, not part of the tuner.

### stele: the experience library harness2 lacks a store for

harness2 keeps its per-domain library as files on disk: a full adopted
harness tree plus `EXPERIENCE.md` with cue / lesson / evidence /
confidence. That is exactly a stele artifact (the harness tree and
trajectories are immutable evidence) plus a stele memory (the lesson,
scoped by `agent_id`, citing `stele://` evidence, superseded when a later
task overturns it). Three specific fits:

- **Lessons that supersede.** harness2 appends; it never retracts a lesson
  that a later task shows was wrong. stele's `add(supersedes=[...])` and
  `retract()` give the library a correction path, and `as_of` lets you
  reconstruct what the library believed when a given task ran. That is a
  real gap in harness2 and stele closes it with no new code.
- **Evidence provenance.** harness2's `_distil` prompt demands that every
  lesson cite the trajectory moment it rests on. stele's `source_refs` must
  be non-empty `stele://` URIs, so the constraint becomes structural
  instead of prompt-enforced.
- **Oversized tool outputs.** `stash_tool_result` is a drop-in for
  harness2's `obs_trunc`: instead of truncating observations at 10k chars
  with a marker, store the full output and hand the model a reference and
  a scrubbed summary. This is also the one piece that plugs into pg_synapse
  directly, as a tower layer or a tool wrapper.

Limits: stele is Python with no CLI and no MCP server yet; the WorkGraph
and runtime packer are on an unmerged branch; extraction is deterministic
(lede + regex) so it will not distil a lesson from a trajectory by itself.
The improver still writes the lesson; stele stores and evolves it.

### chunkshop: the ingest side of a retrieval-aware harness

harness2 has no retrieval. Its "memory" component is an always-on text
file. chunkshop is the right tool for the on-demand alternative: ingest
the domain corpus (and, with the `pg_table` source, the agent's own past
`synapse.messages`) into a pgvector table the agent can query through a
tool, and let the tuner decide what belongs in always-on memory versus
what should be retrieved. Two concrete uses:

- **Corpus for DOM proposals.** harness2's DOM dimension asks the improver
  for "what a practitioner knows." Give the improver a `search_corpus`
  tool backed by a chunkshop sink and the DOM proposal can cite the corpus
  instead of inventing authority, which is one of harness2's two hard
  rules for that dimension.
- **Bakeoff as a harness lever.** The chunker and embedder choice is part
  of the harness. chunkshop's bakeoff already produces `recommended.yaml`
  from a gold set; the tuner can treat that as a component it is allowed
  to change.

Limits: no content-hash dedup, so re-ingesting trajectories re-embeds
them; Python retrieval API is `query_top_k` only, so the agent-facing
search tool is a few lines of SQL over the sink table. The Rust crate
(`chunkshop-rs`) can embed in-process, which matters later if the search
tool moves inside the pg_synapse extension.

### pg-raggraph: the retrieval the agent should have, and time-travel

pg-raggraph is the strongest fit for the agent under test and the
weakest fit for harness2's own loop. Its value for the demo:

- **Time-versioned knowledge.** `query(as_of=..., version_filter=...)`
  with supersession and retraction is the capability nothing else in the
  stack has. An agent deciding a ticket should apply the policy in force
  on the ticket's date; this is one parameter away.
- **Graph-boosted retrieval over trajectories.** Ingest past trajectories
  with `lede_spacy` (no LLM) and the entity graph links tool names, table
  names and error strings across runs. `naive_boost` on that graph is a
  cheap way to find "every run that hit the same error."
- **Scoring weight tuning.** `tune_scoring_weights` grid-searches against
  a gold set; the same shape as the tuner, so it can be driven by it.

Limits: all retrieval SQL is Python-side f-strings, so a Postgres
extension cannot call it; the demo reaches it through a thin HTTP service.
The `facts` and `fact_edges` tables are placeholders. Evolution APIs are
not exposed over MCP or REST, so the service adds them.

### Verdict

| Project | Role in a harness2-style loop | Fit |
| --- | --- | --- |
| stele | Library store: lessons with supersession and evidence | Strong |
| chunkshop | Ingest of corpus and trajectories into tunable retrieval | Medium |
| pg-raggraph | The agent's retrieval tool, with time-travel | Strong for the agent, weak for the tuner |

## Part C: the demo

### What Plexus does that no other stack does

One Postgres holds the agent, its tools, its trajectories, its retrieval
corpus with effective dates, its evidence-backed memory, and the optimizer
that rewrites its harness. Four things fall out of that which no agent
framework offers together:

1. **Self-tuning with an audit trail in SQL.** `bench/tune.py` improves an
   agent from its own `synapse.messages`; every adopted edit and every
   lesson row cites the `execution_id` it came from, and
   `synapse.trajectory(id)` shows the moment. LangGraph, ADK and the
   OpenAI SDK have no optimizer; harness2 has no runtime.
2. **Policy-as-of-date decisions.** The agent retrieves the version of a
   policy that was in force on the row's date, not the newest one, and the
   answer cites the chunk and the version label. No RAG framework exposes
   `as_of` to a tool-calling agent inside the database.
3. **Transactional veto with retrieval.** An inline trigger agent can
   reject an INSERT, and its reason can cite retrieved policy. The write
   rolls back. Nothing outside Postgres can do this.
4. **Memory that supersedes instead of accumulates.** Decisions the agent
   makes about a customer become stele memories; a later correction
   supersedes the earlier one and `as_of` shows what the agent believed
   when it acted. Agent-memory products append.

### Scenario: support triage under a changing refund policy

Built on the existing a3_triage bench scenario so the tuner has a known
baseline. Additions:

- A `policy` corpus: three short markdown documents (refund policy v1,
  refund policy v2 superseding v1 from a given date, escalation matrix),
  ingested by chunkshop into `plexus.chunks` and by pg-raggraph into its
  graph with `effective_from`/`version_label`.
- Tickets carry `created_at` on both sides of the v2 effective date, and
  some ask for refunds that are allowed under one version only.
- The agent gets `search_policy(query, as_of)` via `http_post` to the
  Plexus service, plus `sql_query` and `sql_exec`.
- `assert.sql` checks the refund decision against the policy in force on
  the ticket date, the escalation rule, and the audit row count.
- A `policy_gate` agent attached inline to `support.refunds` vetoes a
  refund that violates the policy in force.
- After triage, decisions are written to stele as memories scoped by
  customer; a correction supersedes one of them and the demo shows the
  `as_of` view.

### Architecture

```
docker compose
  db        pgvector/pgvector:pg17 + pg_synapse extension (plexus-db image)
  api       Python: FastAPI wrapping pg-raggraph query/ingest, stele
            recall/remember, chunkshop ingest. Talks to db over the wire.
host
  ollama    qwen3:4b-instruct-2507 at :11434 (the agent's LLM)
  claude    the improver for bench/tune.py (Claude CLI, OAuth)
  make      the demo driver: up, ingest, seed, run, tune, veto, memory
```

The agent reaches the api service through pg_synapse's `http_post` tool;
the SSRF allowlist is set to the service host.

### Todo

- [x] P1 `db/Dockerfile`: pgvector base + pg_synapse from the
      `harness2-borrowings` branch. Builds; `CREATE EXTENSION` works for
      vector, pg_trgm, pg_synapse_pgrx.
- [x] P2 `api/`: FastAPI service with `/search` (pg-raggraph, `as_of`),
      `/ingest` (chunkshop cell + pg-raggraph ingest), `/remember`,
      `/recall`, `/supersede` (stele). One venv, pinned to the sibling
      checkouts by path.
- [x] P3 `scenario/`: policy corpus, seed SQL with dated tickets,
      agent definitions with components (system prompt, guardrails,
      skills), `assert.sql`, `task.txt`.
- [x] P4 `Makefile` targets: `up`, `ingest`, `seed`, `run`, `tune`,
      `veto`, `memory`, `down`. Each prints what it proves.
- [ ] P5 Run end to end against Ollama; capture `RUN.md` with real
      output: baseline pass/fail, tuned pass/fail, the veto rollback, the
      `as_of` memory view.
- [x] P6 `README.md`: what it is, the four unique capabilities with the
      exact commands that show each, and what is borrowed from where.

## Implementation notes

### P1 image

`pgvector/pgvector:pg17` is derived from `postgres:17`, so the pg_synapse
artifact tree built against PGDG `postgresql-server-dev-17` drops straight
in. A warm build takes about three minutes on this box. `CREATE EXTENSION`
for `vector`, `pg_trgm` and `pg_synapse_pgrx` all succeed from the initdb
script. `PG_SYNAPSE_HTTP_ALLOW=host.docker.internal` on the container is
what lets `http_post` reach the host API past the SSRF guard.

### P2 API

pg-raggraph's time-travel only engages when the instance is built with
`evolution_tier="structural"`; the per-query `evolution_aware=True` flag
cannot turn it on by itself (it can only turn it off). With the tier on,
`query(as_of=...)` filters on the effective window and populates
`version_label` / `effective_from` / `effective_to` on each chunk.
`ingest_records` with `skip_llm=True` needs no LLM; `supersede(...)` writes
v1's `effective_to`. stele's Postgres backend creates its own `artifacts`
and `memories` tables in the same database on first use. chunkshop cells
run through its CLI from the API's venv; `target.database` is a schema.

### P3 scenario

Built on the a3_triage shape (classification, escalation rule, one audit
row per ticket) plus a refund dimension whose correct answer depends on
the policy version in force on the ticket date. Four refund tickets
straddle the 1 July 2026 boundary, so an agent that applies the newest
policy to every ticket gets two of them wrong.

### P5 run (in progress; see ../RUN.md)

Baseline `make run`: 13 turns, 18 s, FAIL. The failure modes are the ones
the tuner's INV and DOM dimensions are designed for: a skill loaded but
its API call skipped (procedure), pro-tier refunds escalated against a
rule sitting in memory (practitioner knowledge), zero audit rows, and
literal inlining after one placeholder error (an error-signature hint
candidate).

`make veto`: the trigger plumbing worked first time (agent ran inline,
retrieved the right version with `as_of`, returned JSON). The 4B model
mis-compared 61 days against a 30-day window until the SQL computed the
day count for it. A harness lesson in miniature: move arithmetic out of
the model and into a tool result.

`make memory`: stele's `as_of` is over belief time, not event time, so the
demo captures the instant between the two writes.

### P4 driver

The API runs on the host (its Python stack is heavy) and detaches with
`setsid -f`; a plain `&` inside a make recipe keeps make's pipe open.

## Gaps and next steps

(Filled in at the end.)
