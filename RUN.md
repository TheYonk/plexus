# Plexus: captured run (2026-10-19)

Box: DGX Spark (GB10, 20 cores). Agent model: `qwen3:4b-instruct-2507-q4_K_M`
via Ollama with a 32k context. Improver: Claude CLI. Database: the
`plexus-db:dev` image (pgvector/pgvector:pg17 + pg_synapse from branch
`harness2-borrowings`). Everything below is pasted from real output; the
tuning section is appended as runs complete.

## `make up` / `make ingest`

```
postgres ready: pg_synapse 0.1.1, pg_trgm 1.6, vector 0.8.1
api ready: http://127.0.0.1:8766

== policy corpus -> pg-raggraph (effective dates, v2 supersedes v1) + chunkshop sink ==
"ingested": ["policy:escalation", "policy:refund-v1", "policy:refund-v2"],
"superseded": [{"old": "policy:refund-v1", "new": "policy:refund-v2", "updated": 1}],
"graph": {"documents": 3, "chunks": 3, ...},
"chunkshop": {"cell": "policy.yaml", "exit": 0, ... "docs=3 chunks=6 wall=0.3s"}

== as_of check: which refund policy was in force on 2026-05-20 vs 2026-07-20? ==
2026-05-20 -> refund-v1
2026-07-20 -> refund-v2
```

The time-travel lookups only work with pg-raggraph's
`evolution_tier="structural"` set on the instance; the per-query
`evolution_aware` flag cannot enable it (see `docs/DESIGN.md`).

## `make seed`

```
triage_agent always-on chars: 1504 / 24000
skills: refund_policy, escalation
inline veto trigger attached to support.refunds: 1
```

## `make run` (baseline harness, before tuning)

```
{'status': 'completed', 'iterations': 13, 'tokens_in': 32050, 'tokens_out': 1026, 'duration_ms': 18191, 'error': None}
tool calls: 12

 id  |    tier    |  created   | charge_date | category | priority | escalated | refund_decision | policy_version
-----+------------+------------+-------------+----------+----------+-----------+-----------------+----------------
 101 | pro        | 2026-05-20 | 2026-05-10  | billing  | urgent   | t         | approve         | refund-v2
 102 | pro        | 2026-06-15 | 2026-05-20  | billing  | urgent   | t         | deny            |
 103 | pro        | 2026-07-20 | 2026-06-28  | billing  | urgent   | t         | credit          | refund-v2
 104 | pro        | 2026-08-01 | 2026-06-01  | billing  | urgent   | t         | approve         | refund-v2
 105 | enterprise | 2026-07-05 |             | api      | urgent   | t         | n/a             |
 106 | enterprise | 2026-07-06 |             | howto    | normal   | f         | n/a             |
 107 | free       | 2026-07-07 |             | howto    | urgent   | f         | n/a             |
 108 | pro        | 2026-07-08 |             | howto    | normal   | f         | n/a             |

== assertion ==
FAIL
```

What the trajectory shows (via `synapse.trajectory`): the agent loaded
both skills but never called the policy API; it labelled every refund
ticket urgent and escalated the pro-tier ones (the escalation rule was in
its memory component); it wrote no audit rows; after one `sql_exec` error
with placeholders it fell back to inlining literals for the remaining
seven updates. This is the "before" the tuner works from.

## `make veto`

First attempt, with the gate agent doing the date arithmetic itself: the
4B model accepted a 61-day refund (it retrieved the right policy version,
then mis-compared). Second attempt, after moving the day count into the
SQL the gate runs (`created_at::date - charge_date AS days_since_charge`)
and stating the comparison mechanically:

