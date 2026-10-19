# Plexus demo driver. Every target prints what it proves.
#
#   make up        start Postgres (pg_synapse + pgvector + pg_trgm) and the API
#   make ingest    policy corpus -> pg-raggraph (versioned) + chunkshop sink
#   make seed      scenario tables, agents, skills, hints, inline veto trigger
#   make run       triage_agent handles every ticket; prints the assertion
#   make veto      a refund that violates the policy in force is rolled back
#   make memory    decisions become stele memories; a correction supersedes one
#   make tune      bench/tune.py improves triage_agent from its own trajectories
#   make down      stop everything
#
# Host requirements: docker, psql, curl, python3, Ollama serving the model
# below on all interfaces (OLLAMA_HOST=0.0.0.0 OLLAMA_CONTEXT_LENGTH=32768
# ollama serve), and the api/.venv created by `make venv`.

SHELL := /bin/bash
HERE  := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PG_PORT ?= 55441
DSN     ?= postgresql://postgres:postgres@127.0.0.1:$(PG_PORT)/plexus
ADMIN_DSN ?= postgresql://postgres:postgres@127.0.0.1:$(PG_PORT)/postgres
API_PORT ?= 8766
LLM_MODEL ?= qwen3:4b-instruct-2507-q4_K_M
# As seen FROM Postgres (the container reaches the host through host.docker.internal).
LLM_BASE_URL ?= http://host.docker.internal:11434/v1
PSQL = psql "$(DSN)" -X -v ON_ERROR_STOP=1
VENV = $(HERE)/api/.venv

.PHONY: up down venv api ingest seed run veto memory tune status trajectories

up:
	docker compose -f $(HERE)/docker-compose.yml up -d --build
	@until $(PSQL) -Atc "select 1" >/dev/null 2>&1; do sleep 1; done
	@$(PSQL) -Atc "select 'postgres ready: pg_synapse ' || synapse.version() || ', ' || string_agg(extname||' '||extversion, ', ') from pg_extension where extname in ('vector','pg_trgm')"
	$(MAKE) api

venv:
	cd $(HERE)/api && uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python \
	  -e "$(HERE)/../stele[postgres,chunkshop,postgres-graph]" -e "$(HERE)/../pg-raggraph" \
	  -e "$(HERE)/../chunkshop/python" fastapi "uvicorn[standard]" "psycopg[binary]"

api:
	@pkill -f "[u]vicorn app:app --host 0.0.0.0 --port $(API_PORT)" 2>/dev/null || true
	@(cd $(HERE)/api && PLEXUS_DSN="$(DSN)" setsid -f $(VENV)/bin/uvicorn app:app --host 0.0.0.0 --port $(API_PORT) > $(HERE)/api/api.log 2>&1 < /dev/null)
	@until curl -sf http://127.0.0.1:$(API_PORT)/health >/dev/null; do sleep 1; done
	@echo "api ready: http://127.0.0.1:$(API_PORT)  (log: api/api.log)"

ingest:
	@echo "== policy corpus -> pg-raggraph (effective dates, v2 supersedes v1) + chunkshop sink =="
	curl -sf -X POST http://127.0.0.1:$(API_PORT)/policy/ingest | python3 -m json.tool | head -40
	@echo "== as_of check: which refund policy was in force on 2026-05-20 vs 2026-07-20? =="
	@for d in 2026-05-20 2026-07-20; do \
	  printf "%s -> " $$d; curl -sf -X POST http://127.0.0.1:$(API_PORT)/policy/search -H 'content-type: application/json' \
	    -d "{\"query\":\"refund window days after charge\",\"as_of\":\"$$d\",\"k\":1}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['policy_in_force'])"; done

seed:
	$(PSQL) -f $(HERE)/scenario/seed.sql
	$(PSQL) -Atc "select synapse.llm_profile_set('llm','openai','$(LLM_MODEL)','$(LLM_BASE_URL)',NULL,'{}'::jsonb)" >/dev/null
	$(PSQL) -f $(HERE)/scenario/agents.sql >/dev/null
	@$(PSQL) -Atc "select 'triage_agent always-on chars: ' || (synapse.agent_harness('triage_agent')->>'always_on_chars') || ' / ' || (synapse.agent_harness('triage_agent')->>'always_on_cap')"
	@$(PSQL) -Atc "select 'skills: ' || string_agg(name, ', ') from synapse.skills where agent='triage_agent'"
	@$(PSQL) -Atc "select 'inline veto trigger attached to support.refunds: ' || (select count(*) from pg_trigger where tgrelid = 'support.refunds'::regclass and not tgisinternal)"

run:
	@$(HERE)/scripts/run_triage.sh "$(DSN)" triage_agent

