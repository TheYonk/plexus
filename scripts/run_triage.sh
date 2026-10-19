#!/usr/bin/env bash
# Run triage_agent over the open tickets, then print decisions, the
# assertion verdict, and the trajectory head. Usage: run_triage.sh <dsn> [agent]
set -euo pipefail
DSN="$1"; AGENT="${2:-triage_agent}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK="$(cat "$HERE/scenario/task.txt")"
echo "== $AGENT handles every open ticket (agent inside Postgres, LLM via Ollama, policy via as_of search) =="
RAW="$(psql "$DSN" -X -At -v ON_ERROR_STOP=1 -c "SET statement_timeout = '900s'; SELECT synapse.execute('$AGENT', \$plx\$${TASK}\$plx\$)")"
echo "$RAW" | tail -1 | python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
print({k: d.get(k) for k in ('status', 'iterations', 'tokens_in', 'tokens_out', 'duration_ms', 'error')})
print('tool calls:', len(d.get('tool_calls', [])))
print('output:', (d.get('output') or '')[:400])
open('$HERE/.last_execution', 'w').write(d.get('execution_id') or '')
"
echo "== decisions =="
psql "$DSN" -X -c "select t.id, c.tier, t.created_at::date as created, t.charge_date, t.category, t.priority, t.escalated, t.refund_decision, t.policy_version from support.tickets t join support.customers c on c.id=t.customer_id order by t.id"
echo "== assertion (policy in force on the ticket date, escalation rule, one audit row per ticket) =="
psql "$DSN" -X -At -c "$(cat "$HERE/scenario/assert.sql")" | sed 's/^t$/PASS/; s/^f$/FAIL/'
printf 'per condition: '
psql "$DSN" -X -At -f "$HERE/scenario/conditions.sql" | sed 's/|t$/ PASS/; s/|f$/ FAIL/' | paste -sd'|' | sed 's/|/ | /g'
EXEC="$(cat "$HERE/.last_execution")"
if [[ -n "$EXEC" ]]; then
  echo "== trajectory (actions, errors, hints) =="
  psql "$DSN" -X -At -c "select synapse.trajectory('$EXEC'::uuid, 400)" | grep -E "^\[ACTION\]|^\[ERROR\]|^HINT|^\[ASSISTANT\]" | head -40
fi
