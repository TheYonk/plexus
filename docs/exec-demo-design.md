# Plexus executive cut: the customer outcome video

Started 2026-10-20 14:40 EST. The user asked for a second demo video that
shows a customer outcome: a big use case for a larger customer, why they
would want this, something that lands with a CEO. And: why this is better
than just harness2 plus whatever stack you would bolt around it. Choices
are mine unless marked (the user said "use your best judgment" for the
first video and did not ask for questions here).

## Intent

The first video is for engineers: how it works. This one is for the person
who signs the cheque: what goes wrong today when an AI agent makes money
decisions at scale, what Plexus does about it, and what that is worth. It
should feel like a business case with two live proofs, not a feature tour.

## Goals

1. A customer the viewer recognises: a large subscription retailer, about
   two million support tickets a month, refund and escalation policies
   that change every quarter. Clearly labelled illustrative.
2. Three outcomes, each shown live or from a real artifact, never claimed:
   - **Money cannot leak.** The inline veto: a refund that breaks the
     policy in force on the ticket date is rejected inside the
     transaction; a valid one lands. Live.
   - **Every decision answers the auditor.** Pick a refund: the decision,
     the policy version applied, the audit line, the policy text as of the
     ticket date, and the trajectory step where the agent looked it up.
     Live query.
   - **It gets cheaper without an engineer.** The tuner result: 5/5 kept,
     about 37% fewer input tokens, the lesson it wrote. From the recorded
     tune.
3. The "why not harness2 plus the usual stack" answer, as a side-by-side.
4. A value calculator with every assumption visible and adjustable, and
   measured numbers marked as measured.
5. Same voice, same pipeline (v4, tags, stitching, leveling), 3 to 4
   minutes.

## Non-goals

- No new agent capability. Everything shown already exists in Plexus.
- No live 8-ticket run (the first video has it; it is slow and the CEO
  does not need to watch it).

## Anti-goals

- Invented customer results. The customer is a scenario; the dollar
  figures come from assumptions on screen, and the narration says so.
- Claims about harness2 it would dispute. harness2 is the method and it is
  good; the point is where the method runs, not that it is wrong.
- Promising rollback or versioning that is not built (there is no harness
  history table; each tune keeps base and adopted side by side on disk).

## Design

### Page: `web/exec.html` + `web/exec.js` at `GET /exec` (loopback-only)

Full-bleed slides, one visible at a time, same tokens as `style.css`:

1. **Cold open.** "Two million tickets a month. Every refund is a money
   decision." Customer card (illustrative).
2. **What goes wrong today.** Three cards: wrong policy version (money
   leaks or customers get shorted), decisions nobody can explain
   (chargebacks, regulators), agents that only improve when an engineer
   babysits them (cost, drift).
3. **Proof 1, the guardrail is the database.** Button runs the two veto
   inserts; shows the rejected one with the agent's reason as the
   Postgres error, the accepted one, and the refunds table after.
4. **Proof 2, answer the auditor.** One ticket's full chain, from one
   query.
5. **Proof 3, cheaper on its own.** Tuner numbers and the lesson.
6. **Why not harness2 + the usual stack.** Three columns: a typical agent
   stack (framework + vector DB + memory service + eval tool), harness2 on
   its own, Plexus. Rows: where the agent runs, what a half-finished run
   leaves behind, policy as of a date, audit trail, what tuning learns
   from, how a change is adopted, systems to run and secure.
7. **The math.** Sliders: tickets per month, share needing a refund
   decision, average refund, wrong-policy rate today, input tokens per
   ticket (default measured), price per million tokens. Outputs: refund
   exposure per year, token spend saved by tuning per year.
8. **Close.** One line, the repo.

### Backend: added to `api/ui.py`

- `POST /exec/veto`: resets the refunds table, runs the two inserts in
  separate transactions with a statement timeout, returns
  `{rejected: {ok, error}, allowed: {ok}, rows}`.
