# tune: plexus (k=2, model=qwen36-nvfp4, improver=claude)

Run: tuned/20261019-125722 (kept in results/tune-reference/ as the reference run)

## Rollouts

| label | dim | passed | score | iterations | tokens in+out | error |
|---|---|---|---|---|---|---|
| base1 | base | True | 1.0 | 31 | 195553+19176 |  |
| base2 | base | True | 1.0 | 34 | 227346+31246 |  |
| inv1 | INV | True | 1.0 | 24 | 122541+13680 |  |
| dom1 | DOM | True | 1.0 | 30 | 182660+14034 |  |
| inv2 | INV | True | 1.0 | 28 | 155044+12606 |  |
| dom2 | DOM | True | 1.0 | 31 | 180661+11993 |  |
| agg1 | AGG | True | 1.0 | 25 | 133163+7418 |  |
| agg2 | AGG | True | 1.0 | 28 | 160162+14737 |  |

## Selection

Adopted: `agg1`. 2/2 finals passed the task's end-state check; `agg1` passed with the fewest tokens (133163+7418). Base passed 2/2.

## Conditions met

- base1: classification=ok, escalation=ok, refund decisions=ok, policy_version=ok, audit (one row per ticket)=ok
- base2: classification=ok, escalation=ok, refund decisions=ok, policy_version=ok, audit (one row per ticket)=ok
- inv1: classification=ok, escalation=ok, refund decisions=ok, policy_version=ok, audit (one row per ticket)=ok
- dom1: classification=ok, escalation=ok, refund decisions=ok, policy_version=ok, audit (one row per ticket)=ok
- inv2: classification=ok, escalation=ok, refund decisions=ok, policy_version=ok, audit (one row per ticket)=ok
- dom2: classification=ok, escalation=ok, refund decisions=ok, policy_version=ok, audit (one row per ticket)=ok
- agg1: classification=ok, escalation=ok, refund decisions=ok, policy_version=ok, audit (one row per ticket)=ok
- agg2: classification=ok, escalation=ok, refund decisions=ok, policy_version=ok, audit (one row per ticket)=ok

## Decisions

### inv1 (INV)

revised -> system_prompt.md (procedure) -> base1 and base2 both made three http_post calls in a row (as_of 05-20, 06-15, 07-20) and then batched the UPDATEs, so ticket 104 never had its own lookup. Replaced the one-line "one ticket at a time" with an explicit per-ticket a/b/c sequence in id order.
added -> system_prompt.md (UPDATE/INSERT template with params example) -> base1 first sent "false" as text, then sent params as a string ("there is no parameter $7"). base2 put the id first ("integer = text") and then sent a 7-item array for 6 placeholders. A template with a fixed param order and casts removes both mistakes.
added -> system_prompt.md ("handled_at is always now() in the SQL") -> both runs bound handled_at to the ticket's created_at (base1 line 145, base2 line 150), when the task says now().
added -> tool_hints.json `column "handled_at"` (sql_exec) -> both runs hit "column handled_at is of type timestamptz but expression is of type text", and the generic hint told them to cast, which locked in the wrong value. The new hint, plus an exception line in the generic hint, tells the agent to use now() instead.
added -> system_prompt.md ("Never UPDATE or audit a ticket twice"; audit states the same values as the UPDATE) -> base1 re-updated 102, 104 and 107. base2 re-updated 104 three times, 105 and 107. The audits for 104 (base1 "31 days", base2 "Denied") contradict the final credit UPDATE.
added -> system_prompt.md (definition of done, then stop calling tools) -> base2 spent turns after the last audit on verification SELECTs that errored ("102::int", ANY($1::int[])) plus another UPDATE of 104, reaching 34 of 40 turns.
dropped -> memory.md "Lessons from earlier runs" paragraph -> it is advice on how to edit the harness, not something the agent acts on, and no run used it. Cutting it offsets the procedure text added above.
kept -> guardrails.md, skills/escalation, skills/refund_policy, the other tool_hints -> both runs loaded both skills on time, and the existing hints for param count, wrong position and wrong type fixed their errors within one or two retries.

### dom1 (DOM)