```
ticket 104: pro tier, charge 2026-06-01, ticket 2026-08-01 (61 days, under v2 the window is 30 days) -> must be rejected
ERROR:  synapse inline trigger rejected: policy version, 61 days since charge exceeds the 30-day window
CONTEXT:  PL/pgSQL function synapse_trig_support_refunds() line 37 at RAISE
ticket 103: pro tier, charge 2026-06-28, ticket 2026-07-20 (22 days, under v2 the window is 30 days) -> allowed
INSERT 0 1

== rows that survived (only the allowed one) ==
 id | ticket_id | amount_usd |            note
----+-----------+------------+-----------------------------
  4 |       103 |      29.00 | customer changed their mind
```

The gate's trajectory: `sql_query` for the ticket, `http_post` to
`/policy/search` with `as_of = 2026-08-01` (returned `refund-v2`), then the
JSON verdict. The INSERT rolled back inside the writer's transaction.

## `make memory`

```
== decisions become stele memories (each cites a stele:// evidence artifact) ==
"memory_id": "01e1e699d015489e9caa8f5956cd728a", "evidence_ref": "stele://support/ae090c5b2f32..."
== a correction supersedes the earlier memory ==
"memory_id": "0261a27b25624450a4b29668b44bde3d", "superseded_ids": ["01e1e699d015489e9caa8f5956cd728a"]
== recall now vs recall as_of the instant between the two writes ==
 now   : active     | Correction: the May 10 refund was reversed on 2026-05-28 at the customer's request; account credit issued instead.
 as_of : superseded | Refund for the May 10 charge approved under refund-v1 (10 days since charge).
```

stele's `as_of` is about when a memory was believed, not about the event
it describes, so the demo captures the instant between the two writes.

## `make trajectories`

```
cell plexus_trajectories DONE docs=4 chunks=23 wall=1.6s
search "refund policy version applied" ->
  0.823  execution e7d14df1...  (the triage run: the refund_policy skill body as loaded)
  0.812  execution 3f048810...  (a gate run: the /policy/search observation returning refund-v2)
```

chunkshop's `pg_table` source reads `plexus.trajectory_docs`, a view that
renders each `synapse.executions` row with `synapse.trajectory()`. Past
runs are now searchable from the same database.

## `make tune K=2` (output dir `tuned/20261019-070455/`)

Base from the live agent: 1504 always-on chars, 2 skills, 5 hints. Eight
rollouts, each in a fresh database; improver sessions are Claude CLI.

```
label  dim   turns  tokens in+out  assertion
base1  base   23    93655+1287     FAIL
base2  base   23    93746+1316     FAIL
inv1   INV    12    35076+921      FAIL   (changed: system_prompt, guardrails, refund_policy skill)
dom1   DOM    21    76325+1152     FAIL   (changed: memory, both skills, system_prompt)
inv2   INV    24    84022+1560     FAIL
dom2   DOM    20    14580+2174     FAIL
agg1   AGG    13    39367+750      FAIL   (merge: memory, both skills, system_prompt, tool_hints)
agg2   AGG    21    76626+1306     FAIL
selection: agg1: nothing passed (base 0/2); agg1 at least completed without error. Adopted provisionally.
```

No harness passed all assertion conditions with the 4B model; the tuner
reported that rather than claiming a win. The reflection step finished at
07:36: `lesson 1 written to triage_agent`, `adopted harness applied`.
Full edit table: `tuned/20261019-070455/REPORT.md`. Two rows matter:

- **helped (4/4 vs 0/4):** the `memory.md` sentences that name the
  negative case ("pro and free are always escalated = false, whatever the
  priority"; "a plain refund request is normal priority"). Every run
  carrying them wrote normal/false on the pro-tier refund tickets; every
  run without them wrote urgent/true, including runs that shared all the
  other edits. One run regressed the positive case (enterprise+urgent).
- **confounded, strongest negative signal:** every one of the six
  candidates rewrote the `refund_policy` skill and every one made zero
  policy lookups, while both base runs made the lookup (with the wrong
  as_of). No candidate isolates the skill rewrite from the system-prompt
  rewrite, so the reflector refused to attribute it.

The lesson that landed in `synapse.lessons` (confidence medium): when the
agent contradicts a rule already in always-on context that is stated as a
formula, add the explicit negative-case sentence naming the combination it
got wrong, instead of restating the formula; keep the other clauses so the
positive case is not weakened. It is now folded into `triage_agent`'s
memory on every run.

## `make run` after the tune (tuned harness + lesson 1 folded into memory)

```
{'status': 'completed', 'iterations': 21, 'tokens_in': 76476, 'tokens_out': 1254, 'duration_ms': 27433}
tool calls: 20

 id  |    tier    |  created   | charge_date | category | priority | escalated | refund_decision | policy_version
-----+------------+------------+-------------+----------+----------+-----------+-----------------+----------------
 101 | pro        | 2026-05-20 | 2026-05-10  | billing  | normal   | f         | approve         | refund-v2
 102 | pro        | 2026-06-15 | 2026-05-20  | billing  | normal   | f         | deny            |
 103 | pro        | 2026-07-20 | 2026-06-28  | billing  | normal   | f         | credit          | refund-v2
 104 | pro        | 2026-08-01 | 2026-06-01  | billing  | normal   | f         | credit          | refund-v2
 105 | enterprise | 2026-07-05 |             | api      | urgent   | t         | n/a             |
 106 | enterprise | 2026-07-06 |             | other    | normal   | f         | n/a             |
 107 | free       | 2026-07-07 |             | howto    | low      | f         | n/a             |
 108 | pro        | 2026-07-08 |             | howto    | low      | f         | n/a             |

assertion: FAIL
per condition: classification PASS | escalation PASS | refund decisions FAIL | policy_version FAIL | audit (one row per ticket) PASS
```

Before versus after, on the assertion's five conditions: baseline passed
one (classification); the tuned harness passes three (classification,
escalation, audit). The escalation fix is exactly the edit the reflector
rated "helped" and turned into lesson 1. What still fails is the policy
lookup: the agent again skipped `http_post` and guessed `refund-v2` for
May tickets, and it again put a sentence in the `$6` id slot, got the
type hint, and fell back to inlining. Those two are the next tuning
targets; a per-condition score in `tune.py` would let the tuner see this
3-of-5 as progress instead of a failure (next step 2 in `docs/TURNOVER.md`).

## Phase 2 (10:15 to 10:20): pg_synapse 0.2.0 image, same tuned harness

`plexus-db:dev` rebuilt from the branch with the timeout-trajectory fix, the
upgrade script and the 0.2.0 version (`select synapse.version()` = `0.2.0`).
The DB is ephemeral, so the tuned `triage_agent` harness and lesson 1 were
exported before `make down` and restored after `make seed`; a component by
component comparison of `synapse.agent_harness('triage_agent')` matched.

`make run` now prints the conditions from `scenario/conditions.sql`:

```
{'status': 'completed', 'iterations': 21, 'tokens_in': 79203, 'tokens_out': 1259, 'duration_ms': 24979, 'error': None}
assertion: FAIL
per condition: classification PASS | escalation PASS | refund decisions FAIL | policy_version FAIL | audit (one row per ticket) PASS
```

Same 3 of 5 as the 09:52 run, same two failures: no `http_post` policy
lookup (`refund-v2` guessed for the May tickets) and `"strconv(101)"` in
the `$6` id slot, type hint, then inlined literals.

Timeout check, throwaway database, agent budget 1.2 s:

```
{"status": "timed_out", "tokens_in": 272, "iterations": 1, "tokens_out": 36, "duration_ms": 1200, "execution_id": "8f3f0bd5-..."}
messages logged: 4
executions row status: timed_out
[ACTION] sql_query {"query": "SELECT n*n FROM nums WHERE n = $1", "params": ["1"]}
[OBSERVATION] sql_query
[{"?column?":1}]
```

Before the fix the same call returned `timed_out` with no execution id
and nothing in `synapse.messages`.

## Qwen3.6-35B-A3B NVFP4 on 192.168.1.133 (12:45 to 12:58), same tuned harness

The LLM profile was re-pointed with
`synapse.llm_profile_set('llm','openai','qwen36-nvfp4','http://192.168.1.133:8000/v1',NULL,'{}')`
(vLLM on the second GB10, thinking left on). Only the profile changed: the
tuned harness and lesson 1 are the ones the 4B runs used, and
`scenario/seed.sql` alone reset the tickets (re-running `make seed` would
also re-run `agents.sql` and overwrite the tuned harness).

First run: 0 tickets written. The model passed `http_post.body` as a
JSON-encoded string (`"{\"query\": ...}"`) instead of an object, the API
answered 422 ("Input should be a valid dictionary") every time, and the
agent spent 44 iterations retrying the lookup. The two passing conditions
in that run are vacuous (nothing was written).

Fix in pg-synapse (`plugins/pg-synapse-tools-http`): a string body that
parses to a JSON object or array is sent parsed; any other string is
unchanged. The `.so` from the rebuilt image was copied into the running
container and the container restarted, so the database and the harness
were kept.

Second run:

```
{'status': 'max_iterations', 'iterations': 41, 'tokens_in': 282687, 'tokens_out': 16668, 'duration_ms': 166603, 'error': None}
assertion: FAIL
per condition: classification PASS | escalation PASS | refund decisions PASS | policy_version PASS | audit (one row per ticket) FAIL
```

4 of 5, and the first run where the refund decisions and policy versions
are right (v1 for the May and June tickets, v2 after 1 July). The audit
failed on budget, not judgment: the agent wrote duplicate audit rows for
101, spent iterations deleting them, re-ran lookups it already had, and
hit `max_iterations` (40) with 105 to 108 unaudited. It also took the
`$n` type and count hints and recovered both times.

## Tune on Qwen3.6 (12:57 to 13:27), then the adopted harness

`make tune K=2 LLM_MODEL=qwen36-nvfp4 LLM_BASE_URL=http://192.168.1.133:8000/v1`,
report in `tuned/20261019-125722/REPORT.md`:

```
rollout base1: passed=True score=1.0 iters=31 tokens=195553+19176
rollout base2: passed=True score=1.0 iters=34 tokens=227346+31246
rollout inv1:  passed=True score=1.0 iters=24 tokens=122541+13680
rollout dom1:  passed=True score=1.0 iters=30 tokens=182660+14034
rollout inv2:  passed=True score=1.0 iters=28 tokens=155044+12606
rollout dom2:  passed=True score=1.0 iters=31 tokens=180661+11993
rollout agg1:  passed=True score=1.0 iters=25 tokens=133163+7418
rollout agg2:  passed=True score=1.0 iters=28 tokens=160162+14737
selection: agg1 passed with the fewest tokens. Base passed 2/2.
lesson 2 written to triage_agent
```

Both base rollouts passed, so the 4-of-5 run above was variance (the
40-iteration cap is close to what this model needs with the old harness).
The tuner's win is cost: `agg1` gives one copyable write statement per
table with casts in the SQL and `handled_at = now()`, which removed the
type and count retries. Lesson 2 records that pattern.

`make run` on the applied harness, tickets reset with `scenario/seed.sql`:

```
{'status': 'completed', 'iterations': 24, 'tokens_in': 133114, 'tokens_out': 8693, 'duration_ms': 86307, 'error': None}
assertion: PASS
per condition: classification PASS | escalation PASS | refund decisions PASS | policy_version PASS | audit (one row per ticket) PASS
```

First full pass of the Plexus scenario. The live profile now points at
`qwen36-nvfp4` on .133; `make seed` (or `llm_profile_set`) with the
Makefile defaults puts it back on the local 4B Ollama model.