- `GET /exec/audit/{ticket_id}`: ticket, customer tier, decision, policy
  version, audit action, the policy text as of the ticket date (via
  `search_policy`), and the trajectory step that called the policy tool
  in the latest execution.
- `GET /exec/numbers`: measured base and adopted input tokens per run and
  per ticket from the newest `tuned/*/summary.json`.

### Pipeline

`voice.py`, `record.py`, `mux.py` take `--script exec`: it loads
`demo/exec_script.py` and writes under `demo/out/exec/`. Steps use the
same markers; a new `@wait_veto` waits for the veto call (the inline
trigger agent calls the LLM). `make exec-video`.

## Todo

- [x] E1 backend: `/exec`, `/exec/veto`, `/exec/audit/{id}`, `/exec/numbers`
- [x] E2 `web/exec.html`, `exec.js`, slide styles; calculator
- [x] E3 `window.execDemo` hooks (goto, spotlight, runVeto, setSlider)
- [x] E4 parameterise voice/record/mux by script; `@wait_veto`
- [x] E5 `demo/exec_script.py` narration (the-yonk voice, CEO register,
      v4 tags, respellings), AI-tell review
- [x] E6 smoke-test page and endpoints in a browser (veto reliability)
- [x] E7 render audio, record, mux; frame check
- [x] E8 Makefile target, README, design-doc notes, secret scan, commit

## Implementation notes

- `api/ui.py` gained `/exec`, `/exec/veto`, `/exec/audit/{id}`, `/exec/numbers`
  on the same loopback-only router.
- Found while building: `scenario/seed.sql` recreates `support.refunds`,
  which silently drops `policy_gate`'s trigger, so after any ticket reset
  both refunds landed (and `make veto` would have too). `/ui/reset` and
  `/exec/veto` now re-attach it when it is missing (`_ensure_veto_trigger`).
  With it attached the veto was right 4 times out of 4 on Qwen3.6 (5 to 11
  seconds per insert).
- The audit slide shows ticket 104's real chain: the run decided `credit`
  under refund-v2 (61 days is past v2's 60-day limit), which is correct, so
  the narration says so. The policy excerpt is clauses 1 to 3, not the
  document header; the lookup step is rendered as `POST /policy/search
  as_of <date>`.
- Numbers on the "cheaper" slide come from `tuned/20261019-125722`: base
  211,450 input tokens per 8-ticket run (mean of 2), adopted 133,163, so
  26,431 to 16,645 per ticket, 37% less. All 8 rollouts passed.
- Calculator defaults (all labelled assumptions): 2M tickets a month, 20%
  needing a refund decision, 2% wrong-policy rate, $45 average refund,
  $3 per million input tokens. Outputs: $4.3M a year exposed, $705k a year
  saved. The narration quotes these defaults and says they are
  assumptions.
- Pipeline: `demo/scripts.py` maps `--script walkthrough|exec` to the
  module and output directory; `voice.py`, `record.py` and `mux.py` all
  take it. `@veto` retries a wrong veto outcome with a cut, like the run
  block. `make exec-video`.

- Final take: `demo/out/exec/plexus-exec.mp4`, 4:04, veto right on the
  first attempt, no page errors. Transcripts of every clip checked; two
  phrases that read badly aloud were rewritten ("the veto is in the write
  path" heard as "right path"; "the policy in force is enforced").

## Next steps and gaps

- The calculator's wrong-policy rate is an assumption with no measured
  basis here; a real pilot would measure it by replaying historical
  tickets with and without the as-of lookup.
- "in force" is still heard as "enforced" in a couple of lines; "in
  effect" would be clearer if the user wants another pass.
- The veto is an LLM call per insert (5 to 11 s on Qwen3.6). Fine for
  refunds, too slow for a hot write path; a rules fast path in front of
  the agent would be the production shape.
- No harness version history in pg_synapse; the video avoids claiming
  rollback. A `synapse.harness_history` table would make that claim true.