revised -> memory.md (dropped "Lessons from earlier runs" block) -> both runs: that ~800-char block of advice for whoever edits the harness had no action the agent could take, and its rules were already stated above it; removing it pays for the new lines
added -> memory.md (credit past last limit, never deny) -> base1 L238 and base2 L203: ticket 104 (61 days, refund-v2) first written as refund_decision 'deny', then changed to 'credit'
added -> memory.md (handled_at = now() in the SQL text, not a param, not created_at) -> base1 L145 onward and base2 L150 onward: every UPDATE bound handled_at to the ticket's created_at value
added -> memory.md (audit must match the ticket's final UPDATE) -> base1 L223: 104 audit says "31 days" (actually 61); base2 L238: 104 audit says "Denied" but final value is credit; base2 L258 vs L228: 108 audit says "low" but stored priority is normal
revised -> memory.md priority line (+ "a how/where question is low") -> difference between runs: base1 L203 wrote 108 as low, base2 L228 wrote 108 as normal
revised -> skills/refund_policy (count charge_date rows = number of lookups; before each refund UPDATE, confirm a response whose as_of equals this ticket's created_at) -> both runs made only 3 http_post lookups for 4 refund tickets; 104 (as_of 2026-08-01) was never looked up
revised -> skills/refund_policy step 3 (beyond last limit = credit, never deny, with the 61-day refund-v2 example from the policy text) -> same 104 deny→credit flip in both runs
revised -> system_prompt.md (closing SELECT checked against the rules and the audit sentences; build the report from that SELECT) -> base2 L286: the check query returned 108 priority=normal, yet the report at L308 says low and nothing was fixed
kept -> skills/escalation -> 105 escalation, 106 other/normal and 107 api/high/not-escalated ended correct in both runs; the 107 normal→high correction happened without help
kept -> guardrails.md, tool_hints.json -> tool errors and casts belong to the other candidate; nothing domain-related there

### inv2 (INV)

revised -> system_prompt.md (procedure sentence replaced by a 4-step per-ticket loop plus a definition of done) -> both runs: lookups for 101–103 then batch UPDATEs; 104 never got its own policy lookup; 104 updated 3× (credit/deny/credit) and 107 2× in both runs; base2 audit for 104 "Denied" vs written credit; base1 audit for 104 "31 days"; 31/34 of 40 turns used
revised -> system_prompt.md (report counts from the final verification SELECT, then stop) -> base2 ran a final SELECT showing 108 = normal but reported 108 = low; base2 spent 3 extra turns on ad-hoc check queries
revised -> guardrails.md (handled_at = now() stays in the SQL text, not a param) -> base1 and base2 first UPDATEs both bound handled_at to the ticket's created_at, likely because "never inline literal values" was read as covering now(); the task says handled_at = now()
added -> tool_hints.json `column "handled_at"` -> the handled_at timestamptz error in base1 (2nd retry) and base2 (2nd retry); the generic cast hint told the agent to cast the wrong value instead of switching to now()
revised -> tool_hints.json "but expression is of type" (handled_at exception) -> same moment, in case only one hint is attached
revised -> tool_hints.json "invalid input syntax for type" (tool_name null; casts never inside params) -> base2 sql_query with params ["102::int"] got no hint because the entry was sql_exec-only; base2 UPDATE with "105::int" in params
revised -> tool_hints.json "there is no parameter $" (params must be a JSON array, not a string) -> base1 sent params as the string "['billing', ..., 101]" and got "no parameter $7"
kept -> other tool_hints entries, memory.md, skills/escalation, skills/refund_policy -> both runs loaded the skills and made the policy calls correctly; category/priority content belongs to the parallel candidate

### dom2 (DOM)

revised -> memory.md (handled_at line) -> base1 and base2 both passed created_at as the handled_at param ("2026-05-20T09:00:00+00:00" for 101, etc.); task says handled_at = now(); added "write now() in the SQL text, never created_at"
revised -> memory.md (decide-then-write, one UPDATE + one audit per ticket) -> base1 ran UPDATE 104 three times (credit, deny, credit) and 107 twice (normal, then high); base2 ran 104 three times, 107 twice and 105 twice; base2's 104 audit says "Denied" against a final 'credit' row
revised -> memory.md (final SELECT check, report built from it) -> base2's database has 108 priority=normal but its report table says low; the final SELECT showed normal and the agent reported something else
revised -> memory.md (priority negatives: howto question low, one user unable to log in high) -> base2 wrote 108 as normal (base1 got low); both runs first wrote 107 as normal, then fixed it to high
dropped -> memory.md ("Lessons from earlier runs" meta-bullet) -> always-on text that is advice about editing the harness, not a domain fact; no run acted on it
revised -> skills/refund_policy (number of lookups = number of charge_date rows; never reuse another ticket's response) -> both runs called policy/search only for as_of 2026-05-20, 06-15 and 07-20; 104 (created 2026-08-01) never got its own lookup
revised -> skills/refund_policy ("deny only in the middle band; past the last limit is always credit") -> both runs first wrote 104 (61 days, past v2's 60-day limit) as 'deny', and base2's 104 audit kept "Denied"
revised -> skills/refund_policy (audit days = step-2 number) -> base1's 104 audit says "31 days after charge" when it was 61
kept -> skills/escalation -> category and escalation came out right in both runs' final rows; the 107/108 priority slips are covered in memory
kept -> system_prompt.md, guardrails.md -> no run's mistake traces to their wording
kept -> tool_hints.json -> tool errors belong to the other candidate

### agg1 (AGG)

revised -> system_prompt.md (a/b/c per-ticket procedure with a fixed UPDATE/INSERT template using `$3::boolean`, `$6::int` and `handled_at = now()`; never UPDATE twice; stop after done) -> base1 L145-157 and base2 L150-166 each lost 3 retries to params errors and bound handled_at to created_at; both re-updated 104 (credit→deny→credit) and 107; base2 ran 34 iterations, partly on failing check queries. inv1, using this text, had 0 errors and 24 iterations with one UPDATE and one audit per ticket. dom1, dom2 and inv2, without the full template, still had 2-5 params errors.
added -> guardrails.md (handled_at = now() is the exception to "never inline") (from inv2) -> "never inline literal values" pushed both base runs to bind handled_at to the ticket's created_at; this removes the conflict at its source.
added -> tool_hints.json `column "handled_at"` (inv1 wording) + handled_at exception in the "but expression is of type" hint -> base1 L160 and base2 L159: the general cast hint led straight to `$6::timestamptz` with created_at.
revised -> tool_hints.json "there is no parameter $" (params must be a JSON array, not a quoted string; tool_name null) (from inv2) -> dom1 L162-171 sent params as a string twice and dom2 L156-183 three times under the old hint; in inv2 L151-157 the new hint got a correct resend on the next call.
revised -> tool_hints.json "invalid input syntax for type" (tool_name null; casts never inside params) (from inv2) -> base2 L229 sql_query with params ["102::int"] got no hint because the entry only applied to sql_exec.
dropped -> memory.md "Lessons from earlier runs" block -> advice about editing the harness, not something the agent can act on; all four proposers cut it and no run used it.
revised -> memory.md priority line (+ "how/where question is low; one user unable to log in is high, whatever the tier") (from dom2) -> base2 L228 wrote 108 as normal; base1 L198 and base2 L178 first wrote 107 as normal; inv1 L213 kept 107 normal "for free tier" because its no-re-UPDATE rule stopped the correction.
revised -> skills/refund_policy (lookup count = number of charge_date rows; no reusing another ticket's response) (from dom2) -> base1 and base2 made 3 http_post calls for 4 refund tickets, so 104 (as_of 2026-08-01) was never looked up.
revised -> skills/refund_policy step 3 (past the last limit is credit, never deny; 61-day refund-v2 example) (from dom1) -> base1 L238 and base2 L203 both wrote 104 as deny before switching to credit; base2's 104 audit kept "Denied".
dropped -> dom2 skill step-6 "same number from step 2" -> dom2's own run still wrote "31 days" for 104 (L247), so the edit didn't change behaviour.
dropped -> dom1/dom2 closing "SELECT, check, re-UPDATE any row that differs" -> it contradicts the never-UPDATE-twice rule that removed the base re-update churn; inv1 reported correct counts without it.
dropped -> inv2 "report from one SELECT of handled rows" -> inv2 L243 ran that count with no id filter, so it would also count tickets handled before this run.
dropped -> dom1/dom2 memory lines for handled_at and audit matching -> already covered by the system_prompt template, clause c and the guardrail; keeping them would repeat always-on text.
kept -> skills/escalation, the semicolon, missing-query, operator and blocked-host hints -> every run loaded the skill in time and ended with correct categories and escalation for 105 and 106; no run's mistake traces to these hints.

### agg2 (AGG)

revised -> system_prompt.md (per-ticket a/b/c procedure with UPDATE/INSERT templates, handled_at = now(), "never UPDATE or audit twice", definition of done) -> base1 and base2 each made only 3 policy lookups (104 had none), bound handled_at to created_at, and re-updated 104 three times (credit/deny/credit). inv1 used this template and finished in 24 turns with zero tool errors, 4 lookups, one UPDATE per ticket and now()
added -> system_prompt.md (final GROUP BY SELECT on the triaged ids, report from it, then stop) -> base2's final SELECT showed 108 = normal but its report said low, and it spent turns 263–283 on failing ad-hoc checks. inv2's GROUP BY report matched its stored rows. Scoped to the first SELECT's ids because inv2's query was not
dropped -> dom1 "re-UPDATE any row that differs" -> it contradicts the one-UPDATE rule, and repeated re-UPDATEs are what broke the 104 audits in both base runs
revised -> guardrails.md (handled_at = now() is the exception to "never inline literal values") -> both base runs put handled_at into params and then cast created_at to fit (base1 L145, base2 L162). Taken from inv2, whose run used now() from the first UPDATE
revised -> tool_hints.json (taken from inv2: new `column "handled_at"` hint, handled_at exception in the cast hint, "no parameter $" says params must be a JSON array, invalid-input hint applies to any tool) -> in dom1 (base hints) params sent as a string failed three times with "no parameter $6" before a correct call. In inv2 the revised hint fixed the same mistake on the next call (L151→L157). base2's sql_query with "102::int" got no hint because that entry was sql_exec-only
dropped -> memory.md "Lessons from earlier runs" block -> all four proposers cut it. It is advice about editing the harness and no run acted on it
revised -> memory.md priority line (+ how/where question is low, one user unable to log in is high) -> base2 wrote 108 as normal. Both base runs first wrote 107 as normal, and inv1 wrote 107 normal and never fixed it under the one-UPDATE rule. dom2 (with this line), dom1 and inv2 all wrote 107 high the first time
revised -> skills/refund_policy (number of lookups = number of charge_date rows, never reuse another ticket's response) -> both base runs looked up only 05-20, 06-15 and 07-20, never 08-01 for 104. All four candidate runs made 4 lookups
revised -> skills/refund_policy ("deny" only in the middle band, past the last limit is always credit) -> both base runs first wrote 104 (61 days, refund-v2) as deny, and base2's 104 audit kept "Denied"
revised -> skills/refund_policy step 6 (audit day count = step-2 number) -> base1's 104 audit said "31 days" (actual 61). dom2 had this line and still wrote "31 days", but it batched audits far from the decision. The per-ticket audit step in the system prompt targets that mechanism, as in inv1/inv2, where the 104 audits were correct
kept -> skills/escalation -> both base runs loaded it and their final category and escalation values were right. The 107/108 priority slips are handled in memory
not adopted -> dom1/dom2 memory lines on handled_at and audit matching -> the system prompt template and guardrail already cover both, so they would only repeat always-on text

## Experience

| Component | What changed (candidates) | Observed difference in execution | Verdict |
|---|---|---|---|
| system_prompt.md: a literal UPDATE/INSERT template with `$3::boolean`, `$6::int`, `handled_at = now()` and an example params array (inv1, agg1, agg2) | Before, the prompt only described the rule in prose ("use placeholders, never inline"). The candidates added a copyable statement. | The first UPDATE succeeded with no error in all three template runs (inv1 L153, agg1 L152, agg2 L159). Every run without the template failed its first UPDATE several times: base1 L145–163 (3 errors: text bool, params sent as a string, handled_at type), base2 L150–164 (3), dom1 L156–176 (4), dom2 L156–182 (5), inv2 L145–153 (2). In the template runs every later UPDATE had the same shape. | helped. The split is 3 runs vs 5, one rollout per candidate, but the moment is the same in each. |
| handled_at = now() written into the SQL text: placed in memory (dom1, dom2), guardrails (inv2, agg1, agg2) or the template (inv1) | Before, "never inline literal values" was the only guidance. | Both base runs bound handled_at to the ticket's created_at and then cast it to make it fit (base1 L163, base2 L162). All six candidates wrote `handled_at = now()` from their first UPDATE, wherever the line was placed. | helped. Six runs, three placements, same result. |
| system_prompt.md: per-ticket a/b/c procedure, "never UPDATE or audit twice", definition of done (inv1, inv2, agg1, agg2) | Replaced the one-line "one ticket at a time" instruction. | agg1 still ran all 4 policy lookups first (L132–138), so per-ticket ordering of lookups did not happen. Each UPDATE was followed by its own audit, there were 8 UPDATEs and 8 audits, nothing was re-updated, no check queries ran, and the run took 25 iterations. Base: 104 updated 3× and 107 2×, base2's 104 audit says "Denied" while the row says credit, 34 iterations. | confounded (bundled with the template) |
| skills/refund_policy: number of lookups = number of charge_date rows, never reuse another ticket's response (dom1, dom2, agg1, agg2) | Added. | Every candidate made 4 lookups, including as_of 2026-08-01 for 104. Both base runs made 3. inv1 and inv2 got 4 lookups without this line, from the procedure change alone. | confounded (two independent edits gave the same result) |
| skills/refund_policy: past the last limit = credit, never deny, with a 61-day example (dom1, agg1, agg2) | Added. | agg1 wrote 104 as credit once (L182) and its audit says "61 days … credit" (L187). Base runs first wrote credit, then flipped to deny and back. inv1 and inv2 had no such line and also didn't flip, because they had the one-UPDATE rule. | confounded |
| skills/refund_policy step 6: audit day count = step-2 number (dom2 only) | Added. | dom2's 104 audit still said "31 days". | no observed effect (not adopted) |
| tool_hints.json "there is no parameter $": params must be a JSON array, not a quoted string (inv2, agg1, agg2) | Revised hint text. | agg1 L227: params sent as a string → L231 new hint → L233 correct on the next call. inv2 L151 → L157 the same. Under the old hint, dom1 and dom2 repeated the string mistake 2–3 times. | helped (few instances) |
| tool_hints.json: new `column "handled_at"` hint and a handled_at exception in the cast hint (inv1, inv2, agg1, agg2) | Added. | The hint never fired in any candidate, because now() was used from the start. | no observed effect |
| tool_hints.json "invalid input syntax": applies to any tool, casts never in params (inv2, agg1, agg2) | Revised. | The hint never fired. | no observed effect |
| memory.md: dropped the "Lessons from earlier runs" block (all six) | Removed. | No base run had used it. No behavioural difference can be attributed to removing it. | no observed effect |
| memory.md priority line: how/where question = low, one user unable to log in = high (dom2, agg1, agg2) | Added. | agg1 wrote 107 high and 108 low on the first attempt (L212, L222). inv1, which lacked the line, left 107 at normal. dom1 and inv2 also lacked it and still wrote 107 high, and base1 wrote 108 low without it. | confounded |
| system_prompt.md: report from a final GROUP BY over the triaged ids (agg2 only) | Added. | agg2 ran 28 iterations with 1 http_post error and 1 sql error. It used more tokens than agg1 and the report showed no difference. | no observed effect (not adopted) |

- **cue**: The agent writes rows through a parameterized SQL tool, and the harness gives the binding rules only in prose ("use $n placeholders, never inline literals", "set the timestamp to now()"). Early tool calls fail on type mismatches, params sent as a string, or a server-side timestamp bound as a parameter.
- **lesson**: In system_prompt, give one literal, copyable write statement per table. Put the casts on non-text placeholders in the SQL (`$3::boolean`, `$6::int`), write server-computed columns as functions in the SQL text (`handled_at = now()`, never a param), and add one example params JSON array in placeholder order. Separately, change the tool_hints entry for "no parameter $n" so it says params must be a JSON array, not a quoted string.
- **evidence**: Template row. inv1, agg1 and agg2 had the template, and each first UPDATE succeeded with zero errors. base1, base2, dom1, dom2 and inv2 had prose only, and each lost 2–5 retries on the first UPDATE. handled_at row: all six candidates used now() from the first write, while both base runs bound created_at. tool_hints row: under the revised hint, agg1 L227→L233 and inv2 L151→L157 fixed a string-params call in one retry; dom1 and dom2 repeated the mistake 2–3 times under the old hint.
- **confidence**: medium

Lesson id 2 written to `triage_agent`.