veto:
	@echo "== inline veto: a refund request that violates the policy in force on its ticket date =="
	@echo "ticket 104: pro tier, charge 2026-06-01, ticket 2026-08-01 (61 days, under v2 the window is 30 days) -> must be rejected"
	-$(PSQL) -Atc "set statement_timeout='300s'; insert into support.refunds (ticket_id, amount_usd, note) values (104, 49.00, 'customer changed their mind')"
	@echo "ticket 103: pro tier, charge 2026-06-28, ticket 2026-07-20 (22 days, under v2 the window is 30 days) -> allowed"
	-$(PSQL) -Atc "set statement_timeout='300s'; insert into support.refunds (ticket_id, amount_usd, note) values (103, 29.00, 'customer changed their mind')"
	@echo "== rows that survived (only the allowed one) =="
	@$(PSQL) -c "select id, ticket_id, amount_usd, note from support.refunds order by id"

memory:
	@echo "== decisions become stele memories (each cites a stele:// evidence artifact) =="
	@curl -sf -X POST http://127.0.0.1:$(API_PORT)/memory/remember -H 'content-type: application/json' \
	  -d '{"user_id":"bo@startup.example","text":"Refund for the May 10 charge approved under refund-v1 (10 days since charge).","kind":"decision","evidence":"ticket 101: charge 2026-05-10, created 2026-05-20, pro tier; policy in force refund-v1 (14-day window)."}' | python3 -m json.tool
	@sleep 2; date -u +%Y-%m-%dT%H:%M:%SZ > $(HERE)/.memory_t1; sleep 2
	@echo "== a correction supersedes the earlier memory =="
	@ID=$$(curl -sf -X POST http://127.0.0.1:$(API_PORT)/memory/recall -H 'content-type: application/json' -d '{"user_id":"bo@startup.example","query":"refund"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['memories'][0]['id'])"); \
	  curl -sf -X POST http://127.0.0.1:$(API_PORT)/memory/remember -H 'content-type: application/json' \
	  -d "{\"user_id\":\"bo@startup.example\",\"text\":\"Correction: the May 10 refund was reversed on 2026-05-28 at the customer's request; account credit issued instead.\",\"kind\":\"decision\",\"evidence\":\"support call 2026-05-28, ticket 101 reopened.\",\"supersedes\":[\"$$ID\"]}" | python3 -m json.tool
	@echo "== recall now (current belief) vs recall as_of the moment between the two writes (what the agent believed then) =="
	@curl -sf -X POST http://127.0.0.1:$(API_PORT)/memory/recall -H 'content-type: application/json' -d '{"user_id":"bo@startup.example","query":"refund"}' | python3 -c "import sys,json; [print(' now   :', m['status'], '|', m['text']) for m in json.load(sys.stdin)['memories']]"
	@curl -sf -X POST http://127.0.0.1:$(API_PORT)/memory/recall -H 'content-type: application/json' -d "{\"user_id\":\"bo@startup.example\",\"query\":\"refund\",\"as_of\":\"$$(cat $(HERE)/.memory_t1)\"}" | python3 -c "import sys,json; [print(' as_of :', m['status'], '|', m['text']) for m in json.load(sys.stdin)['memories']]"
	@echo "(stele time-travel is over WHEN a memory was believed, so the as_of here is the instant between the two writes.)"

trajectories:
	@echo "== past runs -> chunkshop (pg_table source over synapse.executions) -> plexus.trajectory_chunks =="
	curl -sf -X POST http://127.0.0.1:$(API_PORT)/trajectories/ingest | python3 -m json.tool | head -20
	@curl -sf -X POST http://127.0.0.1:$(API_PORT)/trajectories/search -H 'content-type: application/json' -d '{"query":"refund policy version applied","k":2}' | python3 -m json.tool | head -30

K ?= 1
tune:
	@echo "== Propose-Probe-Compose on the Plexus scenario: improver = Claude CLI, judge = assert.sql, lessons -> synapse.lessons =="
	python3 $(HERE)/../pg-synapse/bench/tune.py --scenario $(HERE)/scenario --from-agent triage_agent \
	  --dsn "$(ADMIN_DSN)" --llm-base-url "$(LLM_BASE_URL)" --llm-model "$(LLM_MODEL)" \
	  --k $(K) --agent-timeout 900 --improver claude \
	  --library-dsn "$(DSN)" --library-agent triage_agent --apply \
	  --out $(HERE)/tuned/$$(date +%Y%m%d-%H%M%S)
	@$(PSQL) -c "select lesson_id, cue, lesson, confidence from synapse.lessons where agent='triage_agent' order by lesson_id"

status:
	@$(PSQL) -c "select agent_name, status, tokens_in, tokens_out, duration_ms, started_at from synapse.executions order by started_at desc limit 10"

down:
	-pkill -f "[u]vicorn app:app --host 0.0.0.0 --port $(API_PORT)"
	docker compose -f $(HERE)/docker-compose.yml down -v
